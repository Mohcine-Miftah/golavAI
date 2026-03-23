"""
app/workers/tasks/process_inbound.py — AI orchestration Celery task.

This is the main worker that:
1. Loads conversation context (customer, messages, open booking)
2. Checks if the conversation is escalated (if so, stop)
3. Calls OpenAI with the conversation history
4. Validates the structured output
5. Executes proposed tool calls
6. Writes outbound message(s) to the outbox
7. Updates the inbound_event processing_status
"""
import asyncio
import uuid
from datetime import datetime, timezone

from celery import Task

from app.core.logging import get_logger
from app.core.security import compute_dedupe_key
from app.services.tool_executor import execute_tool
from app.integrations.openai.adapter import call_openai
from app.services.conversation_service import build_llm_messages, get_recent_messages
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


def _run(coro):
    """Run an async coroutine from a sync Celery task."""
    return asyncio.get_event_loop().run_until_complete(coro)


@celery_app.task(
    name="app.workers.tasks.process_inbound.process_inbound_message",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="ai",
    acks_late=True,
)
def process_inbound_message(
    self: Task,
    inbound_event_id: str,
    conversation_id: str,
    customer_id: str,
    message_sid: str,
) -> None:
    """AI orchestration task — processes a single inbound message end to end."""
    logger.info("process_inbound_start", event_id=inbound_event_id, conv_id=conversation_id)
    try:
        _run(_process(self, inbound_event_id, conversation_id, customer_id, message_sid))
    except Exception as exc:
        logger.error("process_inbound_error", event_id=inbound_event_id, error=str(exc))
        try:
            raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            _run(_mark_event_failed(inbound_event_id, str(exc)))


async def _process(
    task: Task,
    inbound_event_id: str,
    conversation_id: str,
    customer_id: str,
    message_sid: str,
) -> None:
    from app.db.session import AsyncSessionLocal
    from app.models.conversation import Conversation
    from app.models.inbound_event import InboundEvent
    from app.models.message import Message
    from app.models.outbound_message import OutboundMessage
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        # Load conversation — check escalation flag
        conv_result = await session.execute(
            select(Conversation).where(Conversation.id == uuid.UUID(conversation_id))
        )
        conversation = conv_result.scalar_one_or_none()

        if conversation is None:
            logger.error("conversation_not_found", conv_id=conversation_id)
            return

        if conversation.escalated:
            logger.info("conversation_escalated_skip", conv_id=conversation_id)
            await _mark_event_done(session, inbound_event_id)
            await session.commit()
            return

        # Load recent messages for LLM context
        messages = await get_recent_messages(session, conversation_id)
        llm_messages = build_llm_messages(messages)

        if not llm_messages:
            logger.warning("no_messages_for_llm", conv_id=conversation_id)
            await _mark_event_done(session, inbound_event_id)
            await session.commit()
            return

        # Call OpenAI
        try:
            ai_output = await call_openai(llm_messages, conversation_id)
        except Exception as exc:
            logger.error("openai_call_failed", conv_id=conversation_id, error=str(exc))
            # Write a fallback outbound message
            error_reply = (
                "شكراً على تواصلك 🙏 واجهنا مشكل تقني صغير. سنعود إليك قريباً."
                "\n\nMerci de votre contact. Un problème technique est survenu. Nous revenons vers vous très bientôt."
            )
            await _write_outbound(session, conversation_id, error_reply, event_id=inbound_event_id)
            await _mark_event_done(session, inbound_event_id)
            await session.commit()
            return

        # Handle needs_human flag
        if ai_output.needs_human or ai_output.confidence < 0.6:
            reason = ai_output.needs_human_reason or "low_confidence"
            handoff_result = await execute_tool(
                "create_human_handoff",
                {"reason": reason, "reason_text": ai_output.needs_human_reason},
                session,
                conversation_id,
                customer_id,
            )
            logger.info("human_handoff_triggered", conv_id=conversation_id, reason=reason)

        # Execute proposed actions sequentially
        tool_results: list[dict] = []
        for action in ai_output.proposed_actions:
            result = await execute_tool(
                action.type,
                action.params,
                session,
                conversation_id,
                customer_id,
            )
            tool_results.append({"tool": action.type, "result": result})

            # If escalation was triggered, stop processing further actions
            if action.type == "create_human_handoff":
                break

        # Write the customer-facing reply to the outbox
        reply = ai_output.customer_facing_reply
        if reply:
            await _write_outbound(session, conversation_id, reply, event_id=inbound_event_id)

        # Update conversation last_outbound_at
        conversation.last_outbound_at = datetime.now(timezone.utc)

        # Update inbound_event
        await _mark_event_done(session, inbound_event_id)

        await session.commit()

    logger.info("process_inbound_done", event_id=inbound_event_id, conv_id=conversation_id)


async def _write_outbound(
    session,
    conversation_id: str,
    body: str,
    event_id: str,
    media_url: str | None = None,
) -> None:
    from app.models.outbound_message import OutboundMessage
    from sqlalchemy.exc import IntegrityError

    dedupe_key = compute_dedupe_key(conversation_id, event_id, body[:50])
    msg = OutboundMessage(
        conversation_id=uuid.UUID(conversation_id),
        dedupe_key=dedupe_key,
        body_text=body,
        media_url=media_url,
        send_status="pending",
    )
    session.add(msg)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        logger.info("outbound_deduplicated", dedupe_key=dedupe_key[:16])


async def _mark_event_done(session, event_id: str) -> None:
    from app.models.inbound_event import InboundEvent
    from sqlalchemy import select
    result = await session.execute(
        select(InboundEvent).where(InboundEvent.id == uuid.UUID(event_id))
    )
    event = result.scalar_one_or_none()
    if event:
        event.processing_status = "processed"
        event.processed_at = datetime.now(timezone.utc)


async def _mark_event_failed(event_id: str, error: str) -> None:
    from app.db.session import AsyncSessionLocal
    from app.models.inbound_event import InboundEvent
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(InboundEvent).where(InboundEvent.id == uuid.UUID(event_id))
        )
        event = result.scalar_one_or_none()
        if event:
            event.processing_status = "failed"
            event.error = error
        await session.commit()

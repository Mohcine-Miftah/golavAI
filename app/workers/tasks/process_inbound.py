"""
app/workers/tasks/process_inbound.py — AI orchestration Celery task.
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
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        # 1. LOCK & CHECK IDEMPOTENCY
        event_result = await session.execute(
            select(InboundEvent).where(InboundEvent.id == uuid.UUID(inbound_event_id)).with_for_update()
        )
        event = event_result.scalar_one_or_none()
        
        if not event:
            logger.error("inbound_event_not_found", event_id=inbound_event_id)
            return

        current_retries = getattr(task.request, "retries", 0)
        is_stale = False
        if event.updated_at:
            diff = datetime.now(timezone.utc) - event.updated_at
            if diff.total_seconds() > 300:
                is_stale = True

        if event.processing_status == "processed":
            logger.info("event_already_processed_skip", event_id=inbound_event_id)
            return

        if event.processing_status == "processing" and current_retries == 0 and not is_stale:
            logger.info("event_currently_processing_skip", event_id=inbound_event_id)
            return

        # Mark as processing
        event.processing_status = "processing"
        await session.flush()

        # 2. LOAD CONVERSATION
        conv_result = await session.execute(
            select(Conversation).where(Conversation.id == uuid.UUID(conversation_id))
        )
        conversation = conv_result.scalar_one_or_none()

        if conversation is None or conversation.escalated:
            logger.info("conversation_skip", conv_id=conversation_id, escalated=conversation.escalated if conversation else "None")
            event.processing_status = "processed"
            event.processed_at = datetime.now(timezone.utc)
            await session.commit()
            return

        # 3. CONTEXT & AI CALL
        messages = await get_recent_messages(session, conversation_id)
        llm_messages = build_llm_messages(messages)

        if not llm_messages:
            event.processing_status = "processed"
            await session.commit()
            return

        try:
            ai_output = await call_openai(llm_messages, conversation_id)
        except Exception as exc:
            logger.error("openai_call_failed", conv_id=conversation_id, error=str(exc))
            error_reply = "Désolé, un problème technique est survenu. Nous revenons vers vous bientôt."
            await _write_outbound(session, conversation_id, error_reply, inbound_event_id)
            event.processing_status = "processed"
            await session.commit()
            return

        # Handle needs_human flag
        if ai_output.needs_human or ai_output.confidence < 0.6:
            await execute_tool("create_human_handoff", {"reason_text": ai_output.needs_human_reason}, session, conversation_id, customer_id)

        # Execute proposed actions
        tool_results = []
        for action in ai_output.proposed_actions:
            result = await execute_tool(action.type, action.params, session, conversation_id, customer_id)
            tool_results.append({"tool": action.type, "result": result})
            if action.type == "create_human_handoff": break

        # Follow-up if tools ran
        if tool_results:
            import json as _json
            augmented_messages = llm_messages + [
                {"role": "assistant", "content": ai_output.model_dump_json()},
                {"role": "user", "content": f"[SYSTEM: Tool Results]\n{_json.dumps(tool_results, ensure_ascii=False)}\nNow respond."}
            ]
            try:
                ai_output = await call_openai(augmented_messages, conversation_id)
            except Exception:
                pass 

        # Write outbound WITH raw_payload for history!
        reply = ai_output.customer_facing_reply
        if reply:
            await _write_outbound(session, conversation_id, reply, inbound_event_id, raw_payload=ai_output.model_dump())

        # Update and commit
        conversation.last_outbound_at = datetime.now(timezone.utc)
        event.processing_status = "processed"
        event.processed_at = datetime.now(timezone.utc)
        await session.commit()

    logger.info("process_inbound_done", event_id=inbound_event_id, conv_id=conversation_id)


async def _write_outbound(
    session,
    conversation_id: str,
    body: str,
    event_id: str,
    media_url: str | None = None,
    raw_payload: dict | None = None,
) -> None:
    from app.models.outbound_message import OutboundMessage
    from app.models.message import Message
    from sqlalchemy.exc import IntegrityError

    async with session.begin_nested():
        dedupe_key = compute_dedupe_key(conversation_id, event_id, body[:50])
        msg = OutboundMessage(
            conversation_id=uuid.UUID(conversation_id),
            dedupe_key=dedupe_key,
            body_text=body,
            media_url=media_url,
            send_status="pending",
        )
        session.add(msg)
        
        # Save to history immediately WITH the metadata!
        history_msg = Message(
            conversation_id=uuid.UUID(conversation_id),
            direction="outbound",
            provider="twilio",
            body_text=body,
            raw_payload=raw_payload, # THE KEY FIX
            message_type="text",
        )
        session.add(history_msg)

        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()


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

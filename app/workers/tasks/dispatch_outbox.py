"""
app/workers/tasks/dispatch_outbox.py — Reliable outbound message dispatcher.

Reads pending outbound_messages rows and sends them via Twilio.
Uses exponential backoff for retries and dead-letters after max retries.
"""
import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from app.config import settings
from app.core.logging import get_logger
from app.core.metrics import outbox_sends_total
from app.integrations.twilio.adapter import send_whatsapp_message
from app.workers.celery_app import celery_app
from app.core.exceptions import TwilioSendError

logger = get_logger(__name__)

BATCH_SIZE = 10  # Process N messages per tick


@celery_app.task(
    name="app.workers.tasks.dispatch_outbox.dispatch_pending_outbox",
    queue="outbox",
    acks_late=True,
)
def dispatch_pending_outbox() -> None:
    asyncio.get_event_loop().run_until_complete(_dispatch())


async def _dispatch() -> None:
    from app.db.session import AsyncSessionLocal
    from app.models.outbound_message import OutboundMessage
    from app.models.conversation import Conversation
    from app.models.customer import Customer
    from sqlalchemy import select, and_, or_
    from sqlalchemy.orm import selectinload

    now_utc = datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        # Fetch pending messages that are ready to send (respecting retry schedule)
        result = await session.execute(
            select(OutboundMessage)
            .where(
                OutboundMessage.send_status.in_(["pending", "queued"]),
                or_(
                    OutboundMessage.next_retry_at == None,
                    OutboundMessage.next_retry_at <= now_utc,
                ),
            )
            .order_by(OutboundMessage.created_at.asc())
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)  # Skip rows locked by concurrent dispatchers
        )
        messages = result.scalars().all()

        if not messages:
            return

        logger.info("outbox_dispatch_batch", count=len(messages))

        for msg in messages:
            await _send_one(session, msg)

        await session.commit()


async def _send_one(session, msg) -> None:
    from app.models.conversation import Conversation
    from app.models.customer import Customer
    from sqlalchemy import select

    # Get recipient phone
    conv_result = await session.execute(
        select(Conversation).where(Conversation.id == msg.conversation_id)
    )
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        msg.send_status = "failed"
        msg.last_error = "Conversation not found"
        return

    cust_result = await session.execute(
        select(Customer).where(Customer.id == conversation.customer_id)
    )
    customer = cust_result.scalar_one_or_none()
    if not customer:
        msg.send_status = "failed"
        msg.last_error = "Customer not found"
        return

    # Attempt Twilio send (sync SDK called in thread pool via asyncio.to_thread)
    try:
        sid = await asyncio.to_thread(
            send_whatsapp_message,
            customer.phone_e164,
            msg.body_text,
            msg.media_url,
        )
        msg.send_status = "sent"
        msg.provider_message_sid = sid
        msg.next_retry_at = None
        outbox_sends_total.labels(status="sent").inc()
        logger.info("outbox_sent", msg_id=str(msg.id), sid=sid, phone=customer.phone_e164)

    except TwilioSendError as exc:
        # Non-retryable — dead letter immediately
        msg.send_status = "dead_lettered"
        msg.last_error = str(exc)
        msg.retry_count += 1
        outbox_sends_total.labels(status="dead_lettered").inc()
        logger.error("outbox_dead_lettered", msg_id=str(msg.id), error=str(exc))

    except Exception as exc:
        msg.retry_count += 1
        if msg.retry_count >= settings.outbox_max_retries:
            msg.send_status = "dead_lettered"
            msg.last_error = f"Max retries ({settings.outbox_max_retries}) exceeded: {exc}"
            outbox_sends_total.labels(status="dead_lettered").inc()
            logger.error("outbox_max_retries_exceeded", msg_id=str(msg.id))
        else:
            backoff_seconds = settings.outbox_retry_backoff_base * (2 ** (msg.retry_count - 1))
            msg.send_status = "queued"
            msg.next_retry_at = datetime.now(UTC) + timedelta(seconds=backoff_seconds)
            msg.last_error = str(exc)
            outbox_sends_total.labels(status="failed").inc()
            logger.warning(
                "outbox_retry_scheduled",
                msg_id=str(msg.id),
                retry_count=msg.retry_count,
                next_retry_in=backoff_seconds,
            )

"""
app/services/conversation_service.py — Conversation and customer context management.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.booking import Booking
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.escalation_task import EscalationTask
from app.models.message import Message
from app.models.audit_log import AuditLog

logger = get_logger(__name__)

RECENT_MESSAGE_LIMIT = 20  # Messages to include in LLM context window


async def get_or_create_customer(session: AsyncSession, phone_e164: str, name: str | None = None) -> Customer:
    """Find an existing customer by phone or create a new one."""
    result = await session.execute(
        select(Customer).where(Customer.phone_e164 == phone_e164)
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        customer = Customer(phone_e164=phone_e164, name=name)
        session.add(customer)
        await session.flush()
        logger.info("customer_created", phone=phone_e164)
    elif name and not customer.name:
        customer.name = name
    return customer


async def get_or_create_conversation(session: AsyncSession, customer_id: str) -> Conversation:
    """Get the latest active conversation for a customer, or create a new one."""
    result = await session.execute(
        select(Conversation)
        .where(
            Conversation.customer_id == uuid.UUID(customer_id),
            Conversation.state == "active",
        )
        .order_by(Conversation.created_at.desc())
        .limit(1)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        conversation = Conversation(
            customer_id=uuid.UUID(customer_id),
            channel="whatsapp",
            state="active",
            escalated=False,
        )
        session.add(conversation)
        await session.flush()
        logger.info("conversation_created", customer_id=customer_id, conv_id=str(conversation.id))
    return conversation


async def get_recent_messages(session: AsyncSession, conversation_id: str) -> list[Message]:
    """Return the last N messages for building the LLM context."""
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == uuid.UUID(conversation_id))
        .order_by(Message.created_at.asc())
        .limit(RECENT_MESSAGE_LIMIT)
    )
    return list(result.scalars().all())


async def get_open_booking(session: AsyncSession, conversation_id: str) -> Booking | None:
    """Return the most recent non-terminal booking for this conversation."""
    terminal_statuses = {"cancelled", "completed", "failed"}
    result = await session.execute(
        select(Booking)
        .where(
            Booking.conversation_id == uuid.UUID(conversation_id),
            Booking.status.not_in(terminal_statuses),
        )
        .order_by(Booking.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def build_llm_messages(messages: list[Message]) -> list[dict[str, str]]:
    """
    Convert Message rows to the OpenAI messages format.
    Inbound → role=user, outbound → role=assistant.
    """
    result = []
    for m in messages:
        role = "user" if m.direction == "inbound" else "assistant"
        content = m.body_text or ""
        result.append({"role": role, "content": content})
    return result


async def escalate_conversation(
    session: AsyncSession,
    conversation_id: str,
    reason_code: str,
    reason_text: str | None = None,
) -> EscalationTask:
    """Mark a conversation as escalated and create an escalation task."""
    result = await session.execute(
        select(Conversation).where(Conversation.id == uuid.UUID(conversation_id))
    )
    conv = result.scalar_one_or_none()
    if conv:
        conv.escalated = True

    task = EscalationTask(
        conversation_id=uuid.UUID(conversation_id),
        reason_code=reason_code,
        reason_text=reason_text,
        status="open",
    )
    session.add(task)

    session.add(AuditLog(
        entity_type="conversation",
        entity_id=uuid.UUID(conversation_id),
        action="conversation.escalated",
        actor_type="ai",
        details={"reason_code": reason_code, "reason_text": reason_text},
    ))

    await session.flush()
    logger.info("conversation_escalated", conversation_id=conversation_id, reason=reason_code)
    return task

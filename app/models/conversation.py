"""
app/models/conversation.py — Conversation model.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Conversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(20), default="whatsapp", nullable=False)
    state: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    # OpenAI Responses API conversation ref (for multi-turn memory if using stored conversations)
    openai_conversation_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_outbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    assigned_human: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="conversations")  # noqa: F821
    messages: Mapped[list["Message"]] = relationship(  # noqa: F821
        "Message", back_populates="conversation", lazy="noload"
    )
    outbound_messages: Mapped[list["OutboundMessage"]] = relationship(  # noqa: F821
        "OutboundMessage", back_populates="conversation", lazy="noload"
    )
    bookings: Mapped[list["Booking"]] = relationship(  # noqa: F821
        "Booking", back_populates="conversation", lazy="noload"
    )
    escalation_tasks: Mapped[list["EscalationTask"]] = relationship(  # noqa: F821
        "EscalationTask", back_populates="conversation", lazy="noload"
    )

    __table_args__ = (
        Index("ix_conversations_customer_id", "customer_id"),
        Index("ix_conversations_escalated", "escalated"),
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} customer_id={self.customer_id} state={self.state}>"

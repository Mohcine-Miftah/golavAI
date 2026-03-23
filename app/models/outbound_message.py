"""
app/models/outbound_message.py — Outbox table.

Messages are never sent directly from the request thread.
They are written here first; the dispatcher worker reads pending rows and sends via Twilio.
The dedupe_key prevents the same logical message from being sent twice.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class OutboundMessage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "outbound_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True
    )
    dedupe_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    template_variables: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    send_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # pending | queued | sent | delivered | read | failed | dead_lettered
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_message_sid: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship(  # noqa: F821
        "Conversation", back_populates="outbound_messages"
    )

    __table_args__ = (
        Index("ix_outbound_messages_send_status", "send_status"),
        Index("ix_outbound_messages_next_retry_at", "next_retry_at"),
        Index("ix_outbound_messages_conversation_id", "conversation_id"),
    )

    def __repr__(self) -> str:
        return f"<OutboundMessage id={self.id} status={self.send_status} key={self.dedupe_key[:12]}>"

"""
app/models/message.py — Message model (inbound and outbound).
"""
import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Message(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)     # inbound | outbound
    provider: Mapped[str] = mapped_column(String(20), default="twilio", nullable=False)
    provider_message_sid: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_normalized: Mapped[str | None] = mapped_column(Text, nullable=True)  # lowercased/stripped
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_type: Mapped[str] = mapped_column(String(20), default="text", nullable=False)  # text | image | template
    delivery_status: Mapped[str | None] = mapped_column(String(30), nullable=True)  # queued|sent|delivered|read|failed
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")  # noqa: F821

    __table_args__ = (
        Index("ix_messages_conversation_id", "conversation_id"),
        Index("ix_messages_provider_message_sid", "provider_message_sid"),
    )

    def __repr__(self) -> str:
        return f"<Message id={self.id} direction={self.direction} status={self.delivery_status}>"

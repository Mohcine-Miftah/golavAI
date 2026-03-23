"""
app/models/inbound_event.py — Raw inbound event inbox (idempotency guard).

Every Twilio webhook is persisted here first before any processing.
The unique constraint on provider_event_id prevents duplicate processing.
processing_status drives the worker state machine.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class InboundEvent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "inbound_events"

    provider_event_id: Mapped[str] = mapped_column(
        String(200), unique=True, nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(20), default="twilio", nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # inbound_message | status_update
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending | processing | processed | failed | duplicate
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_inbound_events_processing_status", "processing_status"),
        Index("ix_inbound_events_provider_event_id", "provider_event_id"),
    )

    def __repr__(self) -> str:
        return f"<InboundEvent id={self.id} status={self.processing_status} event_id={self.provider_event_id}>"

"""
app/models/booking_slot_hold.py — Slot hold model.

A slot hold is a temporary reservation created before the customer confirms.
It expires automatically (expire_holds task). When expired, the slot
becomes available again for other bookings.

The unique constraint on hold_key prevents two holds for the same slot.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class BookingSlotHold(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "booking_slot_holds"

    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    hold_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # active | confirmed | expired | released

    # Relationships
    booking: Mapped["Booking | None"] = relationship("Booking", back_populates="slot_holds")  # noqa: F821

    __table_args__ = (
        Index("ix_slot_holds_status", "status"),
        Index("ix_slot_holds_expires_at", "expires_at"),
        Index("ix_slot_holds_scheduled_start", "scheduled_start"),
    )

    def __repr__(self) -> str:
        return f"<BookingSlotHold id={self.id} status={self.status} start={self.scheduled_start}>"

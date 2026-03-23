"""
app/models/booking.py — Booking model.

This is the canonical booking record. The AI never writes here directly.
The booking_service confirms bookings inside an ACID transaction.
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Booking(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "bookings"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Vehicle info
    vehicle_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vehicle_category: Mapped[str] = mapped_column(String(30), nullable=False)  # citadine | berline | suv
    service_type: Mapped[str] = mapped_column(String(30), nullable=False)       # exterieur | complet

    # Location
    address_text: Mapped[str] = mapped_column(Text, nullable=False)
    area_name: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)

    # Schedule
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Pricing
    price_mad: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="MAD", nullable=False)

    # Status
    status: Mapped[str] = mapped_column(String(30), default="inquiry", nullable=False, index=True)
    # inquiry | awaiting_details | slot_pending | slot_held | confirmed | assigned
    # | in_progress | completed | cancelled | reschedule_requested | rescheduled | failed

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(10), default="ai", nullable=False)  # ai | human
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="bookings")  # noqa: F821
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="bookings")  # noqa: F821
    slot_holds: Mapped[list["BookingSlotHold"]] = relationship(  # noqa: F821
        "BookingSlotHold", back_populates="booking", lazy="noload"
    )

    __table_args__ = (
        Index("ix_bookings_scheduled_start", "scheduled_start"),
        Index("ix_bookings_status", "status"),
        Index("ix_bookings_customer_id", "customer_id"),
    )

    def __repr__(self) -> str:
        return f"<Booking id={self.id} status={self.status} start={self.scheduled_start}>"

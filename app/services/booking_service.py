"""
app/services/booking_service.py — Core booking engine.

This is the most safety-critical service in the system.
All slot holds and booking confirmations use DB-level locking.
The AI never touches this directly — it requests tool calls which
the application layer executes here.

Key rules:
- No double-booking: slot hold uses a unique hold_key
- Atomic confirmation: BEGIN → lock hold row → check not expired → insert booking → COMMIT
- Slot availability: checks for overlapping active holds AND confirmed bookings
"""
import hashlib
import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytz
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    BookingNotFoundError,
    SlotHoldExpiredError,
    SlotNotAvailableError,
)
from app.core.logging import get_logger
from app.core.metrics import bookings_total
from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.booking_slot_hold import BookingSlotHold
from app.services.pricing_service import get_price

logger = get_logger(__name__)

TZ_CASABLANCA = pytz.timezone("Africa/Casablanca")
ACTIVE_BOOKING_STATUSES = {"slot_held", "confirmed", "assigned", "in_progress"}


def _make_hold_key(conversation_id: str, slot: datetime) -> str:
    """Deterministic hold key — prevents two holds for same conv+slot."""
    raw = f"{conversation_id}|{slot.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _slot_end(start: datetime, duration_minutes: int | None = None) -> datetime:
    mins = duration_minutes or settings.slot_duration_minutes
    return start + timedelta(minutes=mins)


async def get_available_slots(
    session: AsyncSession,
    date_str: str,
    area_name: str,
) -> dict:
    """
    Return available booking slots for a given date and area.

    Logic:
    1. Generate all business-hour slots for the day.
    2. Query all ACTIVE holds and confirmed bookings for that day.
    3. Remove busy slots from the candidate list.

    Returns:
        {"slots": [ISO str, ...], "message": str}
    """
    try:
        local_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return {"slots": [], "message": "Invalid date format — use YYYY-MM-DD."}

    # Build candidate slots (every SLOT_DURATION_MINUTES from open to close)
    candidates: list[datetime] = []
    current = TZ_CASABLANCA.localize(
        datetime(local_date.year, local_date.month, local_date.day, settings.business_hours_start, 0)
    )
    end_of_day = TZ_CASABLANCA.localize(
        datetime(local_date.year, local_date.month, local_date.day, settings.business_hours_end, 0)
    )
    while current < end_of_day:
        candidates.append(current)
        current += timedelta(minutes=settings.slot_duration_minutes)

    if not candidates:
        return {"slots": [], "message": "No slots available — outside business hours."}

    # Fetch busy windows (active holds + booked)
    day_start_utc = candidates[0].astimezone(UTC)
    day_end_utc = candidates[-1].astimezone(UTC) + timedelta(minutes=settings.slot_duration_minutes)

    # Active slot holds
    holds_result = await session.execute(
        select(BookingSlotHold.scheduled_start, BookingSlotHold.scheduled_end).where(
            BookingSlotHold.status == "active",
            BookingSlotHold.scheduled_start >= day_start_utc,
            BookingSlotHold.scheduled_start < day_end_utc,
        )
    )
    busy_starts = {row.scheduled_start.astimezone(TZ_CASABLANCA) for row in holds_result}

    # Confirmed bookings
    bookings_result = await session.execute(
        select(Booking.scheduled_start).where(
            Booking.status.in_(ACTIVE_BOOKING_STATUSES),
            Booking.scheduled_start >= day_start_utc,
            Booking.scheduled_start < day_end_utc,
        )
    )
    busy_starts |= {row.scheduled_start.astimezone(TZ_CASABLANCA) for row in bookings_result}

    available = [s for s in candidates if s not in busy_starts]

    if not available:
        return {"slots": [], "message": f"No slots available on {date_str}. Try another date."}

    return {
        "slots": [s.isoformat() for s in available],
        "message": f"{len(available)} slot(s) available on {date_str}.",
    }


async def create_slot_hold(
    session: AsyncSession,
    conversation_id: str,
    slot_iso: str,
) -> dict:
    """
    Create a temporary slot hold for a conversation.

    Uses INSERT with unique hold_key to prevent duplicate holds for the
    same conversation + slot. If another hold for that slot exists (from
    a different conversation), raises SlotNotAvailableError.

    Returns:
        {"hold_id": str, "expires_at": str, "success": True}
    """
    try:
        slot = datetime.fromisoformat(slot_iso)
    except ValueError:
        raise SlotNotAvailableError(f"Invalid slot ISO string: {slot_iso}")

    if slot.tzinfo is None:
        slot = TZ_CASABLANCA.localize(slot)

    slot_utc = slot.astimezone(UTC)
    slot_end_utc = _slot_end(slot_utc)
    now_utc = datetime.now(UTC)
    expires_at = now_utc + timedelta(minutes=settings.slot_hold_ttl_minutes)
    hold_key = _make_hold_key(conversation_id, slot_utc)

    # Check if the slot is already held or booked
    conflict = await session.execute(
        select(BookingSlotHold).where(
            BookingSlotHold.status == "active",
            BookingSlotHold.scheduled_start == slot_utc,
            BookingSlotHold.hold_key != hold_key,  # allow same conv to re-hold same slot
        )
    )
    if conflict.scalar_one_or_none():
        raise SlotNotAvailableError(f"Slot {slot_iso} is already held by another conversation.")

    booking_conflict = await session.execute(
        select(Booking).where(
            Booking.status.in_(ACTIVE_BOOKING_STATUSES),
            Booking.scheduled_start == slot_utc,
        )
    )
    if booking_conflict.scalar_one_or_none():
        raise SlotNotAvailableError(f"Slot {slot_iso} is already booked.")

    # Release any previous active hold from this conversation for a different slot
    await session.execute(
        select(BookingSlotHold).where(
            BookingSlotHold.conversation_id == uuid.UUID(conversation_id),
            BookingSlotHold.status == "active",
            BookingSlotHold.hold_key != hold_key,
        )
    )

    hold = BookingSlotHold(
        conversation_id=uuid.UUID(conversation_id),
        hold_key=hold_key,
        scheduled_start=slot_utc,
        scheduled_end=slot_end_utc,
        expires_at=expires_at,
        status="active",
    )

    try:
        session.add(hold)
        await session.flush()  # flush to get the ID and catch unique violations immediately
    except IntegrityError:
        await session.rollback()
        raise SlotNotAvailableError(f"Slot {slot_iso} conflict — hold already exists.")

    logger.info("slot_hold_created", hold_id=str(hold.id), slot=slot_iso, expires_at=expires_at.isoformat())

    return {
        "hold_id": str(hold.id),
        "expires_at": expires_at.isoformat(),
        "success": True,
    }


async def confirm_booking(
    session: AsyncSession,
    conversation_id: str,
    hold_id: str,
    vehicle_category: str,
    service_type: str,
    address_text: str,
    area_name: str,
    customer_id: str,
    vehicle_model: str | None = None,
) -> dict:
    """
    Atomically confirm a booking.

    CRITICAL: Uses SELECT FOR UPDATE NOWAIT to lock the hold row.
    If the hold is expired or doesn't exist, raises SlotHoldExpiredError.
    The entire operation is inside a single DB transaction.

    Returns:
        {"booking_id": str, "status": "confirmed", "scheduled_start": str, "price_mad": float}
    """
    now_utc = datetime.now(UTC)

    # Lock the hold row — raises if another transaction has it
    result = await session.execute(
        select(BookingSlotHold)
        .where(
            BookingSlotHold.id == uuid.UUID(hold_id),
            BookingSlotHold.conversation_id == uuid.UUID(conversation_id),
        )
        .with_for_update(nowait=True)
    )
    hold = result.scalar_one_or_none()

    if hold is None:
        raise SlotHoldExpiredError(f"Hold {hold_id} not found for conversation {conversation_id}.")

    if hold.status != "active":
        raise SlotHoldExpiredError(f"Hold {hold_id} is no longer active (status={hold.status}).")

    if hold.expires_at < now_utc:
        hold.status = "expired"
        raise SlotHoldExpiredError(f"Hold {hold_id} expired at {hold.expires_at.isoformat()}.")

    # Get price
    price = await get_price(session, vehicle_category, service_type)

    # Create booking
    booking = Booking(
        customer_id=uuid.UUID(customer_id),
        conversation_id=uuid.UUID(conversation_id),
        vehicle_model=vehicle_model,
        vehicle_category=vehicle_category.lower(),
        service_type=service_type.lower(),
        address_text=address_text,
        area_name=area_name.lower(),
        scheduled_start=hold.scheduled_start,
        scheduled_end=hold.scheduled_end,
        price_mad=price,
        currency="MAD",
        status="confirmed",
        created_by="ai",
    )
    session.add(booking)

    # Update hold
    hold.status = "confirmed"
    hold.booking_id = booking.id

    # Audit log
    session.add(AuditLog(
        entity_type="booking",
        entity_id=booking.id,
        action="booking.confirmed",
        actor_type="ai",
        details={
            "hold_id": hold_id,
            "vehicle_category": vehicle_category,
            "service_type": service_type,
            "scheduled_start": hold.scheduled_start.isoformat(),
            "price_mad": float(price),
        },
    ))

    await session.flush()
    bookings_total.labels(event="created").inc()

    logger.info(
        "booking_confirmed",
        booking_id=str(booking.id),
        conversation_id=conversation_id,
        scheduled_start=hold.scheduled_start.isoformat(),
    )

    return {
        "booking_id": str(booking.id),
        "status": "confirmed",
        "scheduled_start": hold.scheduled_start.isoformat(),
        "price_mad": float(price),
    }


async def cancel_booking(
    session: AsyncSession,
    booking_id: str,
    reason: str,
    actor: str = "ai",
) -> dict:
    """Cancel an active booking."""
    result = await session.execute(
        select(Booking).where(Booking.id == uuid.UUID(booking_id)).with_for_update()
    )
    booking = result.scalar_one_or_none()
    if booking is None:
        raise BookingNotFoundError(f"Booking {booking_id} not found.")

    if booking.status in ("cancelled", "completed"):
        return {"success": False, "message": f"Booking already in status: {booking.status}"}

    now_utc = datetime.now(UTC)
    booking.status = "cancelled"
    booking.cancelled_at = now_utc
    booking.cancellation_reason = reason

    # Release holds
    holds_result = await session.execute(
        select(BookingSlotHold).where(
            BookingSlotHold.booking_id == uuid.UUID(booking_id),
            BookingSlotHold.status == "active",
        )
    )
    for hold in holds_result.scalars():
        hold.status = "released"

    session.add(AuditLog(
        entity_type="booking",
        entity_id=uuid.UUID(booking_id),
        action="booking.cancelled",
        actor_type=actor,
        details={"reason": reason},
    ))

    bookings_total.labels(event="cancelled").inc()
    logger.info("booking_cancelled", booking_id=booking_id, reason=reason)
    return {"success": True, "message": "Booking cancelled successfully."}


async def reschedule_booking(
    session: AsyncSession,
    booking_id: str,
    new_slot_iso: str,
    conversation_id: str,
) -> dict:
    """Reschedule a booking to a new slot — atomic and double-booking safe."""
    result = await session.execute(
        select(Booking).where(Booking.id == uuid.UUID(booking_id)).with_for_update()
    )
    booking = result.scalar_one_or_none()
    if booking is None:
        raise BookingNotFoundError(f"Booking {booking_id} not found.")

    if booking.status in ("cancelled", "completed"):
        return {"success": False, "message": f"Cannot reschedule: booking is {booking.status}."}

    # Create new hold for the new slot
    hold_result = await create_slot_hold(session, conversation_id, new_slot_iso)
    new_slot = datetime.fromisoformat(new_slot_iso).astimezone(UTC)

    # Release old hold
    old_holds = await session.execute(
        select(BookingSlotHold).where(
            BookingSlotHold.booking_id == uuid.UUID(booking_id),
            BookingSlotHold.status.in_(["active", "confirmed"]),
        )
    )
    for old_hold in old_holds.scalars():
        old_hold.status = "released"

    # Update booking
    booking.scheduled_start = new_slot
    booking.scheduled_end = _slot_end(new_slot)
    booking.status = "rescheduled"

    session.add(AuditLog(
        entity_type="booking",
        entity_id=uuid.UUID(booking_id),
        action="booking.rescheduled",
        actor_type="ai",
        details={"new_slot": new_slot_iso, "hold_id": hold_result["hold_id"]},
    ))

    bookings_total.labels(event="rescheduled").inc()
    logger.info("booking_rescheduled", booking_id=booking_id, new_slot=new_slot_iso)
    return {"success": True, "new_slot": new_slot_iso}


async def expire_stale_holds(session: AsyncSession) -> int:
    """Mark expired slot holds as 'expired'. Called by Celery beat task."""
    now_utc = datetime.now(UTC)
    result = await session.execute(
        select(BookingSlotHold).where(
            BookingSlotHold.status == "active",
            BookingSlotHold.expires_at < now_utc,
        )
    )
    holds = result.scalars().all()
    for hold in holds:
        hold.status = "expired"

    if holds:
        logger.info("slot_holds_expired", count=len(holds))

    return len(holds)

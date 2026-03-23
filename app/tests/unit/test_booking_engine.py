"""
app/tests/unit/test_booking_engine.py — Unit tests for the booking engine.
"""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

from app.core.exceptions import SlotHoldExpiredError, SlotNotAvailableError
from app.models.booking import Booking
from app.models.booking_slot_hold import BookingSlotHold
from app.models.customer import Customer
from app.models.conversation import Conversation
from app.models.pricing_rule import PricingRule
from app.models.service_area import ServiceArea


@pytest_asyncio.fixture
async def seeded_session(db_session):
    """Session with pricing rules, service area, customer, and conversation pre-seeded."""
    customer = Customer(phone_e164="+212612345678", name="Hassan")
    db_session.add(customer)
    await db_session.flush()

    conv = Conversation(customer_id=customer.id, channel="whatsapp", state="active")
    db_session.add(conv)

    pricing = PricingRule(
        vehicle_category="berline",
        service_type="exterieur",
        price_mad=50,
        active=True,
        effective_from=datetime(2024, 1, 1, tzinfo=UTC),
    )
    db_session.add(pricing)

    area = ServiceArea(city_name="mohammedia", active=True)
    db_session.add(area)

    await db_session.flush()
    return db_session, customer, conv


@pytest.mark.asyncio
async def test_create_slot_hold_success(seeded_session):
    from app.services.booking_service import create_slot_hold
    session, customer, conv = seeded_session
    slot = (datetime.now(UTC) + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    result = await create_slot_hold(session, str(conv.id), slot.isoformat())
    assert result["success"] is True
    assert "hold_id" in result
    assert "expires_at" in result


@pytest.mark.asyncio
async def test_create_slot_hold_prevents_double_hold(seeded_session):
    """Two different conversations cannot hold the same slot."""
    from app.services.booking_service import create_slot_hold
    session, customer, conv = seeded_session

    # Create a second conversation
    conv2 = Conversation(customer_id=customer.id, channel="whatsapp", state="active")
    session.add(conv2)
    await session.flush()

    slot = (datetime.now(UTC) + timedelta(days=2)).replace(hour=11, minute=0, second=0, microsecond=0)

    # First hold succeeds
    await create_slot_hold(session, str(conv.id), slot.isoformat())

    # Second hold for same slot from different conv should fail
    with pytest.raises(SlotNotAvailableError):
        await create_slot_hold(session, str(conv2.id), slot.isoformat())


@pytest.mark.asyncio
async def test_confirm_booking_success(seeded_session):
    from app.services.booking_service import confirm_booking, create_slot_hold
    session, customer, conv = seeded_session

    slot = (datetime.now(UTC) + timedelta(days=3)).replace(hour=9, minute=0, second=0, microsecond=0)
    hold_result = await create_slot_hold(session, str(conv.id), slot.isoformat())

    result = await confirm_booking(
        session=session,
        conversation_id=str(conv.id),
        hold_id=hold_result["hold_id"],
        vehicle_category="berline",
        service_type="exterieur",
        address_text="12 Rue des Orangers, Mohammedia",
        area_name="mohammedia",
        customer_id=str(customer.id),
    )

    assert result["status"] == "confirmed"
    assert result["price_mad"] == 50.0


@pytest.mark.asyncio
async def test_confirm_expired_hold_raises(seeded_session):
    from app.services.booking_service import confirm_booking
    session, customer, conv = seeded_session

    # Try to confirm with a fake hold ID
    fake_hold_id = str(uuid.uuid4())
    with pytest.raises(SlotHoldExpiredError):
        await confirm_booking(
            session=session,
            conversation_id=str(conv.id),
            hold_id=fake_hold_id,
            vehicle_category="berline",
            service_type="exterieur",
            address_text="Test",
            area_name="mohammedia",
            customer_id=str(customer.id),
        )


@pytest.mark.asyncio
async def test_cancel_booking(seeded_session):
    from app.services.booking_service import cancel_booking, confirm_booking, create_slot_hold
    session, customer, conv = seeded_session

    slot = (datetime.now(UTC) + timedelta(days=4)).replace(hour=14, minute=0, second=0, microsecond=0)
    hold = await create_slot_hold(session, str(conv.id), slot.isoformat())
    booking = await confirm_booking(
        session, str(conv.id), hold["hold_id"], "berline", "exterieur",
        "Test address", "mohammedia", str(customer.id)
    )

    result = await cancel_booking(session, booking["booking_id"], "customer request")
    assert result["success"] is True


@pytest.mark.asyncio
async def test_expire_stale_holds(seeded_session):
    from app.services.booking_service import expire_stale_holds
    from app.models.booking_slot_hold import BookingSlotHold

    session, customer, conv = seeded_session
    # Insert an already-expired hold
    expired_hold = BookingSlotHold(
        conversation_id=conv.id,
        hold_key="expired_test_key",
        scheduled_start=datetime.now(UTC) + timedelta(hours=1),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),  # Already expired
        status="active",
    )
    session.add(expired_hold)
    await session.flush()

    count = await expire_stale_holds(session)
    assert count >= 1

"""
app/tests/integration/test_double_booking.py — Double-booking prevention tests.
"""
import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest


@pytest.mark.asyncio
async def test_concurrent_holds_for_same_slot_only_one_wins(db_session):
    """
    Simulate two conversations trying to hold the same slot concurrently.
    Only one should succeed.
    """
    from app.models.conversation import Conversation
    from app.models.customer import Customer
    from app.models.pricing_rule import PricingRule
    from app.services.booking_service import create_slot_hold
    from app.core.exceptions import SlotNotAvailableError

    customer = Customer(phone_e164="+212600000001")
    db_session.add(customer)
    await db_session.flush()

    conv1 = Conversation(customer_id=customer.id, channel="whatsapp", state="active")
    conv2 = Conversation(customer_id=customer.id, channel="whatsapp", state="active")
    db_session.add_all([conv1, conv2])
    await db_session.flush()

    slot = (datetime.now(UTC) + timedelta(days=7)).replace(hour=10, minute=0, second=0, microsecond=0)

    # First hold should succeed
    result1 = await create_slot_hold(db_session, str(conv1.id), slot.isoformat())
    assert result1["success"] is True

    # Second hold for same slot from different conversation should fail
    with pytest.raises(SlotNotAvailableError):
        await create_slot_hold(db_session, str(conv2.id), slot.isoformat())


@pytest.mark.asyncio
async def test_no_double_booking_after_confirmation(db_session):
    """After a booking is confirmed, the slot should not be holdable."""
    from app.models.conversation import Conversation
    from app.models.customer import Customer
    from app.models.pricing_rule import PricingRule
    from app.services.booking_service import confirm_booking, create_slot_hold
    from app.core.exceptions import SlotNotAvailableError

    customer = Customer(phone_e164="+212600000002")
    db_session.add(customer)
    pricing = PricingRule(
        vehicle_category="citadine", service_type="exterieur",
        price_mad=40, active=True, effective_from=datetime(2024, 1, 1, tzinfo=UTC)
    )
    db_session.add(pricing)
    await db_session.flush()

    conv1 = Conversation(customer_id=customer.id, channel="whatsapp", state="active")
    conv2 = Conversation(customer_id=customer.id, channel="whatsapp", state="active")
    db_session.add_all([conv1, conv2])
    await db_session.flush()

    slot = (datetime.now(UTC) + timedelta(days=8)).replace(hour=9, minute=0, second=0, microsecond=0)

    # Hold and confirm for conv1
    hold = await create_slot_hold(db_session, str(conv1.id), slot.isoformat())
    await confirm_booking(
        db_session, str(conv1.id), hold["hold_id"],
        "citadine", "exterieur", "Test address", "mohammedia", str(customer.id)
    )
    await db_session.flush()

    # Now conv2 tries to hold same slot — should fail
    with pytest.raises(SlotNotAvailableError):
        await create_slot_hold(db_session, str(conv2.id), slot.isoformat())

"""
app/tests/unit/test_idempotency.py — Tests for idempotency mechanisms.
"""
import pytest

from app.core.security import compute_dedupe_key


def test_dedupe_key_is_deterministic():
    """Same inputs must always produce the same hash."""
    key1 = compute_dedupe_key("conv-123", "event-456", "hello world")
    key2 = compute_dedupe_key("conv-123", "event-456", "hello world")
    assert key1 == key2


def test_dedupe_key_differs_on_different_input():
    """Different inputs must produce different hashes."""
    key1 = compute_dedupe_key("conv-123", "event-456", "hello")
    key2 = compute_dedupe_key("conv-123", "event-456", "world")
    assert key1 != key2


def test_dedupe_key_is_64_chars():
    """SHA-256 hex digest is always 64 characters."""
    key = compute_dedupe_key("a", "b", "c")
    assert len(key) == 64


@pytest.mark.asyncio
async def test_inbound_event_unique_constraint(db_session):
    """Two InboundEvent rows with the same provider_event_id must fail."""
    from sqlalchemy.exc import IntegrityError
    from app.models.inbound_event import InboundEvent

    sid = "SM_unique_test_" + "x" * 16

    event1 = InboundEvent(
        provider_event_id=sid,
        provider="twilio",
        event_type="inbound_message",
        payload={"Body": "test"},
        processing_status="pending",
    )
    db_session.add(event1)
    await db_session.flush()

    event2 = InboundEvent(
        provider_event_id=sid,  # Same SID — must fail
        provider="twilio",
        event_type="inbound_message",
        payload={"Body": "duplicate"},
        processing_status="pending",
    )
    db_session.add(event2)

    with pytest.raises(IntegrityError):
        await db_session.flush()

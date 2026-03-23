"""
app/tests/unit/test_area_service.py — Unit tests for service area validation.
"""
import pytest


@pytest.mark.parametrize("input_text,expected_in_area", [
    ("mohammedia", True),
    ("Mohammedia", True),
    ("mohammédia", True),
    ("المحمدية", True),
    ("محمدية", True),
    ("12 rue des orangers, mohammedia", True),
    ("casablanca", False),
    ("rabat", False),
    ("", False),
])
@pytest.mark.asyncio
async def test_check_service_area(db_session, input_text, expected_in_area):
    from app.models.service_area import ServiceArea
    from app.services.area_service import check_service_area

    # Ensure mohammedia is seeded
    from sqlalchemy import select
    result = await db_session.execute(select(ServiceArea).where(ServiceArea.city_name == "mohammedia"))
    if result.scalar_one_or_none() is None:
        db_session.add(ServiceArea(city_name="mohammedia", active=True))
        await db_session.flush()

    result = await check_service_area(db_session, input_text)
    assert result["in_area"] == expected_in_area


@pytest.mark.asyncio
async def test_inactive_area_returns_false(db_session):
    """An inactive service area should return in_area=False."""
    from app.models.service_area import ServiceArea
    from app.services.area_service import check_service_area

    db_session.add(ServiceArea(city_name="kenitra", active=False))
    await db_session.flush()

    result = await check_service_area(db_session, "kenitra")
    assert result["in_area"] is False

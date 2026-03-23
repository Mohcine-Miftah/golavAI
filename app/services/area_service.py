"""
app/services/area_service.py — Service area validation.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.service_area import ServiceArea

logger = get_logger(__name__)

# Aliases for fuzzy matching (client might type in Darija, French, or English)
CITY_ALIASES: dict[str, str] = {
    # Mohammedia variants
    "mohammedia": "mohammedia",
    "mohammédia": "mohammedia",
    "mohamedia": "mohammedia",
    "محمدية": "mohammedia",
    "المحمدية": "mohammedia",
    "الحمدية": "mohammedia",
}


def normalize_city(city_or_address: str) -> str | None:
    """Extract and normalize a city name from free text."""
    text = city_or_address.strip().lower()
    for alias, canonical in CITY_ALIASES.items():
        if alias in text:
            return canonical
    return None


async def check_service_area(
    session: AsyncSession,
    city_or_address: str,
) -> dict:
    """
    Check if a city or address is within the active service area.

    Returns:
        {"in_area": bool, "city_name": str | None, "message": str}
    """
    canonical = normalize_city(city_or_address)

    if canonical is None:
        logger.info("area_check_unknown", input=city_or_address)
        return {
            "in_area": False,
            "city_name": None,
            "message": f"Unable to determine city from '{city_or_address}'. Please confirm you are in Mohammedia.",
        }

    result = await session.execute(
        select(ServiceArea).where(
            ServiceArea.city_name == canonical,
            ServiceArea.active == True,
        )
    )
    area = result.scalar_one_or_none()

    if area:
        return {"in_area": True, "city_name": canonical, "message": f"{canonical.title()} is within our service area."}

    return {
        "in_area": False,
        "city_name": canonical,
        "message": f"{canonical.title()} is not currently in our service area. We only serve Mohammedia.",
    }

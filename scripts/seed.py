"""
scripts/seed.py — Seed the database with default pricing rules and service areas.

Run once after migrations: python scripts/seed.py
Idempotent — safe to run multiple times.
"""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.pricing_rule import PricingRule
from app.models.service_area import ServiceArea

PRICING_DEFAULTS = [
    # (vehicle_category, service_type, price_mad)
    ("citadine", "exterieur", 40),
    ("citadine", "complet",   69),
    ("berline",  "exterieur", 50),
    ("berline",  "complet",   79),
    ("suv",      "exterieur", 60),
    ("suv",      "complet",   89),
]

SERVICE_AREAS = [
    {"city_name": "mohammedia", "active": True, "notes": "Ville principale — zone opérationnelle GOLAV"},
]

EPOCH = datetime(2024, 1, 1, tzinfo=timezone.utc)


async def seed() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        await seed_service_areas(session)
        await seed_pricing(session)
        await session.commit()

    await engine.dispose()
    print("✅ Database seeded successfully.")


async def seed_service_areas(session: AsyncSession) -> None:
    for area in SERVICE_AREAS:
        existing = await session.execute(
            select(ServiceArea).where(ServiceArea.city_name == area["city_name"])
        )
        if existing.scalar_one_or_none() is None:
            session.add(ServiceArea(**area))
            print(f"  + ServiceArea: {area['city_name']}")
        else:
            print(f"  ~ ServiceArea already exists: {area['city_name']}")


async def seed_pricing(session: AsyncSession) -> None:
    for vehicle_category, service_type, price in PRICING_DEFAULTS:
        existing = await session.execute(
            select(PricingRule).where(
                PricingRule.vehicle_category == vehicle_category,
                PricingRule.service_type == service_type,
                PricingRule.active == True,
            )
        )
        if existing.scalar_one_or_none() is None:
            session.add(PricingRule(
                vehicle_category=vehicle_category,
                service_type=service_type,
                price_mad=price,
                active=True,
                effective_from=EPOCH,
            ))
            print(f"  + PricingRule: {vehicle_category}/{service_type} = {price} MAD")
        else:
            print(f"  ~ PricingRule already exists: {vehicle_category}/{service_type}")


if __name__ == "__main__":
    asyncio.run(seed())

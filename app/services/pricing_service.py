"""
app/services/pricing_service.py — Pricing lookups from the database.
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import GolavBaseError
from app.core.logging import get_logger
from app.models.pricing_rule import PricingRule

logger = get_logger(__name__)


async def get_price(
    session: AsyncSession,
    vehicle_category: str,
    service_type: str,
) -> Decimal:
    """
    Fetch the active price for a vehicle category + service type.
    Raises GolavBaseError if no active pricing rule found.
    """
    result = await session.execute(
        select(PricingRule).where(
            PricingRule.vehicle_category == vehicle_category.lower(),
            PricingRule.service_type == service_type.lower(),
            PricingRule.active == True,
        ).order_by(PricingRule.effective_from.desc()).limit(1)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        logger.error("pricing_rule_missing", category=vehicle_category, service=service_type)
        raise GolavBaseError(f"No active pricing rule for {vehicle_category}/{service_type}")
    return rule.price_mad


async def get_all_prices(session: AsyncSession) -> list[dict]:
    """Return all active pricing rules as a list of dicts (for price card generation)."""
    result = await session.execute(
        select(PricingRule)
        .where(PricingRule.active == True)
        .order_by(PricingRule.vehicle_category, PricingRule.service_type)
    )
    rules = result.scalars().all()
    return [
        {
            "vehicle_category": r.vehicle_category,
            "service_type": r.service_type,
            "price_mad": float(r.price_mad),
        }
        for r in rules
    ]

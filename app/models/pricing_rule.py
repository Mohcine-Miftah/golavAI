"""
app/models/pricing_rule.py — Pricing rule model.

Prices are stored in DB and editable via admin API.
Only one active rule per (vehicle_category, service_type) at a time.
effective_to=NULL means the rule is valid indefinitely.
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class PricingRule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "pricing_rules"

    vehicle_category: Mapped[str] = mapped_column(String(30), nullable=False)  # citadine | berline | suv
    service_type: Mapped[str] = mapped_column(String(30), nullable=False)       # exterieur | complet
    price_mad: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_pricing_rules_category_type_active", "vehicle_category", "service_type", "active"),
    )

    def __repr__(self) -> str:
        return f"<PricingRule {self.vehicle_category}/{self.service_type} = {self.price_mad} MAD>"

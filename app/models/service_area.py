"""
app/models/service_area.py — Service area model.
"""
from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class ServiceArea(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "service_areas"

    city_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    geojson: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # Optional polygon boundary
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_service_areas_city_name", "city_name"),)

    def __repr__(self) -> str:
        return f"<ServiceArea {self.city_name} active={self.active}>"

"""
app/models/daily_export.py — Record of nightly export runs.
"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class DailyExport(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "daily_exports"

    export_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    booking_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending | done | failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<DailyExport {self.export_date} status={self.status}>"

"""
app/workers/tasks/nightly_export.py — Nightly Excel/CSV export task.
"""
import asyncio
from datetime import date

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    name="app.workers.tasks.nightly_export.run_nightly_export",
    queue="maintenance",
    acks_late=True,
)
def run_nightly_export(export_date_str: str | None = None) -> None:
    asyncio.get_event_loop().run_until_complete(_export(export_date_str))


async def _export(export_date_str: str | None) -> None:
    from app.db.session import AsyncSessionLocal
    from app.exports.excel_exporter import generate_daily_export

    if export_date_str:
        export_date = date.fromisoformat(export_date_str)
    else:
        from datetime import datetime
        import pytz
        export_date = datetime.now(pytz.timezone("Africa/Casablanca")).date()

    async with AsyncSessionLocal() as session:
        await generate_daily_export(session, export_date)
        await session.commit()

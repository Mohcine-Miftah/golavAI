"""
app/workers/tasks/expire_holds.py — Slot hold expiry maintenance task.
"""
import asyncio

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    name="app.workers.tasks.expire_holds.expire_stale_slot_holds",
    queue="maintenance",
    acks_late=True,
)
def expire_stale_slot_holds() -> None:
    asyncio.get_event_loop().run_until_complete(_expire())


async def _expire() -> None:
    from app.db.session import AsyncSessionLocal
    from app.services.booking_service import expire_stale_holds

    async with AsyncSessionLocal() as session:
        count = await expire_stale_holds(session)
        await session.commit()
        if count > 0:
            logger.info("holds_expired", count=count)


# ── app/workers/tasks/nightly_export.py ──────────────────────────────────────

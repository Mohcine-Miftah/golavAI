"""
app/workers/celery_app.py — Celery application factory.
"""
from celery import Celery

from app.config import settings

celery_app = Celery(
    "golav",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.tasks.process_inbound",
        "app.workers.tasks.dispatch_outbox",
        "app.workers.tasks.expire_holds",
        "app.workers.tasks.nightly_export",
    ],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="Africa/Casablanca",
    enable_utc=True,
    # Reliability
    task_acks_late=True,              # ACK only after task completes (survive worker crash)
    task_reject_on_worker_lost=True,  # Re-queue if worker dies mid-task
    worker_prefetch_multiplier=1,     # Fair dispatching — critical for AI tasks
    # Result expiry
    result_expires=3600,
    # Task routing
    task_routes={
        "app.workers.tasks.process_inbound.*": {"queue": "ai"},
        "app.workers.tasks.dispatch_outbox.*": {"queue": "outbox"},
        "app.workers.tasks.expire_holds.*": {"queue": "maintenance"},
        "app.workers.tasks.nightly_export.*": {"queue": "maintenance"},
    },
    # Beat schedule (loaded from separate file)
    beat_schedule_filename="celerybeat-schedule",
)

# Import beat schedule
from app.workers.beat_schedule import BEAT_SCHEDULE  # noqa: E402
celery_app.conf.beat_schedule = BEAT_SCHEDULE

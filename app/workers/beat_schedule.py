"""
app/workers/beat_schedule.py — Celery beat periodic task schedule.
"""
from celery.schedules import crontab

BEAT_SCHEDULE = {
    # Dispatch pending outbound messages every 15 seconds
    "dispatch_outbox_every_15s": {
        "task": "app.workers.tasks.dispatch_outbox.dispatch_pending_outbox",
        "schedule": 15.0,
        "options": {"queue": "outbox"},
    },
    # Expire stale slot holds every 60 seconds
    "expire_slot_holds_every_60s": {
        "task": "app.workers.tasks.expire_holds.expire_stale_slot_holds",
        "schedule": 60.0,
        "options": {"queue": "maintenance"},
    },
    # Nightly export at 00:05 Africa/Casablanca
    "nightly_export_0005": {
        "task": "app.workers.tasks.nightly_export.run_nightly_export",
        "schedule": crontab(hour=0, minute=5),
        "options": {"queue": "maintenance"},
    },
}

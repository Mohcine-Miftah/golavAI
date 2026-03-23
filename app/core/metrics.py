"""
app/core/metrics.py — Prometheus metrics exposed via /metrics endpoint.
"""
from prometheus_client import Counter, Histogram

# ── Inbound events ────────────────────────────────────────────────────────────
inbound_events_total = Counter(
    "golav_inbound_events_total",
    "Total inbound WhatsApp events received",
    ["status"],  # received | duplicate | error
)

# ── AI orchestration ─────────────────────────────────────────────────────────
ai_calls_total = Counter(
    "golav_ai_calls_total",
    "Total OpenAI API calls",
    ["status"],  # success | error | circuit_open
)
ai_call_duration_seconds = Histogram(
    "golav_ai_call_duration_seconds",
    "Duration of OpenAI API calls in seconds",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

# ── Outbox dispatcher ─────────────────────────────────────────────────────────
outbox_sends_total = Counter(
    "golav_outbox_sends_total",
    "Total outbound message sends attempted",
    ["status"],  # sent | failed | dead_lettered
)

# ── Bookings ─────────────────────────────────────────────────────────────────
bookings_total = Counter(
    "golav_bookings_total",
    "Total bookings created or transitioned",
    ["event"],  # created | cancelled | rescheduled | confirmed
)

# ── Escalations ──────────────────────────────────────────────────────────────
escalations_total = Counter(
    "golav_escalations_total",
    "Total human escalations triggered",
    ["reason_code"],
)

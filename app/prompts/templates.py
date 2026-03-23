"""
app/prompts/templates.py — WhatsApp approved template names for out-of-session messages.

IMPORTANT: These templates must be pre-approved in your Twilio console before use.
Outside the 24-hour customer-initiated session window, only these approved templates
can be sent. Free-form messages will fail with a Twilio error.
"""

# Template names as registered in Twilio Content Template Builder
class WhatsAppTemplates:
    # Used when the agent needs to re-engage a customer after the 24h window expires
    BOOKING_REMINDER = "golav_booking_reminder"
    # Booking confirmation summary
    BOOKING_CONFIRMED = "golav_booking_confirmed"
    # Cancellation acknowledgement
    BOOKING_CANCELLED = "golav_booking_cancelled"
    # Rescheduling confirmation
    BOOKING_RESCHEDULED = "golav_booking_rescheduled"
    # Service complete notification
    SERVICE_COMPLETED = "golav_service_completed"
    # Coverage expansion notification (for out-of-area customers who opted in)
    ZONE_EXPANDED = "golav_zone_expanded"


# Fallback: if no template matches and session is active, send free-form
def is_within_session(last_inbound_at) -> bool:
    """Check if the customer's 24-hour WhatsApp session is still open."""
    if last_inbound_at is None:
        return False
    from datetime import UTC, datetime, timedelta
    return (datetime.now(UTC) - last_inbound_at) < timedelta(hours=23, minutes=50)

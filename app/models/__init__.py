"""
app/models/__init__.py — Export all models so Alembic can find them for autogenerate.
"""
from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.booking_slot_hold import BookingSlotHold
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.daily_export import DailyExport
from app.models.escalation_task import EscalationTask
from app.models.inbound_event import InboundEvent
from app.models.message import Message
from app.models.outbound_message import OutboundMessage
from app.models.pricing_rule import PricingRule
from app.models.service_area import ServiceArea

__all__ = [
    "AuditLog",
    "Booking",
    "BookingSlotHold",
    "Conversation",
    "Customer",
    "DailyExport",
    "EscalationTask",
    "InboundEvent",
    "Message",
    "OutboundMessage",
    "PricingRule",
    "ServiceArea",
]

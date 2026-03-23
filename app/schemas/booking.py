"""
app/schemas/booking.py — Request/response schemas for booking API.
"""
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class BookingCreateRequest(BaseModel):
    """Used by human admin to manually create a booking."""
    customer_phone: str
    vehicle_model: str | None = None
    vehicle_category: str
    service_type: str
    address_text: str
    area_name: str
    scheduled_start: datetime
    notes: str | None = None


class BookingResponse(BaseModel):
    """API response shape for a booking."""
    id: uuid.UUID
    customer_id: uuid.UUID
    vehicle_category: str
    service_type: str
    address_text: str
    area_name: str
    scheduled_start: datetime
    price_mad: Decimal
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BookingStatusUpdateRequest(BaseModel):
    status: str
    notes: str | None = None


class SlotAvailability(BaseModel):
    available: bool
    slots: list[datetime] = Field(default_factory=list)
    message: str | None = None

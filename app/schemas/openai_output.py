"""
app/schemas/openai_output.py — Pydantic v2 schema for the structured LLM output.
"""
from typing import Literal
from pydantic import BaseModel, Field


class BookingEntities(BaseModel):
    """Structured entities extracted from the conversation."""
    model_config = {"extra": "forbid"}

    vehicle_model: str | None = Field(..., description="Vehicle model (e.g. Golf 7, Dacia Logan)")
    vehicle_category: str | None = Field(..., description="citadine | berline | suv")
    service_type: str | None = Field(..., description="exterieur | complet")
    requested_date: str | None = Field(..., description="ISO YYYY-MM-DD")
    requested_time: str | None = Field(..., description="HH:MM 24h format")
    address_text: str | None = Field(..., description="Full address in Mohammedia")
    area_name: str | None = Field(..., description="mohammedia")
    customer_name: str | None = Field(..., description="Customer name")


class ProposedActionParams(BaseModel):
    """
    OpenAI 'Strict' mode parameters. All fields must be present in the required array.
    """
    model_config = {"extra": "forbid"}

    city_or_address: str | None = Field(..., description="For check_service_area")
    vehicle_text: str | None = Field(..., description="For classify_vehicle")
    vehicle_category: str | None = Field(..., description="For get_price and confirm_booking")
    service_type: str | None = Field(..., description="For get_price and confirm_booking")
    date: str | None = Field(..., description="For get_available_slots")
    area_name: str | None = Field(..., description="mohammedia")
    slot: str | None = Field(..., description="ISO datetime for create_slot_hold")
    hold_id: str | None = Field(..., description="Required for confirm_booking!")
    address_text: str | None = Field(..., description="Required for confirm_booking")
    vehicle_model: str | None = Field(..., description="Specific vehicle model")
    booking_id: str | None = Field(..., description="For cancel/reschedule")
    reason: str | None = Field(..., description="For cancel")
    reason_text: str | None = Field(..., description="For human explanation")
    new_slot: str | None = Field(..., description="For reschedule")


class ProposedAction(BaseModel):
    """A single action the AI wants the app layer to execute."""
    model_config = {"extra": "forbid"}

    type: str = Field(..., description="Tool name: get_available_slots, create_slot_hold, confirm_booking, etc.")
    params: ProposedActionParams = Field(..., description="Parameters for the tool.")


class AIStructuredOutput(BaseModel):
    """
    The single JSON object the LLM must return on every turn.
    """
    model_config = {"extra": "forbid"}

    intent: str = Field(..., description="intent: greeting | check_availability | confirming_booking | human_handoff")
    language: str = Field(..., description="fr | ar | dar")
    confidence: float = Field(..., ge=0.0, le=1.0)
    customer_facing_reply: str = Field(..., description="Response to the user.")
    needs_human: bool = Field(...)
    needs_human_reason: str | None = Field(...)
    missing_fields: list[str] = Field(...)
    proposed_actions: list[ProposedAction] = Field(...)
    entities: BookingEntities = Field(...)

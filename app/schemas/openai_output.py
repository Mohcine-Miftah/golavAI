"""
app/schemas/openai_output.py — Pydantic v2 schema for the structured LLM output.

This schema is used for OpenAI Strict Structured Outputs.
ALL fields must be required in the JSON schema (no defaults at the top level).
Optional fields are handled as Union[T, None] / Optional[T].
"""
from typing import Literal

from pydantic import BaseModel, Field


class BookingEntities(BaseModel):
    """Structured entities extracted from the conversation."""
    model_config = {"extra": "forbid"}

    vehicle_model: str | None = Field(..., description="The specific model of the vehicle if known.")
    vehicle_category: str | None = Field(..., description="One of: citadine | berline | suv")
    service_type: str | None = Field(..., description="One of: exterieur | complet")
    requested_date: str | None = Field(..., description="ISO date string YYYY-MM-DD")
    requested_time: str | None = Field(..., description="HH:MM 24h format")
    address_text: str | None = Field(..., description="Full address in Mohammedia")
    area_name: str | None = Field(..., description="Defaults to mohammedia")
    customer_name: str | None = Field(..., description="Customer name if provided")


class ProposedActionParams(BaseModel):
    """
    Explicitly defined parameters for all GOLAV tools.
    OpenAI 'Strict' mode requires all properties to be predefined (no arbitrary dicts).
    """
    model_config = {"extra": "forbid"}

    city_or_address: str | None = Field(None, description="For check_service_area")
    vehicle_text: str | None = Field(None, description="For classify_vehicle")
    vehicle_category: str | None = Field(None, description="For get_price and confirm_booking")
    service_type: str | None = Field(None, description="For get_price and confirm_booking")
    date: str | None = Field(None, description="For get_available_slots")
    area_name: str | None = Field(None, description="Region, defaults to mohammedia")
    slot: str | None = Field(None, description="ISO datetime for create_slot_hold")
    address_text: str | None = Field(None, description="For confirm_booking")
    vehicle_model: str | None = Field(None, description="Specific vehicle model")
    booking_id: str | None = Field(None, description="For cancel/reschedule")
    reason: str | None = Field(None, description="For cancel (standard reason)")
    reason_text: str | None = Field(None, description="For human handoff explanation")
    new_slot: str | None = Field(None, description="For reschedule_booking")


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

    intent: str = Field(..., description="Short internal description of customer intent.")
    language: str = Field(..., description="ISO language code of current reply (fr, ar, dar).")
    confidence: float = Field(..., ge=0.0, le=1.0)
    customer_facing_reply: str = Field(..., description="The message to send back to the WhatsApp user.")
    needs_human: bool = Field(..., description="Triggered if request is out-of-scope or customer is upset.")
    needs_human_reason: str | None = Field(..., description="Internal explanation if needs_human=true.")
    missing_fields: list[str] = Field(..., description="Fields needed but not yet provided by the customer.")
    proposed_actions: list[ProposedAction] = Field(..., description="Tools requested during this turn.")
    entities: BookingEntities = Field(..., description="Entities extracted from history.")

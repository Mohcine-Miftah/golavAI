"""
app/schemas/openai_output.py — Pydantic v2 schema for the structured LLM output.

The OpenAI Responses API is configured with response_format=json_schema.
The LLM must produce JSON conforming to this schema exactly.
The app layer then validates it here before executing any tools.
"""
from typing import Literal

from pydantic import BaseModel, Field


class BookingEntities(BaseModel):
    """Structured entities extracted from the conversation."""
    vehicle_model: str | None = None
    vehicle_category: Literal["citadine", "berline", "suv"] | None = None
    service_type: Literal["exterieur", "complet"] | None = None
    requested_date: str | None = None    # ISO date string YYYY-MM-DD
    requested_time: str | None = None    # HH:MM 24h format
    address_text: str | None = None
    area_name: str | None = None
    customer_name: str | None = None


class ProposedAction(BaseModel):
    """A single action the AI wants the app layer to execute."""
    type: Literal[
        "check_service_area",
        "classify_vehicle",
        "get_price",
        "get_available_slots",
        "create_slot_hold",
        "confirm_booking",
        "cancel_booking",
        "reschedule_booking",
        "send_price_card",
        "escalate",
        "no_op",
    ]
    params: dict = Field(default_factory=dict)


class AIStructuredOutput(BaseModel):
    """
    The single JSON object the LLM must return on every turn.
    The app layer validates this, executes proposed_actions, and sends the reply.
    """
    intent: Literal[
        "greeting",
        "ask_price",
        "ask_service_area",
        "ask_how_it_works",
        "booking_request",
        "reschedule_request",
        "cancel_request",
        "follow_up",
        "complaint",
        "review",
        "unknown",
    ]
    language: Literal[
        "french",
        "darija_arabic",    # Arabic script
        "darija_latin",     # Arabizi / Latin Darija
        "en",
        "unknown",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    customer_facing_reply: str = Field(
        description="The message to send to the customer, in their detected language."
    )
    needs_human: bool = False
    needs_human_reason: str | None = None
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Fields still needed before confirming a booking.",
    )
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    entities: BookingEntities = Field(default_factory=BookingEntities)

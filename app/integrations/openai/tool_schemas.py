"""
app/integrations/openai/tool_schemas.py — JSON schemas for OpenAI function tools.

These are passed to the Responses API so the model can request tool calls.
The app layer executes the actual implementations in services/.
"""
from typing import Any

# Each tool schema follows the OpenAI function tool format.
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_business_policies",
            "description": (
                "Returns GOLAV's business policies, FAQ, working hours, and service description. "
                "Call this when the customer asks how the service works, what you do, or any policy question."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_service_area",
            "description": (
                "Checks whether a given city or address is within GOLAV's service area (Mohammedia only). "
                "Returns {in_area: bool, city_name: str, message: str}."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city_or_address": {
                        "type": "string",
                        "description": "The city name or street address provided by the customer.",
                    }
                },
                "required": ["city_or_address"],
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "classify_vehicle",
            "description": (
                "Classify a vehicle into its category (citadine, berline, or suv) given the model name "
                "or free-text description. Returns {category: str, confidence: float}."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "vehicle_text": {
                        "type": "string",
                        "description": "Vehicle model name or free-text description (e.g. 'Logan', 'Dacia Duster').",
                    }
                },
                "required": ["vehicle_text"],
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price",
            "description": (
                "Returns the price in MAD for a given vehicle category and service type. "
                "Do NOT quote prices from memory — always use this tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "vehicle_category": {
                        "type": "string",
                        "enum": ["citadine", "berline", "suv"],
                        "description": "Vehicle category.",
                    },
                    "service_type": {
                        "type": "string",
                        "enum": ["exterieur", "complet"],
                        "description": "Service type.",
                    },
                },
                "required": ["vehicle_category", "service_type"],
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_slots",
            "description": (
                "Returns available booking slots for a given date and area. "
                "Returns {slots: list[str], message: str} where each slot is an ISO datetime string."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (Africa/Casablanca timezone).",
                    },
                    "area_name": {
                        "type": "string",
                        "description": "Area/city name, e.g. 'mohammedia'.",
                    },
                },
                "required": ["date", "area_name"],
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_slot_hold",
            "description": (
                "Creates a temporary slot hold to prevent double-booking. "
                "Must be called BEFORE confirming with the customer. "
                "Returns {hold_id: str, expires_at: str, success: bool}."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "conversation_id": {
                        "type": "string",
                        "description": "UUID of the current conversation.",
                    },
                    "slot": {
                        "type": "string",
                        "description": "ISO datetime string for the desired slot start.",
                    },
                },
                "required": ["conversation_id", "slot"],
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_booking",
            "description": (
                "Atomically confirms a booking. Must have a valid hold_id from create_slot_hold. "
                "Returns {booking_id: str, status: str, scheduled_start: str, price_mad: float}."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "conversation_id": {"type": "string"},
                    "hold_id": {"type": "string"},
                    "vehicle_category": {"type": "string", "enum": ["citadine", "berline", "suv"]},
                    "service_type": {"type": "string", "enum": ["exterieur", "complet"]},
                    "address_text": {"type": "string"},
                    "area_name": {"type": "string"},
                    "vehicle_model": {"type": ["string", "null"]},
                },
                "required": ["conversation_id", "hold_id", "vehicle_category", "service_type", "address_text", "area_name"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_booking",
            "description": "Cancels an active booking. Returns {success: bool, message: str}.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {"type": "string", "description": "UUID of the booking to cancel."},
                    "reason": {"type": "string", "description": "Reason for cancellation."},
                },
                "required": ["booking_id", "reason"],
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_booking",
            "description": "Reschedules an existing booking to a new slot. Returns {success: bool, new_slot: str}.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {"type": "string"},
                    "new_slot": {"type": "string", "description": "New ISO datetime slot."},
                },
                "required": ["booking_id", "new_slot"],
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_price_card",
            "description": "Sends a price card image to the customer. Returns {success: bool}.",
            "parameters": {
                "type": "object",
                "properties": {
                    "conversation_id": {"type": "string"},
                },
                "required": ["conversation_id"],
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_human_handoff",
            "description": (
                "Escalates the conversation to a human agent. "
                "Stops all autonomous AI replies for this conversation. "
                "Returns {task_id: str, success: bool}."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "conversation_id": {"type": "string"},
                    "reason": {
                        "type": "string",
                        "description": "Machine-readable reason code for the handoff.",
                    },
                    "reason_text": {
                        "type": "string",
                        "description": "Human-readable explanation for the handoff.",
                    },
                },
                "required": ["conversation_id", "reason"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_conversation_summary",
            "description": "Returns a summary of the ongoing conversation including any open bookings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "conversation_id": {"type": "string"},
                },
                "required": ["conversation_id"],
            },
            "strict": True,
        },
    },
]

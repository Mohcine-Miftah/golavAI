"""
app/services/tool_executor.py — Application-layer tool execution bridge.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.services.area_service import check_service_area
from app.services.booking_service import (
    cancel_booking,
    confirm_booking,
    create_slot_hold,
    get_available_slots,
    reschedule_booking,
)
from app.services.conversation_service import escalate_conversation, get_open_booking
from app.services.pricing_service import get_all_prices, get_price
from app.services.vehicle_service import classify_vehicle

logger = get_logger(__name__)

BUSINESS_POLICIES_TEXT = """\
GOLAV est un service de lavage automobile à domicile (sans eau).
Nous opérons uniquement à Mohammedia.
Horaires: Lundi–Samedi de 08h00 à 18h00.
Types de service: Extérieur (carrosserie) ou Complet (inté + extérieur).
Paiement à la fin du service.
Annulation gratuite jusqu'à 1h avant le rendez-vous.
Pour toute réclamation, contactez-nous directement.
"""


async def execute_tool(
    tool_name: str,
    params: any,
    session: AsyncSession,
    conversation_id: str,
    customer_id: str,
) -> dict:
    """
    Execute a single tool call and return a result dict.
    """
    # Normalize params to dict if it's a Pydantic model (Strict Mode)
    if hasattr(params, "model_dump"):
        params = params.model_dump()
    elif not isinstance(params, dict) and params is not None:
        params = dict(params)
    elif params is None:
        params = {}

    try:
        logger.info("tool_execute", tool=tool_name, params=params, conversation_id=conversation_id)

        if tool_name == "get_business_policies":
            return {"policy_text": BUSINESS_POLICIES_TEXT, "success": True}

        elif tool_name == "check_service_area":
            return await check_service_area(session, params.get("city_or_address", ""))

        elif tool_name == "classify_vehicle":
            return classify_vehicle(params.get("vehicle_text", ""))

        elif tool_name == "get_price":
            price = await get_price(
                session,
                params.get("vehicle_category"),
                params.get("service_type"),
            )
            return {"price_mad": float(price), "currency": "MAD", "success": True}

        elif tool_name == "get_available_slots":
            # Fixed: Use .get() for safety
            return await get_available_slots(session, params.get("date"), params.get("area_name", "mohammedia"))

        elif tool_name == "create_slot_hold":
            return await create_slot_hold(session, conversation_id, params.get("slot"))

        elif tool_name == "confirm_booking":
            result = await confirm_booking(
                session=session,
                conversation_id=conversation_id,
                vehicle_category=params.get("vehicle_category"),
                service_type=params.get("service_type"),
                address_text=params.get("address_text"),
                area_name=params.get("area_name", "mohammedia"),
                customer_id=customer_id,
                vehicle_model=params.get("vehicle_model"),
            )
            await session.commit()
            return result

        elif tool_name == "cancel_booking":
            booking_id = params.get("booking_id")
            if not booking_id:
                booking = await get_open_booking(session, conversation_id)
                if booking:
                    booking_id = str(booking.id)
            if not booking_id:
                return {"success": False, "message": "No active booking found to cancel."}
            result = await cancel_booking(session, booking_id, params.get("reason", "customer request"))
            await session.commit()
            return result

        elif tool_name == "reschedule_booking":
            booking_id = params.get("booking_id")
            if not booking_id:
                booking = await get_open_booking(session, conversation_id)
                if booking:
                    booking_id = str(booking.id)
            if not booking_id:
                return {"success": False, "message": "No active booking found to reschedule."}
            result = await reschedule_booking(session, booking_id, params.get("new_slot"), conversation_id)
            await session.commit()
            return result

        elif tool_name == "send_price_card":
            prices = await get_all_prices(session)
            return {"success": True, "prices": prices, "send_media": True}

        elif tool_name == "create_human_handoff":
            task = await escalate_conversation(
                session,
                conversation_id,
                reason_code=params.get("reason", "manual"),
                reason_text=params.get("reason_text"),
            )
            await session.commit()
            return {"task_id": str(task.id), "success": True}

        elif tool_name == "get_conversation_summary":
            booking = await get_open_booking(session, conversation_id)
            return {
                "conversation_id": conversation_id,
                "open_booking_id": str(booking.id) if booking else None,
                "open_booking_status": booking.status if booking else None,
                "success": True,
            }

        else:
            logger.warning("tool_unknown", tool=tool_name)
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

    except Exception as exc:
        logger.error("tool_execute_error", tool=tool_name, error=str(exc))
        return {"success": False, "error": str(exc)}

"""
app/api/webhooks/twilio_status.py — Twilio message delivery status callback.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.config import settings
from app.core.logging import get_logger
from app.core.security import validate_twilio_signature
from app.models.outbound_message import OutboundMessage
from app.schemas.twilio import TwilioStatusPayload
from fastapi.responses import Response

router = APIRouter()
logger = get_logger(__name__)


@router.post("/status")
async def twilio_status_callback(
    request: Request,
    x_twilio_signature: str = Header(alias="X-Twilio-Signature", default=""),
    session: AsyncSession = Depends(get_db),
):
    """Update outbound message delivery status from Twilio callback."""
    form_data = await request.form()
    params = dict(form_data)

    if settings.app_env == "production":
        if not validate_twilio_signature(str(request.url), params, x_twilio_signature):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    try:
        payload = TwilioStatusPayload(**params)
    except Exception as exc:
        logger.error("status_payload_parse_error", error=str(exc))
        raise HTTPException(status_code=400, detail="Invalid payload")

    logger.info(
        "twilio_status_received",
        sid=payload.MessageSid,
        status=payload.MessageStatus,
    )

    # Update the outbound_message delivery status
    result = await session.execute(
        select(OutboundMessage).where(OutboundMessage.provider_message_sid == payload.MessageSid)
    )
    msg = result.scalar_one_or_none()
    if msg:
        msg.send_status = payload.MessageStatus
        if payload.ErrorCode:
            msg.last_error = f"{payload.ErrorCode}: {payload.ErrorMessage}"
        await session.commit()
        logger.info("outbound_status_updated", sid=payload.MessageSid, status=payload.MessageStatus)
    else:
        logger.warning("outbound_message_not_found_for_status", sid=payload.MessageSid)

    return Response(content="<Response/>", media_type="application/xml", status_code=200)

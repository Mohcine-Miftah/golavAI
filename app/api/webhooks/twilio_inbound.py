"""
app/api/webhooks/twilio_inbound.py — Twilio inbound WhatsApp webhook.

Responsibilities:
1. Validate Twilio signature (reject forged requests immediately)
2. Parse Twilio form payload
3. Persist raw inbound_event atomically (idempotency)
4. Create/update customer + conversation + message records
5. Enqueue Celery job for async AI processing
6. Return HTTP 200 immediately (Twilio requires fast ACK)
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.config import settings
from app.core.exceptions import DuplicateEventError
from app.core.logging import get_logger
from app.core.metrics import inbound_events_total
from app.core.security import validate_twilio_signature
from app.models.inbound_event import InboundEvent
from app.models.message import Message
from app.schemas.twilio import TwilioInboundPayload
from app.services.conversation_service import (
    get_or_create_conversation,
    get_or_create_customer,
)
from app.workers.tasks.process_inbound import process_inbound_message

router = APIRouter()
logger = get_logger(__name__)


@router.post("/inbound")
async def twilio_inbound_webhook(
    request: Request,
    x_twilio_signature: str = Header(alias="X-Twilio-Signature", default=""),
    session: AsyncSession = Depends(get_db),
):
    """
    Receive inbound WhatsApp messages from Twilio.

    Critical path — must return 200 quickly.
    All heavy work is done asynchronously in Celery.
    """
    # 1. Read raw form body for signature validation
    form_data = await request.form()
    params = dict(form_data)
    url = str(request.url)

    # 2. Validate Twilio signature
    if settings.app_env == "production":
        if not validate_twilio_signature(url, params, x_twilio_signature):
            logger.warning("twilio_sig_invalid", url=url)
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    # 3. Parse payload
    try:
        payload = TwilioInboundPayload(**params)
    except Exception as exc:
        logger.error("twilio_payload_parse_error", error=str(exc))
        raise HTTPException(status_code=400, detail="Invalid payload")

    message_sid = payload.MessageSid
    phone = payload.from_phone

    logger.info("twilio_inbound_received", sid=message_sid, from_phone=phone)

    # 4. Idempotency check — attempt to insert inbound_event
    try:
        event = InboundEvent(
            provider_event_id=message_sid,
            provider="twilio",
            event_type="inbound_message",
            payload=params,
            processing_status="pending",
        )
        session.add(event)
        await session.flush()
    except IntegrityError:
        await session.rollback()
        inbound_events_total.labels(status="duplicate").inc()
        logger.info("twilio_inbound_duplicate", sid=message_sid)
        return Response(content="<Response/>", media_type="application/xml", status_code=200)

    # 5. Get or create customer
    customer = await get_or_create_customer(session, phone, payload.ProfileName)

    # 6. Get or create conversation
    conversation = await get_or_create_conversation(session, str(customer.id))
    conversation.last_inbound_at = datetime.now(timezone.utc)

    # 7. Persist message record
    msg = Message(
        conversation_id=conversation.id,
        direction="inbound",
        provider="twilio",
        provider_message_sid=message_sid,
        body_text=payload.Body,
        body_normalized=(payload.Body or "").strip().lower(),
        media_url=payload.MediaUrl0,
        message_type="image" if payload.NumMedia != "0" else "text",
        delivery_status="received",
        raw_payload=params,
    )
    session.add(msg)

    # 8. Mark event as pending (the worker will transition to processing)
    event.processing_status = "pending"

    await session.commit()

    inbound_events_total.labels(status="received").inc()

    # 9. Enqueue Celery task (fire and forget)
    process_inbound_message.delay(
        inbound_event_id=str(event.id),
        conversation_id=str(conversation.id),
        customer_id=str(customer.id),
        message_sid=message_sid,
    )

    logger.info("twilio_inbound_enqueued", sid=message_sid, conv_id=str(conversation.id))

    # 10. Return empty TwiML response (Twilio expects XML or 200)
    return Response(content="<Response/>", media_type="application/xml", status_code=200)

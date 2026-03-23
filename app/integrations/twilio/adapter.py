"""
app/integrations/twilio/adapter.py — Twilio WhatsApp adapter.

Handles:
- Outbound message sending via Twilio REST API
- Signature validation for inbound webhooks
- Retry with tenacity for transient Twilio errors
"""
import time

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client as TwilioClient

from app.config import settings
from app.core.exceptions import TwilioSendError
from app.core.logging import get_logger
from app.core.metrics import outbox_sends_total

logger = get_logger(__name__)

# Singleton Twilio client
_twilio_client: TwilioClient | None = None


def get_twilio_client() -> TwilioClient:
    global _twilio_client
    if _twilio_client is None:
        _twilio_client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
    return _twilio_client


@retry(
    retry=retry_if_exception_type(TwilioRestException),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, max=30),
    reraise=True,
)
def send_whatsapp_message(
    to_phone: str,
    body: str,
    media_url: str | None = None,
) -> str:
    """
    Send a WhatsApp message via Twilio REST API (sync — called from Celery worker).

    Args:
        to_phone: E.164 phone number of the recipient (without 'whatsapp:' prefix).
        body: Message text.
        media_url: Optional URL of a media attachment.

    Returns:
        Twilio MessageSid of the sent message.

    Raises:
        TwilioSendError: On non-retryable Twilio error.
        TwilioRestException: On transient error after retries.
    """
    client = get_twilio_client()
    to_address = f"whatsapp:{to_phone}"
    from_address = settings.twilio_whatsapp_from

    try:
        kwargs: dict = {"body": body, "from_": from_address, "to": to_address}
        if media_url:
            kwargs["media_url"] = [media_url]

        message = client.messages.create(**kwargs)
        outbox_sends_total.labels(status="sent").inc()
        logger.info("twilio_send_success", to=to_phone, sid=message.sid, status=message.status)
        return message.sid

    except TwilioRestException as exc:
        # Non-retryable errors: invalid number, blocked, etc.
        if exc.status in (400, 21211, 21408, 21610, 21614):
            outbox_sends_total.labels(status="failed").inc()
            logger.error("twilio_send_non_retryable", to=to_phone, code=exc.code, msg=exc.msg)
            raise TwilioSendError(f"Non-retryable Twilio error {exc.code}: {exc.msg}") from exc
        # Transient — let tenacity retry
        logger.warning("twilio_send_transient_error", to=to_phone, code=exc.code, attempt="retrying")
        raise

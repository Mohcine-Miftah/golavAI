"""
app/core/security.py — Twilio webhook signature validation.

Twilio signs every request using HMAC-SHA1 with the auth token.
We validate the signature to reject forged webhook calls.
"""
import hashlib
import hmac
from base64 import b64decode, b64encode
from urllib.parse import urlparse

from twilio.request_validator import RequestValidator

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def validate_twilio_signature(
    url: str,
    params: dict[str, str],
    signature: str,
) -> bool:
    """
    Validate a Twilio request signature.

    Args:
        url: Full URL that Twilio POSTed to (must match exactly what Twilio knows).
        params: POST form parameters (or empty dict for JSON bodies).
        signature: Value of X-Twilio-Signature header.

    Returns:
        True if valid, False otherwise.
    """
    validator = RequestValidator(settings.twilio_auth_token)
    is_valid = validator.validate(url, params, signature)
    if not is_valid:
        logger.warning("twilio_signature_invalid", url=url)
    return is_valid


def compute_dedupe_key(*parts: str) -> str:
    """Deterministic SHA-256 hash for deduplication keys."""
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode()).hexdigest()

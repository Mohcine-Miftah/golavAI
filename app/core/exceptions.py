"""
app/core/exceptions.py — Domain exception hierarchy.
"""
from fastapi import HTTPException, status


class GolavBaseError(Exception):
    """Base for all GOLAV domain errors."""


class DuplicateEventError(GolavBaseError):
    """Raised when an inbound event has already been processed (idempotency guard)."""


class SlotNotAvailableError(GolavBaseError):
    """Raised when attempting to hold or confirm a slot that is no longer free."""


class SlotHoldExpiredError(GolavBaseError):
    """Raised when trying to confirm a booking whose hold has expired."""


class ServiceAreaError(GolavBaseError):
    """Raised when a customer location is outside the service area."""


class BookingNotFoundError(GolavBaseError):
    """Raised when a booking cannot be found."""


class ConversationEscalatedError(GolavBaseError):
    """Raised if the AI tries to process an escalated conversation."""


class RateLimitExceededError(GolavBaseError):
    """Raised when a customer exceeds the per-minute message rate."""


class TwilioSendError(GolavBaseError):
    """Raised when a Twilio outbound send fails (non-retryable)."""


class OpenAIError(GolavBaseError):
    """Raised when an OpenAI API call fails."""

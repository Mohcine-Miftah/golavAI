"""
app/schemas/twilio.py — Pydantic v2 schemas for Twilio webhook payloads.
"""
from pydantic import BaseModel, Field


class TwilioInboundPayload(BaseModel):
    """
    Twilio sends inbound WhatsApp messages as form-encoded POST.
    Only the fields GOLAV cares about are modeled here.
    """
    MessageSid: str
    SmsSid: str | None = None
    AccountSid: str
    From_: str = Field(alias="From")       # e.g. "whatsapp:+212612345678"
    To: str                                 # e.g. "whatsapp:+212XXXXXXXXX"
    Body: str | None = None
    NumMedia: str = "0"
    MediaUrl0: str | None = None
    MediaContentType0: str | None = None
    WaId: str | None = None               # WhatsApp ID (phone without whatsapp: prefix)
    ProfileName: str | None = None        # Customer's WhatsApp display name

    model_config = {"populate_by_name": True}

    @property
    def from_phone(self) -> str:
        """Returns E.164 phone number, stripping 'whatsapp:' prefix."""
        return self.From_.replace("whatsapp:", "")

    @property
    def message_sid(self) -> str:
        return self.MessageSid


class TwilioStatusPayload(BaseModel):
    """Twilio message status callback payload."""
    MessageSid: str
    MessageStatus: str  # queued | sent | delivered | read | failed | undelivered
    To: str
    From_: str = Field(alias="From")
    ErrorCode: str | None = None
    ErrorMessage: str | None = None

    model_config = {"populate_by_name": True}

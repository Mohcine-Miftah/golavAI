"""
app/tests/mocks/mock_twilio.py — Mock Twilio adapter for tests.
"""
from unittest.mock import MagicMock


class MockTwilioAdapter:
    """
    Drop-in mock for send_whatsapp_message.
    Tracks all calls and returns configurable SIDs.
    """

    def __init__(self, fail: bool = False, sid_prefix: str = "SM"):
        self.calls: list[dict] = []
        self.fail = fail
        self.sid_prefix = sid_prefix
        self._call_count = 0

    def __call__(self, to_phone: str, body: str, media_url: str | None = None) -> str:
        self._call_count += 1
        call = {"to": to_phone, "body": body, "media_url": media_url}
        self.calls.append(call)

        if self.fail:
            from twilio.base.exceptions import TwilioRestException
            raise TwilioRestException(status=500, uri="/messages", msg="Mock server error", code=20001)

        return f"{self.sid_prefix}{'x' * 32}{self._call_count:04d}"

    @property
    def call_count(self) -> int:
        return self._call_count

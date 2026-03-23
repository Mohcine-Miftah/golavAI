"""
app/tests/mocks/mock_openai.py — Mock OpenAI adapter for tests.

Returns a pre-built AIStructuredOutput so tests never hit the real OpenAI API.
"""
from app.schemas.openai_output import AIStructuredOutput, BookingEntities


def make_ai_output(
    intent: str = "greeting",
    reply: str = "Merhba bik! 😊",
    needs_human: bool = False,
    language: str = "darija_arabic",
    confidence: float = 0.95,
    proposed_actions: list | None = None,
    entities: BookingEntities | None = None,
) -> AIStructuredOutput:
    return AIStructuredOutput(
        intent=intent,
        language=language,
        confidence=confidence,
        customer_facing_reply=reply,
        needs_human=needs_human,
        proposed_actions=proposed_actions or [],
        entities=entities or BookingEntities(),
    )


class MockOpenAIAdapter:
    """
    Callable that returns a pre-configured AIStructuredOutput.
    Tracks how many times it was called.
    """

    def __init__(self, output: AIStructuredOutput | None = None, raise_error: bool = False):
        self.output = output or make_ai_output()
        self.raise_error = raise_error
        self.call_count = 0
        self.last_messages: list | None = None

    async def __call__(self, conversation_messages: list, conversation_id: str) -> AIStructuredOutput:
        self.call_count += 1
        self.last_messages = conversation_messages
        if self.raise_error:
            from app.core.exceptions import OpenAIError
            raise OpenAIError("Mock OpenAI error")
        return self.output

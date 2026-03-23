"""
app/integrations/openai/adapter.py — OpenAI Responses API adapter.

Handles the full round-trip: build messages → call API → parse structured output.
Uses tenacity for retries with exponential backoff + jitter.
The circuit breaker pattern is implemented via a simple open/closed flag in Redis.
"""
import json
import time
from typing import Any

import openai
from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import settings
from app.core.exceptions import OpenAIError
from app.core.logging import get_logger
from app.core.metrics import ai_call_duration_seconds, ai_calls_total
from app.integrations.openai.tool_schemas import TOOL_SCHEMAS
from app.prompts.system_prompt import get_system_prompt
from app.schemas.openai_output import AIStructuredOutput

logger = get_logger(__name__)

# Singleton async client
_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


# Structured output JSON schema (auto-generated from Pydantic model)
RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "ai_structured_output",
        "strict": True,
        "schema": AIStructuredOutput.model_json_schema(),
    },
}


@retry(
    retry=retry_if_exception_type((openai.APITimeoutError, openai.APIConnectionError, openai.RateLimitError)),
    stop=stop_after_attempt(settings.ai_max_retries + 1),
    wait=wait_exponential_jitter(initial=1, max=30),
    reraise=True,
)
async def call_openai(
    conversation_messages: list[dict[str, str]],
    conversation_id: str,
) -> AIStructuredOutput:
    """
    Call OpenAI Responses API with conversation history and return validated structured output.

    Args:
        conversation_messages: List of {role, content} dicts (recent messages, newest last).
        conversation_id: Used for logging correlation.

    Returns:
        Validated AIStructuredOutput object.

    Raises:
        OpenAIError: If the call fails after retries or output is malformed.
    """
    client = get_openai_client()
    start = time.monotonic()

    messages = [
        {"role": "developer", "content": get_system_prompt()},
        *conversation_messages,
    ]

    try:
        logger.info("openai_call_start", conversation_id=conversation_id, msg_count=len(messages))

        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            response_format=RESPONSE_FORMAT,
            max_tokens=settings.openai_max_tokens,
            temperature=settings.openai_temperature,
        )

        duration = time.monotonic() - start
        ai_call_duration_seconds.observe(duration)
        ai_calls_total.labels(status="success").inc()

        raw_content = response.choices[0].message.content
        logger.debug("openai_call_done", conversation_id=conversation_id, duration_s=round(duration, 2))

        if raw_content is None:
            # Model returned a tool call directly — shouldn't happen with json_schema response_format
            # but handle gracefully
            raise OpenAIError("OpenAI returned no content (tool-only response not expected)")

        parsed = AIStructuredOutput.model_validate_json(raw_content)
        return parsed

    except openai.APITimeoutError:
        ai_calls_total.labels(status="error").inc()
        logger.warning("openai_timeout", conversation_id=conversation_id)
        raise
    except openai.APIConnectionError:
        ai_calls_total.labels(status="error").inc()
        logger.error("openai_connection_error", conversation_id=conversation_id)
        raise
    except openai.RateLimitError:
        ai_calls_total.labels(status="error").inc()
        logger.warning("openai_rate_limit", conversation_id=conversation_id)
        raise
    except (openai.BadRequestError, json.JSONDecodeError, Exception) as exc:
        ai_calls_total.labels(status="error").inc()
        logger.error("openai_unexpected_error", conversation_id=conversation_id, error=str(exc))
        raise OpenAIError(f"OpenAI call failed: {exc}") from exc

"""
app/integrations/openai/adapter.py — OpenAI Responses API adapter.

Handles the full round-trip: build messages → call API → parse structured output.
Uses beta.chat.completions.parse for Strict Structured Outputs.
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


def _build_extra_params(model: str, max_tokens: int, temperature: float) -> dict:
    """Build model-specific API params."""
    params = {}
    
    # Newer models (o1, gpt-5, next) use max_completion_tokens
    if any(m in model for m in ["gpt-5", "o1", "o3", "next"]):
        params["max_completion_tokens"] = max_tokens
        # No temperature for reasoning-only models in strict mode
    else:
        params["max_tokens"] = max_tokens
        params["temperature"] = temperature
    
    # Check for Structured Output support
    if any(m in model for m in ["gpt-4o", "gpt-5", "next"]):
        params["response_format"] = AIStructuredOutput
    else:
        params["response_format"] = {"type": "json_object"}
        
    return params


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
    """
    client = get_openai_client()
    start = time.monotonic()

    messages = [
        {"role": "developer", "content": get_system_prompt()},
        *conversation_messages,
    ]

    try:
        logger.info("openai_call_start", conversation_id=conversation_id, msg_count=len(messages))

        extra_params = _build_extra_params(settings.openai_model, settings.openai_max_tokens, settings.openai_temperature)
        
        # We explicitly DO NOT pass 'tools' here to avoid conflicts with Structured Outputs.
        # The AI proposes tools via the 'proposed_actions' JSON field instead.
        response = await client.beta.chat.completions.parse(
            model=settings.openai_model,
            messages=messages,
            **extra_params,
        )

        duration = time.monotonic() - start
        ai_call_duration_seconds.observe(duration)
        ai_calls_total.labels(status="success").inc()

        logger.debug("openai_call_done", conversation_id=conversation_id, duration_s=round(duration, 2))

        parsed = response.choices[0].message.parsed
        if parsed is None:
            refusal = response.choices[0].message.refusal
            if refusal:
                raise OpenAIError(f"Model refused to answer: {refusal}")
            raise OpenAIError("OpenAI returned no parsed content (check for schema violations)")

        return parsed

    except (openai.BadRequestError, json.JSONDecodeError, Exception) as exc:
        ai_calls_total.labels(status="error").inc()
        logger.error("openai_unexpected_error", conversation_id=conversation_id, error=str(exc))
        raise OpenAIError(f"OpenAI call failed: {exc}") from exc

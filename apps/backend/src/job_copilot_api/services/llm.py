"""Provider-agnostic LLM dispatch for structured outputs.

One entry: ``call_json(prompt, user_text) -> dict``.
Supported providers: openai (default) | anthropic.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

from ..config import settings

log = structlog.get_logger(__name__)

_LLM_TIMEOUT_SECONDS = 60


async def _call_openai(system_prompt: str, user_text: str) -> dict[str, Any]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.chat.completions.create(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    )
    return json.loads(resp.choices[0].message.content or "{}")


async def _call_anthropic(system_prompt: str, user_text: str, *, schema: dict | None = None) -> dict[str, Any]:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    kwargs: dict[str, Any] = dict(
        model=settings.llm_model,
        max_tokens=8192,
        temperature=settings.llm_temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_text}],
    )
    if schema is not None:
        tool = {"name": "emit", "description": "Emit structured JSON.", "input_schema": schema}
        kwargs["tools"] = [tool]
        kwargs["tool_choice"] = {"type": "tool", "name": "emit"}
        resp = await client.messages.create(**kwargs)
        for block in resp.content:
            if block.type == "tool_use":
                return block.input  # type: ignore[return-value]
        raise RuntimeError("Anthropic returned no tool_use block")
    resp = await client.messages.create(**kwargs)
    text = "".join(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


async def call_json(
    system_prompt: str,
    user_text: str,
    *,
    schema: dict | None = None,
    timeout: float = _LLM_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Call the configured provider and return a dict.

    Raises ``asyncio.TimeoutError`` if the provider does not respond within
    ``timeout`` seconds. ``schema`` is only used by the Anthropic tool-use path.
    """
    log.info("llm.call", provider=settings.llm_provider, model=settings.llm_model, chars=len(user_text))

    if settings.llm_provider == "anthropic":
        coro = _call_anthropic(system_prompt, user_text, schema=schema)
    else:
        coro = _call_openai(system_prompt, user_text)

    try:
        result = await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        log.warning("llm.timeout", provider=settings.llm_provider, timeout=timeout)
        raise

    return result

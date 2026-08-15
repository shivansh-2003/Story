import asyncio
import json
import logging
from collections.abc import AsyncIterator
from functools import lru_cache

import httpx
from openai import AsyncOpenAI

from app.config import get_settings

logger = logging.getLogger("story_assistant.llm")

RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = (1, 2)  # sleep before attempt 2, before attempt 3


@lru_cache
def _openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=get_settings().openai_api_key)


@lru_cache
def _ollama_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=120)


def _messages(user: str, system: str | None) -> list[dict[str, str]]:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    return messages


async def _call_ollama(user: str, max_tokens: int, system: str | None) -> str:
    settings = get_settings()
    # Ollama's OpenAI-compatible shim doesn't honor "think": false (verified
    # against 0.30.10 — reasoning models like qwen3.6 burn the whole token
    # budget on <think> and never reach content). Its native /api/chat does.
    response = await _ollama_client().post(
        f"{settings.ollama_base_url}/api/chat",
        json={
            "model": settings.ollama_model,
            "messages": _messages(user, system),
            "think": False,
            "stream": False,
            "options": {"num_predict": max_tokens},
        },
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


async def _call_openai(user: str, max_tokens: int, system: str | None) -> str:
    settings = get_settings()
    response = await _openai_client().chat.completions.create(
        model=settings.openai_model,
        messages=_messages(user, system),
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


async def call_model(user: str, max_tokens: int, system: str | None = None) -> str:
    """Non-streaming — used by the background summarizer, which has no client
    waiting on incremental output. Retries on failure: a summarization call
    that silently never lands leaves a permanent gap in story continuity —
    unlike live generation, which already surfaces failures visibly to the
    user via an SSE error frame and doesn't need this."""
    provider = get_settings().llm_provider
    last_error: Exception = RuntimeError("call_model: no attempts made")
    for attempt in range(RETRY_ATTEMPTS):
        if attempt:
            await asyncio.sleep(RETRY_BACKOFF_SECONDS[attempt - 1])
        try:
            if provider == "ollama":
                return await _call_ollama(user, max_tokens, system)
            return await _call_openai(user, max_tokens, system)
        except Exception as e:
            last_error = e
            logger.warning("call_model attempt %d/%d failed", attempt + 1, RETRY_ATTEMPTS, exc_info=True)
    raise last_error


async def _stream_ollama(user: str, max_tokens: int, system: str | None) -> AsyncIterator[str]:
    settings = get_settings()
    async with _ollama_client().stream(
        "POST",
        f"{settings.ollama_base_url}/api/chat",
        json={
            "model": settings.ollama_model,
            "messages": _messages(user, system),
            "think": False,
            "stream": True,
            "options": {"num_predict": max_tokens},
        },
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            content = chunk.get("message", {}).get("content")
            if content:
                yield content
            if chunk.get("done"):
                break


async def _stream_openai(user: str, max_tokens: int, system: str | None) -> AsyncIterator[str]:
    settings = get_settings()
    stream = await _openai_client().chat.completions.create(
        model=settings.openai_model,
        messages=_messages(user, system),
        max_tokens=max_tokens,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def stream_model(user: str, max_tokens: int, system: str | None = None) -> AsyncIterator[str]:
    if get_settings().llm_provider == "ollama":
        return _stream_ollama(user, max_tokens, system)
    return _stream_openai(user, max_tokens, system)

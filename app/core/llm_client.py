import asyncio
import json
import logging
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import TypeVar

import httpx
from openai import APIConnectionError, APIStatusError, AsyncOpenAI
from pydantic import BaseModel

from app.config import get_settings
from app.core.logging_utils import log_execution

logger = logging.getLogger("story_assistant.llm")

RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = (1, 2)  # sleep before attempt 2, before attempt 3
JsonModel = TypeVar("JsonModel", bound=BaseModel)
EMBEDDING_MODEL = "text-embedding-3-small"
MODEL_DEADLINE_SECONDS = 180


async def call_json_model(user: str, response_model: type[JsonModel], max_tokens: int, system: str) -> JsonModel:
    """Validate a bounded JSON proposal using the existing provider abstraction."""
    async with asyncio.timeout(150):
        raw = await call_model(user, max_tokens=max_tokens, system=system)
    if len(raw) > 60000:
        raise ValueError("Model response exceeds the proposal limit")
    raw = raw.strip()
    if raw.startswith("```json\n") and raw.endswith("```"):
        raw = raw[8:-3].strip()
    elif raw.startswith("```\n") and raw.endswith("```"):
        raw = raw[4:-3].strip()
    return response_model.model_validate_json(raw)


@lru_cache
def _openai_client() -> AsyncOpenAI:
    # Retries are owned here, rather than multiplied by SDK retries.
    return AsyncOpenAI(api_key=get_settings().openai_api_key, timeout=120, max_retries=0)


@lru_cache
def _ollama_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=120)


async def close_model_clients() -> None:
    closers = []
    if _openai_client.cache_info().currsize:
        closers.append(_openai_client().close())
        _openai_client.cache_clear()
    if _ollama_client.cache_info().currsize:
        closers.append(_ollama_client().aclose())
        _ollama_client.cache_clear()
    results = await asyncio.gather(*closers, return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            logger.warning("AI client cleanup failed (%s)", type(result).__name__)


def is_transient(error: Exception) -> bool:
    if isinstance(error, (APIConnectionError, httpx.TransportError)):
        return True
    if isinstance(error, APIStatusError):
        return error.status_code in (408, 429) or error.status_code >= 500
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in (408, 429) or error.response.status_code >= 500
    return False


async def embed_text(text: str) -> list[float]:
    async with asyncio.timeout(60):
        response = await _openai_client().embeddings.create(
            model=EMBEDDING_MODEL, input=text
        )
    return response.data[0].embedding


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


@log_execution
async def call_model(user: str, max_tokens: int, system: str | None = None) -> str:
    """Non-streaming — used by the background summarizer, which has no client
    waiting on incremental output. Retries on failure: a summarization call
    that silently never lands leaves a permanent gap in story continuity —
    unlike live generation, which already surfaces failures visibly to the
    user via an SSE error frame and doesn't need this."""
    async with asyncio.timeout(MODEL_DEADLINE_SECONDS):
        return await _call_with_retries(user, max_tokens, system)


async def _call_with_retries(user: str, max_tokens: int, system: str | None) -> str:
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
            if not is_transient(e):
                raise
            last_error = e
            logger.warning("call_model attempt %d/%d failed", attempt + 1, RETRY_ATTEMPTS, exc_info=True)
    raise last_error


@log_execution(label="LLM_STREAM")
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


@log_execution(label="LLM_STREAM")
async def _stream_openai(user: str, max_tokens: int, system: str | None) -> AsyncIterator[str]:
    settings = get_settings()
    stream = await _openai_client().chat.completions.create(
        model=settings.openai_model,
        messages=_messages(user, system),
        max_tokens=max_tokens,
        stream=True,
    )
    try:
        async for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
    finally:
        await stream.close()


# Provider generators own their timing; this wrapper owns the deadline and
# deterministic cleanup when a client disconnects or closes the stream.
async def stream_model(user: str, max_tokens: int, system: str | None = None) -> AsyncIterator[str]:
    stream = (_stream_ollama if get_settings().llm_provider == "ollama" else _stream_openai)(user, max_tokens, system)
    try:
        async with asyncio.timeout(MODEL_DEADLINE_SECONDS):
            async for delta in stream:
                yield delta
    finally:
        await stream.aclose()

from functools import lru_cache

import httpx
from openai import AsyncOpenAI

from app.config import get_settings


@lru_cache
def _openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=get_settings().openai_api_key)


async def _call_ollama(prompt: str, max_tokens: int) -> str:
    settings = get_settings()
    # Ollama's OpenAI-compatible shim doesn't honor "think": false (verified
    # against 0.30.10 — reasoning models like qwen3.6 burn the whole token
    # budget on <think> and never reach content). Its native /api/chat does.
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [{"role": "user", "content": prompt}],
                "think": False,
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
        )
        response.raise_for_status()
        return response.json()["message"]["content"]


async def _call_openai(prompt: str, max_tokens: int) -> str:
    settings = get_settings()
    response = await _openai_client().chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


async def call_model(prompt: str, max_tokens: int) -> str:
    if get_settings().llm_provider == "ollama":
        return await _call_ollama(prompt, max_tokens)
    return await _call_openai(prompt, max_tokens)

"""
Gemini service — fallback LLM via Google Generative AI REST API.

Design choices
──────────────
• Uses the REST streaming endpoint so no extra SDK is needed (only httpx).
• API key is read from settings only; never logged or returned to callers.
• Converts the internal OpenAI-style message list to Gemini's "contents" format.
• Raises on HTTP or JSON errors (caller handles final error response).
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_GEMINI_STREAM_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:streamGenerateContent?alt=sse&key={key}"
)

# Shared async client for Gemini (no base_url because the path is fixed above)
_gemini_client: httpx.AsyncClient | None = None


def _get_gemini_client() -> httpx.AsyncClient:
    global _gemini_client
    if _gemini_client is None or _gemini_client.is_closed:
        _gemini_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=5.0),
        )
    return _gemini_client


async def close_client() -> None:
    global _gemini_client
    if _gemini_client and not _gemini_client.is_closed:
        await _gemini_client.aclose()
        _gemini_client = None


def _to_gemini_contents(messages: list[dict]) -> list[dict]:
    """Convert OpenAI-style messages to Gemini 'contents' format."""
    contents = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    return contents


# ── Public API ────────────────────────────────────────────────────────────────


def is_configured() -> bool:
    """Return True if a Gemini API key has been provided."""
    return bool(settings.gemini_api_key)


async def stream_chat(
    messages: list[dict],
) -> AsyncIterator[str]:
    """
    Stream response tokens from Gemini.

    Yields raw text fragments.
    Raises on HTTP errors or missing API key.
    """
    if not settings.gemini_api_key:
        raise RuntimeError("Gemini API key is not configured.")

    url = _GEMINI_STREAM_URL.format(
        model=settings.gemini_model,
        key=settings.gemini_api_key,
    )

    payload = {
        "contents": _to_gemini_contents(messages),
        "generationConfig": {
            "maxOutputTokens": 2048,
            "temperature": 0.7,
        },
    }

    client = _get_gemini_client()
    async with client.stream(
        "POST",
        url,
        json=payload,
        headers={"Content-Type": "application/json"},
    ) as response:
        response.raise_for_status()
        async for raw_line in response.aiter_lines():
            # SSE lines start with "data: "
            if not raw_line.startswith("data:"):
                continue
            json_str = raw_line[len("data:"):].strip()
            if not json_str or json_str == "[DONE]":
                continue
            try:
                chunk = json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning("Gemini: unparse-able SSE line: %r", raw_line)
                continue

            # Extract text from nested structure
            try:
                text = chunk["candidates"][0]["content"]["parts"][0]["text"]
                if text:
                    yield text
            except (KeyError, IndexError):
                pass

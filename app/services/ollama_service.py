"""
Ollama service — streams tokens from the local Ollama server.

Design choices
──────────────
• A single shared HTTPX AsyncClient is created once (connection re-use).
• Health-check uses a lightweight /api/tags request with a short timeout.
• Streaming uses /api/chat with Ollama's native SSE-like NDJSON protocol.
• keep_alive is forwarded so the model stays loaded between requests.
• No retries — the router_service handles fallback.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Shared async client (created once, reused for every request) ───────────────
_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=httpx.Timeout(connect=5.0, read=120.0, write=30.0, pool=5.0),
        )
    return _client


async def close_client() -> None:
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


# ── Public API ────────────────────────────────────────────────────────────────


async def is_available() -> bool:
    """Return True if the local Ollama server responds within timeout."""
    try:
        client = get_client()
        resp = await client.get(
            "/api/tags",
            timeout=settings.ollama_timeout,
        )
        return resp.status_code == 200
    except Exception as exc:
        logger.debug("Ollama health-check failed: %s", exc)
        return False


async def stream_chat(
    messages: list[dict],
) -> AsyncIterator[str]:
    """
    Stream response tokens from Ollama.

    Yields raw text fragments as produced by the model.
    Raises on connection / protocol errors (caller handles fallback).
    """
    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": True,
        "keep_alive": settings.ollama_keep_alive,
        "options": {
            "num_predict": 2048,
        },
    }

    client = get_client()
    async with client.stream(
        "POST",
        "/api/chat",
        json=payload,
        timeout=httpx.Timeout(connect=5.0, read=120.0, write=30.0, pool=5.0),
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Ollama: unparse-able line: %r", line)
                continue

            # Ollama streams {"message": {"content": "..."}, "done": false}
            content: str = data.get("message", {}).get("content", "")
            if content:
                yield content

            if data.get("done"):
                break

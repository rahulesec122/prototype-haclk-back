"""
Router service — provider selection and streaming orchestration.

Priority
────────
1. Ollama/Qwen  → tried first, always
2. Gemini       → only when Ollama is unavailable or raises
3. Both fail    → raises AllProvidersUnavailableError

Latency telemetry is collected here and returned to the caller.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncIterator

from app.services import gemini_service, ollama_service

logger = logging.getLogger(__name__)


class AllProvidersUnavailableError(Exception):
    """Raised when every configured provider fails."""


def _ts() -> float:
    """High-resolution monotonic timestamp (seconds)."""
    return time.monotonic()


async def stream_response(
    messages: list[dict],
) -> AsyncIterator[tuple[str, str, dict]]:
    """
    Determine the best available provider and stream its response.

    Yields
    ──────
    (token: str, provider: str, latency: dict)

    • ``token``    — raw text fragment from the model
    • ``provider`` — "ollama" | "gemini"  (same value on every yield)
    • ``latency``  — populated dict only on the *last* yield (after completion)
                     empty dict ``{}`` on intermediate token yields

    Raises
    ──────
    AllProvidersUnavailableError — when every provider fails.
    """
    telemetry: dict[str, float] = {"request_received": _ts()}

    # ── 1. Select provider ────────────────────────────────────────────────────
    ollama_ok = await ollama_service.is_available()
    provider: str

    if ollama_ok:
        provider = "ollama"
        logger.info("Provider selected: ollama")
    elif ollama_service.get_client() and gemini_service.is_configured():
        provider = "gemini"
        logger.info("Ollama unavailable — falling back to gemini")
    elif gemini_service.is_configured():
        provider = "gemini"
        logger.info("Ollama unavailable — falling back to gemini")
    else:
        raise AllProvidersUnavailableError(
            "Ollama is not reachable and Gemini API key is not configured."
        )

    telemetry["provider_selected"] = _ts()

    # ── 2. Stream from chosen provider ────────────────────────────────────────
    first_token_recorded = False

    async def _stream_provider(prov: str) -> AsyncIterator[str]:
        if prov == "ollama":
            async for tok in ollama_service.stream_chat(messages):
                yield tok
        else:
            async for tok in gemini_service.stream_chat(messages):
                yield tok

    telemetry["llm_started"] = _ts()

    try:
        async for token in _stream_provider(provider):
            if not first_token_recorded:
                telemetry["first_token"] = _ts()
                first_token_recorded = True
            yield token, provider, {}

    except Exception as primary_exc:
        logger.warning(
            "Provider '%s' failed mid-stream (%s); attempting fallback.",
            provider,
            primary_exc,
        )

        # ── 3. Fallback to Gemini if Ollama failed ─────────────────────────
        if provider == "ollama" and gemini_service.is_configured():
            provider = "gemini"
            telemetry["llm_started"] = _ts()
            try:
                async for token in gemini_service.stream_chat(messages):
                    if not first_token_recorded:
                        telemetry["first_token"] = _ts()
                        first_token_recorded = True
                    yield token, provider, {}
            except Exception as fallback_exc:
                logger.error("Gemini fallback also failed: %s", fallback_exc)
                raise AllProvidersUnavailableError(
                    "Both Ollama and Gemini failed."
                ) from fallback_exc
        else:
            raise AllProvidersUnavailableError(
                "Ollama failed and Gemini is not configured."
            ) from primary_exc

    # ── 4. Emit final latency chunk ───────────────────────────────────────────
    telemetry["stream_completed"] = _ts()
    ref = telemetry.get("request_received", telemetry["stream_completed"])
    telemetry["total_time"] = round(telemetry["stream_completed"] - ref, 4)

    # Convert to relative offsets (ms) for readability
    latency_out = {
        k: round((v - ref) * 1000, 2)
        for k, v in telemetry.items()
        if k != "request_received" and k != "total_time"
    }
    latency_out["total_time_ms"] = round(telemetry["total_time"] * 1000, 2)

    _log_telemetry(telemetry, ref)

    # Yield a sentinel with the final latency dict
    yield "", provider, latency_out


def _log_telemetry(t: dict[str, float], ref: float) -> None:
    def ms(key: str) -> str:
        val = t.get(key)
        if val is None:
            return "n/a"
        return f"{(val - ref) * 1000:.1f} ms"

    logger.info(
        "Latency → provider_selected=%s  llm_started=%s  "
        "first_token=%s  stream_completed=%s  total=%s",
        ms("provider_selected"),
        ms("llm_started"),
        ms("first_token"),
        ms("stream_completed"),
        ms("stream_completed"),
    )

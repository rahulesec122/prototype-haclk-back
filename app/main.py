"""
FastAPI application entry-point.

Startup:
  • Initialises the SQLite database (creates tables if missing).
  • Warms the Ollama HTTP client pool.

Shutdown:
  • Gracefully closes all shared HTTPX clients.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.config import get_settings
from app.database.database import init_db
from app.schemas.chat import HealthResponse
from app.services import gemini_service, ollama_service

settings = get_settings()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    stream=sys.stdout,
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting %s v%s", settings.app_title, settings.app_version)

    # Initialise DB tables
    await init_db()
    logger.info("Database ready at %s", settings.database_url)

    # Warm Ollama client pool (non-blocking — failure is fine at startup)
    available = await ollama_service.is_available()
    logger.info(
        "Ollama (%s / %s): %s",
        settings.ollama_base_url,
        settings.ollama_model,
        "✓ available" if available else "✗ unavailable",
    )

    if settings.gemini_api_key:
        logger.info("Gemini API key: configured ✓")
    else:
        logger.warning("Gemini API key: NOT configured (fallback disabled)")

    yield  # ── application runs ──────────────────────────────────────────────

    logger.info("Shutting down — closing HTTP clients …")
    await ollama_service.close_client()
    await gemini_service.close_client()
    logger.info("Shutdown complete.")


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description="Offline-first AI assistant backend — Ollama primary, Gemini fallback.",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Provider-Used", "X-Conversation-Id"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(chat_router)


# ── Health endpoint ───────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    """
    GET /health

    Quickly checks whether Ollama responds and whether Gemini is configured.
    Does NOT make a live call to Gemini (that would cost tokens / require internet).
    """
    ollama_ok = await ollama_service.is_available()
    gemini_ok = gemini_service.is_configured()

    logger.debug("Health check — ollama=%s gemini=%s", ollama_ok, gemini_ok)

    return HealthResponse(
        status="healthy",
        ollama=ollama_ok,
        gemini=gemini_ok,
    )

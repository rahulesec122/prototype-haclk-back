"""
Chat API router — /api/chat and /api/conversations endpoints.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.database import AsyncSessionLocal, get_db
from app.database.models import Conversation
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationOut,
)
from app.services import memory_service, router_service
from app.services.router_service import AllProvidersUnavailableError

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger(__name__)


# ── Streaming generator ───────────────────────────────────────────────────────


async def _chat_stream(
    request: ChatRequest,
    conversation_id: str,
    history: list[dict],
    db: AsyncSession,
) -> AsyncIterator[str]:
    """
    Async generator that yields SSE-formatted strings.

    Token chunks:    data: {"type":"token","content":"..."}
    Complete chunk:  data: {"type":"complete","provider":"...","conversation_id":"...","latency":{...}}
    Error chunk:     data: {"type":"error","message":"..."}
    """
    messages = history + [{"role": "user", "content": request.message}]
    full_response: list[str] = []
    provider_used: str = "unknown"

    try:
        async for token, provider, latency in router_service.stream_response(messages):
            provider_used = provider

            if token:
                full_response.append(token)
                chunk = json.dumps({"type": "token", "content": token})
                yield f"data: {chunk}\n\n"

            elif latency:
                # Final sentinel — save assistant message asynchronously
                # Use a NEW session so it's independent of the request scope.
                assistant_content = "".join(full_response)

                async def _bg_save(
                    cid: str = conversation_id,
                    content: str = assistant_content,
                    prov: str = provider_used,
                ) -> None:
                    async with AsyncSessionLocal() as bg_db:
                        await memory_service.save_assistant_message(
                            bg_db, cid, content, prov
                        )

                asyncio.create_task(_bg_save())

                complete = json.dumps(
                    {
                        "type": "complete",
                        "provider": provider_used,
                        "conversation_id": conversation_id,
                        "latency": latency,
                    }
                )
                yield f"data: {complete}\n\n"

    except AllProvidersUnavailableError as exc:
        logger.error("All providers unavailable: %s", exc)
        error = json.dumps(
            {
                "type": "error",
                "message": "All AI providers are currently unavailable.",
            }
        )
        yield f"data: {error}\n\n"
    except Exception as exc:
        logger.exception("Unexpected error during streaming: %s", exc)
        error = json.dumps(
            {
                "type": "error",
                "message": "An unexpected error occurred. Please try again.",
            }
        )
        yield f"data: {error}\n\n"


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/chat", response_model=None)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    POST /api/chat

    Accepts a user message and optional conversation_id.
    When stream=true (default) returns Server-Sent Events.
    When stream=false returns a single JSON response.
    """
    # 1. Resolve conversation (eager DB op before streaming)
    conversation_id = await memory_service.get_or_create_conversation(
        db, request.conversation_id
    )

    # 2. Load history (needed to build the prompt — must be before streaming)
    history = await memory_service.load_history(db, conversation_id)

    # 3. Persist user message immediately
    await memory_service.save_user_message(db, conversation_id, request.message)

    if request.stream:
        # Determine provider for the response header (quick check)
        from app.services import ollama_service, gemini_service

        ollama_ok = await ollama_service.is_available()
        provider_header = (
            "ollama"
            if ollama_ok
            else ("gemini" if gemini_service.is_configured() else "none")
        )

        return StreamingResponse(
            _chat_stream(request, conversation_id, history, db),
            media_type="text/event-stream",
            headers={
                "X-Provider-Used": provider_header,
                "X-Conversation-Id": conversation_id,
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    # ── Non-streaming path ────────────────────────────────────────────────────
    messages = history + [{"role": "user", "content": request.message}]
    full_response: list[str] = []
    provider_used = "unknown"
    latency_out: dict = {}

    try:
        async for token, provider, latency in router_service.stream_response(messages):
            provider_used = provider
            if token:
                full_response.append(token)
            if latency:
                latency_out = latency
    except AllProvidersUnavailableError:
        raise HTTPException(
            status_code=503,
            detail="All AI providers are currently unavailable.",
        )

    assistant_content = "".join(full_response)
    await memory_service.save_assistant_message(
        db, conversation_id, assistant_content, provider_used
    )

    return ChatResponse(
        conversation_id=conversation_id,
        message=assistant_content,
        provider=provider_used,
        latency=latency_out,
    )


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
) -> list[ConversationOut]:
    """GET /api/conversations — list all stored conversations."""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    )
    convs = result.scalars().all()
    return [ConversationOut.model_validate(c) for c in convs]


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
) -> ConversationOut:
    """GET /api/conversations/{id} — retrieve a conversation with its messages."""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return ConversationOut.model_validate(conv)

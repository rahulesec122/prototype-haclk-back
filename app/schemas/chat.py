"""
Pydantic schemas for the /api/chat endpoint.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Request ───────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User prompt text.")
    conversation_id: Optional[str] = Field(
        default=None,
        description="Existing conversation UUID; omit to start a new one.",
    )
    stream: bool = Field(
        default=True,
        description="Stream tokens as SSE (Server-Sent Events).",
    )


# ── Streaming chunks ──────────────────────────────────────────────────────────


class TokenChunk(BaseModel):
    type: Literal["token"] = "token"
    content: str


class CompleteChunk(BaseModel):
    type: Literal["complete"] = "complete"
    provider: str
    conversation_id: str
    latency: dict


class ErrorChunk(BaseModel):
    type: Literal["error"] = "error"
    message: str


# ── Non-streaming response ────────────────────────────────────────────────────


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    provider: str
    latency: dict


# ── Health ────────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    ollama: bool
    gemini: bool


# ── Message / Conversation history ───────────────────────────────────────────


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    provider: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut] = []

    model_config = {"from_attributes": True}

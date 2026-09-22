"""
Memory service — loads and saves conversation history to SQLite.

Design choices
──────────────
• History is loaded BEFORE streaming starts (needed to build the prompt).
• The user message is saved to DB before streaming so it always persists.
• The assistant message is saved AFTER streaming completes — saving is
  fire-and-forget (asyncio.create_task) so it never blocks the response.
• Conversation rows are created on demand (upsert pattern).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Conversation, Message

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def get_or_create_conversation(
    db: AsyncSession,
    conversation_id: str | None,
) -> str:
    """Return an existing conversation ID or create a new one."""
    if conversation_id:
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if conv:
            return conv.id
        logger.warning("Conversation %s not found; creating new.", conversation_id)

    new_id = str(uuid.uuid4())
    conv = Conversation(id=new_id)
    db.add(conv)
    await db.commit()
    logger.debug("Created conversation %s", new_id)
    return new_id


async def load_history(
    db: AsyncSession,
    conversation_id: str,
    max_messages: int = 20,
) -> list[dict]:
    """
    Return the last *max_messages* messages as OpenAI-style dicts
    [{"role": "user"|"assistant", "content": "..."}].
    """
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(max_messages)
    )
    rows: list[Message] = list(reversed(result.scalars().all()))
    return [{"role": m.role, "content": m.content} for m in rows]


async def save_user_message(
    db: AsyncSession,
    conversation_id: str,
    content: str,
) -> None:
    """Persist the user's message immediately (before streaming starts)."""
    msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="user",
        content=content,
        provider="",
    )
    db.add(msg)
    # Touch updated_at on the conversation
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(updated_at=_utcnow())
    )
    await db.commit()
    logger.debug("Saved user message for conversation %s", conversation_id)


async def save_assistant_message(
    db: AsyncSession,
    conversation_id: str,
    content: str,
    provider: str,
) -> None:
    """Persist the completed assistant response (called after streaming)."""
    msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="assistant",
        content=content,
        provider=provider,
    )
    db.add(msg)
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(updated_at=_utcnow())
    )
    await db.commit()
    logger.debug(
        "Saved assistant message for conversation %s (provider=%s)",
        conversation_id,
        provider,
    )

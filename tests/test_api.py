"""
Test suite for the offline-first AI assistant backend.

Run with:
    pytest tests/ -v

All tests are async-compatible via pytest-asyncio.
External services (Ollama, Gemini) are mocked with unittest.mock.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.database import init_db, engine, Base


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="session")
async def setup_db():
    """Create in-memory tables once per test session."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(setup_db) -> AsyncIterator[AsyncClient]:
    """HTTPX async test client backed by the FastAPI ASGI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ── Helpers ───────────────────────────────────────────────────────────────────


async def fake_ollama_stream(messages):
    """Simulate Ollama yielding a few tokens."""
    for token in ["Hello", " ", "world", "!"]:
        yield token


async def fake_gemini_stream(messages):
    """Simulate Gemini yielding a few tokens."""
    for token in ["Gemini", " ", "fallback", "."]:
        yield token


# ── Test 1: Ollama available → Ollama is selected ────────────────────────────


@pytest.mark.asyncio
async def test_ollama_selected_when_available(client: AsyncClient):
    """When Ollama is available it should be used and never Gemini."""
    with (
        patch(
            "app.services.ollama_service.is_available", new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.services.ollama_service.stream_chat",
            side_effect=fake_ollama_stream,
        ),
    ):
        resp = await client.post(
            "/api/chat",
            json={"message": "Hello", "stream": False},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "ollama"
    assert "Hello" in body["message"] or "world" in body["message"]


# ── Test 2: Ollama unavailable → Gemini fallback ─────────────────────────────


@pytest.mark.asyncio
async def test_gemini_fallback_when_ollama_unavailable(client: AsyncClient):
    """When Ollama is down, the response should come from Gemini."""
    with (
        patch(
            "app.services.ollama_service.is_available", new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "app.services.gemini_service.is_configured",
            return_value=True,
        ),
        patch(
            "app.services.gemini_service.stream_chat",
            side_effect=fake_gemini_stream,
        ),
    ):
        resp = await client.post(
            "/api/chat",
            json={"message": "Hello", "stream": False},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "gemini"


# ── Test 3: Both unavailable → proper error ───────────────────────────────────


@pytest.mark.asyncio
async def test_error_when_both_providers_unavailable(client: AsyncClient):
    """When both providers fail the API returns HTTP 503."""
    with (
        patch(
            "app.services.ollama_service.is_available", new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "app.services.gemini_service.is_configured",
            return_value=False,
        ),
    ):
        resp = await client.post(
            "/api/chat",
            json={"message": "Hello", "stream": False},
        )

    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower()


# ── Test 4: Streaming response works ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_streaming_response(client: AsyncClient):
    """Streaming endpoint should yield SSE data lines with token chunks."""
    with (
        patch(
            "app.services.ollama_service.is_available", new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.services.ollama_service.stream_chat",
            side_effect=fake_ollama_stream,
        ),
    ):
        resp = await client.post(
            "/api/chat",
            json={"message": "Stream test", "stream": True},
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")

    lines = [l for l in resp.text.split("\n") if l.startswith("data:")]
    assert len(lines) >= 1

    # At least one token chunk
    token_chunks = []
    complete_chunks = []
    for line in lines:
        data = json.loads(line[len("data:"):].strip())
        if data["type"] == "token":
            token_chunks.append(data)
        elif data["type"] == "complete":
            complete_chunks.append(data)

    assert len(token_chunks) > 0, "Expected at least one token chunk"
    assert len(complete_chunks) == 1, "Expected exactly one complete chunk"
    assert complete_chunks[0]["provider"] == "ollama"


# ── Test 5: Conversation messages are stored ─────────────────────────────────


@pytest.mark.asyncio
async def test_conversation_messages_stored(client: AsyncClient):
    """After a chat, the conversation and messages should exist in the DB."""
    with (
        patch(
            "app.services.ollama_service.is_available", new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.services.ollama_service.stream_chat",
            side_effect=fake_ollama_stream,
        ),
    ):
        chat_resp = await client.post(
            "/api/chat",
            json={"message": "Remember this!", "stream": False},
        )

    assert chat_resp.status_code == 200
    conv_id = chat_resp.json()["conversation_id"]
    assert conv_id

    # Fetch the conversation via API
    conv_resp = await client.get(f"/api/conversations/{conv_id}")
    assert conv_resp.status_code == 200
    conv = conv_resp.json()

    roles = [m["role"] for m in conv["messages"]]
    assert "user" in roles
    assert "assistant" in roles

    user_msg = next(m for m in conv["messages"] if m["role"] == "user")
    assert user_msg["content"] == "Remember this!"


# ── Test 6: /health works ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    """GET /health should return 200 with status/ollama/gemini fields."""
    with (
        patch(
            "app.services.ollama_service.is_available", new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.services.gemini_service.is_configured",
            return_value=False,
        ),
    ):
        resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["ollama"] is True
    assert body["gemini"] is False


# ── Test 7: Continuing an existing conversation ───────────────────────────────


@pytest.mark.asyncio
async def test_continue_conversation(client: AsyncClient):
    """Sending a second message with the same conversation_id should append."""
    with (
        patch(
            "app.services.ollama_service.is_available", new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.services.ollama_service.stream_chat",
            side_effect=fake_ollama_stream,
        ),
    ):
        first = await client.post(
            "/api/chat",
            json={"message": "First message", "stream": False},
        )
        conv_id = first.json()["conversation_id"]

        second = await client.post(
            "/api/chat",
            json={"message": "Second message", "conversation_id": conv_id, "stream": False},
        )

    assert second.status_code == 200
    assert second.json()["conversation_id"] == conv_id

    conv_resp = await client.get(f"/api/conversations/{conv_id}")
    messages = conv_resp.json()["messages"]
    contents = [m["content"] for m in messages]
    assert "First message" in contents
    assert "Second message" in contents

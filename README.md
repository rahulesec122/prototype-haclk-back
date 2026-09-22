# Offline-First AI Assistant — Backend Prototype

A FastAPI backend that routes prompts to **Ollama/Qwen3** locally first, falls back
to **Gemini API** when offline, streams tokens as SSE, and persists conversation
history in SQLite.

---

## Architecture

```
backend/
├── app/
│   ├── main.py                  ← FastAPI app, lifespan, CORS, /health
│   ├── config.py                ← Pydantic Settings (reads .env)
│   ├── api/
│   │   └── chat.py              ← POST /api/chat, GET /api/conversations
│   ├── services/
│   │   ├── ollama_service.py    ← Ollama HTTPX streaming client
│   │   ├── gemini_service.py    ← Gemini REST streaming client
│   │   ├── router_service.py    ← Provider routing + latency telemetry
│   │   └── memory_service.py    ← SQLite conversation CRUD
│   ├── database/
│   │   ├── database.py          ← Async SQLAlchemy engine + session factory
│   │   └── models.py            ← Conversation + Message ORM models
│   └── schemas/
│       └── chat.py              ← Pydantic request/response schemas
├── tests/
│   └── test_api.py              ← 7 pytest tests (all mocked)
├── .env.example
├── requirements.txt
├── pytest.ini
└── README.md
```

---

## Provider Routing

```
Request
  │
  ▼
Ollama available?  ──Yes──► Stream from Ollama ──► Respond
  │
  No
  │
  ▼
Gemini configured? ──Yes──► Stream from Gemini ──► Respond
  │
  No
  │
  ▼
HTTP 503 / SSE error chunk
```

> **Important:** Gemini is **never** called when Ollama is working. The health
> check is a cheap `GET /api/tags` with a 5-second timeout.

---

## Setup

### 1. Create a virtual environment

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Install & start Ollama

Download from <https://ollama.com/download> and start the server:

```bash
ollama serve
```

### 4. Pull Qwen3 8B

```bash
ollama pull qwen3:8b
```

> The model is ~5 GB. Pull once; it stays cached locally.

### 5. Configure `.env`

```bash
cp .env.example .env
```

Edit `.env` and set your Gemini API key (optional — leave blank for offline-only):

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
OLLAMA_KEEP_ALIVE=30m
GEMINI_API_KEY=your_google_gemini_api_key_here
DATABASE_URL=sqlite+aiosqlite:///./assistant.db
LOG_LEVEL=INFO
```

Get a free Gemini API key at <https://aistudio.google.com/app/apikey>.

### 6. Start the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The server will print startup diagnostics:

```
2026-09-22T17:00:00  INFO     app.main — Starting Offline-First AI Assistant v0.1.0
2026-09-22T17:00:00  INFO     app.main — Database ready at sqlite+aiosqlite:///./assistant.db
2026-09-22T17:00:00  INFO     app.main — Ollama (http://localhost:11434 / qwen3:8b): ✓ available
2026-09-22T17:00:00  INFO     app.main — Gemini API key: configured ✓
```

---

## API Reference

### `GET /health`

```bash
curl http://localhost:8000/health
```

**Response:**

```json
{
  "status": "healthy",
  "ollama": true,
  "gemini": true
}
```

---

### `POST /api/chat` — streaming (default)

```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Explain Python in simple words", "stream": true}'
```

**Streamed SSE output:**

```
data: {"type":"token","content":"Python"}
data: {"type":"token","content":" is"}
data: {"type":"token","content":" a"}
...
data: {"type":"complete","provider":"ollama","conversation_id":"abc-123","latency":{"provider_selected_ms":3.2,"llm_started_ms":4.1,"first_token_ms":312.5,"stream_completed_ms":4201.0,"total_time_ms":4201.0}}
```

**Response headers:**

```
X-Provider-Used: ollama
X-Conversation-Id: abc-123
Content-Type: text/event-stream
```

---

### `POST /api/chat` — non-streaming

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is 2+2?", "stream": false}'
```

**Response:**

```json
{
  "conversation_id": "abc-123",
  "message": "2 + 2 equals 4.",
  "provider": "ollama",
  "latency": {
    "provider_selected_ms": 3.1,
    "llm_started_ms": 4.0,
    "first_token_ms": 289.0,
    "stream_completed_ms": 1420.0,
    "total_time_ms": 1420.0
  }
}
```

---

### `POST /api/chat` — continue a conversation

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Give me a code example", "conversation_id": "abc-123", "stream": false}'
```

---

### `GET /api/conversations`

```bash
curl http://localhost:8000/api/conversations
```

---

### `GET /api/conversations/{id}`

```bash
curl http://localhost:8000/api/conversations/abc-123
```

---

## Gemini Fallback Example

Stop Ollama (`ollama stop`) or set `OLLAMA_BASE_URL=http://localhost:9999` in `.env`.
The same chat request will automatically use Gemini:

```
data: {"type":"token","content":"Python"}
...
data: {"type":"complete","provider":"gemini","conversation_id":"xyz-456","latency":{...}}
```

Response header: `X-Provider-Used: gemini`

---

## Both Providers Fail

```bash
# With Ollama stopped and GEMINI_API_KEY blank:
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "stream": false}'
```

**Response (HTTP 503):**

```json
{"detail": "All AI providers are currently unavailable."}
```

Streaming response (HTTP 200 with error chunk):

```
data: {"type":"error","message":"All AI providers are currently unavailable."}
```

---

## Latency Telemetry Example

Server log output for a typical Ollama request:

```
2026-09-22T17:01:23  INFO  app.services.router_service —
  Latency → provider_selected=3.2 ms  llm_started=4.1 ms
            first_token=312.5 ms  stream_completed=4201.0 ms  total=4201.0 ms
```

Fields in the `latency` JSON (all relative to `request_received`, in ms):

| Field | Description |
|---|---|
| `provider_selected_ms` | Time to decide which provider to use |
| `llm_started_ms` | Time to open the streaming connection |
| `first_token_ms` | Time-to-first-token (TTFT) |
| `stream_completed_ms` | Total streaming duration |
| `total_time_ms` | End-to-end wall-clock time |

---

## Running Tests

```bash
pytest tests/ -v
```

Expected output:

```
tests/test_api.py::test_ollama_selected_when_available           PASSED
tests/test_api.py::test_gemini_fallback_when_ollama_unavailable  PASSED
tests/test_api.py::test_error_when_both_providers_unavailable    PASSED
tests/test_api.py::test_streaming_response                       PASSED
tests/test_api.py::test_conversation_messages_stored             PASSED
tests/test_api.py::test_health_endpoint                          PASSED
tests/test_api.py::test_continue_conversation                    PASSED

7 passed in X.XXs
```

---

## Interactive API Docs

With the server running:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen3:8b` | Model tag |
| `OLLAMA_KEEP_ALIVE` | `30m` | Model memory retention |
| `OLLAMA_TIMEOUT` | `5.0` | Health-check timeout (s) |
| `GEMINI_API_KEY` | *(blank)* | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model name |
| `DATABASE_URL` | `sqlite+aiosqlite:///./assistant.db` | SQLAlchemy async URL |
| `CORS_ORIGINS` | localhost:3000/5173/8000 | JSON list of allowed origins |
| `LOG_LEVEL` | `INFO` | Python log level |

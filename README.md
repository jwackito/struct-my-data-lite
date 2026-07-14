# Struct My Data

Extract structured data (JSON) from documents using LLMs. Upload a file (PDF, DOCX, TXT, CSV), define a Pydantic schema, and get structured output powered by [Instructor](https://github.com/jxnl/instructor).

## Quick Start

```bash
docker compose up -d --build
docker compose exec app python -m alembic upgrade head
```

```bash
# Health check
curl http://localhost:8080/health

# Upload a document
curl -X POST http://localhost:8080/upload -F "file=@document.pdf"

# Extract with a Pydantic schema
curl -X POST http://localhost:8080/extract \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "<uploaded-doc-id>",
    "pydantic_schema": "from pydantic import BaseModel\n\nclass Invoice(BaseModel):\n    total: float\n    vendor: str\n    date: str"
  }'

# Poll for result
curl http://localhost:8080/jobs/<job-id>

# Or connect via WebSocket for real-time updates
ws ws://localhost:8080/ws/jobs/<job-id>
```

## Architecture

```
POST /upload  →  Document stored (local fs + DB)
POST /extract →  ExtractionJob created → BackgroundTask:
                   1. Parse document (PDF/DOCX/TXT/CSV)
                   2. Send text + schema to LLM
                   3. Store structured result
GET  /jobs/{id}   →  Poll job status
WS   /ws/jobs/{id} →  Real-time status push
```

## Stack

| Component | Choice |
|---|---|
| Backend | Python 3.12, FastAPI |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| LLM | Ollama (`qwen3.6:35b`), OpenAI scaffolded |
| Extraction | Instructor |
| Realtime | WebSocket |
| Testing | pytest, pytest-asyncio, httpx |
| Containers | Docker Compose |

## Development

```bash
# Start services
docker compose up -d

# Run migrations
docker compose exec app python -m alembic upgrade head

# Run tests
docker compose exec app python -m pytest

# Restart after code changes (no rebuild needed)
docker compose restart app

# Rebuild when requirements.txt changes
docker compose up -d --build
```

Requires an Ollama instance running on the host at `host.docker.internal:11434`.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/upload` | Upload a document (10 MB max) |
| POST | `/extract` | Create an extraction job |
| GET | `/jobs/{id}` | Poll job status and result |
| WS | `/ws/jobs/{id}` | Real-time job status updates |

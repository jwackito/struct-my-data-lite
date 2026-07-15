# Struct My Data

Extract structured data (JSON/YAML) from documents using LLMs. Upload a file (PDF, DOCX, TXT, CSV), define a Pydantic schema, and get structured output powered by [Instructor](https://github.com/jxnl/instructor).

## Quick Start

```bash
docker compose up -d --build
docker compose exec app python -m alembic upgrade head
```

Open **http://localhost:8080** in your browser:
1. Upload a document (PDF, DOCX, TXT, or CSV)
2. Paste or write a Pydantic schema
3. Click **Extract** — result renders as a table via HTMX polling

Or use the API directly:

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
── API ──────────────────────────────────────────
POST /upload        →  Document stored (local fs + DB)
POST /extract       →  ExtractionJob created → BackgroundTask:
                           1. Parse document (PDF/DOCX/TXT/CSV)
                           2. Send text + schema to LLM (thread pool)
                           3. Store structured result
GET  /jobs/{id}     →  Poll job status
WS   /ws/jobs/{id}  →  Real-time status push

── Web UI (HTMX) ─────────────────────────────────
GET  /              →  Static HTML page with upload form
POST /ui/extract    →  Upload + job creation in one call
GET  /ui/jobs/{id}  →  HTML fragment (spinner / table / error)
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
| Frontend | Static HTML + HTMX (no build step) |
| Testing | pytest, pytest-asyncio, httpx |
| Containers | Docker Compose |

## API

| Method | Path | Description |
|---|---|---|
| GET | `/` | Web UI — upload form and schema editor |
| GET | `/health` | Health check |
| POST | `/upload` | Upload a document (10 MB max) |
| POST | `/extract` | Create an extraction job (JSON body) |
| GET | `/jobs/{id}` | Poll job status and result (JSON) |
| POST | `/ui/extract` | Upload + job creation (multipart form, returns HTML) |
| GET | `/ui/jobs/{id}` | Job status as HTML fragment (for HTMX polling) |
| WS | `/ws/jobs/{id}` | Real-time job status updates |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/structmydata` | Async PostgreSQL connection string |
| `OLLAMA_HOST` | `http://host.docker.internal:11434` | Ollama server base URL |
| `OLLAMA_MODEL` | `qwen3.6:35b` | Model name for extraction |
| `OLLAMA_TIMEOUT` | `120` | HTTP timeout in seconds for Ollama calls |
| `MAX_UPLOAD_SIZE` | `10485760` (10 MB) | Max file upload size in bytes |
| `PORT` | `8000` | App HTTP server port |
| `SKIP_DB_WAIT` | `false` | Skip DB readiness check on startup |

For production, at minimum set `DATABASE_URL`, `OLLAMA_HOST`, and `OLLAMA_MODEL`.

## Development

```bash
# Start services (hot-reload enabled, code mounted as volume)
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

## Production

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Differences from development:
- Multi-stage Dockerfile — smaller image, no build tools in runtime
- No volume mounts — code is baked into the image
- `restart: unless-stopped` — auto-restart on failure or host reboot
- No `--reload` flag
- Healthchecks on both app and database services

See `docker-compose.prod.yml` and `.dockerignore`.

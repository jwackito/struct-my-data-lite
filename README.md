# Struct My Data — Lite Edition

**Self-hosted document-to-structured-data extraction.**

Upload documents (PDF, DOCX, TXT, CSV, image), define a Pydantic schema via a visual builder or raw code, and get structured JSON output powered by [Instructor](https://github.com/jxnl/instructor) and an LLM provider of your choice (Ollama, OpenAI, or Gemini).

> **Lite Edition** — single instance, self-deployed, with multi-user support (JWT auth, admin dashboard, per-user API keys and usage tracking).

## Prerequisites

- **Docker** and **Docker Compose**
- **Ollama** running on the host with:
  - A [vision-capable model](https://ollama.com/search?c=vision) for image OCR (e.g., `gemma3:12b`, `llava`, `qwen3.6:35b`)
  - Ollama listening on all interfaces: `OLLAMA_HOST=0.0.0.0:11434 ollama serve`

## Quick Start

```bash
docker compose up -d --build
docker compose exec app python -m alembic upgrade head
docker compose exec app python -m app.seed --email admin@example.com --password <password> --role admin
```

Open **http://localhost:8080** in your browser:
1. Log in with the seeded admin account (or register if `ALLOW_REGISTRATION=true`)
2. Upload one or more documents (PDF, DOCX, TXT, CSV, or image)
3. Build a Pydantic schema using the visual field builder (or write raw code)
4. Click **Extract** — single files go to the result page; multiple files form a batch with per-file progress and results

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

# Using an API token (generate one in Settings > API Tokens)
export SMD_TOKEN=smd_your_token_here
curl -H "Authorization: Bearer $SMD_TOKEN" http://localhost:8080/upload -F "file=@document.pdf"
```

## Features

| Feature | Description |
|---|---|
| **Document parsing** | PDF (text + scanned via OCR), DOCX, TXT, CSV, images (JPEG/PNG/WebP) |
| **Bulk processing** | Upload 1–50 files at once — batch progress page, per-file results, combined JSON download, retry failed, cancel pending |
| **Visual field builder** | Drag-and-drop schema builder with nested model support — no Python required |
| **Raw code mode** | Write Pydantic v2 schemas directly in the Code tab |
| **LLM extraction** | Powered by Instructor + Ollama, OpenAI, or Gemini — structured output from unstructured docs |
| **Multi-user auth** | Register/login with JWT sessions, per-user data isolation, `ALLOW_REGISTRATION` toggle |
| **Admin interface** | User management (enable/disable, promote/demote, delete), system-wide usage view |
| **Bring Your Own API Key** | Users can register their own provider keys alongside admin-managed global connections |
| **API tokens** | Generate scoped tokens (`smd_...`) for programmatic access, with hashed storage and revocation |
| **Usage & cost tracking** | Per-user and system-wide token/cost statistics with model pricing table |
| **Schema templates** | Save and reuse schemas; load from a dropdown |
| **Real-time updates** | WebSocket and HTMX polling for job status |
| **API-first** | Full REST API + WebSocket for programmatic access |

## Architecture

```
── API ──────────────────────────────────────────
POST /upload                    →  Document stored (local fs + DB)
POST /extract                   →  ExtractionJob created → BackgroundTask:
                                     1. Parse document (PDF/DOCX/TXT/CSV/image)
                                     2. Send content + schema to LLM (thread pool)
                                     3. Store structured result
GET  /jobs/{id}                 →  Poll job status
GET  /models                    →  List available LLM models
GET  /schemas                   →  List saved schema templates
POST /schemas/parse             →  Parse schema code into builder fields
GET  /providers/connections     →  List provider connections
PUT  /providers/connections/{n} →  Create/update connection
WS   /ws/jobs/{id}              →  Real-time status push

── Web UI (HTMX) ─────────────────────────────────
GET  /              →  Upload form, field builder, schema editor, template dropdown
GET  /ui/settings   →  Provider connection management
GET  /ui/jobs       →  Job history with pagination
POST /ui/extract    →  Upload + job creation in one call
GET  /ui/jobs/{id}  →  HTML fragment (spinner / table / error)
POST /ui/jobs/{id}/retry  →  Retry a failed job
```

Scanned PDFs (no extractable text on any page) are detected per-page and
rendered to PNG images, then sent as multi-image messages to a vision-capable
model. Gemini supports PDF natively via its File API — see `AGENTS.md` for
the provider limitation and future work.

## Stack

| Component | Choice |
|---|---|
| Backend | Python 3.12, FastAPI |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| LLM | Ollama, OpenAI, Gemini (via connection registry) |
| Extraction | Instructor |
| Realtime | WebSocket |
| Frontend | Static HTML + HTMX (no build step) |
| OCR | Ollama multimodal (image parser) |
| Testing | pytest, pytest-asyncio, httpx |
| Containers | Docker Compose |

## API

| Method | Path | Description |
|---|---|---|
| GET | `/` | Web UI — upload form, field builder, schema editor, template dropdown |
| GET | `/ui/settings` | Settings page — manage provider connections |
| GET | `/ui/jobs` | Job history with pagination |
| GET | `/ui/jobs/{id}` | Job status as HTML fragment (for HTMX polling) |
| POST | `/ui/jobs/{id}/retry` | Retry a failed job |
| POST | `/ui/extract` | Upload + job creation (multipart form, returns HTML) |
| GET | `/health` | Health check |
| POST | `/upload` | Upload a document (10 MB max) |
| POST | `/extract` | Create an extraction job (JSON body) |
| GET | `/jobs/{id}` | Poll job status and result (JSON) |
| GET | `/models` | List available LLM models across all connections |
| GET | `/schemas` | List saved schemas |
| POST | `/schemas` | Create a saved schema |
| GET | `/schemas/{id}` | Get a single schema |
| PUT | `/schemas/{id}` | Update schema name or code |
| DELETE | `/schemas/{id}` | Delete a schema |
| GET | `/schemas/{id}/export` | Download schema as `.py` file |
| POST | `/schemas/import` | Upload `.py` or `.json` file to create schema |
| POST | `/schemas/parse` | Parse Pydantic code into builder fields |
| GET | `/providers/connections` | List provider connections |
| PUT | `/providers/connections/{name}` | Create or update a connection |
| DELETE | `/providers/connections/{name}` | Delete a connection |
| POST | `/providers/connections/{name}/test` | Test a connection |
| WS | `/ws/jobs/{id}` | Real-time job status updates |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/structmydata` | Async PostgreSQL connection string |
| `OLLAMA_HOST` | `http://host.docker.internal:11434` | Ollama server base URL |
| `OLLAMA_MODEL` | `qwen3.6:35b` | Model name for text extraction |
| `OLLAMA_VISION_MODEL` | `gemma4:31b` | Model name for image extraction |
| `OLLAMA_TIMEOUT` | `3600` (1h) | HTTP timeout in seconds for Ollama calls |
| `MAX_UPLOAD_SIZE` | `10485760` (10 MB) | Max file upload size in bytes |
| `PORT` | `8000` | App HTTP server port |
| `SKIP_DB_WAIT` | `false` | Skip DB readiness check on startup |
| `OPENAI_API_KEY` | `""` | OpenAI API key (optional, use connections UI instead) |
| `OPENAI_BASE_URL` | `""` | OpenAI-compatible base URL (optional) |
| `GEMINI_API_KEY` | `""` | Gemini API key (optional, use connections UI instead) |
| `APP_SECRET_KEY` | `""` | Fernet key for encrypting stored provider secrets |

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

To make Ollama reachable from Docker containers, start it on all interfaces:

```bash
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

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

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

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
| **i18n** | English and Spanish UI — EN/ES switcher on every page, stored in a `lang` cookie; API errors and HTMX fragments localize to match |
| **Real-time updates** | WebSocket and HTMX polling for job status |
| **API-first** | Full REST API + WebSocket for programmatic access |

## Architecture

```
── API ──────────────────────────────────────────
POST /auth/register            →  Create account (JWT cookie + token)
POST /auth/login               →  Authenticate
POST /auth/logout              →  Clear session
POST /upload                   →  Document stored (local fs + DB)
POST /extract                  →  ExtractionJob created → BackgroundTask:
                                     1. Parse document (PDF/DOCX/TXT/CSV/image)
                                     2. Send content + schema to LLM (thread pool, 2 concurrent)
                                     3. Store structured result
GET  /jobs/{id}                →  Poll job status
GET  /api/batches              →  List batches
POST /api/batches              →  Create batch from document IDs
GET  /api/batches/{id}         →  Batch progress (per-job status)
POST /api/batches/{id}/retry-failed →  Re-run failed jobs
POST /api/batches/{id}/cancel  →  Cancel pending jobs
GET  /api/batches/{id}/results →  Download all results as one JSON
GET  /api/usage                →  User usage stats (tokens, cost)
GET  /admin/usage/data         →  System-wide usage (admin)
GET  /admin/users/data         →  User management list (admin)
GET  /models                   →  List available LLM models
GET  /schemas                  →  List saved schema templates
POST /schemas/parse            →  Parse schema code into builder fields
GET  /api/keys                 →  User's own API keys (BYOAK)
GET  /api/tokens               →  User's API tokens
WS   /ws/jobs/{id}             →  Real-time status push

── Web UI (HTMX) ─────────────────────────────────
GET  /              →  Upload form, field builder, schema editor, template dropdown
GET  /login         →  Login page
GET  /register      →  Registration page
GET  /usage         →  Usage stats (own)
GET  /ui/batches    →  Batch list
GET  /ui/batches/{id} →  Batch progress + per-file results
GET  /ui/jobs       →  Job history with pagination
POST /ui/batch-extract →  Upload 1–50 files + schema + model → batch
GET  /ui/jobs/{id}/result →  Dedicated result page (JSON + download)
POST /ui/jobs/{id}/retry  →  Retry a failed job
GET  /admin         →  Admin dashboard
GET  /admin/users   →  Admin user management page
GET  /admin/usage   →  System-wide usage page
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
| GET | `/login` | Login page |
| GET | `/register` | Registration page (hidden when `ALLOW_REGISTRATION=false`) |
| POST | `/auth/register` | Create account, returns JWT + sets cookie |
| POST | `/auth/login` | Authenticate, returns JWT + sets cookie |
| POST | `/auth/logout` | Clear session |
| GET | `/auth/me` | Current user info |
| GET | `/health` | Health check |
| POST | `/upload` | Upload a document (10 MB max) |
| POST | `/extract` | Create an extraction job (JSON body) |
| GET | `/jobs/{id}` | Poll job status and result (JSON) |
| GET | `/models` | List available LLM models across all connections |
| POST | `/api/batches/estimate` | Preflight cost estimate for file sizes + model |
| POST | `/api/batches` | Create a batch from document IDs |
| GET | `/api/batches` | List user's batches (paginated) |
| GET | `/api/batches/{id}` | Batch progress with per-job status |
| POST | `/api/batches/{id}/retry-failed` | Re-run failed jobs in a batch |
| POST | `/api/batches/{id}/cancel` | Cancel pending jobs |
| GET | `/api/batches/{id}/results` | Download all batch results as one JSON |
| GET | `/api/usage` | User's own usage stats (tokens, cost, breakdown) |
| GET | `/admin/usage/data` | System-wide usage with per-user breakdown (admin) |
| GET | `/admin/users/data` | User list with job counts (admin) |
| POST | `/admin/users/{id}/toggle-status` | Enable/disable a user (admin) |
| POST | `/admin/users/{id}/set-role` | Promote/demote a user (admin) |
| DELETE | `/admin/users/{id}` | Soft-delete a user (admin) |
| GET | `/schemas` | List saved schemas |
| POST | `/schemas` | Create a saved schema |
| GET | `/schemas/{id}` | Get a single schema |
| PUT | `/schemas/{id}` | Update schema name or code |
| DELETE | `/schemas/{id}` | Delete a schema |
| GET | `/schemas/{id}/export` | Download schema as `.py` file |
| POST | `/schemas/import` | Upload `.py` or `.json` file to create schema |
| POST | `/schemas/parse` | Parse Pydantic code into builder fields |
| GET | `/api/keys` | List user's personal provider keys |
| POST | `/api/keys` | Create a personal provider key |
| PUT | `/api/keys/{name}` | Update a personal provider key |
| DELETE | `/api/keys/{name}` | Delete a personal provider key |
| GET | `/api/tokens` | List user's API tokens |
| POST | `/api/tokens` | Generate an API token (shown once) |
| DELETE | `/api/tokens/{id}` | Revoke an API token |
| GET | `/providers/connections` | List global connections (admin) |
| PUT | `/providers/connections/{name}` | Create/update a global connection (admin) |
| DELETE | `/providers/connections/{name}` | Delete a global connection (admin) |
| POST | `/providers/connections/{name}/test` | Test a connection (admin) |
| WS | `/ws/jobs/{id}` | Real-time job status updates |

## Bulk Processing

Selecting multiple files on the extraction page creates a **batch** — one `ExtractionJob` per file, all sharing the same schema and model.

- **Batch page** (`/ui/batches/{id}`): progress bar, per-file status, links to individual result pages, combined JSON download, retry-failed and cancel buttons
- **Cost estimate**: before submitting, the UI shows an estimated cost and asks for confirmation when the estimated cost is greater than zero
- **Concurrency**: at most 2 extraction jobs run at once (`BATCH_CONCURRENCY`), protecting Ollama and API rate limits; the rest queue automatically
- **Limits**: up to 50 files per batch (`MAX_BATCH_SIZE`), 10 MB per file
- **Single files**: uploading one file also creates a batch of one, and the batch page auto-redirects to the job result page when done
- **History**: batch jobs also appear in the job history tab; the batch list is at `/ui/batches`

## i18n

The UI ships in English and Spanish. A language switcher (EN/ES) appears on every page; the choice is stored in a `lang` cookie.

- **Client side**: `app/static/i18n.js` translates `data-i18n` elements on load and after every HTMX swap; inline scripts use `window.t()`. No build step.
- **Server side**: `app/i18n.py` reads the same JSON dictionaries (`app/i18n/en.json`, `app/i18n/es.json` — keys are the English strings themselves). A per-request language context makes API error messages and server-rendered HTMX fragments (job stats, history, batch notices) follow the visitor's language.
- **Selection order**: `lang` cookie → `Accept-Language` header → English. Unknown languages fall back to English.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/structmydata` | Async PostgreSQL connection string |
| `OLLAMA_HOST` | `http://host.docker.internal:11434` | Ollama server base URL |
| `OLLAMA_MODEL` | `qwen3.6:35b` | Model name for text extraction |
| `OLLAMA_VISION_MODEL` | `gemma4:31b` | Model name for image extraction |
| `OLLAMA_TIMEOUT` | `3600` (1h) | HTTP timeout in seconds for Ollama calls |
| `MAX_UPLOAD_SIZE` | `10485760` (10 MB) | Max file upload size in bytes |
| `MAX_BATCH_SIZE` | `50` | Max files per batch |
| `BATCH_CONCURRENCY` | `2` | Max concurrent extraction jobs |
| `PORT` | `8000` | App HTTP server port |
| `SKIP_DB_WAIT` | `false` | Skip DB readiness check on startup |
| `OPENAI_API_KEY` | `""` | OpenAI API key (optional, use connections UI instead) |
| `OPENAI_BASE_URL` | `""` | OpenAI-compatible base URL (optional) |
| `GEMINI_API_KEY` | `""` | Gemini API key (optional, use connections UI instead) |
| `APP_SECRET_KEY` | `""` | Fernet key for encrypting stored provider secrets |
| `JWT_SECRET` | `""` (auto-generated) | Secret for signing JWTs |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_EXPIRY_HOURS` | `24` | JWT session lifetime in hours |
| `ALLOW_REGISTRATION` | `true` | Whether public registration is open |

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

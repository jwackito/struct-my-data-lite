# Struct My Data (lite) — contributor notes

Extract structured data (JSON/YAML) from documents using LLMs.

Upload a document (PDF, DOCX, DOC, TXT, CSV, image), define a Pydantic model for
the target structure, and let an Instructor-powered LLM produce the structured
output.

This is the **lite** edition: a single-instance, self-hostable app with
multi-user support.

## Stack

| Component | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 + PostgreSQL 16, Pydantic v2 |
| Migrations | Alembic (async, asyncpg) |
| LLM orchestration | Instructor |
| LLM providers | Ollama, OpenAI, Gemini via a connection registry |
| Task queue | FastAPI BackgroundTasks |
| Realtime | WebSocket |
| Frontend | Static HTML + HTMX (no build step) |
| Testing | pytest, pytest-asyncio, pytest-cov |
| Containerization | Docker Compose (Ollama runs externally on the host) |
| OCR | Ollama multimodal (image parser) |
| Max upload | 10 MB |

## Repository

- GitHub: `struct-my-data-lite`
- Domain: `structmydata.com.ar` / `smd.com.ar`

## Workflow

1. Write a failing test (`pytest` → RED)
2. Implement the minimal code to pass (`pytest` → GREEN)
3. Refactor if needed
4. Commit (`test: ...` then `feat: ...`)

Every feature starts with a failing test. Every bug fix starts with a failing
test that reproduces it.

### Commit convention

```
type: short description
```

Types: `test`, `feat`, `fix`, `chore`, `docs`.

## Running

See `README.md` for the full setup. In short:

```bash
docker compose up -d
docker compose exec app python -m alembic upgrade head
docker compose exec app python -m pytest
```

Inside the container, always use `python -m` to run Python tools (alembic,
pytest, etc.).

## Security

- The user-provided `pydantic_schema` is compiled and executed to build the
  Pydantic classes Instructor introspects. It runs through an AST-allowlist
  sandbox with restricted builtins (`app/schema_sandbox.py`); escape attempts
  are rejected with `422`.
- Documents and jobs are ownership-checked per user.
- `JWT_SECRET` is mandatory when `ENV` is not `dev`.

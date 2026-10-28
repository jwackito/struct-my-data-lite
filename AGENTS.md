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
| Testing | pytest, pytest-asyncio |
| Planning | OpenSpec changes (`openspec/`) |
| Containerization | Docker Compose (Ollama runs externally on the host) |
| OCR | Ollama multimodal (image parser) |
| Max upload | 10 MB |

## Repository

- GitHub: `struct-my-data-lite`
- Domain: `structmydata.com.ar` / `smd.com.ar`

## Workflow

Every contribution is an OpenSpec change. Create or continue one before writing
code, and keep the change directory in the branch.

1. `openspec new change <change-name>`.
2. Fill `proposal.md`, the spec delta under `specs/<capability>/`, `design.md`
   when the change is cross-cutting, and `tasks.md`.
3. Run `openspec validate <change-name> --strict`.
4. Work through the tasks test-first.
5. Archive in the PR that completes the change:
   `openspec archive <change-name> --yes`.

Docs, tests, chores and style-only changes still use a change, with
`skip_specs: true` in `.openspec.yaml` and `archive --skip-specs`.

Every behaviour change starts with a failing test (`pytest` → RED), then the
minimal implementation (`pytest` → GREEN), then refactor. Every bug fix starts
with a failing test that reproduces it.

### Commit convention

Full Conventional Commits:

```text
type(scope)!: short description
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`,
`ci`, `chore`, `revert`. `Merge` and `Revert "..."` subjects are allowed.
A breaking change uses `!` and a `BREAKING CHANGE:` footer.

### Branching & pull requests

`main` is **pull-request only** — never push to it directly.

1. Work on `change/<change-name>`, e.g. `change/add-doc-parser`.
2. Keep the branch focused on one OpenSpec change.
3. Push the branch and open a PR. The OpenSpec validation job must pass.
4. Archive the change in the completing PR and say `Archives: <change-name>`.
5. Merge with a **merge commit** (never squash — the branch trail is history).
6. Agents open PRs and merge only after the maintainer approves in chat.

Guardrails (Free plan, so no server-side branch protection):
`bash scripts/install_hooks.sh` enables the `pre-push` hook (it copies the hooks
to an executable location, since git ignores hooks on a `noexec` mount);
`pr-guards.yml` checks the branch and commit format; `main-guard.yml` flags a
commit that reached `main` without a PR; `openspec.yml` validates the change.

## Running

See `README.md` and `CONTRIBUTING.md` for the full setup. In short:

```bash
cp .env.example etc/.env
docker compose up -d --build
docker compose exec app python -m alembic upgrade head
docker compose exec app python -m pytest
```

Inside the container, always use `python -m` to run Python tools (alembic,
pytest, etc.).

OpenSpec needs Node.js 20.19+ and is pinned to `1.14.3`:

```bash
npm install -g @fission-ai/openspec@1.14.3
openspec validate <change-name> --strict
```

## Security

- The user-provided `pydantic_schema` is compiled and executed to build the
  Pydantic classes Instructor introspects. It runs through an AST-allowlist
  sandbox with restricted builtins (`app/schema_sandbox.py`); escape attempts
  are rejected with `422`.
- Documents and jobs are ownership-checked per user.
- `JWT_SECRET` is mandatory when `ENV` is not `dev`.
- Vulnerabilities go through the private advisory flow in `SECURITY.md`, never a
  public issue or change.

# Changelog

## Unreleased

### Added
- Tenant isolation: uploads record the owning user and dedup is scoped per user; job, batch and WebSocket access are ownership-checked (admins keep override)
- Model access is enforced at job creation via `authorize_model()`, not only when listing models
- WebSocket `/ws/jobs/{id}` authenticates and verifies ownership before accepting (close `4401`/`4403`)
- Schema `exec()` sandbox: AST allowlist plus restricted builtins, shared by extract, batch and schema import
- DB-backed per-user active/daily job caps (`app/quotas.py`), gated by `USAGE_ENFORCED` (default off)
- `ENV`, `PER_USER_CONCURRENCY`, `DAILY_JOB_CAP` and `USAGE_ENFORCED` environment variables

### Changed
- `JWT_SECRET` is mandatory when `ENV` is not `dev`; the app fails fast at startup otherwise

## v1.2.4-lite (2026-09-22)

### Added
- Admin failure observability: `/admin/failures` (filters by user, model, connection, content type and date; paginated) and `/admin/jobs/{id}` detail showing the document, schema, model/connection/provider, timings/tokens, error and full traceback, plus an admin-only download of the original document
- `extraction_jobs.error_detail` persists the failure traceback (8 KB cap), and extraction failures are logged with a stack trace
- `LOG_LEVEL` environment variable (default `INFO`) configures application logging

## v1.2.3-lite (2026-09-22)

### Added
- Legacy `.doc` (Word 97-2003) support: `WordParser` sniffs the file signature and extracts text via `antiword` (OLE2) or `python-docx` (OOXML). The parser factory routes `application/msword` (and variants) and falls back to the filename extension for `application/octet-stream`, so mislabeled `.doc`/`.docx` uploads still parse. `antiword` is installed in the runtime image.

## v1.2.2-lite (2026-09-22)

### Added
- App-level rate limiting (dependency-free token bucket): per-user on `/upload`, `/extract` and batch routes, per-IP on `/auth/login` and `/auth/register`; over-limit requests get `429` with `Retry-After`
- Bounded background job queue: `batch_concurrency` jobs run at once, `job_queue_max` more may wait, and overflow enqueues return `503` instead of piling up
- `RATE_LIMIT_*`, `BATCH_CONCURRENCY` and `JOB_QUEUE_MAX` environment variables documented in `.env.example`

### Changed
- The app container runs as a non-root user (UID 10001); `/app/storage` is created and owned by it in the image
- Production compose adds resource limits (app/db 4 GB / 2 CPU, caddy 256 MB / 0.5 CPU), json-file log rotation, `init`, `stop_grace_period`, and a DB-aware `/health/ready` healthcheck
- Base images (`python:3.12-slim`, `postgres:16-alpine`, `caddy:2`) are pinned by digest

### Fixed
- Deploy script loaded `etc/.env` only into containers, not into compose interpolation, so `POSTGRES_PASSWORD` fell back to the default and migrations failed; compose now runs with `--env-file etc/.env`
- Deploy script read `etc/ghcr.env` after resolving the previous image, leaving the auto-rollback guard inert; GHCR config is now loaded before the previous-image check
- Rollback passed a full image reference as `IMAGE_TAG` (producing an invalid `repo:repo:tag`); deploy and rollback now pass a complete image ref via `IMAGE_REF`, enabling rollback by tag or digest
- A failed `up -d app` could be masked by a health gate passing against a stale container; app start failures now abort the deploy

## v1.2.1-lite (2026-09-21)

### Added
- Schema sharing: per-user unique schema names, an admin-publishable `is_public` flag, `GET /schemas/shared`, and `POST /schemas/{id}/duplicate` for copying a shared schema into your own namespace
- Admin schema management page (`/admin/schemas`) with publish/unpublish and delete; admins have full control over any schema
- Schema selector groups "Mine" / "Shared" with owner labels and a Copy action
- Server-rendered Jinja2 base layout and canonical nav (`app/templates/base.html`, `app/templates/_nav.html`, `app/static/app.css` served at `/app.css`); the logged-in user name is rendered in the nav

### Fixed
- Admin Models page now lists implicit Ollama models — the registry query used an inner join that dropped rows with a NULL `connection_id` (`app/main.py`)
- Schema access control: get/update/delete/export now enforce ownership (owners or admins only; public schemas readable), closing an IDOR

## v1.2.0-lite (2026-09-09)

### Added
- Builder-first schema editor: the visual Builder is now the primary way to define extraction schemas; Pydantic code is hidden behind a collapsed Advanced debug panel
- Auto code generation at submit from builder fields; `manualCode` mode lets advanced edits be submitted as-is
- Expanded type system: `datetime`, `List[bool]`, `List[date]`, `List[datetime]`, per-field Optional checkbox and default input
- 1:1 round-trip parity between Builder, generated code, and parser (structural, enforced by `tests/test_schema_roundtrip.py`); `app/schema_codegen.py` mirrors client codegen for testability
- Saved schemas load into the Builder via parsing (no code shown); builder state persists in `sessionStorage`
- SaaS productization roadmap (`specs/11-saas-roadmap.md`)

### Fixed
- Stale integration tests from the pre-auth era: authenticate before API calls and drop tests targeting the removed `/ui/extract` route (`tests/integration/test_api.py`, `test_pipeline.py`, `test_ollama.py`)
- Alembic downgrades: FK constraints created with `op.create_foreign_key(None, ...)` were unnamed, making `alembic downgrade` fail; all FK constraints now use explicit names (`<table>_<column>_fkey`)
- Docker healthcheck: image has no `curl`, so compose probes failed and the app showed unhealthy; healthcheck now uses a Python one-liner (dev + prod compose)

## v1.1.1-lite (2026-08-04)

### Added
- Site footer on every page: app version (parsed from this changelog), © Purrfect AI — purrfectai.com.ar, and MIT license link
- `GET /api/version` endpoint returning the current app version
- `GET /LICENSE` route serving the MIT license file
- MIT license for the project (`LICENSE`, © 2026 Purrfect AI)
- Admins can create users from `/admin/users` (modal with email/password validation)
- Caddy reverse proxy with TLS for production deployments (docs + compose config)

### Fixed
- Production hardening: app and database no longer exposed on host ports, persistent storage volume for uploads, Alembic migrations bundled in the image, secrets moved to `.env` (see `.env.example`)

## v1.1.0-lite (2026-07-31)

### Added
- i18n: English + Spanish UI with an EN/ES switcher on every page (cookie-based, falls back to `Accept-Language`)
- Client-side translation via `app/static/i18n.js` (`data-i18n`, `data-i18n-ph`, `data-i18n-title`, `window.t()`) re-applied on HTMX swaps
- Server-side localization of API error messages and HTMX fragments via `app/i18n.py` (`t`, `t_req`, request-scoped language context)
- Single source of truth: `app/i18n/en.json` / `app/i18n/es.json` shared by Python and JS

## v1.0.0-lite (2026-07-31)

### Added
- Bulk processing: Batch model, multipart batch upload (1–50 files), batch progress page, batch list page
- Per-batch actions: retry failed jobs, cancel pending jobs, download all results as one JSON
- Cost estimate + confirmation dialog before batch submissions (when estimated cost > 0)
- Concurrency limit on extraction jobs (`BATCH_CONCURRENCY`, default 2) to protect Ollama and API rate limits
- Uniform batches: single-file uploads create a batch of one, auto-redirecting to the job result page on completion
- Admin usage page with system-wide stats and per-user breakdown (with user emails)
- Usage nav links on all pages (users → `/usage`, admins → `/admin/usage`)
- Job stats displayed as visual cards with hover tooltips (tokens, cost, timing, model)
- Schema backup/restore CLI: `python -m app.backup_schemas export|import [--user email]`
- Admin users page now renders HTML (`/admin/users`), JSON moved to `/admin/users/data`
- Specs 05–08: admin HTML page, usage nav, job stats cards, bulk processing

### Fixed
- `/api/usage` and `/admin/usage` crashed with `NameError` (missing `calculate_cost` import)
- Date filtering in usage routes failed (`timestamptz` vs string comparison)
- Batch multipart upload returned 422 (field name mismatch between form and route)
- Cost confirmation dialog leaked to the History tab requests
- Request path rewriting broke the History tab loading
- Admin users test hitting the wrong endpoint (`/admin/users` vs `/admin/users/data`)

### Changed
- All uploads now go through `/ui/batch-extract` (uniform batches, single or multi-file)
- Removed the now-unused `/ui/extract` route
- README updated: features, architecture, API table, env vars, bulk processing section

## v0.6.0-lite (2026-07-29)

### Added
- User authentication: register, login, JWT session management, route protection
- Admin interface: user management (list, search, enable/disable, promote/demote, delete)
- Personal API keys (BYOAK): users can register their own LLM provider keys
- API tokens for programmatic access: generate, list, revoke with Bearer auth
- Usage tracking & expense calculation: pricing table, `/api/usage`, cost shown per job
- Usage page with summary cards and breakdown table
- Settings page split into global connections (admin) and personal API keys

## v0.5.0-lite (2026-07-29)

### Added
- Form state persistence — last used model and schema survive page navigation
- Scanned PDF auto-detection: pages with no text rendered to PNG and routed through multimodal vision model
- Multi-user auth spec (Phase 0–4) — planned in `specs/`

### Docs
- AGENTS.md: PDF image routing strategy with Gemini limitation
- README.md: scanned PDF handling note

## v0.4.0-lite (2026-07-29)

### Fixed
- OpenAI model classification: unknown models fall back to "text" instead of being silently filtered out
- Empty model ID in dropdown now uses connection's default model
- `process_job` falls back to connection's default model when `model_name` is empty
- Connection test returns real API errors (401, timeout) instead of false positive "connected with 0 models"
- Stable `APP_SECRET_KEY` via `secrets.env` — encryption survives container restarts
- Result page 500 error fixed (correct `TemplateResponse` argument order)

### Added
- Dedicated result page at `/ui/jobs/{id}/result` with full-page output display
- JSON download endpoint at `/ui/jobs/{id}/download`
- Output rendered as formatted JSON in monospaced font (replaced HTML tables)
- Syntax highlighting for JSON output via highlight.js
- Light/dark theme toggle on all pages, persisted in localStorage

## v0.3.0-lite (2026-07-29)

### Fixed
- Schema parser `_find_model` picks last `BaseModel` subclass (not first)
- HTMX polling loop (`hx-swap="outerHTML"`)
- Browser cache on polling responses
- Process job failure handling (commit guard, notify protection inside try)
- Sanitize `output_data` with `jsonable_encoder`

### Docs
- Update AGENTS.md (stack, phases, data models, directory tree, provider abstraction)
- Update README.md (env vars, API table, features, architecture; replace roadmap with changelog link)
- Add CHANGELOG.md

## v0.2.0-lite

### Added
- Token & timing tracking (input/output tokens, per-stage timing, UI display)
- Job retry endpoint + UI retry button
- Job history page with pagination
- OpenAI & Gemini providers (full, not scaffolded)
- Provider connection management with Fernet-encrypted secrets
- Settings page UI for managing provider connections
- Model selector dropdown in extraction UI
- Code-to-builder reverse parser (`POST /schemas/parse`)
- Content hash deduplication on upload
- Ollama multimodal OCR for image documents

## v0.1.0-lite

Initial Lite Edition release.

- P1-P10: Full backend (DB, parsers, extraction, jobs, WebSocket)
- P11: HTMX Web UI with upload, schema form, result polling
- P12: Visual field builder with nested models
- P13: Schema template saving, export/import
- P14: Image OCR via Ollama multimodal

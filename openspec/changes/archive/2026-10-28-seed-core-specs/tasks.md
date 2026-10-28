# Tasks

## 1. Sources

- [x] 1.1 Read the routes, models, parsers, queue and tests for auth, documents, extraction and batches; verify each requirement candidate has a code path or a test.

## 2. Capability specs

- [x] 2.1 Write `specs/auth/spec.md` with registration, login, session, logout, API tokens, roles, rate limiting and password storage; verify every requirement has at least one WHEN/THEN scenario.
- [x] 2.2 Write `specs/documents/spec.md` with upload, size limit, storage names, per-user deduplication, ownership, deferred type validation and metadata; verify the limits match `app/config.py`.
- [x] 2.3 Write `specs/extraction/spec.md` with creation, schema sandbox, model authorization, lifecycle, results, parsing, vision, retry, queue overflow and usage; verify the status codes match `app/main.py`.
- [x] 2.4 Write `specs/batches/spec.md` with creation, ownership, listing, progress, retry, cancel, results, estimate, multipart batches and quotas; verify the limits match `MAX_BATCH_SIZE` and the plan hooks.

## 3. Validate

- [x] 3.1 Run `openspec validate seed-core-specs --strict` and fix every warning, including requirement descriptions over 500 characters and scenarios without four hashtags.
- [x] 3.2 Open the PR with `Change: seed-core-specs`, verify the guards, tests and OpenSpec jobs pass, and confirm the four spec files are the only content changes.

## Workflow follow-up

- Archive this change in the completing PR with `openspec archive seed-core-specs --yes`, then run `openspec validate --archived` and `openspec validate --specs --strict`.
- Merge with a merge commit and verify `openspec list --specs` shows `auth`, `documents`, `extraction` and `batches`.
- Start `change/seed-data-specs` for `schemas` and `providers`, then `change/seed-surface-specs` for `i18n`, `admin` and `deployment`.

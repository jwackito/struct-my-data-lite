# Proposal

## Why

OpenSpec is now the contribution workflow, but `openspec/specs/` is empty, so
every change invents capability names and reviewers cannot see the behaviour
they are changing. Baseline specs for the core flows give contributors stable
paths and make future deltas reviewable against something.

## What Changes

- Add `openspec/specs/auth/spec.md` covering registration, login, sessions, API
  tokens, roles and rate limiting.
- Add `openspec/specs/documents/spec.md` covering upload, size limits, storage
  names, deduplication and ownership.
- Add `openspec/specs/extraction/spec.md` covering job creation, the schema
  sandbox, model authorization, lifecycle, parsing, vision, retry, queue limits
  and usage recording.
- Add `openspec/specs/batches/spec.md` covering batch creation, ownership,
  progress, retry, cancel, combined results, estimates, the upload form and
  quotas.
- No runtime behaviour changes. The specs describe the current system and are
  derived from routes, models and tests.
- Out of scope: `schemas`, `providers`, `i18n`, `admin` and `deployment`, which
  land in separate changes.

## Capabilities

### New Capabilities

- `auth`: registration, login, sessions, API tokens, roles and auth rate limits.
- `documents`: upload intake, limits, storage, deduplication and ownership.
- `extraction`: parsing, schema sandbox, model authorization and job lifecycle.
- `batches`: batch creation, progress, retry, cancel, results and estimates.

### Modified Capabilities

None. These capabilities do not exist yet in `openspec/specs/`.

## Impact

- Four new spec files under `openspec/specs/`; no application code, CI or
  dependency changes.
- Future changes to these areas must use `MODIFIED Requirements` deltas against
  the new spec paths.
- The spec content is normative for behaviour; if it disagrees with the code, the
  disagreement is a defect to resolve in a follow-up change.

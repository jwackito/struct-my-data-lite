# Proposal

## Why

The core capabilities now have baseline specs, but `schemas` and `providers` are
still undocumented. They own saved extraction definitions, connection scope,
model listing, authorization and pricing — the pieces every extraction depends
on. Documenting them gives future changes stable paths and makes security and
pricing changes reviewable.

## What Changes

- Add `openspec/specs/schemas/spec.md` covering CRUD, naming, access control,
  limits, the validation boundary, sharing, import, export, parsing, builder
  round-trip and admin management.
- Add `openspec/specs/providers/spec.md` covering supported providers, the
  implicit Ollama connection, scope resolution, admin and personal connections,
  secret handling, model listing, authorization, registry sync and pricing.
- No runtime behaviour changes. The specs describe the current system and are
  derived from routes, models and tests.
- Out of scope: `i18n`, `admin` and `deployment`, which land in a separate change.

## Capabilities

### New Capabilities

- `schemas`: saved schemas, builder, import/export, sharing and sandbox boundary.
- `providers`: connections, personal keys, model registry, authorization and
  pricing.

### Modified Capabilities

None. These capabilities do not exist yet in `openspec/specs/`.

## Impact

- Two new spec files under `openspec/specs/`; no application code, CI or
  dependency changes.
- Future changes to these areas must use `MODIFIED Requirements` deltas.
- Security-sensitive current behaviour, including the admin single-connection
  secret detail, is documented so a later change can tighten it visibly.

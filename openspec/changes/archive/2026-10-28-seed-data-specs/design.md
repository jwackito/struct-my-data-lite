# Design

## Context

See `proposal.md` for motivation. The specs document behaviour that already
exists. Sources: `app/connections.py`, `app/providers/`, `app/pricing.py`,
`app/schema_parser.py`, `app/schema_codegen.py`, `app/schema_sandbox.py`,
`app/models.py`, schema and provider routes in `app/main.py`, and the pytest
suite.

## Goals / Non-Goals

**Goals:**

- Stable `schemas` and `providers` paths with observable requirements.
- Explicit defaults, status codes and security boundaries.
- Document the quirks that future changes are likely to tighten.

**Non-Goals:**

- Changing behaviour or fixing the quirks while documenting them.
- Documenting internal classes, function names or provider SDK details.
- `i18n`, `admin` and `deployment`, which get a separate change.

## Decisions

### Two capabilities by ownership boundary

`schemas` owns saved definitions and the builder; `providers` owns connections,
the registry and pricing. Authorization at job creation is documented in
`providers` because it depends on connections and model access, while the
`extraction` spec points at the same outcome.

### Quirks are recorded, not silently fixed

Two current behaviours are worth naming: saved-schema create and update do not
run the sandbox, and the admin single-connection detail returns decrypted
secrets for editing. Both are stated so a later change can MODIFY them visibly
instead of discovering them in production.

### Requirements stay testable

Each requirement states one behaviour; scenarios cover the normal path, the main
denial path and a limit. This keeps `openspec validate --strict` green.

## Risks / Trade-offs

- **Documenting a security exception may look like endorsement** → the spec
  names it as an exception, and a future change can close it with a MODIFIED
  delta.
- **Specs drift from provider APIs** → requirements describe the application's
  behaviour, not each provider's response format.
- **Too much detail in pricing** → only the lookup order and rounding are
  specified; tables remain data.

## Migration Plan

None. Specs are additive. Rollback removes the two spec files and archives the
change; no code or data migration is involved.

## Open Questions

None. Provider-specific model tables and capabilities remain configuration, not
spec content.

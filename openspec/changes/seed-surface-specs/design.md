# Design

## Context

See `proposal.md` for motivation. The specs document behaviour that already
exists. Sources: `app/i18n.py`, the dictionaries, `app/static/i18n.js`, templates,
admin routes and tests, `Dockerfile`, both compose files, `.env.example`,
`scripts/migrate.py`, `.github/workflows/` and the health, startup, migration and
version tests.

## Goals / Non-Goals

**Goals:**

- Stable `i18n`, `admin` and `deployment` paths.
- Explicit language selection order, admin authorization and production
  guarantees.
- Document the production contract that CI and compose already implement.

**Non-Goals:**

- Changing localization, admin behaviour or deployment configuration.
- Documenting every template, provider SDK or host-specific setup.
- Replacing operator documentation; the spec states guarantees, not a tutorial.

## Decisions

### Split the surface by audience

`i18n` owns language behaviour, `admin` owns privileged operations, and
`deployment` owns the runtime and release contract. This keeps each spec
reviewable by the people who change it.

### State the server/client difference in i18n

Server selection is cookie, then `Accept-Language`, then English; the browser
script uses cookie, then `navigator.language`. The spec records both because the
difference is observable and easy to break.

### Admin spec covers override, not every page

The admin spec states authorization, user operations, observability, job
inspection, model administration and grants. Individual HTML layouts are not
normative.

### Deployment spec is a contract, not a runbook

It states topology, image properties, configuration requirements, migration
locking, health semantics, CI gates and release tags. Exact YAML stays in the
repository and is reviewed as implementation.

## Risks / Trade-offs

- **Specs drift from compose or workflows** → changes to either must update the
  deployment spec in the same change.
- **i18n client/server differences** → both selection paths are stated
  explicitly, and the dictionary parity test backs the key rules.
- **Admin behaviour leaks into user routes** → the spec names admin override and
  the personal listing boundary.

## Migration Plan

None. Specs are additive. Rollback removes the three spec files and archives the
change.

## Open Questions

None. Remaining follow-up work, removing the transitional branch regex, is a
separate `chore` change.

# Proposal

## Why

The core, schema and provider capabilities now have baseline specs. The remaining
surface areas — localization, administration and deployment — are the last
undocumented parts of the system. Without them, changes to languages, admin
views or the production image have no durable contract to review against.

## What Changes

- Add `openspec/specs/i18n/spec.md` covering supported languages, selection and
  fallback, dictionary integrity, server and client rendering, the switcher and
  dictionary endpoints.
- Add `openspec/specs/admin/spec.md` covering authorization, user management,
  system usage, failure observability, job inspection, model administration,
  model grants and admin override.
- Add `openspec/specs/deployment/spec.md` covering topology, the production
  image, hardening, configuration and secrets, migrations, health, startup, CI,
  release and defaults.
- No runtime behaviour changes. The specs describe the current system and are
  derived from code, configuration and tests.

## Capabilities

### New Capabilities

- `i18n`: English/Spanish UI and API localization, dictionaries and switcher.
- `admin`: administrative users, usage, failures, jobs and models.
- `deployment`: compose topology, image, configuration, migrations, health, CI
  and release.

### Modified Capabilities

None. These capabilities do not exist yet in `openspec/specs/`.

## Impact

- Three new spec files under `openspec/specs/`; no application code, CI or
  dependency changes.
- Future changes to these areas must use `MODIFIED Requirements` deltas.
- After this lands, the transitional legacy branch format can be removed from
  `pr-guards.yml`, completing the OpenSpec adoption.

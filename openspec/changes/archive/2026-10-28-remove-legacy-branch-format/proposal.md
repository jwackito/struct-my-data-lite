# Proposal

## Why

The OpenSpec workflow has landed: CONTRIBUTING, the CI job and all nine baseline
specs are on `main`. The `pr-guards` branch check still accepts the legacy
`type/<n>-<slug>` form as a bootstrap concession, which lets a pull request skip
the change mapping. Remove it so every branch maps to a change.

## What Changes

- `pr-guards.yml` accepts only `change/<change-name>` branches.
- The legacy branch warning and the transitional comment are removed.
- The linked-issue check remains optional; bug fixes may still use `Closes #N`.
- No application behaviour changes.

## Capabilities

### New Capabilities

None. This is a CI policy cleanup. The change's `.openspec.yaml` sets
`skip_specs: true`.

### Modified Capabilities

None.

## Impact

- `.github/workflows/pr-guards.yml` only.
- No application, documentation or dependency changes.

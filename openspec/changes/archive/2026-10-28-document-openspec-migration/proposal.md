# Proposal

## Why

The migration to OpenSpec is documented only by six archived changes and a
local, ephemeral plan. A maintainer starting the same migration in another
edition or repository has to reconstruct the order, the CI bootstrap workaround
and the pitfalls from history. A durable playbook makes the process repeatable
and gives future maintainers the reasoning behind the current workflow.

## What Changes

- Add `docs/migrating-to-openspec.md`: a process document covering decisions,
  the migration sequence, a worked example from this repository, pitfalls,
  a checklist, rollback and a minimum viable migration.
- Link it from the Maintainers section of `CONTRIBUTING.md`.
- No application code, CI or dependency changes.

## Capabilities

### New Capabilities

None. This change adds documentation only. The change's `.openspec.yaml` sets
`skip_specs: true`.

### Modified Capabilities

None.

## Impact

- New `docs/` file and one link in `CONTRIBUTING.md`.
- The local plan file outside the repository is removed after this lands; the
  repository document replaces it.

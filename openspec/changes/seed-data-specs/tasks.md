# Tasks

## 1. Sources

- [x] 1.1 Read the schema and provider routes, models, parsers, registry, pricing and tests; verify each requirement candidate has a code path or a test.

## 2. Capability specs

- [x] 2.1 Write `specs/schemas/spec.md` with CRUD, uniqueness, access control, limits, validation boundary, sharing, import, export, parsing, builder round-trip and admin management; verify the status codes match `app/main.py`.
- [x] 2.2 Write `specs/providers/spec.md` with provider types, implicit Ollama, scope resolution, admin and personal connections, secrets, model listing, authorization, registry sync and pricing; verify the defaults match `app/config.py`.

## 3. Validate

- [x] 3.1 Run `openspec validate seed-data-specs --strict` and fix every warning, including requirement descriptions over 500 characters and scenarios without four hashtags.
- [ ] 3.2 Open the PR with `Change: seed-data-specs`, verify the guards, tests and OpenSpec jobs pass, and confirm the two spec files are the only content changes.

## Workflow follow-up

- Archive this change in the completing PR with `openspec archive seed-data-specs --yes`, then run `openspec validate --archived` and `openspec validate --specs --strict`.
- Merge with a merge commit and verify `openspec list --specs` shows `schemas` and `providers`.
- Start `change/seed-surface-specs` for `i18n`, `admin` and `deployment`.

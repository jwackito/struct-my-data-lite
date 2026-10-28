# Tasks

## 1. Sources

- [x] 1.1 Read the i18n module, dictionaries and script, the admin routes and tests, and the deployment configuration, workflows and tests; verify each requirement candidate has a code path or a test.

## 2. Capability specs

- [x] 2.1 Write `specs/i18n/spec.md` with language selection, fallback, dictionary integrity, server and client rendering, the switcher and dictionary endpoints; verify the selection order matches `app/i18n.py` and `app/static/i18n.js`.
- [x] 2.2 Write `specs/admin/spec.md` with authorization, users, usage, failures, job inspection, model administration, grants and override; verify the status codes and filters match `app/main.py`.
- [x] 2.3 Write `specs/deployment/spec.md` with topology, image, hardening, configuration, migrations, health, startup, CI, release and defaults; verify the guarantees match `Dockerfile`, both compose files and the workflows.

## 3. Validate

- [x] 3.1 Run `openspec validate seed-surface-specs --strict` and fix every warning, including requirement descriptions over 500 characters and scenarios without four hashtags.
- [x] 3.2 Open the PR with `Change: seed-surface-specs`, verify the guards, tests and OpenSpec jobs pass, and confirm the three spec files are the only content changes.

## Workflow follow-up

- Archive this change in the completing PR with `openspec archive seed-surface-specs --yes`, then run `openspec validate --archived` and `openspec validate --specs --strict`.
- Merge with a merge commit and verify `openspec list --specs` shows all nine capabilities.
- Remove the transitional legacy `type/<n>-<slug>` branch acceptance from `pr-guards.yml` in a `chore` change.

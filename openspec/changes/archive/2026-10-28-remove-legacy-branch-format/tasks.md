# Tasks

## 1. Tighten the guard

- [x] 1.1 Update `.github/workflows/pr-guards.yml` so only `change/<change-name>` branches pass, removing the legacy `type/<n>-<slug>` branch and its warning; verify the regex accepts `change/remove-legacy-branch-format` and rejects `feat/42-example`.
- [x] 1.2 Run `ruby -ryaml` on the workflow and confirm the change is valid.

## 2. Land

- [x] 2.1 Open the PR with `Change: remove-legacy-branch-format`, verify the guards, tests and OpenSpec jobs pass, and confirm only the workflow changed.

## Workflow follow-up

- Archive this change in the completing PR with `openspec archive remove-legacy-branch-format --yes --skip-specs`.
- Merge with a merge commit and verify a legacy branch now fails the guard.

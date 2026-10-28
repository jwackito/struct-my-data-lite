# Tasks

## 1. Bootstrap the guard change (PR A)

- [x] 1.1 Create the issue "Adopt the OpenSpec contribution workflow" (opened as #13) and verify it is open before the PR; it closes on merge.
- [x] 1.2 Update `.github/workflows/pr-guards.yml` to accept both `change/<name>` and legacy `type/<n>-<slug>` branches, make the linked-issue step optional, and allow full Conventional Commits plus `Merge`/`Revert` subjects; verified with `ruby -ryaml` and regex fixtures.
- [x] 1.3 Add `.opencode/` to `.gitignore`; verified `git status --short` no longer lists it.
- [x] 1.4 Push `chore/13-openspec-guards`, open PR #14 with `Closes #13`, and verify the branch, commit-format and issue steps pass in CI.
- [x] 1.5 Merge PR #14 with a merge commit; verified `main` contains the new guard and #13 is closed.

## 2. Commit the OpenSpec root and config (PR B)

- [x] 2.1 Commit `openspec/config.yaml`, `openspec/specs/.gitkeep`, `openspec/changes/archive/.gitkeep` and the change directory; verified `openspec list --json` resolves the repo root and the change validates.
- [x] 2.2 Populate `openspec/config.yaml` with project context, per-artifact rules and apply/archive guidance; verified `openspec doctor` and `openspec context` run without errors.
- [x] 2.3 Confirm the change's `.openspec.yaml` keeps `skip_specs: true`; verified `openspec status` reports `specs: skipped` and every requested artifact `done`.
- [x] 2.4 Pin Node.js 20.19+ and `@fission-ai/openspec@1.14.3` in the docs and CI; verified the npm registry serves 1.14.3 and the CI step uses the same specifier.

## 3. Write the contributor documentation (PR B)

- [x] 3.1 Rewrite `CONTRIBUTING.md` around the change lifecycle, including the branch/issue table, the lightweight path, setup, tests, architecture map, CC commits, archive and security; verified links and the commands against the repo.
- [x] 3.2 Add `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1) with a real enforcement contact (@jwackito); verified the link from `CONTRIBUTING.md` resolves.
- [x] 3.3 Add `SECURITY.md` with supported versions, private reporting and the advisory carve-out; verified the link from `CONTRIBUTING.md` resolves and the scope matches the sandbox, auth and upload ownership.
- [x] 3.4 Rewrite `.github/pull_request_template.md` to require the change name, validation, archive state, tests and AI disclosure; verified the checklist covers each gate.
- [x] 3.5 Update the bug and feature issue templates so bugs remain intake and features point to a change.
- [x] 3.6 Update `AGENTS.md` to require an OpenSpec change before code, full Conventional Commits and no per-file commit rule; verified it matches `CONTRIBUTING.md`.
- [x] 3.7 Update `README.md` to link `CONTRIBUTING.md` and remove the dead `specs/` and `deploy/` references; verified `grep` finds no stale path.

## 4. Enforce the workflow in CI (PR B)

- [x] 4.1 Add `scripts/check_change.py` implementing branch-to-change mapping, diff membership and archived-state checks; add `tests/test_check_change.py`; verified 19 tests pass.
- [x] 4.2 Add `.github/workflows/openspec.yml` running the pinned validation through `scripts/check_change.py`; verified the YAML parses and the job is triggered by `pull_request`.
- [ ] 4.3 Verify the OpenSpec job passes on PR B and rejects a branch without a matching change directory.

## 5. Validate and integrate (PR B)

- [x] 5.1 Run the full suite with `python -m pytest -q` in the app container; verified 383 passed, 3 skipped.
- [x] 5.2 Run `openspec validate adopt-openspec-workflow --strict` and `openspec validate --specs --strict`; verified both pass with `skip_specs` reported.

## Workflow follow-up

- Archive this change in the completing PR: `openspec archive adopt-openspec-workflow --yes --skip-specs`, then re-run `openspec validate --archived`.
- Open and merge PR B with `Archives: adopt-openspec-workflow`; verify `openspec list` on `main` is empty and the archived directory exists.
- After PR B merges, create a scratch `change/docs-verify-lightweight` with `skip_specs: true`, confirm the OpenSpec job passes, then delete the branch without merging.
- Open PR C as `change/seed-core-specs` for `auth`, `documents`, `extraction`, `batches`, `schemas`, `providers`, `i18n`, `admin` and `deployment`.
- After PR C lands, remove the legacy `type/<n>-<slug>` acceptance from `pr-guards.yml` in a `chore` change.

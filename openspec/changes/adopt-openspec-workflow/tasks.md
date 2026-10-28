# Tasks

## 1. Bootstrap the guard change (PR A)

- [ ] 1.1 Create the issue "Adopt the OpenSpec contribution workflow" and record its number; verify `gh issue view <N> --json state` reports `OPEN`.
- [ ] 1.2 Update `.github/workflows/pr-guards.yml` to accept both `change/<name>` and legacy `type/<n>-<slug>` branches, make the linked-issue step optional, and allow full Conventional Commits plus `Merge`/`Revert` subjects; verify the YAML parses and the diff matches the design in D6.
- [ ] 1.3 Add `.opencode/` to `.gitignore`; verify `git status --short` no longer lists it.
- [ ] 1.4 Push `chore/<N>-openspec-guards`, open PR A with `Closes #N`, and verify the branch, commit-format and issue steps pass in CI.
- [ ] 1.5 Merge PR A with a merge commit; verify `main` contains the new guard and the issue is closed.

## 2. Commit the OpenSpec root and config (PR B)

- [ ] 2.1 Commit `openspec/config.yaml`, `openspec/specs/.gitkeep`, `openspec/changes/archive/.gitkeep` and the change directory; verify `openspec list --json` resolves the repo root and `openspec validate adopt-openspec-workflow --strict` passes.
- [ ] 2.2 Populate `openspec/config.yaml` with project context, per-artifact rules and apply/archive guidance; verify `openspec doctor` and `openspec context` run without errors.
- [ ] 2.3 Confirm the change's `.openspec.yaml` keeps `skip_specs: true` and that `openspec status --change adopt-openspec-workflow --json` reports `specs: skipped` and `tasks: ready`; verify with the status command.
- [ ] 2.4 Pin Node.js 20.19+ and `@fission-ai/openspec@1.14.3` in the docs and CI; verify `openspec --version` reports `1.14.3` locally and the CI step uses the same specifier.

## 3. Write the contributor documentation (PR B)

- [ ] 3.1 Rewrite `CONTRIBUTING.md` around the change lifecycle, including the branch/issue table, the lightweight path, setup, tests, architecture map, CC commits, archive and security; verify every command shown runs as written.
- [ ] 3.2 Add `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1) with real enforcement contact details; verify the link from `CONTRIBUTING.md` resolves and no placeholder remains.
- [ ] 3.3 Add `SECURITY.md` with supported versions, private reporting and the advisory carve-out; verify the link from `CONTRIBUTING.md` resolves and the scope list matches `app/schema_sandbox.py`, auth and upload ownership.
- [ ] 3.4 Rewrite `.github/pull_request_template.md` to require the change name, validation, archive state, tests and AI disclosure; verify the rendered checklist covers each gate in D5.
- [ ] 3.5 Update the bug and feature issue templates so bugs remain intake and features point to a change; verify both still render on GitHub.
- [ ] 3.6 Update `AGENTS.md` to require an OpenSpec change before code, full Conventional Commits and no per-file commit rule; verify it no longer contradicts `CONTRIBUTING.md`.
- [ ] 3.7 Update `README.md` to link `CONTRIBUTING.md` and remove the dead `specs/` and `deploy/` references; verify `grep -n` finds no stale path.

## 4. Enforce the workflow in CI (PR B)

- [ ] 4.1 Add `scripts/check_change.py` implementing branch-to-change mapping, diff membership and archived-state checks; add `tests/test_check_change.py` and verify `python -m pytest tests/test_check_change.py -q` passes.
- [ ] 4.2 Add `.github/workflows/openspec.yml` running the pinned `validate "$CHANGE" --strict`, `validate --specs --strict` and `python scripts/check_change.py`; verify the YAML parses and the job is triggered by `pull_request`.
- [ ] 4.3 Verify the OpenSpec job passes on PR B and fails on a scratch branch with no change directory.

## 5. Validate and integrate (PR B)

- [ ] 5.1 Run the full suite with `python -m pytest -q` (or `docker compose exec app python -m pytest -q`) and verify it is green.
- [ ] 5.2 Run `openspec validate adopt-openspec-workflow --strict`, `openspec validate --specs --strict` and `openspec validate --archived`; verify all pass.
- [ ] 5.3 Run the end-to-end check: create a scratch `change/docs-verify-lightweight` with `skip_specs: true`, validate it, verify the OpenSpec job recognises it, then delete the branch without merging.

## Workflow follow-up

- Archive this change in the completing PR: `openspec archive adopt-openspec-workflow --yes --skip-specs`, then re-run `openspec validate --archived`.
- Open and merge PR B with `Archives: adopt-openspec-workflow`; verify `openspec list` on `main` is empty and the archived directory exists.
- Open PR C as `change/seed-core-specs` for `auth`, `documents`, `extraction`, `batches`, `schemas`, `providers`, `i18n`, `admin` and `deployment`.
- After PR C lands, remove the legacy `type/<n>-<slug>` acceptance from `pr-guards.yml` in a `chore` change.

# Contributing

Thanks for your interest in Struct My Data.

## Workflow

1. **Issue first.** Open an issue describing the change before starting work.
2. **Branch.** Work on a branch named `type/<issue-number>-<short-slug>`,
   e.g. `feat/42-per-user-concurrency`, `fix/57-document-ownership`.
   Allowed types: `feat`, `fix`, `chore`, `docs`, `test`.
   Maintainers branch in this repo; outside contributors fork.
3. **Open a PR** into `main`, referencing the issue with `Closes #<issue>`.
4. **Review and merge.** The PR needs CI green and a maintainer approval, and
   lands as a **merge commit** (never squash: the per-file commit trail is part
   of the project's history).

`main` is **pull-request only**. There is no server-side branch protection on
the GitHub Free plan, so the rule is enforced by:

- `.githooks/pre-push` — refuses pushes to `main`. Enable once per clone:
  ```bash
  git config core.hooksPath .githooks
  ```
- `.github/workflows/pr-guards.yml` — branch name, `Closes #N` on an open issue,
  and commit message format.
- `.github/workflows/main-guard.yml` — fails the run if a commit reaches `main`
  without an associated pull request (detection, not prevention).

A GitHub Pro (or public) repo would allow real rulesets; until then, a bypass
is visible in CI but not blocked.

## Commits

- Message format `type: short description` (`test`, `feat`, `fix`, `chore`,
  `docs`).
- Keep commits small and focused; prefer one logical change per commit.

## Pull requests

Every PR must:

- Reference an existing issue (`Closes #N`).
- Pass CI (tests + shell syntax check).
- Have at least one approval and resolved conversations.

## Development

See `README.md` for running the stack and the test suite. Tests run with
`python -m pytest` inside the app container.

## Security

- Never commit secrets. Use `.env.example` to document required variables.
- Do not weaken the schema sandbox (`app/schema_sandbox.py`).

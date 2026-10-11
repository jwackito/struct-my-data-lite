# Contributing

Thanks for your interest in Struct My Data.

## Workflow

1. **Issue first.** Open an issue describing the change before starting work.
2. **Fork + branch.** Create a branch named `type/<issue-number>-<short-slug>`,
   e.g. `feat/42-per-user-concurrency`, `fix/57-document-ownership`.
   Allowed types: `feat`, `fix`, `chore`, `docs`, `test`.
3. **Open a PR** into `main`, referencing the issue with `Closes #<issue>`.

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

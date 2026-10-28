# Contributing to Struct My Data (Lite)

Thanks for helping. Struct My Data turns documents into structured JSON with an
LLM, and the lite edition is the self-hosted, open-source core.

Two documents sit next to this one:

- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — the behaviour we expect.
- [SECURITY.md](SECURITY.md) — how to report a vulnerability privately.

## What belongs here

This repository is the **lite** edition: single instance, multi-user, no billing.
The application is the shared core for other editions, so keep shared code
edition-neutral:

- Edition-specific behaviour is registered from `app/saas.py` through
  `app/hooks.py`. Lite registers nothing.
- Do not add SaaS assumptions (plans, balances, tenants) to shared modules.
- If a change only makes sense for a hosted edition, open an issue first and
  describe the seam you need instead of forking the shared path.

## Ways to contribute

| Contribution | Start with |
|---|---|
| Bug report | Open a bug issue using the template |
| Feature or behaviour change | An OpenSpec change; open an issue first if you want to discuss the problem |
| Documentation, typo, translation | A lightweight OpenSpec change |
| New parser or provider | An OpenSpec change; see the map below |
| Review, triage, reproduction | Comment on an issue or pull request |
| Security issue | **Never a public issue** — see [SECURITY.md](SECURITY.md) |

## How contribution works: the change is the unit

Every pull request carries an [OpenSpec](https://openspec.dev) change under
`openspec/changes/<change-name>/`. The change is the plan: it records why the
work exists, what behaviour changes, and how completion is verified. Code and
specs land together.

| Change | Artifacts | Branch |
|---|---|---|
| Behaviour change (feature, fix, refactor, perf, CI, build) | `proposal.md`, `specs/<capability>/spec.md`, `design.md` when cross-cutting, `tasks.md` | `change/<change-name>` |
| Docs, tests, chore, style | `proposal.md`, `tasks.md`, `.openspec.yaml` with `skip_specs: true` | `change/<change-name>` |

GitHub issues are the front door for bug reports and open-ended discussion. The
change replaces the issue as the planning record, so a behaviour change does not
need an issue. A bug fix may still say `Closes #N`.

Rules of thumb:

- One change per pull request. If the diff needs two proposals, split it.
- Prefer several small PRs over one large one. A change may span PRs; only the
  final PR archives it.
- If a change alters an API, an environment variable, a migration or stored data,
  say **BREAKING** in the proposal and call it out in the PR.

## OpenSpec in five minutes

OpenSpec needs **Node.js 20.19 or newer**. Install the pinned CLI:

```bash
npm install -g @fission-ai/openspec@1.14.3
# or, without a global install:
npx -y @fission-ai/openspec@1.14.3 --version
```

Create a change:

```bash
git switch -c change/add-csv-delimiter-option
openspec new change add-csv-delimiter-option
openspec status --change add-csv-delimiter-option
```

Fill the artifacts. `openspec instructions <artifact> --change <name>` prints the
current template and rules. Then validate:

```bash
openspec validate add-csv-delimiter-option --strict
```

Work through `tasks.md`, checking each box as you verify it, and run the tests
named in the tasks. When the last task is done, archive the change in the same
PR:

```bash
openspec archive add-csv-delimiter-option --yes
```

For a docs-only or tooling change, set `skip_specs: true` in
`openspec/changes/<name>/.openspec.yaml` and archive with `--skip-specs`. That
still gives the PR a proposal and tasks, without inventing a requirement.

What goes where:

| Artifact | Answers |
|---|---|
| `proposal.md` | Why now, what changes, which capabilities, what is out of scope |
| `specs/<capability>/spec.md` | What the system must do, as requirements and scenarios |
| `design.md` | How, when the change is cross-cutting or has real trade-offs |
| `tasks.md` | The ordered, verifiable steps |

## Which capability?

Capabilities are durable behaviours, not tasks. Reuse an existing path; do not
invent a near-duplicate.

| Area | Capability path |
|---|---|
| Authentication, sessions, API tokens | `auth` |
| Uploads, storage, ownership | `documents` |
| Parsing and LLM extraction | `extraction` |
| Batches, retries, cancellation | `batches` |
| Schema builder, saved schemas, sandbox | `schemas` |
| Provider connections and model selection | `providers` |
| Usage, cost and pricing | `usage` |
| Admin users, failures, system views | `admin` |
| English and Spanish UI | `i18n` |
| Compose, images, migrations in production | `deployment` |

If no path fits, name a new durable capability in the proposal
(`document-parsing`, not `add-docx-fallback`). Baseline specs are being seeded;
until a capability exists, your change creates it under `openspec/specs/`.

## Set up the project

You need Docker and Docker Compose. Ollama is optional for the test suite and
required only for manual extraction.

### Docker (recommended)

```bash
mkdir -p etc && chmod 700 etc
cp .env.example etc/.env      # required: compose declares env_file
docker compose up -d --build
docker compose exec app python -m alembic upgrade head
docker compose exec app python -m pytest -q
```

Generate the two secrets the app expects and put them in `etc/.env`:

```bash
docker compose exec app python -c \
  "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
openssl rand -hex 32
```

The first value is `APP_SECRET_KEY`; the second is `JWT_SECRET`. `JWT_SECRET` is
mandatory when `ENV` is not `dev`.

### Host Python, containers for PostgreSQL

```bash
docker compose up -d db test-db
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/structmydata_test
export MIGRATION_DB_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/structmydata_test_migrations
export MIGRATION_ADMIN_DB_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/postgres
python -m pytest -q
```

The migration tests create `structmydata_test_migrations` when it is missing.

### Ollama (optional)

For manual extraction, run Ollama on the host and make it reachable from the
containers:

```bash
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

Set a text and a vision model in `etc/.env` (`OLLAMA_MODEL`,
`OLLAMA_VISION_MODEL`). Tests in `tests/integration/test_ollama.py` skip
themselves when Ollama is not reachable.

### Troubleshooting

- `docker compose` fails with a missing env file: create `etc/.env`.
- `storage/` is owned by root after running the container: run
  `sudo chown -R "$USER" storage`, or run the tests inside the container.
- Ports: app `8080`, `db` `5432`, `test-db` `5433`, Ollama `11434`.
- Code changes hot-reload; rebuild only when `requirements.txt` changes.

## Tests

```bash
# whole suite
docker compose exec app python -m pytest -q

# one file, one test
docker compose exec app python -m pytest tests/test_parsers.py -q
docker compose exec app python -m pytest tests/test_parsers.py::test_pdf -q
```

Every behaviour change starts with a failing test. Unit tests need PostgreSQL;
Ollama integration tests skip. There is no coverage or type-check gate. CI runs
the full suite, the PR guards and the OpenSpec validation job.

If a test needs a database fixture, reuse the fixtures in `tests/conftest.py`
instead of creating an engine per test.

## Where changes go

| Change | Code | Tests |
|---|---|---|
| Parser | `app/parsers/<name>.py`, register in `app/parsers/factory.py` | `tests/test_parsers.py` |
| Provider | `app/providers/<name>.py`, `factory.py`, `connections.py`, `pricing.py` | `tests/test_providers.py`, `tests/test_factory_models.py` |
| API route | `app/main.py` | nearest `tests/test_*.py`, `tests/integration/test_api.py` |
| Table or column | `app/models.py`, one Alembic revision | `tests/integration/test_migrations.py` |
| UI text | `app/i18n/en.json` **and** `es.json`, templates, `app/static/i18n.js` | `tests/test_i18n.py` |
| Edition behaviour | `app/saas.py`, `app/hooks.py` | `tests/test_plan_hooks.py` |
| Queue and concurrency | `app/queue/`, `app/processing.py` | `tests/test_job_queue.py` |
| Auth and ownership | `app/auth.py`, ownership checks in `app/main.py` | `tests/test_auth.py`, `tests/test_tenant_isolation.py` |

`app/main.py` is the route hub. Keep additions next to related routes and avoid
moving unrelated code in a feature PR.

## Migrations

```bash
docker compose exec app python -m alembic revision --autogenerate -m "add error detail"
```

Review the generated file. Autogenerate misses index changes, data migrations
and constraint renames. Add a downgrade. Never edit a migration that has already
been applied outside your branch. Migration tests run `alembic upgrade head`
against a throwaway database.

Production applies migrations with `python -m scripts.migrate`, never bare
`alembic`.

## Translations

The UI ships in English and Spanish. Keys are the English strings themselves.

- Add the key to **both** `app/i18n/en.json` and `app/i18n/es.json`.
  `tests/test_i18n.py` fails if the key sets differ or a value is empty.
- Client-side text uses `data-i18n` attributes or `window.t()`.
- Server-rendered text uses `t()` from `app/i18n.py`.
- New languages need a resolver, a dictionary and a switcher entry; treat that as
  a feature change, not a docs change.

## Dependencies

- Runtime dependencies live in `requirements.in`; `requirements.txt` is a
  hash-pinned lock. Never hand-edit the lock.
- Regenerate with `tools/lock.sh requirements.in` inside the running container.
- The lite edition installs nothing from `requirements-saas.txt`.
- Prefer the standard library. A new runtime dependency needs a reason in the
  issue or proposal, and a note in the PR about image size and licensing.

## Style

- PEP 8, four spaces, no tabs. Match the surrounding code.
- Type hints on public functions; async all the way through request paths.
- Keep functions small and name things for behaviour, not for the implementation.
- No formatter or linter is configured yet. Do not reformat unrelated code.
- Tests are `tests/test_*.py`, use `pytest.mark.asyncio` for async tests, and
  reuse the fixtures in `tests/conftest.py`.

## Commits

Use Conventional Commits:

```text
feat(parsers): add legacy .doc fallback
fix(auth)!: reject tokens without exp
docs: document the test database ports
refactor(providers): extract retry helper
perf(pricing): cache model lookups
chore(deps): bump instructor
```

| Type | Use for |
|---|---|
| `feat` | A new capability |
| `fix` | A bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no behaviour change |
| `refactor` | Restructuring, no behaviour change |
| `perf` | Performance |
| `test` | Tests only |
| `build` | Dependencies, Dockerfile, lock files |
| `ci` | Workflows and CI configuration |
| `chore` | Housekeeping |
| `revert` | Reverting a commit |

Scopes are optional but recommended: `auth`, `jobs`, `batches`, `parsers`,
`providers`, `schema`, `pricing`, `i18n`, `ui`, `admin`, `db`, `deploy`, `deps`.

- Use the imperative mood, lowercase, no trailing period.
- A breaking change uses `!` and a `BREAKING CHANGE:` footer.
- Keep commits focused; tests before implementation where practical.
- `Merge` and `Revert "..."` subjects are allowed.
- Never squash: merges are merge commits, because the trail is the history.

## Changelog

Add an entry under `## Unreleased` in `CHANGELOG.md` for `feat`, `fix`,
`refactor` and `perf`. Use the existing sections: Added, Changed, Fixed,
Removed, Security. Docs, tests, chores and style do not need an entry.

Releases are tagged `vX.Y.Z-lite` and built from the tag by CI.

## Pull requests

Open the PR early as a draft if you want feedback. Before marking it ready:

- The branch is `change/<change-name>` and the change directory is in the diff.
- `openspec validate <change-name> --strict` passes.
- Every task is checked; if this PR completes the change, it is archived and the
  body says `Archives: <change-name>`.
- `python -m pytest -q` passes locally, or the equivalent command in Docker.
- New UI text is in both language files.
- Docs and changelog are updated when behaviour changed.
- No secrets, keys or `etc/.env` content are committed.
- AI-assisted work is disclosed in the body (see below).

Keep PRs small. A diff of a few hundred lines is easier to review than a
thousand. If a change naturally splits into independent steps, open more than
one PR and keep the change active until the last one.

Reviews are best effort; expect a first response within about a week. A PR with
no activity for 30 days may be closed with an invitation to reopen. Approval and
green CI are required; maintainers merge with a merge commit. Authors do not
self-merge.

## Security

- Never commit secrets. `etc/` is gitignored; `.env.example` documents variables.
- Do not weaken `app/schema_sandbox.py`. Any change there needs tests for the
  escape it prevents.
- Keep ownership checks on documents, jobs, batches, WebSockets and schemas.
- Report vulnerabilities privately, never in a public issue. See
  [SECURITY.md](SECURITY.md).
- Security fixes are the one exception to the public-change rule: work through a
  private advisory, and land the change with the fix after disclosure.

## AI-assisted contributions

AI-assisted contributions are welcome under the same contract as any other work.

- Disclose the tool in the PR body, one line is enough.
- You are responsible for the code, its licences and its tests.
- Ship the same OpenSpec artifacts; there is no relaxed AI lane.
- Agents must use the OpenSpec workflow before writing code.
- Do not open mass-generated issues or PRs. Low-effort PRs may be closed without
  review.

## License

Struct My Data (Lite) is MIT licensed. By contributing you agree that your work
is licensed under the same terms. There is no CLA and no sign-off requirement.

## Maintainers

- Triage issues, label `good first issue`, and turn accepted features into
  changes.
- Seed and maintain baseline specs in `openspec/specs/`.
- Upgrade OpenSpec as a `chore` change and run `openspec validate --all --strict`.
- Releases: update `CHANGELOG.md`, tag `vX.Y.Z-lite`, let CI publish the image.
- Security fixes may bypass the public-change guard; document the advisory in the
  merge notes.

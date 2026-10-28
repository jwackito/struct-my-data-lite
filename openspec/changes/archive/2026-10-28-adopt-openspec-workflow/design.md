# Design

## Context

See `proposal.md` for motivation. The constraints that shape the approach:

- `main` is pull-request only. Merges are merge commits, never squash, so the
  per-branch trail is permanent history.
- The repository is on GitHub Free: no server-side branch protection. Rules are
  enforced by `.github/workflows/pr-guards.yml`, `main-guard.yml` and the
  `pre-push` hook.
- The current guard accepts only `type/<n>-<slug>` branches, requires `Closes #N`
  on an open issue, and allows five commit types. History already contains
  `refactor:`, `ci:`, `build:` and `Revert`, which the guard rejects.
- Tests run on pytest + PostgreSQL; there is no Node toolchain in the project.
- OpenSpec 1.14.3 is installed, requires Node.js 20.19+, uses the `spec-driven`
  schema, and supports `skip_specs: true`, `archive --skip-specs` and
  `validate --archived`.
- `openspec/` is scaffolded but untracked; `openspec/specs/` is empty.

## Goals / Non-Goals

**Goals:**

- One contribution contract that applies to every pull request.
- Proportional effort: full artifacts for behaviour, a lightweight change for
  docs, tests, chores and style.
- Durable specs updated in the same merge as the behaviour they describe.
- A bootstrap that does not fail its own CI because the workflow file changes.
- Small, reviewable pull requests with merge-commit history.

**Non-Goals:**

- Seeding baseline capability specs (follow-up change).
- A custom OpenSpec schema. The built-in `skip_specs` marker covers the
  lightweight path without another schema to maintain.
- A bot that opens archive pull requests. Archive happens in the completing PR
  for v1.
- Mechanically enforcing AI disclosure. It is a disclosure requirement, not a
  gate.
- Any application runtime or dependency change.

## Decisions

### D1. The OpenSpec change is the unit of contribution; issues are optional

Every PR maps to one change directory. GitHub issues remain the front door for
bug reports and open-ended discussion, but the change replaces the issue as the
planning record. Bug fixes may still say `Closes #N`.

*Alternatives:* keep the issue requirement alongside changes (duplicate
tracking, three identifiers per PR); drop issues entirely (loses a front door
for non-contributors).

### D2. Branch `change/<change-name>`; Conventional Commits

The branch maps 1:1 to the artifact directory, so CI can derive the change name
without parsing the PR body. Commit types keep the intent visible:
`feat(parsers): ...`, `fix(auth)!: ...`.

During the bootstrap, `pr-guards` accepts both `change/<name>` and the legacy
`type/<n>-<slug>` form, and the legacy form is removed once the workflow lands.

*Alternatives:* `type/<change-name>` (redundant with the change name);
`type/<n>-<slug>` plus a `Change:` line (two identifiers, more parsing).

### D3. Two artifact shapes, one schema

- Behaviour change: `proposal.md`, `specs/<capability>/spec.md`, `design.md` when
  cross-cutting, `tasks.md`.
- Docs/test/chore/style: `proposal.md`, `tasks.md`, `.openspec.yaml` with
  `skip_specs: true`; no specs or design; `archive --skip-specs`.

*Alternatives:* a project-local lightweight schema (experimental, extra
maintenance); exempting docs from OpenSpec (contradicts the decision that the
change is the unit).

### D4. Archive in the PR that completes the change

A change may span several PRs. The PR that checks the last task runs
`openspec archive <name> --yes`, which moves the directory under
`openspec/changes/archive/` and applies the spec deltas. Earlier PRs leave the
change active and must validate. `validate --archived` is the check that tasks
are complete.

*Alternatives:* archive after merge (specs lag, needs maintainer follow-through);
a bot-opened archive PR (more automation than v1 needs).

### D5. CI validates the named change, the archive, and the specs

A dedicated `openspec` job:

1. `openspec validate "$CHANGE" --strict` for the PR's change.
2. `openspec validate --specs --strict` for durable specs.
3. `scripts/check_change.py` maps branch to change, asserts the path is touched
   in the diff, and runs `validate --archived` when the change is archived.

Validating the named change instead of `--all` prevents one broken active change
from blocking unrelated PRs.

*Alternatives:* `validate --all` (cross-PR coupling); relying on a local hook only
(bypassable).

### D6. Bootstrap in two PRs

GitHub evaluates the workflow from the pull request, so a strict `change/*` regex
would reject the PR that introduces it. Sequence:

1. **PR A**, branch `chore/<N>-openspec-guards`, under the old rules: accept both
   branch forms, make the issue check optional, adopt full Conventional Commits,
   keep the direct-push guard.
2. **PR B**, branch `change/adopt-openspec-workflow`, under the new rules:
   OpenSpec root and config, CONTRIBUTING/CoC/SECURITY, templates, OpenSpec CI
   job, archives itself.
3. **PR C**, branch `change/seed-core-specs`: baseline capabilities, then remove
   the legacy branch regex.

*Alternative:* merge PR A with a red guard (rejected — it normalises bypassing
CI).

### D7. Security fixes bypass the public change requirement

A public `change/fix-auth-bypass` advertises the vulnerability. Security work
uses a private advisory and a private fork; the change is authored there and
lands with the fix after disclosure. Maintainers may bypass the guard for that
merge. This is the one documented exception to "every PR carries a change."

*Alternative:* public change with redacted text (directory names and diffs still
leak the area of the bug).

### D8. AI contributes under the same contract

AI-assisted PRs disclose the tool in the body and ship the same artifacts. Agents
use the OpenSpec skills for ergonomics; humans use the CLI. There is no relaxed
AI lane and no author-based gating.

*Alternatives:* OpenSpec only for AI-authored PRs (unenforceable, partial spec
tree, rewards non-disclosure); human exemption (same problem inverted). An
optional `agent/<change-name>` branch prefix is allowed for reviewer context but
changes nothing in CI.

### D9. Pin the CLI

Document and use Node.js 20.19+ and `@fission-ai/openspec@1.14.3`. CI installs the
same version through `npx`. Upgrades are a `chore` change that runs
`openspec validate --all --strict` before merging.

*Alternative:* `@latest` (schema and validation drift between contributors and
CI).

### D10. Populate the OpenSpec config

`openspec/config.yaml` gains project context and per-artifact rules: the Python
stack, the edition seam, spec style (SHALL, one behaviour per requirement, four
hashtag scenarios), task verification requirements, and apply/archive guidance.
This keeps human and agent artifacts consistent without repeating the rules in
every prompt.

## Risks / Trade-offs

- **Self-referential CI** → transitional superset branch regex in PR A, removed
  in PR C.
- **Node/CLI friction for contributors** → pinned `npx` command, a five-minute
  guide, and the lightweight docs path.
- **Concurrent archives touch the same spec file** → rebase before archiving;
  serialise related PRs; keep changes small.
- **Spec drift while a change stays active** → archive in the completing PR and
  enforce `validate --archived`.
- **Empty baseline specs** → PR C seeds core capabilities before the doors open.
- **Security leak via public artifacts** → private advisory carve-out.
- **Larger review surface** → design only for cross-cutting work; PR size guidance.
- **Private repo today** → fork CI approval only matters after going public.

## Migration Plan

1. Land PR A under the old rules; CI green; merge commit.
2. Rebase `change/adopt-openspec-workflow` on the new `main`, land PR B, archive
   the change, merge.
3. Land PR C, then remove the transitional legacy branch regex.
4. Verify with one docs-only change and one behaviour change.

Rollback: revert PR B, then PR A, both as merge commits. OpenSpec is additive and
has no runtime effect. If archived specs were moved, the revert restores them.

## Open Questions

None that change the approach or task breakdown. Deferred, safely: whether to
automate archive pull requests with a bot, and whether to enforce AI disclosure
through a commit trailer rather than the PR body.

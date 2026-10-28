# Proposal

## Why

Open-source contributors currently follow a maintainer-shaped process — issue-first,
numbered branches, per-file commits — while architectural intent lives only in
issues and commit history. There is no durable record of behaviour, so reviewers
and future contributors reverse-engineer requirements from code. Making OpenSpec
changes the unit of contribution keeps `openspec/specs/` current, makes intent
reviewable before code, and gives AI-assisted and human contributions the same
contract instead of two standards.

## What Changes

- OpenSpec becomes the unit of contribution: every pull request carries a change
  under `openspec/changes/<name>/`, or the archived path when it completes one.
- Behaviour changes ship a proposal, a spec delta and tasks; `design.md` is added
  only for cross-cutting work.
- Docs, tests, chores and style-only changes ship a lightweight change: proposal
  plus tasks with `skip_specs: true`, no specs or design.
- Branches become `change/<change-name>`; commit messages stay Conventional
  Commits (`type(scope)!: subject`).
- GitHub issues become bug intake and discussion. The change replaces the issue
  as the planning record, so behaviour changes no longer require one.
- The pull request that completes the last task archives the change with
  `openspec archive`, updating `openspec/specs/` in the same merge.
- CI validates the named change, requires completed tasks for archived changes,
  and validates the durable specs. The CLI is pinned.
- `CONTRIBUTING.md` is rewritten around the change lifecycle; `CODE_OF_CONDUCT.md`
  and `SECURITY.md` are added and linked.
- The pull request template, issue templates, `AGENTS.md` and `README.md` are
  updated to match, including removal of stale `specs/` and `deploy/` references.
- **BREAKING** for contributors: `type/<issue>-<slug>` branches, mandatory
  `Closes #N`, and the five-type commit allowlist stop being the gate.
- Security fixes use the private advisory flow; no public change or pull request
  before disclosure.
- AI-assisted work is disclosed in the pull request body and follows the same
  artifact requirements. There is no relaxed AI lane.
- Baseline capability specs for the existing system are seeded in a follow-up
  change, out of scope here.

## Capabilities

### New Capabilities

None. This change alters the contribution workflow, CI and documentation, not
application behaviour. The change's `.openspec.yaml` sets `skip_specs: true`.

### Modified Capabilities

None.

## Impact

- **CI and tooling**: `.github/workflows/pr-guards.yml` (branch, issue and commit
  rules), a new OpenSpec validation job, `.githooks/`, and a change-check script.
- **Templates**: `.github/pull_request_template.md`, issue templates, optional
  issue-template config.
- **Documentation**: `CONTRIBUTING.md` (rewrite), new `CODE_OF_CONDUCT.md` and
  `SECURITY.md`, `AGENTS.md`, `README.md`.
- **OpenSpec root**: commit `openspec/` (currently untracked), populate
  `openspec/config.yaml` with project context and artifact rules, and commit the
  change history.
- **Contributor prerequisites**: Node.js 20.19+ and OpenSpec 1.14.3 for authoring
  and validating changes. No new runtime dependency for the application.
- **Bootstrap order**: the guard change lands first under the current rules; the
  documentation and OpenSpec artifacts land second under the new rules.

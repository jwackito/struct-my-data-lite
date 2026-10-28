# Migrating a project to the OpenSpec workflow

This document describes how to move a repository from issue- or branch-driven
planning to OpenSpec changes. It covers the decisions to make first, the order
that works, the CI bootstrap problem, and the failure modes worth avoiding.

The worked example is structmydata-lite, a small self-hosted Python project,
migrated in October 2026. The day-to-day rules live in
[CONTRIBUTING.md](../CONTRIBUTING.md); this document is about the migration
itself.

## 1. The target in one page

| Before | After |
|---|---|
| An issue, branch or PR is the plan | An OpenSpec change under `openspec/changes/<name>/` is the plan |
| Branch names describe the work | `change/<change-name>` maps 1:1 to the artifact |
| Issues gate every PR | Issues are bug intake; the change replaces them as the plan |
| Behaviour lives in code and tests | `openspec/specs/` records observable behaviour |
| Docs and typo fixes skip planning | A lightweight change: proposal + tasks, `skip_specs: true` |
| CI checks tests | CI checks the change, the archive and the specs |

```text
behaviour change   proposal + specs (+ design) + tasks
docs / test / chore  proposal + tasks, skip_specs: true
```

The completing PR archives the change, which applies its spec deltas to
`openspec/specs/`. Earlier PRs may leave the change active.

## 2. Decide before migrating

Write these down before touching CI. Each one changes the guard and the
contributor guide.

| Decision | Recommendation | Main alternative |
|---|---|---|
| What is mandatory | Every PR; docs use the lightweight path | Only behaviour changes |
| Issue policy | Bugs keep issues; the change is the plan | Issue + change for everything |
| Branch naming | `change/<change-name>` | `type/<change-name>` or `type/<n>-<slug>` |
| Commit format | Conventional Commits, optional scope | Free-form messages |
| Archive timing | The PR that completes the last task | After merge, or a bot PR |
| Tooling | Pin the CLI and Node version | `@latest` |
| Baseline specs | Seed them in domain slices | Let them accrue |
| AI policy | Disclose tool/model/version; same artifacts | A separate AI-only lane |
| Security fixes | Private advisory; documented carve-out | Public change with redacted text |

An ADR-style note per decision is enough:

```text
Decision:
Alternatives:
Why:
Consequences:
```

The decisions are the part future maintainers will question. Record them.

## 3. Map the old workflow

Exact names differ per project; map the concepts, not the regex.

| Old concept | New concept |
|---|---|
| Branch pattern such as `feat/42-thing` | `change/thing` |
| Issue required by CI | Optional; a change is required |
| Commit types `feat`, `fix`, `chore` | Full Conventional Commits |
| Tests are the only record | Specs and scenarios are the durable record |
| Docs PRs bypass planning | Docs PRs use a two-file lightweight change |
| CI runs tests | CI runs tests, guards and OpenSpec validation |

## 4. Migration sequence

```text
inventory -> decisions -> OpenSpec root -> guard change (old rules)
          -> adoption change (new rules, archives itself)
          -> baseline specs in slices -> remove compatibility -> verify
```

### Phase 0 — Inventory

Record the current rules and a few baseline numbers: branch regex, commit types,
issue requirement, CI jobs, length of the contributor guide, number of
capabilities and requirements (usually zero). You will want them to describe the
migration later; reconstructing them from history is possible but slow.

### Phase 1 — Initialise the OpenSpec root

```bash
npm install -g @fission-ai/openspec@1.14.3   # Node.js 20.19+
openspec init
openspec validate --specs --strict
```

Commit the root (`openspec/config.yaml`, `openspec/specs/`,
`openspec/changes/archive/`). Fill `config.yaml` with the project context and
per-artifact rules so humans and agents produce consistent artifacts.

Use a commit type your **current** guard accepts. The new rules are not live yet.

### Phase 2 — Capture the migration itself

```bash
openspec new change adopt-openspec-workflow
# set skip_specs: true: this is tooling, not behaviour
openspec validate adopt-openspec-workflow --strict
```

The first change documents the workflow it introduces. This is useful: the
proposal records why the migration exists, and the tasks record the order.

Keep the branch local until the guard can accept it.

### Phase 3 — Change the guard first

The PR that requires `change/<name>` has to pass the old guard first, which still
expects the old branch form. If the old guard requires an issue, open one for
this PR.

A subtlety in GitHub Actions: `pull_request` workflows are evaluated from the
pull request. A strict new branch regex therefore rejects the PR that introduces
it. Use a transitional guard that accepts both forms, and remove the old one in
a cleanup PR later:

```text
^change/[a-z0-9]+(-[a-z0-9]+)*$          # new
^(feat|fix|chore|docs|test)/[0-9]+-[a-z0-9-]+$   # legacy, for now
```

If your CI evaluates the base branch instead, you can skip the transitional
form. Check before assuming.

Merge this PR under the old rules.

### Phase 4 — Land the adoption change

On the new branch, add:

- the rewritten contributor guide, code of conduct and security policy;
- a PR template that names the change and the archive step;
- a CI job that validates the PR's change;
- updates to agent instructions and the README.

The CI job should:

1. derive the change name from `change/<name>`;
2. check the change directory exists and is touched in the diff;
3. run `openspec validate <name> --strict`;
4. run `openspec validate --specs --strict`;
5. for an archived change, run `openspec validate --archived`.

Validate the **named** change, not `--all`: one broken active change on `main`
should not block an unrelated PR.

Archive the change in this PR and merge it:

```bash
openspec archive adopt-openspec-workflow --yes --skip-specs
```

The first change under the new workflow is the one that defines the workflow.

### Phase 5 — Seed baseline specs in slices

Fix the capability list before authoring. Otherwise two contributors invent
`document-extraction` and `extraction` for the same behaviour.

Split the seed by domain, for example:

```text
seed-core-specs      auth, documents, extraction, batches
seed-data-specs      schemas, providers
seed-surface-specs   i18n, admin, deployment
```

Each slice is its own change. Every new capability needs a `## Purpose` and
`## ADDED Requirements` with at least one WHEN/THEN scenario per requirement.
`--strict` enforces the details.

### Phase 6 — Remove compatibility

Delete the legacy branch form from the guard. From here, a branch that does not
map to a change cannot merge.

### Phase 7 — Verify

- Open a docs-only change with `skip_specs: true`; confirm the job passes and
  the archive lands.
- Open a behaviour change with one spec delta; confirm validation, archive and
  `--archived`.
- Confirm a branch without a change fails.
- Optionally tag the migration milestone.

## 5. Worked example: structmydata-lite

Seven rollout PRs, all on 2026-10-28:

| PR | Branch | What it did |
|---|---|---|
| #14 | `chore/13-openspec-guards` | Transitional guard: accepted both branch forms, full Conventional Commits, optional issue |
| #15 | `change/adopt-openspec-workflow` | OpenSpec root, CONTRIBUTING, CoC, Security, templates, CI job, archived itself |
| #16 | `change/update-contribution-policy` | Second conduct/security contact; AI tool/model/version disclosure and `Assisted-by:` trailer |
| #17 | `change/seed-core-specs` | `auth`, `documents`, `extraction`, `batches` |
| #18 | `change/seed-data-specs` | `schemas`, `providers` |
| #19 | `change/seed-surface-specs` | `i18n`, `admin`, `deployment` |
| #20 | `change/remove-legacy-branch-format` | Only `change/<name>` accepted |

Result:

| Metric | Value |
|---|---|
| Archived changes | 6 during the rollout |
| Capabilities | 9 |
| Requirements | 82 |
| CI checks | 4: guards, tests, shell, OpenSpec |
| `CONTRIBUTING.md` | about 56 lines to about 370 |

## 6. Pitfalls and fixes

- **Self-referential CI.** The workflow file is evaluated from the PR; a strict
  branch rule rejects its own migration. Accept both forms during the bootstrap.
- **Strict validation catches long requirements.** A requirement description
  over 500 characters fails `--strict`. Split it into two requirements rather
  than trimming the behaviour away.
- **Capability naming drifts.** Agree the paths before seeding. Reuse an existing
  path; never introduce a near-duplicate.
- **Archive conflicts.** Two changes touching the same capability both edit
  `openspec/specs/<capability>/spec.md`. Serialize related PRs and rebase before
  archiving.
- **Security leaks through public artifacts.** A public change named
  `fix-auth-bypass` discloses the bug. Use a private advisory and a documented
  carve-out; maintainers may bypass the guard for that merge.
- **Docs still need a change.** Keep the lightweight path to two small files.
  Exempting docs instead makes the spec tree partial and impossible to audit.
- **Node becomes a prerequisite.** Pin the CLI, document the `npx` path, and make
  the lightweight path cheap.
- **Do not gate OpenSpec by author.** An "AI-only" lane is unenforceable,
  produces a partial spec tree, and rewards non-disclosure. Disclose AI use, keep
  the same artifacts, and put the model/version in the PR body and an
  `Assisted-by:` trailer.
- **Do not validate `--all` on every PR.** It couples unrelated changes.
- **Do not archive after merge by default.** Specs lag behind the code. Archive
  in the completing PR; multi-PR changes archive in the final one.

## 7. Checklist

- [ ] Decisions recorded with alternatives.
- [ ] CLI and Node version pinned.
- [ ] `openspec/` root committed and `config.yaml` populated.
- [ ] Migration captured as a change with `skip_specs`.
- [ ] Guard transition merged under the old rules.
- [ ] Contributor guide, CoC, Security, templates and agent instructions updated.
- [ ] CI validates the named change, the archive and the specs.
- [ ] Baseline specs seeded in domain slices.
- [ ] Legacy branch format removed.
- [ ] Docs-only and behaviour changes verified end to end.
- [ ] Milestone tagged (optional).

## 8. Rollback

Revert in reverse order: the cleanup, the baseline spec seeds, the adoption
change, then the guard. The OpenSpec root is inert if the policy is dropped, so
it can stay without affecting the application.

## 9. Minimum viable migration

A small project does not need nine capability specs on day one:

1. Commit the OpenSpec root.
2. Capture the adoption change.
3. Ship the contributor guide and a CI validation job.
4. Keep the lightweight docs path.
5. Seed a capability spec only when a change touches it.

That gives the enforcement and the habit first, and the spec tree grows where the
work actually happens.

## References

- [CONTRIBUTING.md](../CONTRIBUTING.md) — the day-to-day contributor rules.
- `openspec/changes/archive/2026-10-28-adopt-openspec-workflow/` — the adoption
  decision, design and tasks.
- `openspec/specs/` — the nine baseline capabilities.
- `scripts/check_change.py` and `.github/workflows/openspec.yml` — the CI
  implementation.
- [OpenSpec documentation](https://openspec.dev/docs).

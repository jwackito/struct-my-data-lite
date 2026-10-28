# Tasks

## 1. Write the playbook

- [x] 1.1 Write `docs/migrating-to-openspec.md` with the before/after table, decisions, migration sequence, worked example, pitfalls, checklist, rollback and minimum viable path; verify the commands and PR references against the repository.
- [x] 1.2 Link the playbook from the Maintainers section of `CONTRIBUTING.md`; verify the relative link resolves.

## 2. Validate

- [x] 2.1 Run `openspec validate document-openspec-migration --strict`; verify the change is valid with `skip_specs`.
- [ ] 2.2 Open the PR with `Change: document-openspec-migration`, verify the guards, tests and OpenSpec jobs pass, and confirm only docs changed.

## Workflow follow-up

- Archive this change in the completing PR with `openspec archive document-openspec-migration --yes --skip-specs`, then run `openspec validate --archived`.
- Merge with a merge commit, delete the local plan file outside the repository, and optionally tag the migration milestone.

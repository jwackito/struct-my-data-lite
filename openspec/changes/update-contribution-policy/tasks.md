# Tasks

## 1. Contacts

- [x] 1.1 Update `CODE_OF_CONDUCT.md` to list `@jwackito` and `@mayvillarrubia`, and use "the maintainers" in the enforcement and obligations text; verify both links resolve and no singular "the maintainer" remains in that section.
- [x] 1.2 Update `SECURITY.md` to offer both handles for direct contact while keeping GitHub Security Advisories as the preferred channel; verify both links resolve.

## 2. AI provenance

- [x] 2.1 Update the AI section in `CONTRIBUTING.md` to require the tool and version, the model and version, the scope, and an `Assisted-by:` trailer; verify the wording matches the trailer format below.
- [x] 2.2 Update `.github/pull_request_template.md` with tool/version, model/version and scope fields, plus a trailer checklist item; verify "none" remains valid for non-AI work.
- [x] 2.3 Add an `AI contributions` section to `AGENTS.md` and update the pull-request step to mention the disclosure; verify the section states the same trailer format as `CONTRIBUTING.md`.

Trailer format:

```text
Assisted-by: <tool> <version>; <model> <version>
```

Example: `Assisted-by: OpenCode 2.1.4; DeepSeek V4.1 Flash`.

## 3. Validate and land

- [x] 3.1 Run `openspec validate update-contribution-policy --strict` and verify the change is valid with `skip_specs`.
- [ ] 3.2 Open the PR with the change name, verify the guards and OpenSpec jobs pass, and confirm no unrelated files changed.

## Workflow follow-up

- Archive this change in the completing PR with `openspec archive update-contribution-policy --yes --skip-specs`, then re-run `openspec validate --archived`.
- Merge with a merge commit and verify `openspec list` on `main` is empty.
- Ask the maintainer before starting `change/seed-core-specs`.

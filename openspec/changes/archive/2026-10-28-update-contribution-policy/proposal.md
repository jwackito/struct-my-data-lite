# Proposal

## Why

The code of conduct and security policy list a single maintainer, but
[@mayvillarrubia](https://github.com/mayvillarrubia) is also a contact and should
be reachable for both. Separately, AI-assisted contributions currently disclose
only the tool name, which is not enough to audit which model produced a change.
Recording the model and version, in the pull request and in an `Assisted-by:`
commit trailer, keeps that provenance with the history.

## What Changes

- `CODE_OF_CONDUCT.md` lists `@jwackito` and `@mayvillarrubia` as private
  contacts and refers to "the maintainers" rather than a single maintainer.
- `SECURITY.md` lists both handles for direct contact; GitHub Security Advisories
  remain the preferred channel.
- `CONTRIBUTING.md` requires AI-assisted contributions to disclose the tool and
  its version, the model and its version, and the scope, and to add an
  `Assisted-by:` trailer to the commits.
- `.github/pull_request_template.md` gains fields for tool/version,
  model/version and scope, plus a checklist item for the trailer.
- `AGENTS.md` gains an "AI contributions" section, which it currently lacks, and
  its pull-request step mentions the disclosure.

## Capabilities

### New Capabilities

None. This change only edits contributor policy documents. The change's
`.openspec.yaml` sets `skip_specs: true`.

### Modified Capabilities

None.

## Impact

- `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CONTRIBUTING.md`, `AGENTS.md`,
  `.github/pull_request_template.md`.
- No application code, CI or dependencies change.

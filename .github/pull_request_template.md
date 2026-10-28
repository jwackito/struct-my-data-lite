## Change

OpenSpec change: `openspec/changes/<change-name>/`

- [ ] `openspec validate <change-name> --strict` passes
- [ ] Every task in `tasks.md` is checked
- [ ] Archived in this PR (`Archives: <change-name>`) or stays active for a follow-up PR

## What

<!-- One or two sentences: what does this change and why? -->

## Issue

<!-- Optional. Bugs usually have one: Closes #N or Refs #N -->

## Checklist

- [ ] A failing test was added first (behaviour changes)
- [ ] `python -m pytest -q` passes locally
- [ ] Commits follow Conventional Commits (`type(scope)!: subject`)
- [ ] Docs and `CHANGELOG.md` updated when behaviour changed
- [ ] New UI text added to both `app/i18n/en.json` and `app/i18n/es.json`
- [ ] No secrets, keys or `etc/.env` content committed
- [ ] Security fixes use the private advisory flow, not a public change

## AI assistance

<!-- Write "none" if not applicable. Use the identifiers your tool reports. -->

- Tool and version:
- Model and version:
- Scope (code / tests / docs):
- [ ] AI-assisted commits carry `Assisted-by: <tool> <version>; <model> <version>`

## Notes

<!-- Tradeoffs, follow-ups, screenshots, migration notes. -->

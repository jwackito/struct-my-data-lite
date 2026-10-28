# Design

## Context

See `proposal.md` for motivation. The specs document behaviour that already
exists. Sources: `app/main.py` routes, `app/auth.py`, `app/storage.py`,
`app/processing.py`, `app/parsers/`, `app/queue/`, `app/models.py` and the
pytest suite. No runtime changes are planned.

## Goals / Non-Goals

**Goals:**

- Four stable capability paths for the core flows: `auth`, `documents`,
  `extraction`, `batches`.
- Requirements that are observable and testable, with scenarios covering the
  normal path, the main error paths and the limits.
- Explicit defaults and status codes so future deltas can change them knowingly.

**Non-Goals:**

- Changing application behaviour or fixing quirks found while documenting.
- Documenting internal classes, function names or libraries.
- The remaining capabilities (`schemas`, `providers`, `i18n`, `admin`,
  `deployment`), which get separate changes.

## Decisions

### One capability per bounded area

`auth` owns identity and tokens; `documents` owns intake; `extraction` owns a
single document's job; `batches` owns groups. This matches the route and test
boundaries and avoids catch-all specs.

### Baseline specs may encode current quirks

For example, uploads accept any content type and unsupported types fail at parse
time; batch cancel also cancels running jobs. The specs state the observable
behaviour rather than the ideal. A later change can use MODIFIED Requirements to
correct a quirk, which makes the change visible.

### Requirements stay under the strict description limit

Each requirement states one behaviour; edge cases go into scenarios. This keeps
`openspec validate --strict` green and makes deltas easy to review.

### No design document per capability

The design is shared: how the baseline was derived and what is out of scope.
Individual capability specs do not need their own design.

## Risks / Trade-offs

- **Specs fossilise current behaviour** → future changes must use MODIFIED
  deltas, and the PR review compares the delta with the code.
- **Specs drift from code** → the pytest suite pins most behaviours; changes
  that alter behaviour must update the spec in the same change.
- **Too much detail** → requirements avoid class and function names, so
  refactors do not invalidate them.

## Migration Plan

None. Specs are additive. Rollback removes the four spec files and archives the
change; no data or code migration is involved.

## Open Questions

None. Quirks discovered during authoring are recorded as current behaviour, not
silently fixed here.

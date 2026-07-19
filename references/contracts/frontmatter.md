# Frontmatter contract

Every ordinary note has the same closed schema and canonical order. The full
field policies, examples, migrations, and query semantics remain in
`../frontmatter.md`.

```text
title, id, created, modified,
description, type, project, area, resource,
status, effort_cadence, effort_level, tags, chosen_location,
source, link, author,
depth, appreciated, importance, pinned,
expires_at,
related, relations, parent, observations, extracted_to
```

Rules required for capture:

- Use every field, with explicit `null`, `[]`, or `false` defaults.
- Do not add operation-specific keys to the universal schema.
- `title` and filename use lowercase ASCII `snake_case`.
- `appreciated` and `importance` are user-only and remain `null` for agents.
- `pinned` defaults to `false`.
- `depth` is `1..5` only when the score adds information.
- Do not infer an effort profile.
- `project` and `resource` are mutually exclusive; `area` is contextual.
- `howto` is global: leave `project` and `resource` null; `area` may remain
  contextual.
- Relation types are limited to `supports`, `contradicts`, `depends_on`,
  `derived_from`, and `example_of`.
- Public timestamps use `dd-MM-YYYY-HH-mm` in UTC. Machine-owned values may
  retain ISO 8601, and daily fleeting filenames remain date-only.

Archive-only fields `archived_at` and `archived_from` are lifecycle extensions,
not normal capture fields and never lifecycle statuses. `archived` is the
status.

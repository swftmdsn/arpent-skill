# Frontmatter

Every vault note follows the universal frontmatter contract in:

`06_indexes/schemas/frontmatter_policy.yaml`

Rules:

- Same fields, same order.
- Dates use `dd-mm-yyyy`; note-facing UTC timestamps use `dd-mm-yyyyTHH:MM:SSZ`. Legacy ISO timestamps remain readable during migration.
- Note language is governed by the primary/adaptive settings in the installed Arpent skill, not by a frontmatter field.
- The schema is closed during normal use. Unsupported per-project fields are rejected. Users may freely add/reorder body sections and create project files/subfolders. Extending the schema requires coordinated canonical schema, order, validation, policy, documentation, and test changes.
- `project` and `resource` are mutually exclusive homes; `area` may accompany either as context.
- `appreciated` and `importance` are user-only.
- `pinned` defaults to `false`.
- Ordinary-note `title` and filename use lowercase ASCII `snake_case`; the immutable `id` stays only in frontmatter. Reserved `_context.md` and fleeting day files keep their prescribed names.
- `description` is `null` when redundant and `depth` is a conservative 1-5 development scale.
- Active actionables may use `effort_cadence: heavylift|slowburn` and `effort_level: low|medium|high`; missing values are never inferred and appear as `unclassified`.
- Tool-specific data belongs in a tool database, documented body format, or reviewed schema field; there is no universal `extra` map.
- `relations[].type` is limited to `supports`, `contradicts`, `depends_on`, `derived_from`, `example_of`.
- Bodies contain one reusable thesis, no repeated H1 or source URL, and only simple Obsidian-compatible Markdown by default.
- Binary/non-text files never contain frontmatter; they use a separate complete Markdown companion reference whose `link` points to the untouched attachment.

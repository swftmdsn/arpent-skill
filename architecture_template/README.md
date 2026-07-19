# Arpent Vault Architecture Template

This directory is a ready-to-copy, annotated minimal vault. `arpent init` creates
the same scaffold and critical operating contracts, while this tree may retain
expanded examples and explanatory documents. Both paths retain every full-mode
skill and default to direct-file operation without Git or a CLI dependency.

It follows the architecture expected by the Arpent skill:

- 7 deterministic buckets: `00_inbox`, `01_projects`, `02_areas`, `03_resources`, `04_archives`, `05_tools`, `06_indexes` - unresolved routing lands in `00_inbox/unsure/`
- `.agent` as the entry point for AI agents
- `.arpent` as the vault marker
- `me.md` as the human-owned orientation file agents read early
- dormant memory contracts and research-wiki structure under `06_indexes/memory/`; optional `MEMORY.md` is not seeded
- portable agent roles, skills, workflows, prompts, and capabilities under `03_resources/agent_infrastructure/`
- whole-vault folder/file inventory with deterministic L0/L2 context and optional AI-generated L1 summaries
- tool know-how centralized in `06_indexes/`; `05_tools/` reserved for declared runtime material
- clean vault knowledge separated from tools, indexes, generated metadata, and agent research scratch

To start a live vault:

1. Copy this directory, open it with an agent, and tell the agent to read `.agent`.
2. Fill `me.md` with user-provided orientation, not inferred memory.
3. In minimal, create a project directly: normalize its name to lowercase ASCII
   kebab-case, require `01_projects/<slug>/` not to exist, create `notes/`,
   `drafts/`, and `attachments/`, then instantiate
   `_template_project/_context.md` at the project root with a unique note ID,
   current UTC timestamps, a snake_case context title, the project slug, and
   either an existing unambiguous area or `null`. Reject reserved names listed in
   the local skill. For a missing area context, instantiate
   `02_areas/_context.template.md` inside that existing area. In full, use
   `arpent project create <name>`.
4. Resume by reading `me.md`, then the target `_context.md`, then only the specific notes or sources needed. Do not read optional `MEMORY.md` without a separate explicit read request.
5. Keep `project` and `resource` mutually exclusive; `area` may accompany either as context.
6. Leave `appreciated` and `importance` as `null`; they are user-only fields.
7. Archive instead of deleting.

Both modes retain the complete skills, contracts, schemas, and documentation.
Minimal operates ordinary notes and context directly in files and leaves
mode-gated state dormant. Full permits CLI-mediated todo, import, generated
context, backup, cron, sweep, and transactional operations when their other
prerequisites are met. With `auto_full: true`, the first mode-gated CLI command
requests vault-mode promotion; the confirmation policy may first require
`arpent mode full --yes`. Use `arpent mode minimal` to return without deleting
any skill or state and to cancel the pending promotion request.

The universal frontmatter schema is closed during normal use; unsupported
per-project fields are rejected. Users may freely add/reorder body sections and
create project files or subfolders. The static `_template_project/_context.md`
is the direct-operation template; the CLI builds the same field set and body
independently. Edit a created context directly in normal use; Arpent developers
must update both surfaces when changing the generated design.

Binary files remain byte-for-byte untouched and never contain YAML. In full,
transactional ingestion moves an attachment to a selected home's `attachments/`
and creates a separate Markdown companion reference with complete frontmatter
and a `link` to that file. In minimal, preserve the raw source and do not claim a
coordinated move. Without a final home, the original stays in inbox and the
companion remains untriaged.

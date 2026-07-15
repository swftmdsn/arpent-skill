# Arpent Vault Architecture Template

This directory is the reference full-vault structure mirrored by `arpent init`.
For a live vault, prefer the CLI so current seeds and marker semantics are used.

It follows the architecture expected by the Arpent skill:

- 7 deterministic buckets: `00_inbox`, `01_projects`, `02_areas`, `03_resources`, `04_archives`, `05_tools`, `06_indexes` - unresolved routing lands in `00_inbox/unsure/`
- `.agent` as the entry point for AI agents
- `.arpent` as the vault marker
- `me.md` as the human-owned orientation file agents read early
- delegated memory zone under `06_indexes/memory/`
- portable agent roles, skills, workflows, prompts, and capabilities under `03_resources/agent_infrastructure/`
- whole-vault folder/file inventory with deterministic L0/L2 context and optional AI-generated L1 summaries
- tool know-how centralized in `06_indexes/`; `05_tools/` reserved for declared runtime material
- clean vault knowledge separated from tools, indexes, generated metadata, and agent research scratch

To start a live vault:

1. Run `arpent init <path>` or `arpent init <path> --minimal` rather than copying this tree as the primary path.
2. Fill `me.md` with user-approved orientation, not inferred memory.
3. Create each project deliberately with `arpent project create <name>`; do not rename `_template_project` as the primary workflow.
4. Resume by reading `me.md`, then the target `_context.md`, then only the specific notes or sources needed. Do not read optional `MEMORY.md` without explicit user opt-in.
5. Keep `project` and `resource` mutually exclusive; `area` may accompany either as context.
6. Leave `appreciated` and `importance` as `null`; they are user-only fields.
7. Archive instead of deleting.

Both modes include project creation, project/area `_context.md`, session closure,
actionable triage/ingestion, and usage reporting. `MEMORY.md` is disabled and
unseeded by default; `session end --memory-log` opts one invocation into the
optional log. Minimal mode does not seed `06_indexes/memory/`. Full mode
additionally ships the optional modules and delegated-memory queue surface
represented by this template.

The universal frontmatter schema is closed during normal use; unsupported
per-project fields are rejected. Users may freely add/reorder body sections and
create project files or subfolders. The static `_template_project/_context.md`
does not control the code-generated `arpent project create` template. Edit a
created context directly in normal use; Arpent developers must update both the
runtime builder and this static template when changing the generated design.

Binary files remain byte-for-byte untouched and never contain YAML. Ingestion
moves an attachment transactionally to a selected home's `attachments/` and
creates a separate Markdown companion reference with complete frontmatter and a
`link` to that file. Without a final home, the original stays in inbox and the
companion remains untriaged.

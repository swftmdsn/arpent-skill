# COMPASS - compact vault router

Use this file only when the current operation is not already clear from the
active Arpent skill.

## Select The Mode

Read `.arpent` before acting.

- `minimal`: read, search, create, edit, route, and archive directly in files.
- `full`: use CLI-mediated vault operations.
- If minimal has `auto_full: true`, the first mode-gated CLI command requests
  vault-mode promotion. The confirmation policy may require
  `arpent mode full --yes` first.

The confirmation policy and batch threshold live in
`06_indexes/cli/operations.yaml`.

## Select The Operation

| Intent | Route |
|---|---|
| Keep readable knowledge | Typed Markdown note |
| Track execution or completion | Todo in full; clearly untracked inbox note in minimal |
| Recall context without execution state | External buffer only when an explicitly enabled provider exists |
| Capture a quick temporary thought | Fleeting daily stream |
| Organize files | Triage inbox and apply deterministic routing |
| Find or recall | Search live files in minimal; bounded CLI search in full |
| Resume work | `me.md`, target `_context.md`, then only needed sources |
| Close work | Update target `_context.md` |
| Archive | Preserve content, update lifecycle metadata, and move |

Minimal keeps orientation in `me.md`, work state in `_context.md`, and readable
material in notes. Full adds CLI-mediated capabilities. External memory remains
a separate, explicitly enabled host capability.

## Routing

Use `project > resource > area > inbox`. `project` and `resource` are mutually
exclusive; `area` may accompany either. Reserved resource homes declared by the
contract may materialize on first write. Never invent another missing
destination. Conflicting or unresolved placement goes to `00_inbox/unsure/`
with a reason. Status and physical location are decoupled.

## Boundaries

Minimal does not emulate coordinated SQLite or multi-file operations. Preserve
current files and switch to full for todo state, import apply, extraction or
dissolution, generated indexes and L1 summaries, Arpent backup, cron, or sweep.

## Invariants

- Prevent silent loss: never silently replace a destination or destroy user
  content. Explicit edits may use checked atomic replacement.
- Use complete canonical frontmatter on ordinary notes.
- Never infer `appreciated`, `importance`, or missing effort values.
- Never invent frontmatter keys, relation types, provider opt-in, or side effects.
- Keep source URLs in `link`, not repeated in note bodies.
- Keep binary files unchanged with separate Markdown companions.
- Apply the local confirmation policy without weakening validation.
- Report actual paths and outcomes concisely.
- `archived` is a status; `archived_at` and `archived_from` are lifecycle event
  metadata, never statuses.

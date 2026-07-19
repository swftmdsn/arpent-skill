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
| Capture a quick temporary thought | Fleeting daily stream |
| Organize files | Triage inbox and apply deterministic routing |
| Find or recall | Search live files in minimal; bounded CLI search in full |
| Resume work | `me.md`, target `_context.md`, then only needed sources |
| Close work | Update target `_context.md` |
| Archive | Preserve content, update lifecycle metadata, and move |

Minimal keeps user-provided orientation in `me.md`, working state in `_context.md`,
and durable readable material in notes. Full permits CLI-mediated todo, context,
import, backup, cron, and sweep capabilities when their other prerequisites are
met; delegated memory also requires provider opt-in.

## Routing

Use `project > resource > area > inbox`. `project` and `resource` are mutually
exclusive; `area` may accompany either. Never create a missing destination
silently. Conflicting or unresolved placement goes to `00_inbox/unsure/` with a
reason.

## Boundaries

Minimal does not emulate coordinated SQLite or multi-file operations. Preserve
current files and switch to full for todo state, import apply, extraction or
dissolution, generated indexes and L1 summaries, Arpent backup, cron, sweep, or
delegated queues.

## Invariants

- Never delete or overwrite user content. Archive.
- Use complete canonical frontmatter on ordinary notes.
- Never infer `appreciated`, `importance`, or missing effort values.
- Never invent frontmatter keys, relation types, provider opt-in, or side effects.
- Keep source URLs in `link`, not repeated in note bodies.
- Keep binary files unchanged with separate Markdown companions.
- Apply the local confirmation policy without weakening validation.
- Report actual paths and outcomes concisely.

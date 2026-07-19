---
name: arpent
description: Operate an Arpent vault for local continuity, typed documents, todo, retrieval, routing, projects, lifecycle, import, and administration. Use when the user asks to save, organize, find, move, archive, import, or continue work in an Arpent vault.
---

# Arpent

Arpent is a filesystem-native continuity layer. Markdown is canonical for
documents; `todo.db` is authoritative for coordinated todo state. Minimal uses
direct files; full adds CLI transactions, tools, indexes, and recovery. Use the
smallest sufficient context.

## Start

1. Read the vault's `.arpent` marker before acting.
2. Use the hot paths; for unclear work read `references/workflows/COMPASS.md`
   and at most one detailed contract.
3. Follow the relevant mode reference. Full commands apply local confirmation;
   minimal and batch planning read it from `06_indexes/cli/operations.yaml`.
4. With minimal `auto_full: true`, a mode-gated command requests promotion. Run
   `arpent mode full --yes` first when policy requires it. Explicit minimal
   cancels the request.

For ordinary capture, do not read the root README, complete architecture, full
COMPASS, or all references.

## Hot Paths

### Typed note

Use for readable knowledge: notes, ideas, meetings, journal entries, references,
drafts, concepts, integrations, maps, how-tos, and production.

- Prefer one reusable thesis per note.
- Before a durable note, search and fully read plausible prior art (`fleeting`
  exempt); tags or emotions alone do not prove one thesis.
- If covered, recommend no change, enrichment, revision, or a new linked note;
  never silently edit instead of a requested creation.
- Use `note` when a more specific type adds no value.
- `project` and `resource` are mutually exclusive; `area` may accompany either.
- Reserved resource homes declared by the routing contract may be materialized
  on first write. Never invent any other missing project, area, or resource.
- Keep source URLs in `link`. Use `source: captured` only with an external URL;
  otherwise record the real provenance.
- Route uncertainty to `00_inbox/unsure/` with a reason.
- `howto` is reviewed current global guidance; `map` is navigation. Keep detail
  and history linked. See `references/workflows/maintain-howto.md`.

```text
arpent note new <title> --type <type> [options] --body <body> --json
```

```text
arpent note new <same arguments> --dry-run --json
arpent note new <same arguments> --plan-hash <plan_sha256> --json
```

Minimal: build complete frontmatter, route, create without replacement, then
verify. See `references/workflows/capture-note.md`.

### Todo

Use for work requiring execution, tracking, completion, deferral, or blocking.
Do not infer optional dates, priority, duration, project, dependency, or
assignee.

“Remember to do X” is a todo. Non-actionable recall context is provider-bound;
without provider opt-in, report it unpersisted. Todo does not promise alerts.

```text
arpent todo add <content> [options] --json
```

Use `--dry-run --json` then `--plan-hash` when policy requires review. Todo's
SQLite/Markdown state requires full mode; minimal may offer an explicitly
untracked inbox note. See `references/workflows/capture-todo.md`.

### Fleeting

Use for quick append-only material that does not yet warrant a structured note.

```text
arpent note new <text> --type fleeting --json
```

The stream lives at `00_inbox/fleeting/dd-mm-yyyy.md`, with `## HH:MM` entries
and no per-entry frontmatter or ID. In minimal mode, preserve the existing
daily file and append one verified block. Detailed procedure:
`references/workflows/capture-fleeting.md`.

## Confirmation

The local `confirmation` contract supports:

| Policy | Behavior |
|---|---|
| `always` | Require confirmation before every registered domain change; use a structured preview when available. |
| `explicit-intent` | Execute an explicit bounded request directly; confirm high-impact operations and batches at or above `bulk_threshold`. |
| `never` | Never ask for additional confirmation; keep every technical validation and safety check. |

Clarification is not confirmation: ask for missing meaning, but in `never` do
not pause to restate a valid plan. Establish intent before the CLI; previews and
plan hashes support inspection but neither proves review nor permission.

## Other Operations

| Intent | Contract to load |
|---|---|
| Route or understand a destination | `references/contracts/routing.md` |
| Build or inspect metadata | `references/contracts/frontmatter.md` |
| Decide provenance or write a body | `references/contracts/provenance-and-body.md` |
| Triage inbox | `references/routing.md` and relevant ingest contract |
| Import an external tree | `references/import-and-migration.md` |
| Edit, mature, archive, extract, dissolve, close session | `references/lifecycle.md` |
| Search, index, or use L0/L1/L2 | `references/indexing-and-context.md` |
| Tools, cron, sweep, backup | `references/tools-and-cron.md` |
| Decide vault vs memory | `references/memory-layers.md` |
| Operate in minimal mode | `references/modes/minimal.md` |
| Operate in full mode | `references/modes/full.md` |
| Change Arpent itself or study every edge case | `references/appendices/complete-reference-index.md` |

## Writing Rules

- Primary language: English. Adaptive languages: French.
- Adapt prose to the conversation; keep metadata syntax unchanged.
- Use ordinary Obsidian Markdown; repeat neither title as H1 nor source URL.
- Concepts, ideas, and integrations must stand on their own.
- Preview a split only when independent theses remain useful independently.

## Frontmatter Rules

- The universal schema is closed during normal use.
- Use complete canonical frontmatter for every ordinary note.
- Never fill `appreciated` or `importance`; `pinned` defaults to `false`.
- Never infer missing effort cadence or level.
- Public timestamps use `dd-MM-YYYY-HH-mm` in UTC. The daily fleeting filename
  remains the explicit date-only exception.
- Titles and filenames use lowercase ASCII `snake_case`; IDs remain metadata.
- Use only declared relation types.
- Preserve IDs, creation dates, user-owned fields, and body sections on edits.

See `references/contracts/frontmatter.md` and `references/frontmatter.md`.

Status and location are decoupled. `archived` is a status;
`archived_at`/`archived_from` describe explicit archive events.

## Safety

- Prevent silent loss: never silently replace a destination or destroy user
  content. Explicitly requested edits may use checked atomic replacement.
- Never silently choose between plausible destinations.
- Never invent an undeclared missing project, area, resource, field, relation
  type, memory destination, or successful side effect.
- Never replace a CLI-mediated full-mode operation with direct file mutation.
- Keep binary files byte-for-byte intact and use separate Markdown companions.
- Keep tool know-how in `06_indexes/`; `05_tools/` is runtime material only.
- Minimal mode keeps user-provided orientation in `me.md`, working state in
  `_context.md`, and durable readable information in notes. External host memory
  remains unavailable until provider opt-in and confirmed provider persistence.
- `session end` writes target context by default. Only an explicit
  `--memory-log` request writes optional `MEMORY.md`, which is never read during
  normal resume.
- `me.md` is human-owned; do not rewrite it from inference.

## Output Discipline

After simple capture, report only the change, path, type/status, and warnings.
Do not then run help, status, triage, index, search, or full verification.
Never treat one page as complete; follow its cursor or use `--all`/`--full`.

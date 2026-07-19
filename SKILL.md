---
name: arpent
description: Operate an Arpent vault for typed capture, todo, retrieval, routing, projects, lifecycle, and filesystem-first personal knowledge. Use when the user asks to save, remember, organize, find, move, archive, mature, import, or continue personal information or work in an Arpent vault.
---

# Arpent

Arpent is a filesystem-native personal operating system. Markdown is canonical;
the CLI adds deterministic routing, transactions, SQLite-backed tools, indexes,
and recovery. Operate with the smallest sufficient context.

## Start

1. Read `references/workflows/COMPASS.md` only when the operation is not already
   clear from the hot paths below.
2. Locate a vault only when reading or changing vault state.
3. With the CLI, let the command apply and report the local confirmation policy.
   In filesystem mode, or before planning a batch, read it from
   `06_indexes/cli/operations.yaml`. An older contract without the section uses
   `always`.
4. Use `references/adapters/cli.md` when the CLI is available; otherwise use
   `references/adapters/filesystem.md`.
5. Load one detailed workflow or contract only when the operation needs it.

Do not read the root README, complete architecture, full COMPASS, or all
references for an ordinary capture.

## Hot Paths

### Typed note

Use for readable knowledge: notes, ideas, meetings, journal entries, references,
drafts, concepts, integrations, maps, and production.

- Prefer one reusable thesis per note.
- Use `note` when a more specific type adds no value.
- `project` and `resource` are mutually exclusive; `area` may accompany either.
- Keep source URLs in `link`, not the body.
- Use `source: captured` only with an external URL; otherwise describe the real
  provenance.
- Route uncertainty to `00_inbox/unsure/` with a reason.

Direct CLI capture:

```text
arpent note new <title> --type <type> [options] --body <body> --json
```

Reviewed CLI capture:

```text
arpent note new <same arguments> --dry-run --json
arpent note new <same arguments> --plan-hash <plan_sha256> --json
```

Filesystem capture: build complete canonical frontmatter, compute the route,
create without replacement, then read back and verify. Detailed procedure:
`references/workflows/capture-note.md`.

### Todo

Use for work requiring execution, tracking, completion, deferral, or blocking.
Do not infer optional dates, priority, duration, project, dependency, or
assignee.

```text
arpent todo add <content> [options] --json
```

Use `--dry-run --json` then `--plan-hash` when policy requires review. Todo's
coordinated SQLite and Markdown state uses the CLI. Without it, offer an ordinary
inbox capture and identify it as untracked. Detailed procedure:
`references/workflows/capture-todo.md`.

### Fleeting

Use for quick append-only material that does not yet warrant a structured note.

```text
arpent note new <text> --type fleeting --json
```

The stream lives at `00_inbox/fleeting/dd-mm-yyyy.md`, with `## HH:MM` entries
and no per-entry frontmatter or ID. In filesystem mode, preserve the existing
daily file and append one verified block. Detailed procedure:
`references/workflows/capture-fleeting.md`.

## Confirmation

The local `confirmation` contract supports:

| Mode | Behavior |
|---|---|
| `always` | Require approval before every mutation; use a structured plan when available. |
| `explicit-intent` | Execute an explicit bounded request directly; confirm high-impact operations, expanded side effects, and batches at or above `bulk_threshold`. |
| `never` | Never ask for a second approval; keep every technical validation and safety check. |

Clarification is not confirmation. Ask for missing meaning when needed. In
`never`, do not pause merely to restate a valid plan.

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
| Operate without CLI | `references/adapters/filesystem.md` |
| Change Arpent itself or study every edge case | `references/appendices/complete-reference-index.md` |

## Writing Rules

- Primary language: English. Adaptive languages: French.
- Adapt prose to the active conversation or source when natural. Keep metadata
  keys, enums, IDs, syntax, and paths unchanged.
- Use ordinary Obsidian-compatible Markdown.
- Do not repeat the title as H1.
- Do not repeat the source URL in the body.
- Concepts, ideas, and integrations must stand on their own.
- Preview a split only when independent theses remain useful independently.

## Frontmatter Rules

- The universal schema is closed during normal use.
- Use complete canonical frontmatter for every ordinary note.
- Never fill `appreciated` or `importance`; `pinned` defaults to `false`.
- Never infer missing effort cadence or level.
- Dates use `dd-mm-yyyy`; note timestamps use `dd-mm-yyyyTHH:MM:SSZ` UTC.
- Titles and filenames use lowercase ASCII `snake_case`; IDs remain metadata.
- Use only declared relation types.
- Preserve IDs, creation dates, user-owned fields, and body sections on edits.

The full field order and policies are in
`references/contracts/frontmatter.md` and `references/frontmatter.md`.

## Safety

- Never delete or overwrite user content. Archive.
- Never silently choose between plausible destinations.
- Never invent a missing project, area, resource, field, relation type, memory
  destination, or successful side effect.
- Never bypass the CLI for a coordinated operation when it is available.
- Keep binary files byte-for-byte intact and use separate Markdown companions.
- Keep tool know-how in `06_indexes/`; `05_tools/` is runtime material only.
- External memory is disabled until the user explicitly enables a host provider.
- `me.md` is human-owned; do not rewrite it from inference.

## Output Discipline

After a simple capture, report only what changed, its relative path, type/status,
and any warning. Do not automatically run help, status, triage, index, search, or
full-content verification commands.

For paginated output, never mistake one page for a complete result. Follow the
cursor or use `--all`/`--full` when the task requires completeness.

## Complete Method

The compact skill does not replace Arpent's detailed model. The complete
architecture, schema examples, lifecycle rationale, memory rules, direct-file
procedures, and edge cases remain indexed in
`references/appendices/complete-reference-index.md`.

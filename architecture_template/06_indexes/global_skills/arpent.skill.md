---
name: arpent
description: Operate an Arpent vault for typed capture, retrieval, routing, projects, lifecycle, and todo.
---

# Arpent

Use for capture, organization, retrieval, routing, archival, project continuity,
import, and actionable todo work.

## Load progressively

1. Read `.agent` once.
2. Use the note, todo, or fleeting hot path without loading full documentation.
3. Read `COMPASS.md` only to classify a less common operation.
4. Read one relevant document under `06_indexes/docs/architecture/` for an edge
   case. Use CLI help only when exact syntax is not already known.

## Capture

- Note: `arpent note new <title> --type <type> ... --json`.
- Reviewed note: add `--dry-run --json`, then re-run with `--plan-hash`.
- Todo: `arpent todo add <content> ... --json` when todo is installed.
- Fleeting: `arpent note new <text> --type fleeting --json`.

The confirmation policy is in `06_indexes/cli/operations.yaml`:

- `always`: require approval before every mutation; use a structured plan when available.
- `explicit-intent`: direct for explicit bounded requests; preview high-impact or
  threshold-sized batches.
- `never`: no second approval; technical checks remain active.

## Method

- Markdown is canonical; use the CLI for coordinated changes when available.
- In filesystem mode, preserve complete frontmatter, typing, routing, and body,
  then verify the written file.
- Never delete, overwrite, guess routing, invent schema fields, infer subjective
  fields, or activate memory without opt-in.
- `project` and `resource` are mutually exclusive; `area` may accompany either.
- Keep source URLs in `link`, titles in lowercase ASCII `snake_case`, and dates
  in day-first format.
- Agent-authored unrequested drafts use `author: agent`, `type: draft`, and the
  standard lifecycle status; no extra frontmatter field is introduced.
- Resume from `me.md`, then target `_context.md`, then only needed sources.
- `MEMORY.md` and external memory require explicit opt-in.

Report concise paths and outcomes. Do not run status, index, triage, search, or a
full reread after an ordinary successful capture.

---
name: arpent
description: Operate an Arpent vault.
---

# Arpent

Use for capture, retrieval, routing, archival, project continuity, import, and todo.

## Load Progressively

1. Read `.agent` and the small `.arpent` marker once.
2. Use the note, todo, or fleeting hot path without loading full documentation.
3. Read `COMPASS.md` only to classify a less common operation.
4. Read one relevant detailed document only for an edge case.

## Modes

- `minimal`: use direct-file operations on canonical files; mode-gated CLI
  commands require vault-mode promotion.
- `full`: use CLI-mediated vault operations.
- If minimal has `auto_full: true`, the first mode-gated command requests
  promotion. Use `arpent mode full --yes` first when the confirmation policy
  requires it.

## Capture

- Full note: `arpent note new <title> --type <type> ... --json`; `howto` is
  current global guidance, `map` navigation.
- Exact-plan note: add `--dry-run --json`, then use `--plan-hash`.
- Full-mode todo: `arpent todo add <content> ... --json`.
- Full-mode fleeting: `arpent note new <text> --type fleeting --json`.

## Minimal Hot Paths

### Note

1. Read `06_indexes/schemas/frontmatter_policy.yaml` and the routing contract.
2. Build complete frontmatter, normalize the title, and compute the route.
3. Reserved resource homes may materialize on first write; never invent another
   missing home.
4. Recheck the destination, create without silently replacing it, read back, and
   verify frontmatter, body, and path.

### Untracked Todo

1. State that coordinated todo is unavailable in minimal mode.
2. If the user still wants capture, create an ordinary inbox note clearly
   labeled as an untracked action; do not claim a todo ID, database row, status
   tracking, or reminder delivery.
3. Suggest promotion to full mode when execution tracking is required.

### Fleeting Append

1. Use the current UTC file `00_inbox/fleeting/dd-mm-yyyy.md`.
2. Preserve the complete existing file and append one `## HH:MM` block.
3. Verify the final block. If safe append cannot be guaranteed, create an
   ordinary inbox note instead of risking previous captures.

Canonical field order: `title, id, created, modified, description, type,
project, area, resource, status, effort_cadence, effort_level, tags,
chosen_location, source, link, author, depth, appreciated, importance, pinned,
expires_at, related, relations, parent, observations, extracted_to`. Use explicit
`null`, `[]`, and `false` defaults. Generate IDs as
`<type>-<UTC YYYYMMDD>-<a..z,aa..>` after scanning all existing IDs.

## Project And Context

- Full: use `arpent project create <name>` and `arpent session end`.
- Minimal: normalize the project name to lowercase ASCII kebab-case, require the
  destination to be absent, and reject `aux`, `clock$`, `con`, `nul`, `prn`,
  `template-project`, `com1..9`, and `lpt1..9`. Create `notes/`, `drafts/`, and
  `attachments/`, then instantiate `01_projects/_template_project/_context.md`
  at `01_projects/<slug>/_context.md`. Replace every placeholder, convert the
  context title to lowercase ASCII snake_case, assign a globally unique note ID
  and current UTC timestamps, and leave the template itself unchanged.
- For a missing area context in minimal, instantiate
  `02_areas/_context.template.md` at the existing area's root with its resolved
  slug, a snake_case title, unique ID, and current UTC timestamps.
- On a direct session close, update `modified` and append the timestamped
  summary, decisions, and next steps without replacing existing body sections.

The confirmation policy is in `06_indexes/cli/operations.yaml`.

## Method

- Markdown is canonical for documents; `todo.db` is authoritative for
  coordinated todo state. All ordinary notes use complete frontmatter.
- Prevent silent loss: never silently replace a destination or destroy user
  content. Explicit edits may use checked atomic replacement. Never guess
  routing, invent schema fields, infer subjective fields, or use delegated
  memory without provider opt-in.
- `project` and `resource` are mutually exclusive; `area` may accompany either.
- Keep source URLs in `link`, titles in lowercase ASCII `snake_case`, and public
  timestamps in `dd-MM-YYYY-HH-mm` UTC format.
- Agent-authored unrequested drafts use `author: agent`, `type: draft`, and the
  standard lifecycle status.
- Resume from `me.md`, then target `_context.md`, then only needed sources.
- Minimal continuity uses `me.md` for approved orientation, `_context.md` for
  work state, and notes for durable content.
- External memory requires provider opt-in; full-mode state remains dormant in
  minimal.
- Status and location are independent. `archived` is a status;
  `archived_at`/`archived_from` describe archive events.

Report concise paths and outcomes. Do not run status, index, triage, search, or a
full reread after an ordinary successful capture.

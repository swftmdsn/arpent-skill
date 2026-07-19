---
name: arpent
description: Operate an Arpent vault for typed capture, retrieval, routing, projects, lifecycle, and todo.
---

# Arpent

Use for capture, organization, retrieval, routing, archival, project continuity,
import, and actionable todo work.

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

- Full-mode note: `arpent note new <title> --type <type> ... --json`.
- Exact-plan note: add `--dry-run --json`, then use `--plan-hash`.
- Full-mode todo: `arpent todo add <content> ... --json`.
- Full-mode fleeting: `arpent note new <text> --type fleeting --json`.
- Minimal: read `06_indexes/schemas/frontmatter_policy.yaml`, the routing section
  of `06_indexes/cli/operations.yaml`, and
  `06_indexes/docs/architecture/routing.md`; build complete frontmatter, compute
  the route, create without replacement, and read back the result.

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

- Markdown is canonical; all ordinary notes use complete frontmatter.
- Never delete, overwrite, guess routing, invent schema fields, infer subjective
  fields, or use delegated memory without provider opt-in.
- `project` and `resource` are mutually exclusive; `area` may accompany either.
- Keep source URLs in `link`, titles in lowercase ASCII `snake_case`, and public
  timestamps in `dd-MM-YYYY-HH-mm` UTC format.
- Agent-authored unrequested drafts use `author: agent`, `type: draft`, and the
  standard lifecycle status.
- Resume from `me.md`, then target `_context.md`, then only needed sources.
- Minimal keeps user-provided orientation in `me.md`, work state in `_context.md`, and
  durable readable material in notes.
- Skills and full-mode state remain retained; mode-gated state is dormant in
  minimal.

Report concise paths and outcomes. Do not run status, index, triage, search, or a
full reread after an ordinary successful capture.

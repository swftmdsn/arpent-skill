# Frontmatter

The universal contract that every vault note follows. Same fields, same order, every time. Field semantics are explicit: what the system fills, what the agent may fill, what only the user fills, what the agent is forbidden from filling.

The schema is closed during normal use. Do not invent per-project fields: CLI validation rejects unsupported keys. Users may freely add or reorder Markdown body sections and create project files or subfolders. Extending the universal schema is deliberate Arpent system development and requires coordinated changes to the canonical schema, field order, validation, policy, documentation, and tests.

## Complete schema

```yaml
---
# === Identity and system timestamps ===
title: <lowercase_ascii_snake_case>
id: <type>-<YYYYMMDD>-<letter>      # stable graph anchor, never used in filename
created: 19-04-2026-14-30
modified: 19-04-2026-14-30

# === Classification and routing ===
description: <useful standalone summary or null>
type: <enum>                         # see Type Enum below
project: <slug or null>
area: <slug or null>
resource: <slug or null>
status: <enum>                       # see Status Enum below
effort_cadence: <heavylift|slowburn|null>
effort_level: <low|medium|high|null>
tags: [tag-one, tag-two, tag-three]
chosen_location: null                # OPTIONAL - one line explaining what this note does here

# === Layer 3: Provenance ===
source: <enum>                       # see Source Enum below
link: <URL or path or null>
author: <user|agent|imported>

# === Enriched ===
depth: <1-5 or null>                 # level of development; see scale below
appreciated: null                    # USER ONLY - agent must leave null
importance: null                     # USER ONLY - agent must leave null
pinned: false                        # default false, user toggles

# === Lifecycle ===
expires_at: null                     # dd-MM-YYYY-HH-mm UTC - documentary expiry only, not task state

# === Layer 6: Graph relations ===
related: []                          # IDs of weak/non-qualified related notes
relations: []                        # typed semantic relations to other notes; see Relation Type Enum
parent: null                         # ID of source note when this note was extracted
observations: []                     # IDs of memory-provider observations generated from this note
extracted_to: []                     # typed-child IDs, appended on extraction and verified on dissolution
---
```

## Field-by-field policy

The full policy is encoded in `06_indexes/schemas/frontmatter_policy.yaml`. Quick reference:

| Field | Filler | Required | Notes |
|---|---|---|---|
| `title` | user, agent | yes | lowercase ASCII `snake_case`; also determines an ordinary note's filename |
| `id` | system | yes | immutable graph anchor, format `<type>-<YYYYMMDD>-<letter>`; never appears in the filename |
| `created` | system | yes | immutable; `dd-MM-YYYY-HH-mm` UTC |
| `modified` | system | yes | updated on edit; `dd-MM-YYYY-HH-mm` UTC |
| `description` | user, agent | no | useful standalone summary; `null` when it would repeat the title or body |
| `type` | user, agent | yes | enum, see below |
| `project` | user, agent | conditional | project-local home matching `01_projects/<slug>`; mutually exclusive with `resource` |
| `area` | user, agent | conditional | area home, or contextual area when `project`/`resource` is set |
| `resource` | user, agent | conditional | global resource home matching `03_resources/<slug>`; mutually exclusive with `project` |
| `status` | user, agent | yes | enum, see below |
| `effort_cadence` | user, agent | no | `heavylift` or `slowburn`; active actionables only; never infer |
| `effort_level` | user, agent | no | `low`, `medium`, or `high`; active actionables only; never infer |
| `tags` | user, agent | no | 3-8 lowercase hyphenated tags |
| `chosen_location` | user, agent | no | **Optional.** One free-text line explaining what this note does in this place in the system - the rationale for its placement (e.g. "kept here as the canonical reference the onboarding flow links to"). Purely documentary; does not affect routing. Useful when a note's home isn't self-evident. |
| `source` | user, agent, system | yes | enum, see below |
| `link` | user, agent | conditional | required for `source: captured` and `imported` |
| `author` | user, agent, system | yes | `user` is default; `agent` when agent creates without explicit user request |
| `depth` | user, agent | no | development level 1-5; leave `null` when the assessment adds no value |
| `appreciated` | **user only** | no | agent forbidden - leave null |
| `importance` | **user only** | no | agent forbidden - leave null |
| `pinned` | user, agent | no | default `false`; user toggles to `true` |
| `expires_at` | user, agent | no | `dd-MM-YYYY-HH-mm` UTC; documentary expiry only, not todo execution or provider-buffer persistence |
| `related` | user, agent | no | IDs of weak/non-qualified related notes |
| `relations` | user, agent | no | Typed semantic relations. Each item is `{type: <relation_type>, target: <note_id>}`. Valid `type` values are centralized in the Relation Type Enum below. |
| `parent` | user, agent | conditional | required for any note extracted from a source note |
| `observations` | user, agent, system | no | IDs of observations in the active memory provider generated from this note |
| `extracted_to` | user, agent, system | conditional | child-note IDs, appended during extraction and reconciled when a linear note is dissolved |

### `depth` scale

`depth` measures how far the note develops its one thesis, not how technical the subject sounds:

```text
1  ordinary, concise treatment
2  developed treatment
3  in-depth treatment with several implications
4  specialized treatment
5  exhaustive reference-level treatment
```

Use `null` when scoring would be arbitrary. A normal note is never assigned `3` by default.

### Effort profile

Effort is explicit planning metadata, not activity tracking. It applies only to actionables with `status: active`:

```text
effort_cadence: heavylift | slowburn
effort_level:   low | medium | high
```

`arpent efforts` groups every active project, area, draft, reading, or other actionable by cadence then level. If either property is `null`, it appears under `unclassified`. The agent never derives an effort profile from timestamps or content without user confirmation.

## Enums

### `type`

```
note          # generic note
concept       # atomic Zettelkasten-style concept
journal       # user-authored journal document
log           # generic activity record
checklist     # structured task list
reference     # note about external content (book, article, podcast)
draft         # production in progress
template      # reusable template
meeting       # meeting notes
idea          # idea to explore
fleeting      # quick capture in inbox/fleeting/
linear        # sequential working note that may be decomposed into typed children
integration   # application of a concept to a real-life problem
angle         # editorial angle
production    # finished published content
map           # Map of Content (MOC) - a navigation note linking other notes
howto         # explicitly reviewed current guidance for one practical problem
artefact      # disposable demonstration, illustration, or temporary script/file note
```

`map` is the Maps-of-Content type (from Nick Milo's ACE). A map is a permanent, evolving navigation note whose body is a structured, annotated set of wikilinks to other notes. Maps live in `03_resources/maps-of-content/`, default to `status: ongoing`, and never rotate or get swept. A map is distinct from `related` and `relations`: those are frontmatter graph edges, while a map is an organized narration of relationships with sections and commentary. See `routing.md` and `lifecycle.md`.

`howto` is a permanent, evolving answer to one specific practical problem. It
contains only the explicitly reviewed guidance that applies now: the current
conclusion, why, how, examples, applicability and limits, and annotated links.
Detailed reasoning, research, alternatives, case studies, and superseded
conclusions remain in linked notes. How-tos live globally in
`03_resources/how-tos/`, default to `status: ongoing`, and never get swept. A
MOC may link several how-tos but remains a navigation note rather than the
authoritative practical answer.

`artefact` is for disposable support material: demonstration files, illustration outputs, temporary scripts, or short-lived examples that should remain outside the clean knowledge buckets. Artefacts live in `05_tools/artefacts/`.

`linear` describes a temporary working form, not a subject or a required output type. It can hold annotated consumption, reflection across concepts, exploratory thinking, or rough material intended to split. Its extracted children may use any note type and route independently. Use `draft` instead when the note itself is one production in progress rather than a source to decompose.

### `status`

```
inbox         # captured, not yet triaged
maturing      # triaged, in active construction, not yet finalized
active        # project, area, or actionable content currently in use
stable        # finalized reusable knowledge
ongoing       # permanent, regularly consulted
standby       # set aside, not abandoned
waiting       # waiting for external dependency
to-start      # to start soon
done          # accomplished or finished terminal content
stale         # terminal content awaiting archival by a tool rule
archived      # retained archive lifecycle state
```

Status describes lifecycle and is not an absolute location. Most status changes
do not move a note; explicit routing or archive operations perform filesystem
moves.

### `source`

```
manual        # written by the user
generated     # created by an Arpent operation
imported      # ingested from an external source
captured      # web clip, screenshot, voice memo, light ingestion
conversation  # extracted from an AI conversation
derived       # synthesized from other notes
```

### `author`

```
user          # default; written by the user
agent         # written by an AI agent without explicit user request
imported      # ingested from an external source
```

### `relation_type`

These are the only valid values for `relations[].type`:

```
supports      # this note strengthens or corroborates the target note
contradicts   # this note conflicts with or challenges the target note
depends_on    # this note requires the target note to be understood or acted on
derived_from  # this note was produced from the target note
example_of    # this note is a concrete example of the target note
```

## Coherence rules

### Body contract

- One reusable thesis per note. If one title cannot state the material cleanly, preview several autonomous notes and ask for one batch confirmation.
- Do not repeat the title as an H1. The `title` property and filename already carry it.
- Put the source URL only in frontmatter `link`, never again under the title or in the body.
- Extracted concepts, ideas, and integrations must make sense without phrases such as "in this source" or "point X from the discussion".
- `reference` and `linear` notes may analyze or quote their source because it is their subject, but still do not repeat its URL.
- A `howto` keeps only the current explicitly reviewed answer in its body. Record
  the review timestamp there and preserve useful removed material in linked
  notes before revising it.
- Default to ordinary Obsidian Markdown: prose, useful headings, lists, and native blockquotes. Avoid callouts and decorative containers unless requested.

### `source` ↔ `link` cross-table

| `source` | `link` constraint |
|---|---|
| `manual` | should be `null` (warn if not) |
| `captured` | URL **required** |
| `imported` | URL or external identifier **required** |
| `generated` | `null` or internal path |
| `conversation` | `null` or session identifier |
| `derived` | `null` |

The CLI validates this at write time. Mismatches → warning, not silent acceptance.

### Routing contract

`project` and `resource` are mutually exclusive homes. `area` may accompany either as context.

A `howto` always uses its global type home. Its `project` and `resource` fields
remain `null`; `area` may identify a contextual domain without changing the
global route.

- `project` set → `01_projects/<project>/`; ordinary content lives in `notes/`
- otherwise `resource` set → `03_resources/<resource>/`
- otherwise `area` set → `02_areas/<area>/`
- all three null → `00_inbox/`
- `project` and `resource` both set → `00_inbox/unsure/<filename>` with `_reason.txt`

A global concept remains in `03_resources/concepts/` even when a project uses it. The project links to it with an Obsidian wikilink; setting `project` would incorrectly make it project-local. A note belongs to the project only when it is not independently useful outside that project.

The CLI implements this as a pure function: `route(frontmatter) → Path`.

### `parent` and `extracted_to`

- A note with `parent: <id>` is a typed child extracted from a linear note. Its parent has `extracted_to: [...]` containing this child's ID.
- The relation is type-agnostic and bidirectional. It is maintained by the `note extract` and `note dissolve` commands.

### `related` and `relations`

- `related` is a flat list of weak/non-qualified note IDs.
- `relations` is a list of typed semantic relations, each shaped as `{type: <relation_type>, target: <note_id>}`.
- Use `relations` when the edge carries meaning (`supports`, `contradicts`, `depends_on`, `derived_from`, `example_of`). Use `related` only when the link is useful but not worth qualifying.

## Examples

### Manual concept note

```yaml
---
title: actionability_gradient
id: concept-20260419-a
created: 19-04-2026-10-00
modified: 19-04-2026-10-00
description: File classification principle ordering items by how much they demand action right now.
type: concept
project: null
area: productivite
resource: concepts
status: stable
effort_cadence: null
effort_level: null
tags: [pkm, classification, para]
chosen_location: null

source: manual
link: null
author: user

depth: 1
appreciated: null
importance: null
pinned: false

expires_at: null

related: [concept-20260415-c]
relations:
  - type: supports
    target: concept-20260415-c
parent: null
observations: []
extracted_to: []
---
```

### Captured article as a reference note

```yaml
---
title: do_things_that_dont_scale
id: reference-20260414-a
created: 14-04-2026-09-15
modified: 14-04-2026-09-15
description: Paul Graham's argument that unscalable founder effort teaches you what users actually want.
type: reference
project: null
area: entrepreneuriat
resource: articles
status: stable
effort_cadence: null
effort_level: null
tags: [entrepreneurship, paul-graham, startups]
chosen_location: null

source: captured
link: https://paulgraham.com/ds.html
author: user

depth: 2
appreciated: null
importance: null
pinned: false

expires_at: null

related: [concept-20260410-c]
relations:
  - type: example_of
    target: concept-20260410-c
parent: null
observations: [obs-20260414-c]
extracted_to: []
---
```

### Linear note - annotated-reading example before dissolution

```yaml
---
title: notes_lecture_how_to_take_smart_notes
id: linear-20260418-a
created: 18-04-2026-20-00
modified: 18-04-2026-22-00
description: Reading notes for Ahrens' book covering Zettelkasten, fleeting/literature/permanent notes, and the slip-box workflow.
type: linear
project: null
area: learning
resource: null
status: maturing
effort_cadence: null
effort_level: null
tags: [zettelkasten, ahrens, pkm, reading]
chosen_location: null

source: imported
link: isbn:9781542866507
author: user

depth: 3
appreciated: null
importance: null
pinned: false

expires_at: null

related: []
relations: []
parent: null
observations: []
extracted_to: []
---
```

After dissolution, this note moves to `04_archives/linear_notes/`, gets `status: archived`, and lists every extracted child regardless of type, for example `extracted_to: [concept-20260420-a, draft-20260420-b, ...]`.

### Agent-authored portrait (in agent_wiki/)

```yaml
---
title: andrej_karpathy_portrait
id: draft-20260419-a
created: 19-04-2026-16-00
modified: 19-04-2026-16-00
description: Co-founder of OpenAI turned independent educator championing radical pedagogy over institutional power.
type: draft
project: null
area: null
resource: null
status: maturing
effort_cadence: null
effort_level: null
tags: [karpathy, ai, education, portrait]
chosen_location: Agent-authored proposal awaiting review in agent_wiki drafts.

source: generated
link: null
author: agent

depth: null
appreciated: null
importance: null
pinned: false

expires_at: null

related: []
relations:
  - type: derived_from
    target: conversation-20260419-a
parent: null
observations: []
extracted_to: []
---
```

### Memory record - time-bound item (buffer role)

This is **not** a vault note. It is non-actionable recall context held only when
the host has an explicitly enabled external-memory provider and that provider
confirms persistence. Shown here for completeness:

```yaml
content: "The cooking venue entrance is on the east side"
project_id: null
area_id: social
expires_at: 15-05-2026-00-00
created_at: 19-04-2026-20-00
```

### Memory record - stable trait (profile role)

Also not a vault note - a memory record in the profile role:

```yaml
content: "I prefer direct feedback over reassurance"
category: communication
confidence: 1.0
created_at: 10-04-2026-15-00
last_confirmed_at: 19-04-2026-10-00
source: manual
```

The exact storage of these records belongs to the active memory system. An
action such as “invite Claire” is a todo, not a buffer. If no provider is
enabled, no memory persistence occurred and no fallback store substitutes for it.
See `memory-layers.md`.

## What this enables

**Pure-function routing.** A complete frontmatter determines its destination uniquely. No agent judgment for placement.

**Powerful queries without embeddings.**

```
# All meetings with Bertrand this quarter
type: meeting AND tags contains "bertrand" AND created on-or-after 01-04-2026-00-00

# All pinned stable knowledge notes
status: stable AND pinned: true

# All captures from this week not yet integrated
type: reference AND source: captured AND created on-or-after 13-04-2026-00-00
```

Use timestamp-aware tooling for chronological comparisons because day-first strings do not sort chronologically. Exact values remain grep-able and jq-able; no LLM is needed.

**Trivial cross-reference.** `related`, `relations`, `parent`, `observations`, `extracted_to` make the graph traversable without parsing markdown body.

**Migration safety.** Immutable `id` makes file renaming and moving safe. An ordinary note's filename is the normalized `title` (`lowercase_ascii_snake_case.md`), while graph references remain valid across automatic renames. Reserved system files such as `_context.md` and append-only fleeting day files keep their prescribed filenames.

**Archive extension.** `archived` is a lifecycle status. `archived_at` and
`archived_from` are lifecycle-only metadata added by an explicit archive event;
they record when and from where the item moved and are never statuses.

## What is NOT in the schema (intentionally)

These were considered and rejected:

- `is_archived` - derivable from `status: archived`
- `word_count`, `read_time` - derivable from content
- `mood`, `emotions` - too subjective; if relevant, use tags (`tags: [triste, espoir]`)
- `visibility: private|team|public` - not needed for solo use; add later if multi-user
- `author_name` - in solo context, always the user; add later if collaboration
- `extra` - an unconstrained extension map encourages redundant metadata and hides tool contracts

The schema stays explicit but non-redundant. New fields go through review before being added.

## Tool-specific data

Tool-specific structured data does not enter an unconstrained universal extension map. It belongs in the tool's database, in a documented body format, or in a new reviewed schema field when it genuinely needs to be queryable across the vault.

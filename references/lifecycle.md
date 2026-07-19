# Lifecycle

How notes evolve over time: from creation to maturation, from active use to archive, and from sequential working material to typed child notes. The lifecycle is encoded in the `status` field plus tool-level rules in `tools.yaml`.

## The eleven statuses

```
inbox      maturing    active    stable    ongoing    standby
waiting    to-start    done      stale     archived
```

### Detailed semantics

| Status | Meaning |
|---|---|
| `inbox` | Captured but not yet triaged. Lives in `00_inbox/`. Should leave within hours/days. |
| `maturing` | Triaged and routed to its final destination, but content not yet finalized. Being actively constructed. |
| `active` | A project, area, or actionable item currently in use: draft, active reading, or other effort. |
| `stable` | Finalized reusable knowledge. The normal state for an established concept or durable note. |
| `ongoing` | Permanent reference, regularly consulted. For things that don't have an end (philosophy notes, profile-like vault entries). |
| `standby` | Set aside, not abandoned. Will return to active later. |
| `waiting` | Blocked on an external dependency (waiting for someone, an event, etc.). |
| `to-start` | Planned to start soon, not yet active. |
| `done` | Accomplished. Mostly used by ephemeral content (todos, articles read). Triggers archival rotation. |
| `stale` | Terminal content no longer current and awaiting archival under a tool rule. |
| `archived` | Moved to archives. Read-only by convention. |

## Status transitions

### Manual (user-initiated)

The user can transition any note's status at any time via:

```bash
arpent note status <id> <new-status>
```

Most transitions are user-driven. The agent never changes status without consent except in narrow automatic cases (see below).

### Automatic (event-driven)

Some transitions are triggered by events, not time:

| Event | Transition |
|---|---|
| Calendar event date passes | `active → done` (auto, on next `calendar sync`) |
| Article marked as read in reader | `active → done` (when user runs `reader read <slug>` and confirms read) |
| Todo marked complete | `active → done` |
| Fleeting note promoted | `inbox → done` (on the source line in fleeting file) |
| Linear note dissolved | `maturing/active → archived` (on `note dissolve`) |
| Project closed | `* → archived` for the project folder |

These are deterministic and the user is informed when they happen.

### Automatic (time-driven, ephemeral sweep)

For tools marked `ephemeral: true` in `tools.yaml`, the cron job `ephemeral-sweep` applies time-based transitions. Automatic archival is limited to `done` and `stale`; `active`, `stable`, and `ongoing` always remain in place. See "Ephemeral sweep" below.

### Suggested (proposed in review)

The system can **suggest** transitions during weekly review without applying them:

- Knowledge notes `maturing` for > 90 days → "consider promoting to `stable` or archiving"
- Notes `standby` for > 6 months → "consider archiving"
- Notes `waiting` with no recent activity on the dependency → "is the dependency still alive?"

The user reviews and confirms. No automatic action.

## The maturation cycle

A note's life often follows this arc:

```
        ┌─────────────────────────────────────┐
        │                                     │
   capture                                    │
        │                                     │
        v                                     │
     inbox  ──[triage]──>  maturing           │
                              │               │
                              v               │
                     active or stable         │
                              │               │
                              v               │
                          ongoing             │
                              │               │
                              v               │
                          standby             │
                              │               │
                              └──> archived ──┘
```

Maturation in detail:

1. **inbox** - capture lands. Triage decides where it goes.
2. **maturing** - note is at its destination and still being worked on; useful relations or wording may remain incomplete.
3. **stable** - reusable knowledge is finalized: its one thesis is autonomous and its useful relations are identified.
4. **active** - reserved for projects, areas, and content that remains actionable rather than merely known.
5. **ongoing** - reserved for permanent evolving references (rare).
6. **standby** - temporary set-aside. Returns to `active` when reactivated.
7. **archived** - final state.

`maturing` is **a status, not a location**. The note already lives at its final destination. Don't move maturing notes to a "drafts" folder unless they're explicitly `type: draft` tied to a project.

## Decision: who decides "stable"?

A knowledge note transitions from `maturing` to `stable` when the user recognizes it as finalized. The system can suggest candidates in weekly review based on:

- Frontmatter coherence (title, routing, source, and any useful relations)
- Time since last edit (no edits for 7+ days suggests stability)
- Has at least 1 useful graph link (`related` for weak links, or `relations` for typed semantic links)

But the agent **never auto-promotes**. The user confirms.

## TTL on `maturing` (passive signal only)

A note `maturing` for > 90 days is flagged in the weekly review report:

```
Stale maturing notes (12):
  - concept-20260120-a - "gradient_actionnabilite"  (90 days maturing)
  - reference-20260115-c - "ahrens_smart_notes"   (95 days maturing)
  ...

Suggestions: review these and either promote to stable, archive, or continue maturing.
```

No automatic action. The user decides.

## Linear note dissolution

A `type: linear` note is a sequential, non-atomic working note whose useful parts may later become separate notes. It is defined by this decomposition lifecycle, not by its subject or by the types it will produce. It may contain an annotated reading or listening, a reflection across existing concepts, exploratory thinking, or rough material from which drafts and other notes emerge.

Use `linear` when the note is a temporary source to work through and potentially split. Use the final semantic type directly when the material already has one identity: for example, use `draft` for one production in progress and `concept` for one atomic concept.

In the continuity loop, "produce" means broad useful work, not a command or a
required note type. Use `type: production` only for an output whose semantic
identity is a finished production; decisions, plans, drafts, concepts, and
other useful results keep their own types.

### Phase 1 - Accumulation

The train of thought is still developing. Passages, annotations, arguments, questions, and possible outputs accumulate in sequence.

- Lives at the destination determined by its own routing frontmatter. Reader-managed content may remain in `05_tools/reader/<type>/<slug>/` while it is being consumed.
- Status: usually `active` while being captured, then `maturing` while being worked through

### Phase 2 - Ready to decompose

The note has enough substance to identify one or more durable outputs. Its routing does not change merely because it reached this level of reflection.

For reader-managed material, finishing the first consumption is one way to reach this phase: `arpent reader finish <slug>` moves the note to the area chosen by the user and sets `status: maturing`.

### Phase 3 - Typed extraction (optional)

The user decides which parts should become independent notes. Every child gets the semantic type that matches what it is, then routes through the normal contract.

```bash
arpent note extract <linear-id> --type concept --title "Actionability gradient" --resource concepts --body "..."
arpent note extract <linear-id> --type draft --title "Essay opening" --project knowledge-essay --stdin
```

Each extraction:
- Creates a child note of the requested type and routes it from its own frontmatter
- The new note has `parent: <linear-id>`
- The linear note's body gets an unambiguous wikilink `[[relative/path/child-title-slug]]` near the relevant passage

The user can extract any number and mixture of child types, including `concept`, `draft`, `idea`, `integration`, `reference`, or another `linear` note. Facts and commitments that belong in agentic memory follow the memory-routing rules instead; their IDs go in `observations`, not `extracted_to`.

### Phase 4 - Dissolution

Once all intended children are extracted, the user dissolves the source:

```bash
arpent note dissolve <linear-id> [--yes]
```

The dissolution:
- Verifies all `extracted_to` IDs exist as notes with `parent` pointing back
- Sets status to `archived`
- Migrates the file to `04_archives/linear_notes/<slug>.md`
- Updates `extracted_to: [list of all extracted child-note IDs]`

The dissolution is deliberate and never inferred automatically. `always` and
`explicit-intent` require `--yes`; `never` executes the user's dissolution
request without a second approval. Validation of every child relation remains
mandatory in all modes.

### Optional path - no extraction

Not every linear note needs to be dissolved. Some working notes remain useful as a whole. A linear note can stay at its routed destination indefinitely with `status: active` or `ongoing`.

## Ephemeral sweep

Installed tools marked `ephemeral: true` in `tools.yaml` have a `lifecycle` config that drives automatic rotation. Example for fleeting:

```yaml
fleeting:
  ephemeral: true
  lifecycle:
    - from: inbox
      after_days: 14
      to: stale
    - from: stale
      after_days: 7
      action: archive
```

The cron job `ephemeral-sweep` runs daily at 04:00 (configurable) and:

1. Reads `tools.yaml`, identifies installed tools with `ephemeral: true`
2. For each tool, reads its `lifecycle` rules
3. Walks `writes_to` directory and examines each file's `status` and `modified`
4. Applies matching transitions, but archives only `done` or `stale` content
5. Logs every change in `06_indexes/logs/sweep.log`
6. Produces a summary visible via `arpent sweep status`

Use `arpent sweep ephemeral --dry-run` to preview due rules without changing
notes. A run applies at most one rule per note and resets `modified` on a status
transition, so a second TTL cannot fire in the same run.

### Sweep actions

Three actions possible for an `archive` step:

#### `archive`

Moves the file to `04_archives/<YYYY_qX>/<tool>/`, preserves frontmatter intact, adds:

```yaml
archived_at: 19-04-2026T04:00:00Z
archived_from: 02_areas/sport/sessions/seance_force.md
```

The file is searchable, readable, but out of the active workspace.

#### `archive-with-trace`

Before archiving the markdown, writes a structured row to the tool's DB. Used when:

- The DB capture is rich enough that the markdown can be lightly purged or moved
- The user values analytics over preserving full markdown history

Example for `todo`:

```sql
-- todo.db trace row retained before markdown archive
INSERT INTO todos (
  id, content, priority, status, linked_project_id, created_at
) VALUES (
  'todo-20260415-a', 'Validate migration plan', 'priority-high', 'done',
  'project-arpent-build', '2026-04-15T09:00:00Z'
)
ON CONFLICT(id) DO UPDATE SET
  content = excluded.content,
  priority = excluded.priority,
  status = excluded.status,
  linked_project_id = excluded.linked_project_id;
```

The markdown still goes to `04_archives/`, but the DB has the structured trace.

#### `delete-after-review`

Reserved for content with no historical value. The file is **proposed** for deletion with a summary; the user must confirm. Rarely used. Opt-in only.

### Default lifecycles for niveau 1 sub-tools

| Tool | Default lifecycle |
|---|---|
| `todo` | `done → archive-with-trace` after 30 days |
| `fleeting` | `inbox → stale` after 14 days; `stale → archive` after 7 more days |
| `reader` | `done → archive-with-trace` after 60 days; **no expiration on `active`** (queue is sacred) |
| `calendar` | `done → archive-with-trace` after 14 days |

These can be overridden per-tool in `tools.yaml`.

### Status gate

There is no per-note lifespan override. A note that remains useful must carry a status that says so: `active` for current action, `stable` for established knowledge, or `ongoing` for permanent evolving material. The sweep may archive only `done` or `stale` notes according to the owning tool's delay.

## Manual archival

Beyond the sweep, the user can manually archive one ordinary note by ID:

```bash
arpent archive <note-id>
```

This:
- Moves the note to `04_archives/<YYYY_qX>/`
- Sets `status: archived` in frontmatter
- Adds `archived_at` and `archived_from`

Todos use `arpent todo archive`; linear notes use confirmed dissolution. A
folder, project, or arbitrary file requires a separately previewed manual
procedure.

## End-of-session protocol

At the end of any working session, the agent updates context in a fixed order so the next session starts coherent. This is adapted from Eliott Meunier's IPCRA update order (project context → agent init → memory log).

At the start of the next session, resume documentarily in either mode: read root
`me.md`, then the target project/area `_context.md`, then only the specific notes
or sources needed. There is no resume command. Normal resume must not read the
optional `06_indexes/memory/MEMORY.md` log unless the user explicitly asks for
or enables it.

The implemented local order is:

1. **Update the `_context.md` by default** for the project or area worked on by
   appending a timestamped `Session update` block. The CLI normalizes it to the
   complete universal frontmatter field set, preserves all free-form body
   sections, and appends rather than rewriting them.
2. **Only with `--memory-log`, prepend a `MEMORY.md` entry** with the session's
   target, summary, decisions, and next steps. This optional cross-project log
   is disabled by default and its existence does not authorize later reads.
3. **Full mode only:** queue supplied observations and traits in
   `pending_db_writes.yaml`. This CLI-owned queue records deferred intent only;
   Arpent has no command that flushes it to an external provider. Minimal mode
   rejects observation/trait flags before mutation and never creates the queue.

The CLI exposes this as:

```bash
arpent session end [--project <slug>] [--area <slug>] [--memory-log]
```

The `_context.md` step and explicit `--memory-log` option work in full and
minimal modes. Fresh vaults in both modes do not seed the log; minimal mode does
not seed `06_indexes/memory/` at all. Minimal mode therefore supports project
creation, project/area context, capture, documentary resume, useful production,
and close without delegated memory.

A close without `--project` or `--area` must name another explicit sink:
`--memory-log`, or in full mode at least one `--observation` or `--trait`.

The host remains responsible for persisting durable observations and traits to
external memory. Queueing them locally does not claim that persistence
succeeded; see `ingestion-and-degraded-mode.md`.

The point: durable local context lives in `_context.md`; `MEMORY.md` is only an explicitly enabled, lightweight, disposable operational thread. Never write session logs into canonical memory, never leave a permanent fact only in `MEMORY.md`, and never read that optional log without user opt-in.

## The memory wiki has its own, looser lifecycle

`06_indexes/memory/wiki/` is the one zone where the normal cleanliness rules are relaxed. It holds the agent's short-to-medium-term research scratch and tolerates drafts and mess. It is **not** swept by the ephemeral sweep and does **not** follow the vault's status lifecycle. Instead, it is pruned and distilled by the agent during periodic cleaning sessions. Pages that prove durable can be distilled into clean vault notes; the rest can be left or discarded. This full-mode zone is deliberately exempt from the strict discipline applied to the 7 buckets.

## What never gets archived

These items live indefinitely in the active workspace:

- `06_indexes/` content (code, schemas, docs, databases, `MEMORY.md`) - infrastructure
- `03_resources/concepts/` notes with `status: stable` or `ongoing` - permanent knowledge base
- `03_resources/maps-of-content/` notes (`type: map`) - permanent navigation, always `status: ongoing`, never rotate or get swept
- `_context.md` files in projects and areas - they travel with their project/area when archived, never independently
- `02_areas/<area>/philosophy.md` and similar foundational area docs
- Any note with `status: active` or `stable`
- Any note with `status: ongoing`

## Maps of Content never rotate

A `type: map` note is permanent and evolving by design. It is created at a "mental squeeze point" (Nick Milo) when a topic has enough notes that navigation gets hard, and it grows with the user's thinking - links get added, reorganized, annotated; large maps get split. A map is always `status: ongoing`, is exempt from the ephemeral sweep, and only leaves the active workspace if the user explicitly archives it.

## Summary

The lifecycle in one sentence: **the active workspace stays light because ephemerals rotate, while permanent content stays accessible because it never auto-archives**. The user controls what is permanent. The system handles the rotation of what isn't.

# Architecture

This is the explanatory architecture of a current Arpent vault. Operational
agents should start with `SKILL.md`, a mode document, and one compact workflow
or contract. The installed CLI and packaged operation contract remain
authoritative for executable behavior.

Arpent is a local continuity and administration layer.

## Vault Root

```text
~/arpent-vault/
├── .agent
├── .arpent
├── .gitignore
├── COMPASS.md
├── me.md
├── 00_inbox/
├── 01_projects/
├── 02_areas/
├── 03_resources/
├── 04_archives/
├── 05_tools/
└── 06_indexes/
```

Full initialization also creates `.git/` without making a commit. Minimal mode
requires neither Git nor subsequent CLI use.

### Entry Files

- `.agent` is the small agent entry point and hard-rule summary.
- `.arpent` is the validated mode marker.
- `COMPASS.md` selects a less common operation; it is not loaded for every
  capture.
- `me.md` is the human-owned orientation file. It is not an inferred profile or
  automatic memory log.

The current marker format is version 2:

```json
{
  "version": 2,
  "name": "arpent",
  "mode": "minimal",
  "auto_full": true
}
```

`mode` is `minimal` or `full`. A minimal marker with `auto_full: true` records a
request for guarded promotion when a mode-gated command is first used. An
explicit return to minimal clears that request.

## Seven Buckets

### `00_inbox/`

Physical intake and visible uncertainty:

```text
00_inbox/
├── captures/
├── fleeting/
│   └── dd-mm-yyyy.md
└── unsure/
```

`triage` inventories non-fleeting inbox content but does not move it. Ambiguous
routing uses `unsure/` plus a neighboring reason file. Fleeting files are
append-only day streams without per-entry frontmatter or IDs.

`status: inbox` commonly describes untriaged capture, but status and location
are not aliases. A physical inbox path and a lifecycle status are independent
dimensions.

### `01_projects/`

A project is a deliberate, time-bounded effort:

```text
01_projects/<project>/
├── _context.md
├── notes/
├── drafts/
└── attachments/
```

`arpent project create <name>` creates this shape. `area` is optional project
context, not a prerequisite; when supplied it must resolve to an existing area.
Project-local notes may carry `project` plus optional `area` metadata.

`session end` closes a working session by appending a handoff to `_context.md`.
It does not close or archive the project. This release has no automatic project
closure or project-folder archival command.

### `02_areas/`

Areas represent ongoing responsibilities. They are user-defined and optional;
Arpent does not seed a personal taxonomy. An area needs `_context.md` only when
the user chooses to maintain continuity for it. The template at
`02_areas/_context.template.md` supports direct minimal-mode instantiation.

The installed todo tool uses its declared area:

```text
02_areas/area__perso__todo__active/
├── active/
├── waiting/
└── done/
```

### `03_resources/`

Resources are reusable document homes. The base scaffold includes:

```text
03_resources/
├── concepts/
├── maps-of-content/
├── how-tos/
├── integrations/
├── templates/
├── agent_wiki/
│   └── drafts/
└── agent_infrastructure/
    ├── agent_roles/
    ├── agent_skills/
    ├── agent_workflows/
    ├── agent_prompts/
    ├── agent_templates/
    ├── agent_style/
    └── capabilities/
```

The routing contract also reserves `books`, `articles`, `portraits`, and
`productions`. Reserved resources are declared homes, so a write may
materialize their directory when first needed. They are not arbitrary guesses.
Any undeclared missing resource routes to `00_inbox/unsure/` until it is
deliberately created, for example through `init --structure` or reviewed import.
Projects and areas are never created as routing side effects.

`maps-of-content/` contains navigation notes for broad subjects. `how-tos/`
contains explicitly reviewed current guidance for specific practical problems;
the detailed reasoning and history remain in linked notes.

`agent_wiki/` holds agent-authored drafts awaiting user review. Portable agent
definitions live under `agent_infrastructure/`; their index in `06_indexes/` is
a discovery derivative, not their canonical content.

### `04_archives/`

Explicit archive operations use quarterly directories. Dissolved linear notes
use the dedicated `linear_notes/` directory:

```text
04_archives/
├── 2026_q3/
└── linear_notes/
```

`archived` is a lifecycle status. `archived_at` and `archived_from` record the
time and source of an archival event; they are lifecycle-only schema extensions,
not statuses. Changing an ordinary note's status to `archived` does not itself
move the file. `arpent archive`, `arpent todo archive`, and `note dissolve` are
the explicit move operations for their respective record kinds.

### `05_tools/`

This is runtime material only. It may hold artifacts, captures, caches, or
outputs explicitly declared by an installed tool. It never holds a skill,
schema, migration, command contract, or maintenance instructions.

The delivered scaffold contains `05_tools/artefacts/`. Planned tools do not gain
runtime availability merely because a registry entry or design path exists.

### `06_indexes/`

This is the control, generated-state, and local-administration zone:

```text
06_indexes/
├── cli/operations.yaml
├── global_skills/
│   ├── arpent.skill.md
│   ├── context_summary.skill.md
│   ├── todo.skill.md
│   ├── reader.skill.md
│   ├── review.skill.md
│   ├── z_backup.skill.md
│   └── _template_tool.skill.md
├── schemas/
├── docs/
├── databases/
├── imports/
├── memory/wiki/
├── backup/
├── logs/
├── tools.yaml
├── cron.json
├── index.json
├── sidecar.json
└── context_index.json
```

The skills actually seeded are exactly those listed above. `arpent`, `todo`,
and `context_summary` describe delivered operation. `reader`, `review`, and
`z_backup` are `status: planned`, in construction, and not invocable as tool
workflows. The core `arpent backup` command is delivered independently of the
planned `z_backup` extension. Future tool design is historical/planning material
outside the operational references, not an operational contract.

`tools.yaml` is a declarative registry. `arpent tools list/show` inspects it; the
current CLI does not install, enable, disable, or dispatch tool skills. A tool
skill may be invoked only when its registry entry says `status: installed` and
its command, mode, dependencies, and configuration are actually available.

`cron.json` is a job registry. Arpent runs no daemon: an external scheduler may
invoke an explicit `cron run --tick`. Local command execution requires a trust
declaration and explicit execution enablement.

## Data Authority

No single phrase such as “files are canonical” accurately covers every state:

- Markdown is canonical for documents, project/area context, and readable
  history.
- Original attachments are canonical source material.
- `todo.db` is authoritative for todo's coordinated structured state; its
  Markdown records are durable readable counterparts and consistency checks bind
  both representations.
- The installed argparse tree is authoritative for command syntax.
- The packaged operation contract owns enums and default routing; the vault copy
  is reviewable configuration with a limited routing overlay.
- `index.json`, `sidecar.json`, search state, context derivatives, and agent
  infrastructure indexes are rebuildable or derived.

## Routing And Location

Ordinary precedence is `project > resource > area > inbox`. `project` and
`resource` are mutually exclusive homes; `area` may accompany either as
context. Type, provenance, and a small number of explicit lifecycle operations
can refine the destination.

Status is not a location. `note status` changes lifecycle state and moves only
when a declared status/type route exists; ordinary archival requires the
explicit archive command. This is why documentation must not describe `inbox`
as an absolute path rule or imply every status transition moves a file.

## Modes

Minimal mode operates ordinary documents and context directly while preserving
the same structure and contracts. Full mode uses the CLI for locking,
confinement, atomic publication, coordinated SQLite/Markdown state, recovery,
imports, indexes, sweep, cron, and backups.

Both modes preserve user-readable information. Minimal does not emulate
coordinated todo state or multi-file transactions.

## Continuity Surfaces

Resume in this order:

1. Read user-authored `me.md`.
2. Read the target project or area `_context.md`.
3. Read only the specific sources needed for the current task.

`_context.md` stores current state, decisions, next steps, and a short session
history. It is never independently swept. `MEMORY.md` is optional, absent by
default, and not part of normal resume. The full-mode `session end` command
creates or updates it only when `--memory-log` is explicitly passed; a later
read requires a separate explicit request.

Arpent does not ship an external memory provider. Provider-bound facts, traits,
or non-actionable recall context are persisted only when the host exposes an
explicitly enabled provider. Without one, no persistence should be claimed and
no fallback store should be substituted.

## Mutation Safety

The invariant is absence of silent loss, not prohibition of mutation. A
requested edit may atomically publish a replacement for its own source.
Destinations are collision-checked and are never silently replaced; ambiguous
routes remain visible; binaries retain their bytes; and batch operations report
partial outcomes honestly.

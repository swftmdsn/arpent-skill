# Architecture

The complete physical and conceptual structure of an Arpent vault.

## Vault root

```
~/arpent-vault/
├── .git/                                  # versions everything except .gitignore exclusions
├── .gitignore
├── .agent                                 # entry point for AI agents
├── .arpent                             # marker JSON: {"version":1,"name":"arpent","mode":"full"}
├── 00_inbox/
├── 01_projects/
├── 02_areas/
├── 03_resources/
├── 04_archives/
├── 05_tools/
└── 06_indexes/
```

Everything outside `.git/`, `.gitignore`, `.agent`, and `.arpent` is buckets.

## The seven buckets

### 00_inbox/ - captures, fleeting, and unresolved routing

Sas of new items not yet routed. Three sub-zones:

```
00_inbox/
├── fleeting/               # fleeting notes, organized by date
│   └── dd-mm-yyyy.md       # one file per day, append-only during the day
├── unsure/                 # ambiguous items parked with a written reason
└── (root)                  # raw files dropped for triage (uploads, captures)
```

The inbox is **transient**. Items leave within hours to days via `triage`. Fleeting notes have their own lifecycle (see `lifecycle.md`).

### 01_projects/ - time-bound efforts with deliverables

Each project has a folder named with a slug. Inside: a `_context.md` at the root, then notes, drafts, attachments related to the project.

```
01_projects/
├── arpent-build/
│   ├── _context.md         # project context, maintained by the agent (see below)
│   ├── notes/
│   ├── drafts/             # drafts tied to this project go here
│   └── attachments/
└── portfolio-v2/
```

A project ends → archived to `04_archives/<YYYY_qX>/projects/`.

**Projects belong to areas.** A project and its local notes carry both `project: <project-slug>` and `area: <area-slug>`. `project` determines the physical route to `01_projects/`; `area` records the contextual responsibility. Reusable concepts remain global resources and are linked from projects with wikilinks rather than moved or duplicated. `arpent efforts` independently groups every `active` actionable by its explicit cadence and level.

### 02_areas/ - ongoing responsibilities

Areas are domains of life that don't end. Health, work, sport, finance, relationships, etc.

```
02_areas/
├── sport/
│   ├── sessions/                   # content written by sport sub-tool
│   ├── measurements/
│   ├── philosophy.md
│   └── notes/
├── journal/
│   └── 2026/04/2026-04-19.md
└── finance/
```

Areas are the natural home for **area-bound sub-tool content** (Option C - see below).

The 18 areas you've listed as initial taxonomy: Work, Voyages, Transport, Sport, Social, Sécurité informatique, Santé, Psychologie, Productivity, Orientation (Personal Alignment), Nutrition, Learning, Investissement, Finances, Habits, Business, Administratif & Papiers, Calendar.

### 03_resources/ - reference and knowledge base

Reusable knowledge not tied to a project or active responsibility.

```
03_resources/
├── concepts/                   # Zettelkasten-style atomic concepts
├── maps-of-content/            # type: map - MOCs, permanent navigation notes (Nick Milo ACE)
├── integrations/               # type: integration - concept applied to a real problem (Thomas)
├── books/
├── articles/
├── portraits/                  # portraits of people who inspire
├── templates/
├── agent_wiki/                 # notes created by agent (separate scope)
│   ├── _README.md
│   ├── concepts/
│   ├── portraits/
│   ├── summaries/
│   ├── connections/
│   └── drafts/
└── agent_infrastructure/       # portable definitions for agents
    ├── _README.md
    ├── agent_roles/
    │   └── <role-name>/AGENT.md
    ├── agent_skills/
    │   └── <skill-name>/SKILL.md
    ├── agent_workflows/
    │   └── <workflow-name>/WORKFLOW.md
    ├── agent_prompts/
    ├── agent_templates/
    ├── agent_style/
    └── capabilities/
        └── <capability-name>/CAPABILITY.yaml
```

### 04_archives/ - flat-temporal archives

Two archive zones with different semantics:

```
04_archives/
├── 2026_q1/                    # quarterly archives - anything archived in this period
│   ├── projects/
│   ├── areas/
│   └── ephemeral/              # ephemeral items archived by the sweep
├── 2026_q2/
└── linear_notes/               # special: dissolved linear notes (no quarter)
    ├── book-sapiens-harari-20260410-a.md
    └── article-paul-graham-20260414-c.md
```

Archives are read-only by convention. The CLI never writes to past quarters. `linear_notes/` is flat, not by quarter - these notes have a separate semantic (dissolved sources of typed child notes).

### 05_tools/ - runtime material only

`05_tools/` contains no know-how. Tool skills, command contracts, schemas,
migrations, creation templates, and maintenance documentation all belong in
`06_indexes/`. A path under `05_tools/` exists only because an installed tool
declares it in `writes_to` for artifacts, queues, captures, caches, or outputs.

Area-bound tools normally write user content directly to `02_areas/<area>/`
and may need no `05_tools/<tool>/` folder. Transversal tools may use a runtime
workspace under `05_tools/<tool>/`, but their definition remains in
`06_indexes/`.

```
05_tools/
├── artefacts/                  # disposable demo files, illustration outputs, temporary scripts
├── reader/                     # transversal - captures from web/books/podcasts
│   ├── articles/
│   │   └── <slug>/
│   │       ├── article.md
│   │       ├── archive.html
│   │       └── .meta.json
│   ├── books/
│   └── podcasts/
└── ...                         # created only when an installed tool writes here
```

Planned tools do not pre-create runtime folders. This control-plane/runtime
boundary is non-negotiable.

### 06_indexes/ - the system's brain

```
06_indexes/
├── cli/                                # reviewable contracts mirrored from the installed CLI
│   └── operations.yaml                 # contract-first operation and routing registry
├── global_skills/                      # SKILL.md for sub-tools - VAULT SKILLS (operate the vault)
│   ├── arpent.skill.md
│   ├── context_summary.skill.md
│   ├── reader.skill.md
│   ├── sport.skill.md
│   └── journal.skill.md
├── schemas/
│   ├── profile_schema.sql               # legacy design reference; no runtime provider
│   ├── holographic_schema.sql           # legacy design reference; no runtime provider
│   ├── todo_schema.sql                  # Phase 2 todo.db initial schema
│   ├── frontmatter_policy.yaml
│   └── scoring_matrices.yaml           # Phase 3+
├── docs/                               # Arpent's own documentation
│   ├── ARPENT.md                       # the constitution
│   ├── mental-model.md
│   ├── architecture/
│   │   ├── cli.md
│   │   ├── frontmatter.md
│   │   ├── indexing-and-context.md
│   │   ├── tools.md
│   │   ├── routing.md
│   │   └── memory-layers.md
│   ├── tools/
│   │   ├── reader.md
│   │   └── ...
│   ├── backlog.md
│   └── usage-journal.md
├── documentation/                      # external doc - third-party tools and references
│   ├── external-tools/
│   │   ├── singlefile.md
│   │   ├── khal.md
│   │   ├── vdirsyncer.md
│   │   ├── exiftool.md
│   │   └── sqlite-fts5.md
│   ├── references/
│   │   ├── para-method.md
│   │   ├── zettelkasten.md
│   │   └── gbrain-patterns.md
│   └── cheatsheets/
│       ├── yaml-frontmatter-syntax.md
│       └── arpent-dates.md
├── databases/                          # tool-owned structured state
│   ├── sport.db                        # area-bound tool DBs
│   ├── journal.db
│   ├── crm.db
│   └── reader.db                       # transversal tool DBs
├── memory/                             # the memory zone (see memory-layers.md)
│   ├── MEMORY.md                       # optional cross-project log; absent by default
│   └── wiki/                           # mini-LLM-Wiki - agentic research scratch (provider: wiki)
│       ├── SCHEMA.md                   # conventions the agent follows when writing here
│       ├── raw/                        # immutable source clippings
│       └── pages/                      # agent-generated, interlinked topic/entity pages
├── backup/                             # rotated local snapshots (external backup also recommended)
│   ├── 2026-04-19/
│   ├── 2026-04-18/
│   └── ...
├── logs/
│   ├── sweep.log
│   ├── triage.log
│   └── cron.log
├── tools.yaml                          # SINGLE index of all installed tools
├── cron.json                           # registry of recurring jobs
├── agent_infrastructure_index.yaml     # index of roles, skills, workflows, prompts, and capabilities
├── index.json                          # generated directory index
├── sidecar.json                        # generated file metadata
├── context_index.json                  # generated L0/L1/L2 cache; L1 is optional AI output
└── pending_db_writes.yaml              # CLI-owned session integration queue; no flush command
```

Memory may be delegated to a host interface beside Arpent (see
`memory-layers.md`). The full-mode memory wiki under `memory/wiki/` holds agent
research scratch. `MEMORY.md` is not seeded and remains disabled unless a
specific `session end --memory-log` opts in. Arpent does not ship or operate a
native memory provider.

`arpent index` inventories folders and all user-owned files, not only notes. It
creates exact file hashes and a generated L0/L1/L2 context cache. L0 is a
deterministic one-line orientation; L1 is an optional AI summary tied to a
semantic source hash; L2 points to the source or direct folder children. AI is
never invoked by indexing. The explicit workflow lives in
`06_indexes/global_skills/context_summary.skill.md`; details are installed at
`06_indexes/docs/architecture/indexing-and-context.md`.

### 00_inbox/unsure/ - ambiguous items

Files the system or agent could not route confidently. Each accompanied by a `<filename>_reason.txt` explaining the ambiguity. As part of the inbox, these items show up in `triage` and the inbox counters.

```
00_inbox/unsure/
├── 20260419-screenshot.png
├── 20260419-screenshot.png_reason.txt
├── article-confused-routing.md
└── article-confused-routing.md_reason.txt
```

The user reviews `00_inbox/unsure/` periodically and resolves the ambiguity manually.

### Binary and non-text attachments

A binary/non-text file is durable source material, remains byte-for-byte
untouched, and cannot contain YAML. `arpent note ingest --attachment` moves the
original transactionally from inbox to the selected project, area, or resource
`attachments/` directory and creates a separate Markdown companion reference
note with the complete universal frontmatter field set. Its `link` points to the
attachment. Without a final home, the original remains in inbox and the
companion reference is created there as untriaged material.

### Reviewed external imports

Bulk migration is a distinct scan/review/apply pipeline, not recursive `note
ingest`. A compact JSON plan stores folder decisions while a hashed JSONL
inventory streams one record per external file. Deterministic classification
proposes Project, Area, Resource, Group, Inbox, or Ignore with confidence and an
inspectable reason. Decisions inherit down the tree and remain inert until the
review is complete.

Apply is copy-only and refuses source/vault overlap. It creates reviewed
destinations, stages one source at a time, and delegates note/attachment creation
to the ordinary ingestion transaction. Durable progress and reports live under
`06_indexes/imports/<import-id>/`, which is excluded from indexing and Git.
Batch application is resumable and per-item atomic; the batch itself may
partially succeed. No format-specific connector or external classifier is part
of the core pipeline.

## Minimal mode - fast setup, full-schema compatible

Arpent can be initialized with `arpent init --minimal` for a deliberately
**minimal mode**: the 7 buckets, the **complete universal frontmatter** on every
note, deterministic PARA routing, and the **index module** (`arpent index`,
regenerating `index.json` + `sidecar.json` so the entire tree of folders and
files stays visible and queryable at a glance). The frontmatter is *not* reduced
in minimal mode: every note is born with the full schema written out, using
`null`, `[]`, or `false` for unused values. What minimal mode strips is optional
**modules**, not the note contract or local continuity. It includes `arpent
project create`, project/area `_context.md`, local `arpent session end`,
actionable triage/ingestion, usage reports, reviewed external import, and the core
note/index/search/archive/health/backup commands. It does not seed
`06_indexes/memory/`; the optional `MEMORY.md` log is created only by an explicit
`--memory-log`. It omits delegated-memory queue writes, context summaries, cron,
todo, tools, sweep, the memory wiki, and portable-agent infrastructure. The
`context`, `tools`, `cron`, `sweep`, and
`todo` command groups refuse to run in this mode; `session` does not. Agents
must always write the full frontmatter and must not create omitted module
structure preemptively.

## Tool control plane and runtime placement

This is **the** architectural decision for tool placement.

```
All tools:
  Skill       → 06_indexes/global_skills/<tool>.skill.md
  CLI contract→ 06_indexes/cli/ (executable installed outside the vault)
  Schema/DB   → 06_indexes/schemas/ + 06_indexes/databases/
  Registry    → entry in 06_indexes/tools.yaml

Area-bound tool (e.g., sport):
  User content → 02_areas/sport/sessions/
  05 runtime   → absent unless explicitly required by writes_to

Transversal tool (e.g., reader):
  Runtime      → 05_tools/reader/
  Know-how     → remains entirely in 06_indexes/
```

When the user opens Obsidian and looks for sport sessions, they go to
`02_areas/sport/`. When an agent needs to understand or evolve the sport tool,
it reads `06_indexes/`. `05_tools/` never teaches the agent how a tool works.

## .git and .gitignore

The vault IS a git repo. `arpent init` runs `git init`; it does not create a
commit, because commit authorship and timing remain user-controlled.
`.gitignore` excludes:

- All `*.db` and journal/wal/shm files (binary, non-mergeable, regeneratable)
- `06_indexes/backup/` (redundant with git history)
- `06_indexes/imports/` (generated resumable import state and reports)
- `06_indexes/index.json`, `06_indexes/sidecar.json`, `06_indexes/context_index.json` (generated)
- Python artifacts (`__pycache__/`, `*.pyc`, `.venv/`, `*.egg-info/`)
- `05_tools/artefacts/*` except `.gitkeep` (disposable demo files, illustration outputs, temporary scripts)
- `05_tools/*/cache/`, `05_tools/*/articles/*/archive.html` (heavy SingleFile snapshots)
- `05_tools/*/articles/*/.meta.json` (regeneratable)
- `06_indexes/secrets/`, `*.pem`, `*.key`, `credentials.json`
- OS cruft (`.DS_Store`, `Thumbs.db`, `*.swp`)
- `.obsidian/workspace.json` (volatile)

Hosting recommendation: local-only initially. If multi-device needed later: self-hosted Gitea/Forgejo. Avoid GitHub for sovereignty.

## .agent and .arpent

`.agent` is the entry point for any AI agent. It contains a quick orientation:

```markdown
# .agent - Entry point for AI agents working in this Arpent vault

Read this FIRST, completely, before doing anything else.

## What this is
An Arpent vault - a personal filesystem-native life OS.

## Reading order
1. Read me.md (human-owned orientation)
2. Read COMPASS.md (operation router)
3. Read 06_indexes/docs/ARPENT.md (the constitution)
4. Read 06_indexes/docs/mental-model.md (the delegated memory model)
5. Read 06_indexes/global_skills/arpent.skill.md (operating skill)
6. Skim 06_indexes/schemas/frontmatter_policy.yaml

For a concrete resume: me.md -> target _context.md -> only needed notes/sources.
Do not read optional MEMORY.md without explicit user opt-in.

## Hard rules
- Never delete files. Archive.
- Never fill subjective fields (appreciated, importance). Leave null.
- Never guess routing. Use 00_inbox/unsure/ with reason.
- Never dump facts into the vault. Delegated memory is disabled by default and
  requires explicit user opt-in; the vault is a clean knowledge base.
- Always announce moves and renames before executing.
- Always use the arpent CLI for state changes.

## Commands
arpent project create / note new / note ingest / import scan-review-apply / triage --json / session end / usage report
arpent status / search / efforts / archive / sweep
(external-memory writes use the host interface when one is available - see memory-layers.md)
```

`.arpent` is a JSON marker file:

```json
{
  "version": 1,
  "name": "arpent",
  "mode": "full"
}
```

The CLI uses `.arpent` to detect that a directory is an Arpent vault root.

## agent_wiki/ - separate scope for agent-authored content

When an agent creates a note without explicit user request (e.g., a synthesized portrait, an extracted concept proposal), it goes to `03_resources/agent_wiki/`, not directly to a final destination.

```yaml
# In the agent_wiki note's frontmatter:
author: agent
agent_wiki_status: draft         # draft | reviewed | integrated | archived
```

Promotion flow:

1. Agent creates note in `agent_wiki/` with `author: agent`, `agent_wiki_status: draft`
2. User reviews; if approves: `agent_wiki_status: reviewed` (stays in agent_wiki)
3. User decides to promote: `agent_wiki_status: integrated`, file moves to final destination (e.g., `03_resources/concepts/`)
4. `author: agent` is **preserved** - the lineage stays.

This keeps a clear separation between user-authored and agent-authored content while allowing seamless integration.

## agent_infrastructure/ - portable agent definitions

Distinct from `06_indexes/global_skills/` (which contains sub-tool skills coupled to Arpent):

| Location | Purpose |
|---|---|
| `06_indexes/global_skills/` | SKILL.md for sub-tools (sport, journal, reader, etc.) - coupled to the CLI |
| `03_resources/agent_infrastructure/` | Generic, reusable, portable roles/skills/workflows/prompts/capabilities not coupled to a sub-tool |

Why separate: `agent_infrastructure/` is potentially shareable (git submodule, public repo) without exposing the rest of the vault. Sub-tool skills are tied to your Arpent and don't make sense outside.

The canonical definitions live in `03_resources/agent_infrastructure/`; `06_indexes/agent_infrastructure_index.yaml` is only their discovery registry. The categories have distinct responsibilities:

| Definition | Location | Responsibility |
|---|---|---|
| Role-based agent | `agent_roles/<id>/AGENT.md` | Role, instructions, boundaries, and permitted capability IDs |
| Agent skill | `agent_skills/<id>/SKILL.md` | Reusable method for accomplishing a task |
| Workflow | `agent_workflows/<id>/WORKFLOW.md` | Predetermined orchestration of roles, skills, prompts, and capabilities |
| Simple prompt | `agent_prompts/` | Small reusable instruction without its own execution package |
| Capability | `capabilities/<id>/CAPABILITY.yaml` | Portable declaration of an available CLI, MCP server, API, or harness plugin |
| Style/template | `agent_style/`, `agent_templates/` | Reusable presentation rules and output structures |

A capability declaration describes how an agent may address a means of action; it does not contain the implementation or a secret. CLI implementations remain installed executables, MCP servers remain external services, API keys remain in environment variables or a secret manager, and harness plugins remain configured by their harness. Capability manifests store only public connection metadata and references such as `credential_ref: env:OPENAI_API_KEY`.

The detailed hierarchy is installed at `06_indexes/docs/architecture/agent-infrastructure.md`.

Examples in `agent_infrastructure/agent_skills/`:

- `capture-portrait/` - synthesize a portrait of a person from web search
- `synthesize-book/` - produce a structured book summary
- `weekly-brief/` - compile the morning brief from agenda + tasks
- `thinking-partner/` - strategic reflection session
- `board-review/` - simulate a board of advisors review (Ulysse-style)
- `integrate/` - apply a concept to a real problem (Thomas-style anti-oubli)

Each skill follows the imposed Trigger / Input / Steps / Output / Method format.

## documentation/ - external knowledge

`06_indexes/documentation/` is for documentation **about the world around Arpent**, not Arpent itself.

```
documentation/
├── external-tools/
│   ├── singlefile.md       # how to use SingleFile CLI for archiving
│   ├── khal.md             # khal calendar quick reference
│   ├── vdirsyncer.md       # CalDAV sync setup
│   └── exiftool.md         # EXIF tag reference
├── references/
│   ├── para-method.md      # synthesis of Tiago Forte's PARA
│   ├── zettelkasten.md
│   └── gbrain-patterns.md  # what we borrowed/rejected from gbrain
└── cheatsheets/
    ├── yaml-frontmatter-syntax.md
    ├── arpent-dates.md
    └── markdown-extensions.md
```

Distinction from `docs/`:

- `docs/` = Arpent's own documentation (constitution, architecture, mental model)
- `documentation/` = documentation Arpent consults (third-party tools, references)

This separation answers "is this doc OF Arpent or is this doc Arpent USES?".

## `_context.md` - per-project and per-area context note

Every `01_projects/<slug>/` and every instrumented `02_areas/<slug>/` carries a `_context.md` at its root. Create a project in either mode with `arpent project create <name> [--area <slug>] [--effort-cadence heavylift|slowburn] [--effort-level low|medium|high]`; this also creates `notes/`, `drafts/`, and `attachments/`. Project creation never creates an area or merges a collision. It happens during init only when explicitly declared by `--structure`; note routing never creates one. The context is the agent's anchor for that project or area and is updated at the end of a working session.

Inspired by Eliott Meunier's IPCRA practice: each project and "casquette" has a context note maintained by the AI so that any session starts with full, current context instead of re-explaining from zero.

A `_context.md` created by `project create` or created/updated by `session end`
carries the complete universal frontmatter field set plus a user-extensible body.
The example below abbreviates null and empty fields for readability; generated
files keep the complete shape:

```yaml
---
title: arpent_project_context
id: note-20260419-z
created: 19-04-2026T10:00:00Z
modified: 19-04-2026T10:00:00Z
description: Living context for the Arpent build project.
type: note
project: arpent-build
area: productivity
resource: null
status: active
effort_cadence: null
effort_level: null
source: generated
author: agent
---

## Vision
One-paragraph statement of what this project is and why it exists.

## Current state
Where things stand right now. Updated at the end of each session.

## Resume here
The exact next place from which useful work can continue.

## Deliverables / definition of done
What completion means for this project.

## Key resources
- [[specification_principale]] - the core spec
- 06_indexes/docs/ARPENT.md - the constitution

## Next steps
- Ship Phase 1 CLI core
- 14-day real-use validation

## Working rhythm and time budget
The user-approved cadence or ritual budget for this project.

## Session history
Timestamped blocks appended by `arpent session end`.
```

Rules:

- A project `_context.md` is `status: active`; an area `_context.md` is
  `status: ongoing`. Both use `author: agent` and `source: generated` (the agent
  maintains them; the user may edit freely).
- Resume in this order: root `me.md`, this target `_context.md`, then only the
  specific notes or sources needed. Do not read optional `MEMORY.md` without
  explicit user opt-in.
- `session end` preserves all body sections and appends its session block.
- The universal schema is closed during normal use. Users may add/reorder body
  sections and create project files/subfolders, but unsupported frontmatter
  fields are rejected. Schema extension requires coordinated canonical schema,
  order, validation, policy, documentation, and test changes.
- The static `architecture_template/01_projects/_template_project/_context.md`
  does not drive the code-generated `project create` template. Edit a created
  `_context.md` directly for normal use; when developing Arpent, change both the
  runtime builder and static template deliberately.
- It is never swept and never auto-archived. When the project is archived, its `_context.md` goes with it.

## `MEMORY.md` - optional cross-project operational log

`06_indexes/memory/MEMORY.md` is an optional, human-readable cross-project log.
It is disabled by default in both modes, fresh vaults do not seed it, and normal
resume must not read it.

- The **agentic memory provider** holds canonical facts and traits. Not session flow.
- **`_context.md`** stores per-project context. Not cross-project session flow.
- The **memory wiki** holds research scratch. Not a session log.

When the user wants this extra surface, `arpent session end --memory-log`
creates or updates it for that invocation. Agents must not read it later unless
the user explicitly asks for or enables that behavior. The pattern was inspired
by Eliott's `memory.md` and Hermes's `MEMORY.md`, but it is no longer part of the
default continuity path.

Format: newest first, with a manual target of roughly 15 entries. The CLI does
not truncate the log; older entries are pruned during confirmed cleaning
sessions.

```markdown
# MEMORY - Arpent working log

## 2026-04-19 - arpent-build
- Decided: maps-of-content as type:map, stored in 03_resources/maps-of-content/
- Decided: `arpent efforts` command for explicit required-investment profiles, never timestamp-derived
- Next: integrate decisions into the skill bundle

## 2026-04-18 - portfolio-v2
- Reviewed 3 deep projects to feature
- Next: draft the "voici ce que je suis" intro
```

Rules:

- `MEMORY.md` is a plain markdown file, not a database. Its existence alone does not authorize agent reads.
- It is updated only when `session end --memory-log` is passed.
- It is disposable operational state, distinct from canonical memory (the provider) and from the memory wiki (research). Prune freely.
- It holds roughly the last 15 sessions - enough continuity without bloating context. Older entries are pruned during periodic cleaning sessions.

## The memory zone and the clean-vault boundary

In full mode, `06_indexes/memory/` can gather the optional `MEMORY.md` log and
the `wiki/` research scratch. Minimal mode does not seed this directory, though
an explicit `--memory-log` can create the log path. Durable facts and traits
remain outside Arpent behind an optional host interface. The boundary is
specified in `memory-layers.md`.

The principle that governs this zone: the 7 buckets must stay **clean and comprehensible to the user**; `06_indexes/memory/wiki/` is the one sanctioned zone with high tolerance for agent-generated mess and drafts.

## Vault skills vs personal-agent commands

Two kinds of "skill" live in the vault, and they must not be confused (distinction from Eliott's slash-commands practice):

| Kind | Location | Purpose | Example |
|---|---|---|---|
| **Vault skills** | `06_indexes/global_skills/` | Operate Arpent itself - coupled to the CLI and the vault's mechanics | `arpent.skill.md`, `sport.skill.md`, `reader.skill.md` |
| **Personal-agent commands** | `03_resources/agent_infrastructure/agent_skills/` | Recurring personal tasks tied to the user's activity, not to vault mechanics | `weekly-brief`, `synthesize-book`, `integrate`, `board-review` |

The test: *"Does this skill operate the vault, or does it perform a task in the user's life?"* A skill that knows how to route a note, run a sweep, or maintain frontmatter is a vault skill. A skill that drafts a newsletter, prepares a coaching session, or applies a concept to a problem is a personal-agent command. Vault skills are coupled to Arpent and don't make sense outside it. Personal-agent commands are portable and could be shared (git submodule, public repo) without exposing the vault.

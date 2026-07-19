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
`06_indexes/`. A path under `05_tools/` exists only because a tool with
`status: installed` declares it in `writes_to` for artifacts, queues, captures,
caches, or outputs.

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
└── ...                         # created only for tools with status installed
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
├── tools.yaml                          # SINGLE index of declared tools and registry status
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
`06_indexes/global_skills/context_summary.skill.md`; details are documented at
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

## Minimal mode - direct files, complete information

Minimal retains the same seven buckets, skills, contracts, schemas, and complete
universal frontmatter as full. Its difference is operational: an agent reads,
searches, creates, routes, updates context, and archives directly in canonical
files. Mode-gated CLI commands require vault-mode promotion. Todo dual state, coordinated import,
extraction/dissolution, generated context, backup, cron, sweep, and delegated
queues remain retained and dormant until the vault returns to full. Minimal
initialization requires neither Git nor a CLI after creation.

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

Full mode uses a Git repository. Full `arpent init` and promotion run `git init`;
they do not create a commit, because commit authorship and timing remain
user-controlled. Minimal initialization requires no Git and an explicit return
to minimal may retain an existing dormant `.git` directory.
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

`.agent` is the compact entry point for any AI agent. It prevents duplicate
loading when a host Arpent skill is already loaded and selects context by
operation:

```markdown
# .agent - Arpent vault entry point

Read this file completely, then load only what the operation needs.

1. Read the small `.arpent` marker.
2. Do not reload the local skill when an Arpent host skill is loaded.
3. Otherwise load the local Arpent skill.
4. Use the loaded skill's hot path for ordinary work.
5. Read COMPASS.md only to classify a less common operation.
6. Read me.md for interaction preferences and concrete resume.
7. On resume, read target _context.md, then only needed notes/sources.

## Hard rules
- Never delete files. Archive.
- Never fill subjective fields (appreciated, importance). Leave null.
- Never guess routing. Use 00_inbox/unsure/ with reason.
- Never dump facts into the vault. Delegated memory is disabled by default and
  requires full mode plus provider opt-in; the vault is a clean knowledge base.
- Apply the local confirmation policy to moves and renames before executing.
- In minimal, operate direct-file capabilities and leave coordinated state
  dormant. In full, use CLI-mediated vault operations.
- Keep the delegated-memory integration disabled until provider opt-in.
```

`.arpent` is a JSON marker file:

```json
{
  "version": 2,
  "name": "arpent",
  "mode": "minimal",
  "auto_full": true
}
```

The CLI uses `.arpent` to detect that a directory is an Arpent vault root. A
minimal marker with `auto_full: true` records a pending guarded vault-mode
promotion request. The first mode-gated CLI command triggers the transition,
which initializes full infrastructure,
switches the guarded marker, rebuilds deterministic derivatives, and restores
the exact minimal marker on failure. Seeded dormant files and `.git` may remain
after a failed reconciliation, leaving the request pending. An explicit return
to minimal clears `auto_full` and cancels the request.

## agent_wiki/ - separate scope for agent-authored content

When an agent creates a note without explicit user request (e.g., a synthesized portrait, an extracted concept proposal), it goes to `03_resources/agent_wiki/`, not directly to a final destination.

```yaml
# In the agent_wiki note's universal frontmatter:
type: draft
status: maturing
author: agent
```

Promotion flow:

1. The agent creates a standard `type: draft`, `author: agent` note in
   `agent_wiki/drafts/`.
2. Review keeps the note there while its ordinary lifecycle status evolves.
3. Promotion changes the standard `type`, routing home, and status, then moves
   the note to its final destination.
4. `author: agent` is preserved so lineage stays visible.

No agent-wiki-only frontmatter key is added to the closed universal schema.

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
| Capability | `capabilities/<id>/CAPABILITY.yaml` | Portable declaration of CLI, MCP, API, or plugin access; not proof of runtime availability |
| Style/template | `agent_style/`, `agent_templates/` | Reusable presentation rules and output structures |

A capability declaration describes how an agent may address a means of action;
it does not contain the implementation or a secret, and does not prove runtime
availability. Availability also requires that the current vault mode permits
use, dependencies are satisfied, and host configuration or enablement is present
where applicable. CLI implementations remain installed executables, MCP servers
remain external services, API keys remain in environment variables or a secret
manager, and harness plugins remain configured by their harness. Capability
manifests store only public connection metadata and references such as
`credential_ref: env:OPENAI_API_KEY`.

The detailed hierarchy is documented at `06_indexes/docs/architecture/agent-infrastructure.md`.

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

Every `01_projects/<slug>/` and every instrumented `02_areas/<slug>/` carries a `_context.md` at its root. Full creates a project with `arpent project create <name> [--area <slug>] [--effort-cadence heavylift|slowburn] [--effort-level low|medium|high]`; minimal creates the same `_context.md`, `notes/`, `drafts/`, and `attachments/` directly. Project creation never creates an area or merges a collision. The context is the agent's anchor for that project or area and is updated at the end of a working session.

Inspired by Eliott Meunier's IPCRA practice: each project and "casquette" has a context note maintained by the AI so that any session starts with full, current context instead of re-explaining from zero.

A `_context.md` created by `project create` or created/updated by `session end`
carries the complete universal frontmatter field set plus a user-extensible body.
The example below abbreviates null and empty fields for readability; generated
files keep the complete shape:

```yaml
---
title: arpent_project_context
id: note-20260419-z
created: 19-04-2026-10-00
modified: 19-04-2026-10-00
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
The user-set cadence or ritual budget for this project.

## Session history
Timestamped blocks appended by `arpent session end`.
```

Rules:

- A project `_context.md` is `status: active`; an area `_context.md` is
  `status: ongoing`. Both use `author: agent` and `source: generated` (the agent
  maintains them; the user may edit freely).
- Resume in this order: root `me.md`, this target `_context.md`, then only the
  specific notes or sources needed. Reading optional `MEMORY.md` requires a
  separate explicit read request.
- `session end` preserves all body sections and appends its session block.
- The universal schema is closed during normal use. Users may add/reorder body
  sections and create project files/subfolders, but unsupported frontmatter
  fields are rejected. Schema extension requires coordinated canonical schema,
  order, validation, policy, documentation, and test changes.
- The seeded project and area context templates drive direct minimal
  instantiation but do not generate CLI-created contexts. Edit instantiated
  `_context.md` files directly; when developing Arpent, change both runtime
  builders and static templates deliberately.
- It is never swept and never auto-archived. When the project is archived, its `_context.md` goes with it.

## `MEMORY.md` - optional cross-project operational log

`06_indexes/memory/MEMORY.md` is an optional, human-readable full-mode
cross-project log. It is disabled by default, fresh vaults do not seed it, and
normal resume must not read it.

- The **agentic memory provider** holds canonical facts and traits. Not session flow.
- **`_context.md`** stores per-project context. Not cross-project session flow.
- The **memory wiki** holds research scratch. Not a session log.

When the user wants this extra surface, `arpent session end --memory-log`
records a one-use full-mode write request. Reading it later requires a separate
explicit read request. The pattern was inspired
by Eliott's `memory.md` and Hermes's `MEMORY.md`, but it is no longer part of the
default continuity path.

Format: newest first, with a manual target of roughly 15 entries. The CLI does
not truncate the log; older entries are pruned during deliberate cleaning
sessions under the confirmation policy.

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

- `MEMORY.md` is a plain markdown file, not a database. Its existence does not
  constitute an explicit read request.
- It is updated only by a one-use full-mode `session end --memory-log` request.
- It is disposable operational state, distinct from canonical memory (the provider) and from the memory wiki (research). Prune freely.
- It holds roughly the last 15 sessions - enough continuity without bloating context. Older entries are pruned during periodic cleaning sessions.

## The memory zone and the clean-vault boundary

In full mode, `06_indexes/memory/` can gather the optional `MEMORY.md` log and
the `wiki/` research scratch. Minimal retains this directory but does not operate
it. Full-mode durable facts and traits may remain outside Arpent behind an
optional host interface. The boundary is specified in `memory-layers.md`.

The principle that governs this zone: the 7 buckets must stay **clean and comprehensible to the user**; `06_indexes/memory/wiki/` is the one sanctioned zone with high tolerance for agent-generated mess and drafts.

## Vault skills vs personal-agent commands

Two kinds of "skill" live in the vault, and they must not be confused (distinction from Eliott's slash-commands practice):

| Kind | Location | Purpose | Example |
|---|---|---|---|
| **Vault skills** | `06_indexes/global_skills/` | Operate Arpent itself - coupled to the CLI and the vault's mechanics | `arpent.skill.md`, `sport.skill.md`, `reader.skill.md` |
| **Personal-agent commands** | `03_resources/agent_infrastructure/agent_skills/` | Recurring personal tasks tied to the user's activity, not to vault mechanics | `weekly-brief`, `synthesize-book`, `integrate`, `board-review` |

The test: *"Does this skill operate the vault, or does it perform a task in the user's life?"* A skill that knows how to route a note, run a sweep, or maintain frontmatter is a vault skill. A skill that drafts a newsletter, prepares a coaching session, or applies a concept to a problem is a personal-agent command. Vault skills are coupled to Arpent and don't make sense outside it. Personal-agent commands are portable and could be shared (git submodule, public repo) without exposing the vault.

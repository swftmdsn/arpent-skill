# Arpent

### Make every project easier to continue, hand over, and build upon.

Arpent keeps context, decisions, and knowledge connected, so the work you do today becomes useful infrastructure for tomorrow.

**Keep the context. Preserve the why. Compound the work.**

---

## What Arpent is

Arpent is a local, single-user, filesystem-native personal LifeOS for people who collaborate with changing AI agents. It combines a structured Markdown vault, a deterministic command-line interface, and operating rules that tell agents where to read, where to write, and when to ask.

The vault is the durable layer: projects, decisions, reusable knowledge, tasks, context, and archives remain in inspectable local files. The CLI applies deterministic operations. AI agents are replaceable operators rather than owners of the system.

Arpent is not a note-taking application, autonomous agent, semantic retrieval service, or bundled long-term memory provider. It is an administration and continuity layer between those tools and the work you intend to keep.

## Quick start

Arpent requires Python 3.9 or later and Git. From a local checkout:

```bash
python3 -m pip install -e .
arpent --version
arpent init ~/my-vault
cd ~/my-vault
```

This installs both `arpent` and the shorter `arp` alias. Use `arpent init ~/my-vault --minimal` for the smaller core vault, or start with the full mode shown above.

The core loop is:

```bash
arpent note new "A question worth exploring"
arpent status
arpent triage
arpent index
arpent search "question"
```

The complete concepts, setup options, workflows, command reference, safety boundaries, limitations, and roadmap follow below.

## At a glance

```text
YOU
 |
 v
AGENT + ARPENT SKILL
understands intent, applies rules, asks when needed
 |
 v
ARPENT CLI
creates, routes, searches, indexes, and archives
 |
 v
LOCAL ARPENT VAULT
projects | areas | resources | todo
context  | indexes | archives | agent workspaces
 |
 +--> OPTIONAL EXTERNAL SERVICES
      memory provider | scheduler | external backup
```

The skill defines how an agent should interpret and operate the system. The CLI performs deterministic operations. The vault holds the durable work. Memory providers, schedulers, and external backups remain optional and replaceable.

### The three layers

Arpent is easier to understand when its three layers remain separate:

| Layer | Responsibility | Source of truth |
|---|---|---|
| **Vault** | Durable notes, source files, project context, task traces, configuration, and archives | Local files under the vault root |
| **CLI** | Validation, deterministic routing, atomic mutations, indexing, search, maintenance, and backup | The installed `arpent` package |
| **Agent operating model** | Interpret natural-language intent, read the right context, propose subjective changes, and invoke the CLI | `.agent`, the installed vault skill, `COMPASS.md`, and host instructions |

The CLI is intentionally non-interactive. It does not understand a natural-language request, conduct a review conversation, or ask for routing clarification. A configured agent can provide that interaction, but the command itself validates its arguments and executes immediately.

### Source, state, and derivatives

Not every file in a vault has the same authority:

- Markdown notes and original attachments are durable source material.
- Frontmatter is structured state attached to a readable note.
- `_context.md` and todo Markdown records are durable continuity surfaces. `MEMORY.md` is an optional cross-project log, disabled and unseeded by default.
- `todo.db` is authoritative structured state for the todo module and must remain consistent with its Markdown records.
- `index.json`, `sidecar.json`, and `search.db` are rebuildable derivatives.
- `context_index.json` is generated, but it can also hold optional L1 summaries that are preserved in backups.
- External memory, schedulers, Git remotes, and backup transport live outside Arpent's core boundary.

Most note systems help you store what happened. Arpent helps the work remain usable:

- projects carry enough context to resume or hand over;
- decisions retain the reasons behind them;
- reusable knowledge escapes the project that produced it;
- temporary material leaves the active workspace without erasing history;
- authorship, sources, relations, and lifecycle state remain inspectable;
- agents can share durable context without sharing a vendor or conversation history.

The result is less reconstruction, less repeated explanation, and more reuse. Good work becomes infrastructure for the next project instead of dead material from the last one.

## Own the system, rent the intelligence

Arpent is filesystem-first. Markdown and original files remain readable without Arpent, and generated indexes can be replaced or rebuilt.

AI is leverage, not the foundation. A configured agent can navigate, maintain, connect, and act on the structure, but the model is replaceable and the work remains yours.

> **Own the system. Rent the intelligence.**

Your next agent does not need the memory of your previous agent. It needs the same durable context, decisions, source material, and operating rules.

## What you use it for

Arpent supports a practical work loop:

1. Capture a thought, task, meeting, reference, or working note without perfect classification.
2. Route it from explicit metadata into a project, area, resource, inbox, archive, or visible uncertainty zone.
3. Resume work from maintained project context instead of reconstructing the past.
4. Extract durable ideas from exploratory material while preserving their source lineage.
5. Review active effort, stale material, unresolved routing, and the balance between capture and reflection.
6. Close a session by recording what changed, what was decided, and what should happen next.

Beside that detailed practical loop, the continuity composition is:

```text
capture -> resume (read files) -> produce -> close
```

| Stage | Current behavior |
|---|---|
| **Capture** | `arpent note new`, fleeting capture, full-mode todo, or `arpent note ingest` |
| **Resume** | Read `me.md`, then the target project/area `_context.md`, then only the specific notes or sources needed; never read optional `MEMORY.md` without explicit user opt-in; there is no resume command |
| **Produce** | Continue broad useful work in ordinary notes or drafts, using the semantically correct type and status |
| **Close** | `arpent session end` records summary, decisions, and next steps for the next session |

Production means useful durable work, not a specialized pipeline. Use `type: production` only when a finished output is semantically a production note; Arpent ships no `production` command or dedicated content pipeline.

With an agent configured to follow Arpent's operating rules, that can feel like:

> "What did we decide, why did we decide it, and what should happen next?"

> "Extract the reusable ideas from this reflection and keep their connection to the source."

> "What has gone stale, and which projects require the most investment?"

These are agent-assisted workflows, not literal CLI commands. The deterministic CLI remains the execution layer beneath them.

### Vocabulary

| Term | Meaning |
|---|---|
| **Vault** | A directory recognized by a valid `.arpent` marker |
| **Bucket** | One of the seven numbered top-level organizational directories; unresolved routing lives under `00_inbox/unsure/` |
| **Structured note** | A Markdown file with Arpent frontmatter and a stable `id` |
| **Linear note** | Exploratory or sequential source material from which typed child notes can be extracted |
| **Fleeting capture** | An append-only entry in a UTC-dated stream, without a per-entry ID |
| **Routing** | Computing a physical path from type, status, and project/area/resource metadata |
| **Context L0/L1/L2** | Deterministic orientation, optional hash-bound summary, and original source respectively |
| **Dissolution** | Archiving a linear source after its durable children have been extracted and validated |
| **Sweep** | Applying configured lifecycle rules to installed ephemeral tools |
| **Full mode** | Core vault plus context, session, tools, cron, sweep, todo, memory surfaces, and agent infrastructure |
| **Minimal mode** | Core notes, routing, project creation, project/area `_context.md` session continuity, index, search, health, archive, and backup; no seeded `06_indexes/memory/` |

## Who it is for

Arpent is designed for researchers, builders, writers, independent operators, and other people whose work spans more projects, decisions, and ideas than one conversation can hold.

It is especially useful if you:

- repeatedly explain the same project context to new agents;
- lose the reasoning behind decisions after a few weeks;
- collect more information than you turn into insight;
- want reusable ideas to strengthen future projects;
- want local, inspectable files instead of application lock-in;
- accept some metadata discipline in exchange for continuity and control.

Arpent is probably not the right fit if you want a five-minute filing method, collaborative cloud software, best-in-class semantic retrieval, or an autonomous system that reorganizes your work in the background. PARA is simpler to adopt, dedicated retrieval and memory systems are stronger on their own axes, and Arpent's differentiating administration layer still needs real-world validation.

### What adoption requires

Arpent trades hidden application behavior for explicit operation. A useful deployment therefore requires:

- comfort with local files, Markdown, and a command line;
- willingness to create project and area destinations deliberately;
- occasional inbox, uncertainty, lifecycle, and backup review;
- a separate strategy for remote backup or multi-device synchronization;
- explicit host configuration if an AI agent should discover and follow the Arpent skill;
- restraint around direct edits to machine-coordinated state such as todo records.

---

## What ships today

Arpent is in active pre-release development. The current implementation includes:

- a seven-bucket vault scaffold for active work, reusable knowledge, tools, archives, and uncertainty under `00_inbox/unsure/`;
- deterministic note creation, editing, routing, status changes, and archival;
- deliberate project creation with canonical complete `_context.md` and project folders;
- append-only fleeting capture;
- project and area context plus local end-of-session continuity in full and minimal modes;
- actionable inbox inventory, structured-note dry-run plans, and lossless raw-file ingestion;
- whole-vault file inventory and local full-text search over structured notes;
- optional L0/L1/L2 progressive context with hash-aware AI summaries;
- effort and health views computed from the live vault;
- extraction of typed child notes from linear working material and deliberate source dissolution;
- configurable lifecycle sweeps with dry runs and audit logs;
- a SQLite-backed todo flow with readable Markdown traces;
- read-only tool inspection, an explicit cron registry, local usage schema v2 logging, and usage reports;
- templates for agent roles, skills, workflows, and capability declarations, plus directories for prompts and styles.

The CLI command surface is tested, but the product has not completed its required real-world validation period.

### Implementation status by capability

| Capability | Current state |
|---|---|
| Vault initialization and discovery | Implemented in full and minimal modes |
| Structured notes and deterministic routing | Implemented |
| Fleeting capture | Implemented through `note new --type fleeting` |
| Inventory, keyword search, and progressive context index | Implemented |
| Explicit L1 summary storage | Implemented; summary generation remains external |
| Project creation and local project/area session continuity | Implemented in full and minimal modes |
| Actionable triage and raw-file ingestion | Implemented in full and minimal modes |
| Local usage v2 events and reports | Implemented in full and minimal modes |
| Todo workflow | Implemented in full mode with SQLite schema version 2 |
| Tool registry inspection | Implemented; installation and activation commands are not |
| Lifecycle sweeps | Implemented for installed ephemeral tools |
| Cron registry execution | Implemented; scheduling daemon is external |
| Logical snapshots, verification, and restore | Implemented |
| Reader, calendar, sport, journal, and CRM | Placeholders or planned specifications, not installed tools |
| Semantic/vector retrieval | Not shipped |
| Delegated long-term memory provider | Optional host integration, disabled and not bundled |
| Collaboration, server, authentication, and built-in sync | Not shipped |

### Current limits

- Arpent is local and single-user. It has no server, authentication, collaboration layer, or built-in sync.
- The editable Python installation installs the CLI only. It does not register an agent skill with a host application.
- `arpent init` seeds `.agent`, `COMPASS.md`, and a compact vault-local operating skill, while this repository keeps the fuller source specification in `SKILL.md` and the reference documents. Host-specific discovery and activation are not automated.
- Delegated memory is an interface and operating model, disabled by default in
  both minimal and full vault modes. Hindsight, Supermemory, and other providers
  require explicit user opt-in at the host level and are not bundled or wired by
  the CLI.
- Search is keyword-based. Semantic search and cross-provider memory search are not shipped.
- Todo is the only installed daily-flow tool. Reader, calendar, journal, sport, and CRM commands currently exit as not installed. Fleeting capture works through `note new --type fleeting`; the separate `fleeting` command is only a placeholder.
- A fresh vault has no autonomous lifecycle. The seeded cron job is disabled and requires an external scheduler.
- Backup creates a verified, restorable logical vault snapshot locally or in a chosen filesystem directory. It includes ordinary local logs, including usage events, but is not encrypted, remote, or a backup of external memory and Git history.
- Re-running `arpent init` only adds missing current-format seeds. It does not
  migrate or upgrade files from previous Arpent formats.
- The CLI has no `area create`, top-level `review`, tool installation, memory
  queue flush, dedicated resume, capture, or production command. Reviewed
  filesystem migration is implemented under `arpent import ...`.
- `triage` inventories every non-fleeting inbox item and exposes actions, ages, and hashes, but remains non-interactive and does not move files itself. An agent must propose and confirm the plan before applying per-item operations.
- Dry runs prevent the target lifecycle or cron mutation, but they can still write usage, audit, sweep, or notification logs.

This distinction is deliberate: the working core, the agent operating specification, and the roadmap are related, but they are not presented as equally shipped.

## Install

Arpent requires Python 3.9 or later. Git is also required by `arpent init`,
which initializes every vault as a repository. From a local checkout of this
repository:

```bash
python3 -m pip install -e .
arpent --version
```

This installs `arpent` and the shorter `arp` alias. The runtime uses only the Python standard library; package installation uses standard Python build tooling.

### Recommended isolated installation

An editable virtual-environment installation keeps development dependencies and entry points isolated:

```bash
git clone <repository-url> arpent
cd arpent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
arpent --version
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

Because this is an editable installation, changes in the checkout are reflected by the installed command. Re-run `python -m pip install -e .` if package metadata or entry points change.

### Verify the prerequisites

```bash
python3 --version
git --version
arpent --version
arpent --help
```

Python must be 3.9 or newer. `git` must be available on `PATH` when `arpent init` runs. Arpent does not create the first commit or configure a remote.

### Agent-host installation is separate

Installing the Python package exposes shell commands only. It does not copy `SKILL.md` into Claude, Codex, OpenCode, or another host; register a skill according to that host's own discovery rules. A newly initialized full vault still includes `.agent`, `COMPASS.md`, and `06_indexes/global_skills/arpent.skill.md` so any agent with filesystem access can be explicitly directed to the vault-local instructions.

There is not yet a published one-command agent-skill installer. An agent can still call the CLI from a shell, but host-specific skill packaging remains release work.

## Start here

The first command to know is `init`:

```bash
arpent init ~/my-vault
```

`arpent init` creates the full scaffold and initializes it as a Git repository.
Use `arpent init ~/my-vault --minimal` for the seven buckets, complete
frontmatter/routing contracts, the core Arpent skill, project creation, local
project/area `_context.md` continuity, and index support. Minimal mode does not
seed delegated-memory queues, the memory wiki, context summaries, cron, todo,
tools, sweep, or portable-agent modules. The `context`, `tools`, `cron`, `sweep`,
and `todo` command groups refuse to run in a minimal vault; `project create` and
local `session end` work alongside core note, index, search, archive, health,
usage report, and backup commands.

Both modes create the seven vault buckets, `.arpent`, `.agent`, `COMPASS.md`,
`me.md`, the complete routing/frontmatter contracts, the core vault-local Arpent
skill, and directories used by indexes, import state, databases, and logs. Full
mode additionally seeds optional context, todo, cron, tool, memory-wiki, backup,
documentation, and portable-agent surfaces. Minimal mode intentionally omits
those optional modules.

Neither mode seeds `MEMORY.md`; minimal mode does not seed `06_indexes/memory/`
at all. An explicit `session end --memory-log` can create the optional log in
either mode for that invocation.

`init` does not create your projects or areas unless they are explicitly declared
with `--structure <file.json|file.md>`. A structure file may independently list
Areas, Resources, and projects; JSON project objects may also set `area`,
`effort_cadence`, and `effort_level`. Area and Resource entries create folders,
while project entries create the canonical project context and subfolders. Init
still does not register the skill with an agent host, create a Git commit, or
enable background jobs. Project creation otherwise remains a deliberate next
step with `arpent project create <name>`; note routing never invents a project.
Running init again in the same mode adds missing current seeds, reuses safe
Area/Resource directories and canonical matching projects without overwriting
them, and refuses incomplete or conflicting projects. This can add local
continuity seeds to an older minimal vault, but it does not rewrite stale
user-edited instructions, perform a version migration, or change a vault
implicitly between modes. Git initialization and privacy-allowlisted usage
telemetry can still have ordinary operational side effects.

### Seed an initial structure

Use `--structure` when the initial Areas, Resources, or projects are already
known and should be created as part of an explicit initialization:

```bash
arpent init ~/my-vault --structure structure.json
```

The file may define any subset of `areas`, `resources`, and `projects`. The
option works in both full and minimal mode.

#### JSON format

The JSON root is an object. Areas and Resources are lists of names. A project
may be a simple name or an object with optional Area and effort metadata:

```json
{
  "areas": ["Personal", "Work"],
  "resources": ["Books", "Design references"],
  "projects": [
    "Website refresh",
    {
      "name": "Office move",
      "area": "Work",
      "effort_cadence": "heavylift",
      "effort_level": "high"
    }
  ]
}
```

Project objects accept only these keys:

| Key | Required | Accepted value |
|---|---:|---|
| `name` | Yes | Non-empty name that produces a safe project slug |
| `area` | No | Configured or already existing Area name/slug, or `null` |
| `effort_cadence` | No | `heavylift`, `slowburn`, or `null` |
| `effort_level` | No | `low`, `medium`, `high`, or `null` |

Unknown root or project keys are rejected rather than silently ignored.

#### Markdown format

Markdown is intended for simple name lists. Use `Areas`, `Resources`, and/or
`Projects` headings followed by bullet items:

```markdown
# Areas
- Personal
- Work

# Resources
- Books
- Design references

# Projects
- Website refresh
- Office move
```

Headings may be singular or plural and may use any Markdown heading level. Text
outside recognized sections is ignored. Inside a recognized section, every
non-empty line must be a `-`, `*`, or `+` list item. Markdown project entries do
not carry Area or effort metadata; use JSON when those fields are needed.

#### Creation and validation rules

- Area names normalize to lowercase ASCII snake case: `Personal Life` becomes `personal_life`.
- Structured Area slugs such as `area__perso__health__active` are preserved.
- Resource names normalize to lowercase ASCII kebab case: `Design References` becomes `design-references`.
- Project names normalize to lowercase ASCII kebab case: `Website Refresh` becomes `website-refresh`.
- Duplicate names that normalize to the same slug are rejected within their section.
- Areas and Resources create only their destination folders under `02_areas/` and `03_resources/`.
- Projects create `01_projects/<slug>/_context.md` plus `notes/`, `drafts/`, and `attachments/`.
- A project Area must already exist or be declared in the same structure file. Existing direct and structured Area aliases resolve through the normal routing rules.
- The complete structure is validated before a new vault is initialized, so a missing project Area or unsafe existing destination does not leave a newly created scaffold behind.
- Reusing the same file is idempotent for existing Area and Resource folders and canonical matching projects.
- An existing project is accepted only when its canonical folders and complete `_context.md` are present and its Area/effort fields match. Arpent never repairs, merges, or overwrites a conflicting project during init.

The structure file configures only initial filesystem destinations. It does not
create notes inside Area or Resource folders, stage files, create a Git commit,
or let later note routing invent missing destinations.

### Import an existing filesystem tree

Bulk migration is separate from `init --structure` and single-file `note ingest`:

```bash
arpent import scan ~/Documents/legacy --output ~/migration/legacy-plan.json
arpent import suggest ~/migration/legacy-plan.json
arpent import review ~/migration/legacy-plan.json
arpent import validate ~/migration/legacy-plan.json --sources
arpent import summary ~/migration/legacy-plan.json
arpent import apply ~/migration/legacy-plan.json --dry-run --json
arpent import apply ~/migration/legacy-plan.json --plan-hash <plan_sha256>
arpent import status ~/migration/legacy-plan.json
```

`scan` is read-only and writes a compact JSON plan plus a uniquely named hashed
JSONL inventory beside it, both outside the source tree. The output parent must
already exist. Existing output is refused unless `--force` is supplied; a forced
rescan publishes a new unique inventory before replacing the plan, so the prior
plan never points at overwritten inventory content. The prior inventory remains
beside the plan and may be removed manually after the replacement is confirmed.
It records every reachable regular file's relative path, full-file text/binary
classification, size, modification time, and SHA-256. An unreadable directory
fails the scan rather than being silently omitted. Symlinks, Windows
reparse-point junctions, special files, common dependency trees, and OS cruft
are skipped rather than followed.

Folder suggestions are deterministic and carry confidence plus an inspectable
reason. They use container names, parent role, finite-work or ongoing-area name
signals, working filenames, reference density, and tree shape. `suggest`
refreshes these proposals. Interactive `review` asks only about uncovered folder
roots and assigns one of six inherited roles:

| Role | Effect |
|---|---|
| `project` | Create or reuse a canonical project and route descendants there |
| `area` | Create or reuse an Area and route descendants there |
| `resource` | Create or reuse a Resource and route descendants there |
| `group` | Review child folders separately; direct files use the fixed `inbox` root default |
| `inbox` | Import without a final PARA home |
| `ignore` | Deliberately leave descendants outside the migration |

For explicit non-interactive review, use `--accept-suggestions` with an optional
`--minimum-confidence 0..1`. Lower-confidence folders stay unresolved and make
validation fail. `review --yes` skips only the final "mark complete" question;
it does not answer folder questions. Choosing Skip leaves that folder unresolved,
and an interrupted review checkpoints decisions already made. Existing decisions
are retained on later reviews. The plan is ordinary strict JSON and can also be
edited directly before its review is marked complete.

Application is copy-only: the external source is never moved or deleted. Source
and vault cannot contain one another. Text and Markdown become complete notes
with source bytes preserved verbatim; existing source frontmatter remains visible
in the body rather than being trusted. Binaries assigned to a Project, Area, or
Resource are copied into that home's `attachments/` and receive companion
reference notes. Inbox binaries remain under
`00_inbox/captures/.arpent-import-<import-id>/` with a companion inbox note.
Failed ingestion can leave owned staging content there for a later retry. Routing
uses the vault's current contract. Files at the source root and directly inside a
Group are not asked about individually and use the fixed Inbox default. Other
descendant folders are flattened into canonical destinations, with source path
components folded into generated titles.

Every item is atomic, but the batch may partially succeed. Existing or internally
duplicated destinations are reported and never overwritten. Durable state under
`06_indexes/imports/<import-id>/` makes application resumable, binds progress to
the reviewed execution hash, retries failures, and verifies recorded destination,
attachment, and retained-inbox hashes before skipping completed items. `status`
reports this recorded-output verification; it does not rehash the external source
or rescan the inventory, and returns nonzero when outputs are missing or changed.
If a destination was deleted, apply can recreate it. If it still exists but its
recorded hash changed, apply refuses to overwrite it and reports a collision that
must be inspected explicitly. Structure creation happens before file processing and is
reported separately, including when all later file imports fail. `apply` asks one
final interactive confirmation; unattended application requires `--yes`. See
[`import-and-migration.md`](references/import-and-migration.md) for the complete format,
safety, and recovery contract.

The JSON dry-run exposes a `plan_sha256` bound to both folder decisions and the
current routing contract. Carry it into `--plan-hash` when apply must be tied to
that exact reviewed execution topology. It is not a fresh source snapshot. Run
`validate --sources` immediately before apply when all scanned sources should be
rehashed first; actual apply still verifies each source again immediately before
copying it, and a later changed item can fail after earlier items have succeeded.
The source tree is expected to remain stable while scan or apply is running; the
portable stdlib implementation rejects stable links and junctions but is not
hardened against a hostile concurrent path replacement race.

### Initialization semantics

```text
arpent init [path] [--minimal] [--structure FILE]
```

- `path` defaults to the current directory and is created when necessary.
- The target and scaffold paths must not be symlinks.
- Existing user files are not replaced; only missing seed files are added.
- `--structure` accepts a UTF-8 `.json` object or `.md` heading lists and may contain any subset of `areas`, `resources`, and `projects`.
- `.arpent` records marker version `1`, name `arpent`, and mode `full` or `minimal`.
- Re-initialization is idempotent only for the same mode and current marker format.
- Initializing a full vault over a minimal vault, or the reverse, is refused rather than treated as a migration.
- `git init` runs, but Arpent neither stages files nor creates a commit.
- The todo database is not created during initialization; the first todo operation creates and validates it.
- Validation catches known structure errors before a new scaffold is published,
  but init is not a whole-filesystem transaction. An unexpected Git, I/O, or
  concurrent failure can leave a partial target that should be inspected before retrying.

### Full versus minimal mode

| Capability | Full | Minimal |
|---|---:|---:|
| Seven buckets and `.arpent` marker | Yes | Yes |
| Universal frontmatter and routing contracts | Yes | Yes |
| Note, archive, status, triage, health | Yes | Yes |
| Inventory, keyword search, backup | Yes | Yes |
| Deliberate project creation | Yes | Yes |
| Project/area `_context.md` and `session end` | Yes | Yes |
| Seeded `MEMORY.md` | No | No |
| Explicit `session end --memory-log` | Yes | Yes |
| Triage JSON, note edit dry-run, and raw ingestion | Yes | Yes |
| Reviewed external filesystem import | Yes | Yes |
| Local usage v2 events, report, and qualitative journal | Yes | Yes |
| Progressive context commands | Yes | No |
| Delegated-memory observation/trait queue on `session end` | Yes | No |
| Tool registry, cron, and lifecycle sweep | Yes | No |
| SQLite todo flow | Yes | No |
| Portable agent infrastructure templates | Yes | No |

Minimal mode reduces optional modules, not local continuity or the note schema. Structured notes still carry the complete visible, user-readable frontmatter contract with empty values represented by `null`, `[]`, or `false`.

### Vault discovery

Most commands locate a vault in this order:

1. Use `ARPENT_VAULT_ROOT` when it is set.
2. Otherwise, start at the current directory and search upward for `.arpent`.
3. Validate the marker before operating.

This allows commands to run from any descendant directory:

```bash
cd ~/my-vault/01_projects/migration/notes
arpent status
```

For automation outside the vault tree, set the root explicitly:

```bash
ARPENT_VAULT_ROOT="$HOME/my-vault" arpent health
```

`backup verify` and `backup restore` are exceptions: they can inspect or restore a snapshot without first discovering a vault.

### First commands

| Command | When to use it |
|---|---|
| `arpent --help` | See the available command groups |
| `arpent <command> --help` | See the flags and accepted values for one command |
| `arpent init <path>` | Create an Arpent vault at the chosen path |
| `arpent init <path> --minimal` | Create only the core vault, contracts, skill, and index support |
| `cd <path>` | Enter the vault; commands also work from its descendant directories |
| `arpent project create "<name>"` | Deliberately create a normalized project, complete `_context.md`, and working folders |
| `arpent note new "..."` | Capture a structured note, initially in the inbox unless routing metadata is supplied |
| `arpent status` | Check note totals by bucket and lifecycle status |
| `arpent triage [--json]` | Inventory inbox items and available edit/ingest/leave dispositions |
| `arpent index` | Build or refresh inventory, search, and context indexes |
| `arpent search "..."` | Search indexed structured notes by keyword |
| `arpent session end --project <slug> --summary "..."` | Close into target local context in either mode; add `--memory-log` only for the optional cross-project log |
| `arpent usage report` | Inspect privacy-preserving command metrics and current triage age |
| `arpent todo add "..."` | Create a task with SQLite state and a readable Markdown trace |
| `arpent todo list` | List current tasks |
| `arpent backup` | Create and verify a logical vault snapshot |
| `arpent <group> <subcommand> --help` | Inspect the complete syntax for a nested operation |

### First run

```bash
# Create a vault
arpent init ~/my-vault
cd ~/my-vault

# Create a deliberate project destination in full or minimal mode
arpent project create "Migration Site" --effort-cadence heavylift --effort-level high

# Capture work directly into the project
arpent note new "Migration constraints" --project migration-site \
  --body "The cutover must preserve existing customer URLs."

# Resume in a later session by reading in this order:
# 1. me.md
# 2. 01_projects/migration-site/_context.md
# 3. only the specific notes or sources needed

# Produce broad useful work; use type: production only if semantically correct
arpent note new "Cutover sequence" --type draft --status active \
  --project migration-site --body "Draft the sequence here."

# Optional full-mode task tracking
arpent todo add "Validate migration plan" --priority high
arpent todo list

# Close local continuity in either mode
arpent session end --project migration-site \
  --summary "Documented constraints and started the cutover sequence." \
  --decision "Preserve existing customer URLs." \
  --next-step "Validate the sequence."

# Inspect, organize, index, retrieve, and report
arpent status
arpent triage --json
arpent efforts
arpent health
arpent index
arpent search "customer URLs"
arpent usage report
```

Projects and areas are intentional destinations. Use `arpent project create` as the primary project path. Area creation remains manual, and Arpent never invents a missing project or area while routing a note.

Commands work from the vault root or any descendant directory because Arpent searches upward for the `.arpent` marker.

### Read command output correctly

Arpent prints human-readable output by default. Commands exposing `--json`, such as `triage`, `note edit --dry-run`, `note ingest --dry-run`, `usage report`, `health`, `context pending`, `todo list`, `todo show`, and `sweep status`, are preferable for scripts. Exit code `0` means the command completed; validation, trust, consistency, or partial failures return a nonzero exit.

Vault-scoped parsed commands append best-effort schema-v2 events to `06_indexes/logs/usage.log`, including read operations and parsed failures when a vault can be identified. This local log is operational telemetry, not the durable content source; it excludes note bodies, titles, summaries, queries, paths, project/area names, URLs, errors, and command payloads.

## Common workflows

### Capture first, classify later

An ordinary note without routing metadata goes to `00_inbox/`:

```bash
arpent note new "Investigate cache invalidation" \
  --description "Question raised during the migration review" \
  --tags "migration,performance" \
  --body "Which cache keys remain valid after the URL cutover?"
```

The command prints the new stable ID. Keep that ID for future mutations; filenames can change, but IDs are the identity layer.

Use `--stdin` when the body is multiline or generated by another command:

```bash
arpent note new "Migration review" --type meeting --project migration --stdin
```

Finish the input with EOF in the terminal. If both a non-empty `--body` and `--stdin` are supplied to `note new`, the explicit body wins; prefer one input mechanism per invocation.

### Triage the inbox

```bash
arpent triage --json
arpent note edit <id> --project migration --area work --dry-run --json
arpent note ingest 00_inbox/raw-notes.txt --title "Raw notes" \
  --project migration --dry-run --json
```

`triage` is an inventory, not an interactive wizard or mutation engine. It recursively classifies every non-fleeting inbox item independently as `note`, `text`, `malformed`, or `binary`, continues past bad files, and does not follow symlinks. Human output remains concise; `--json` exposes each item's path, kind, ID/title when available, safe preview, reason, age and age basis, SHA-256 source hash, and available `edit`, `ingest`, or `leave` actions. An empty JSON inventory is `[]`.

The agent-mediated plan/apply protocol is:

1. Inventory with `arpent triage --json`.
2. Build one combined proposal covering every item, including explicit leaves.
3. Preview structured notes with `arpent note edit <id> ... --dry-run --json` and raw files with `arpent note ingest ... --dry-run --json`.
4. Show complete before/after frontmatter, source and destination, body-change state, warnings, and all known side effects; obtain one confirmation for the batch.
5. Apply the announced per-item commands, then re-run triage to verify.
6. Report every applied, skipped, and failed item. Each item is atomic, but a batch is sequential per-item transactions and may partially succeed.

`note edit --dry-run` and apply use the same planning path. Dry-run does not mutate domain files. `--json` can also be used on apply, and conflicting project/resource or inbox/routing requests are rejected rather than resolved silently.

`note route` replaces the complete routing state. Omitted `project`, `area`, and `resource` values are cleared, so pass every dimension that should remain:

```bash
# Keep both project and contextual area.
arpent note route <id> --project migration --area work

# Move deliberately back to the inbox by clearing all routing fields.
arpent note route <id>
```

Use `note edit` when changing content and routing together. `--inbox` cannot be combined with routing flags. For a reviewed plan/apply pass, carry `plan_sha256` from the JSON dry run into `--plan-hash` so source or routing-topology changes force a fresh review:

```bash
arpent note edit <id> \
  --title "Cache invalidation constraints" \
  --status active \
  --project migration \
  --area work \
  --tags "migration,performance"

arpent note edit <id> --project migration --dry-run --json
arpent note edit <id> --project migration --plan-hash <plan_sha256>
```

Use `note ingest` for inbox sources that do not have valid structured frontmatter:

```bash
# UTF-8 text or malformed frontmatter: preserve the entire source as note body.
arpent note ingest 00_inbox/interview.txt --title "Interview notes" \
  --project migration --source imported

# Binary or non-UTF-8: preserve the original in attachments/ and create a reference note.
arpent note ingest 00_inbox/diagram.pdf --title "Migration diagram" \
  --project migration --attachment --source imported
```

Text and malformed-frontmatter ingestion keeps every source byte as body text; malformed metadata is warned about rather than discarded. Binary ingestion transactionally moves the original and links a complete reference note to it. Without a final home, the original remains in inbox and the reference is reported as captured but not triaged. No note or attachment collision is overwritten. Carry `source_sha256` from the ingest JSON dry-run (or `sha256` from triage JSON) into `--source-hash <hash>` when applying to reject a source changed since preview.

If a destination slug does not exist, or both `project` and `resource` are set, the note goes to `00_inbox/unsure/` and receives a neighboring reason file. Resolve the metadata or create the intended destination, then route it again.

### Capture fleeting thoughts

```bash
arpent note new "The argument needs a counterexample" --type fleeting
```

Fleeting capture appends to `00_inbox/fleeting/dd-mm-yyyy.md` using UTC. Entries have a time heading but no individual frontmatter or ID. Consequently they do not appear in `status`, `triage`, structured-note search, or note-by-ID operations. Promote anything durable by creating a structured note; do not treat the stream as a permanent knowledge base.

### Create and use project context

Create projects deliberately in either full or minimal mode. Human input is normalized to a lowercase ASCII kebab-case slug and shown when it differs; collisions fail rather than acquiring a silent suffix:

```bash
arpent project create "Migration Site" \
  --area work \
  --effort-cadence heavylift \
  --effort-level high

arpent note new "Migration constraints" \
  --type note \
  --project migration-site \
  --body "The cutover must preserve existing customer URLs."

arpent session end \
  --project migration-site \
  --summary "The migration constraints are documented." \
  --decision "Preserve existing customer URLs." \
  --next-step "Draft the cutover sequence."
```

`project create` creates `01_projects/<slug>/_context.md` with the complete universal frontmatter field set plus `notes/`, `drafts/`, and `attachments/`. Its context body starts with Vision, Current state, Resume here, Deliverables / definition of done, Key resources, Next steps, Working rhythm and time budget, and Session history. Area and effort metadata are optional. The command does not create an area, index, stage, commit, or tool state, and never merges into an existing project.

To resume project work, read files rather than invoking a synthetic command:

1. Read root `me.md` for human-owned orientation.
2. Read `01_projects/<slug>/_context.md` for the project's current state and "Resume here" handoff.
3. Load only the specific notes, indexes, or source material the work requires.

Normal resume must not read `06_indexes/memory/MEMORY.md`. That optional log is
disabled by default and may be read only when the user explicitly asks for or
enables it.

`session end` updates the target `_context.md` by default in both modes. Every
context it creates or updates has the complete universal frontmatter field set;
existing body sections are preserved and its timestamped block is appended.
`--memory-log` explicitly opts that invocation into creating or updating
`06_indexes/memory/MEMORY.md`.

```bash
arpent session end \
  --summary "Reviewed the general operating model." \
  --next-step "Return to the migration project tomorrow." \
  --memory-log
```

Project and area can be supplied together: project determines the physical
context while area remains contextual metadata. A no-target close requires an
explicit sink: `--memory-log`, or in full mode at least one observation/trait.
In full mode only, supplied observations and traits are also appended to
`06_indexes/pending_db_writes.yaml`; Arpent currently ships no command to flush
this queue into an external memory provider. Minimal mode rejects those flags
before any mutation and never creates that queue.

### Manage a todo from capture to archive

Todo is available only in full mode. The first todo command creates and validates `06_indexes/databases/todo.db`.

```bash
arpent todo add "Validate migration plan" \
  --priority high \
  --due 2026-07-12 \
  --duration 30m \
  --project migration

arpent todo list
arpent todo show <todo-id>
arpent todo defer <todo-id> --to 2026-07-15
arpent todo block <todo-id> --on <object-id>
arpent todo edit <todo-id> --clear-dependency
arpent todo done <todo-id>
arpent todo archive <todo-id>
```

Each task has both a SQLite row and a readable Markdown checklist record under `02_areas/area__perso__todo__active/{active,waiting,done}/`. A dependency makes a new todo `waiting` unless a status is explicitly supplied. Clearing a dependency from a waiting todo returns it to `active` unless another status is explicitly requested.

Only a `done` todo can be archived. Archival moves its Markdown trace under the current quarterly archive while retaining the SQLite row. Generic `note edit`, `note route`, `note status`, and top-level `archive` reject todo IDs. Avoid manually moving or editing todo Markdown because every todo mutation checks database/file lifecycle consistency.

### Extract durable knowledge

```bash
arpent note extract <linear-id> \
  --type concept \
  --title "Actionability gradient" \
  --resource concepts \
  --body "A useful framework becomes more valuable as its next action becomes clearer."

arpent note dissolve <linear-id> --yes
```

Extraction creates independently routed child notes and records their parent. Dissolution validates the lineage and archives the decomposed source.

The source must be a non-archived `linear` note. Extraction sets `source: derived`, records `parent: <linear-id>` on the child, and adds the child ID and wikilink to the source. Use `--after "exact passage"` to insert the wikilink at a specific point; if the passage is absent, the entire operation aborts without partial output.

Before dissolution, the source must be `maturing` or `active` and have at least one valid child. `note dissolve --yes` verifies both directions of the lineage, discovers additional children that point to the source, and moves the source to `04_archives/linear_notes/`. A dissolved source is immutable through ordinary edit, route, and status commands.

### Build and maintain progressive context

Full mode can store explicit summaries without making indexing depend on an AI provider:

```bash
arpent index
arpent context pending --json
arpent context show 01_projects/migration --level l2
arpent context set 01_projects/migration \
  --summary "Migration project, current constraints, decisions, and open work." \
  --source-hash <hash-from-pending> \
  --provider <agent-id>
arpent context pending
```

The safe protocol is:

1. Rebuild the index.
2. Read `context pending` and retain the returned source hash.
3. Load L2 for the exact item requiring a summary.
4. Produce the summary outside the indexer.
5. Store it with the same hash.
6. Confirm that the item is no longer pending.

`context set` checks the indexed and current live semantic hashes so a summary cannot silently attach to changed content. Replacing a fresh L1 summary requires `--force`. `--stdin` can replace `--summary` for multiline input. L1 can be absent or stale; L0 and L2 remain usable.

### Inspect work and system health

```bash
arpent status
arpent efforts
arpent health
arpent health --json
```

- `status` counts ID-bearing records by top-level bucket and frontmatter status.
- `efforts` groups active project/area context and active notes by explicit `heavylift` or `slowburn` cadence, then low/medium/high effort. Missing profiles remain visible as unclassified.
- `health` performs a live scan for input/output density, integrations, maps, stale notes, old maturing notes, and unresolved `00_inbox/unsure/` items.

The health input/output ratio is diagnostic, not a score: `captured` and `imported` notes count as input, while `manual` and `derived` notes count as reflective output. A ratio below `0.5` produces a warning that accumulation may be outrunning synthesis.

### Review local usage and continuity friction

```bash
arpent usage report
arpent usage report --since 2026-07-01
arpent usage report --since 2026-07-01 --json
```

The append-only local `06_indexes/logs/usage.log` accepts historical unversioned v1 records and writes versioned v2 command events without rewriting history. V2 records capture categorical outcomes, success/failure, duration, counts, effective note types/status transitions, and opaque correlation IDs where needed. Writes are locked, complete-line, and best effort so telemetry cannot break a domain command; malformed or truncated records are skipped and counted.

`usage report` covers command counts and failures, active days, p50/p95 duration where v2 data exists, captures, ingestions, project creations, semantically typed productions, session closes and close duration, effective note types, status transitions, malformed lines, and the current inbox count/oldest age/age buckets. It reports v1/v2 coverage rather than pretending historical events contain v2 detail.

All telemetry remains in the vault. Events never include note bodies, titles, summaries, URLs, search queries, filesystem paths, project/area names, error text, or command-line payloads. Local does not necessarily mean unsynchronized: the vault itself may be in a synced folder, and the current logical backup includes ordinary logs such as `usage.log`.

Resume is documentary reading, so automatic metrics cannot know that a resume started, which files were read, how much re-explanation was avoided, or whether context was useful. Record those judgments in `06_indexes/logs/usage-journal.md`, alongside capture, production, close, and triage friction. The qualitative journal complements the report rather than being replaced by it.

### Preview lifecycle changes

```bash
arpent sweep ephemeral --dry-run
arpent sweep ephemeral
arpent sweep status
```

Sweeps affect only installed ephemeral tools with explicit lifecycle rules. Permanent content and active states are protected.

`--dry-run` prevents note/database lifecycle changes, but still writes operational usage, sweep log, lock state, and a summary. Review `sweep status --json` after either a preview or a real run. Rules can mark content stale, archive terminal content, archive with a SQLite trace, or propose deletion for review; they cannot silently delete protected knowledge.

### Operate with an AI agent

A newly initialized vault gives an agent a local reading order:

1. `.agent` identifies the directory as an agent-operated Arpent vault.
2. `COMPASS.md` explains how to classify intent and select an operation.
3. `06_indexes/global_skills/arpent.skill.md` defines the compact mechanics.
4. `06_indexes/docs/` explains architecture and policy in depth.
5. `me.md` stores human-owned orientation, preferences, boundaries, and current direction and should be read early.

For a concrete resume, use the narrower documentary order: `me.md`, then the target project or area `_context.md`, then only the specific notes or sources needed. This protocol works in minimal and full vaults and is not a CLI command. Do not read optional `MEMORY.md` without explicit user opt-in.

Tell a new agent to read `.agent` before acting. The expected operating protocol is to identify intent, inspect relevant context, announce meaningful moves or renames, invoke the CLI, and report the result. The CLI enforces mechanical invariants; the agent remains responsible for subjective interpretation and user confirmation.

If the CLI is unavailable, source files remain readable, but safe mutation becomes more limited. Do not manually emulate todo dual state, extraction, dissolution, sweep, context-summary, backup, or delegated-queue transactions. The repository's [`ingestion-and-degraded-mode.md`](references/ingestion-and-degraded-mode.md) documents direct ordinary-note work and the default `_context.md` close fallback; optional `MEMORY.md` writes still require explicit user opt-in.

### Back up before risky maintenance

```bash
arpent backup --destination /Volumes/Backups/arpent
arpent backup verify /Volumes/Backups/arpent/<snapshot>
arpent backup restore /Volumes/Backups/arpent/<snapshot> \
  --to "$HOME/restored-vault"
cd "$HOME/restored-vault"
git init
arpent index
```

The restore target must not already exist. `.git/` is outside the snapshot, so initialize a new repository if the restored copy should be versioned. Rebuilding the index refreshes intentionally omitted derivatives.

---

## How it works

### Clear boundaries

Arpent separates material by role:

- **Projects** hold time-bound work, decisions, sessions, and next steps.
- **Areas** hold responsibilities that continue without a finish line.
- **Resources** hold reusable concepts, references, maps, and integrations.
- **The inbox** receives material that has not been classified yet.
- **Archives** preserve completed history outside the active workspace.
- **Agent drafts** stay separate until a person reviews and integrates them.
- **Research scratch** has a mess-tolerant zone away from the clean knowledge base.
- **Memory** remains a separate concern for durable facts, traits, and reminders.

The vault is organized by utility, not topic:

```text
00_inbox/       unclassified captures and fleeting thoughts
  unsure/       visible ambiguity with a written reason
01_projects/    time-bound efforts with deliverables
02_areas/       ongoing responsibilities
03_resources/   reusable knowledge, maps, and references
04_archives/    completed or dissolved material
05_tools/       declared runtime material and disposable artefacts
06_indexes/     schemas, skills, indexes, context, memory, and logs
```

### The vault marker

The root contains a strict JSON marker:

```json
{
  "version": 1,
  "name": "arpent",
  "mode": "full"
}
```

All three fields are validated. `mode` must be `full` or `minimal`; changing it manually does not install or remove modules and can leave the vault inconsistent.

### Structured note anatomy

Every ordinary Arpent note has readable Markdown plus complete, visible, user-readable universal YAML frontmatter. A concept looks like:

```markdown
---
title: Actionability gradient
id: concept-20260710-a
created: 10-07-2026T10:00:00Z
modified: 10-07-2026T10:00:00Z

description: A framework becomes more useful as its next action becomes clearer.
type: concept
project: null
area: null
resource: concepts
status: maturing
effort_cadence: null
effort_level: null
tags:
  - execution
chosen_location: null

source: manual
link: null
author: user

depth: null
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

A useful framework becomes more valuable as its next action becomes clearer.
```

The CLI writes empty optional values explicitly. Some fields, including `appreciated`, `importance`, `pinned`, rich relations, and observations, currently have no direct command-line flag and should not be invented by an agent without a clear operating rule.

#### IDs and filenames

- IDs follow `<type>-<UTC-date>-<letter>`, for example `concept-20260710-a`.
- The ID stays in frontmatter and survives file renames or routing moves.
- Titles are converted to lowercase ASCII `snake_case` filenames.
- A destination file is never silently overwritten; collisions fail.
- Use IDs rather than paths in note lifecycle commands.

#### Accepted note types

`note`, `concept`, `journal`, `log`, `checklist`, `reference`, `draft`, `template`, `meeting`, `idea`, `fleeting`, `linear`, `integration`, `angle`, `production`, `map`, and `artefact`.

Type establishes the default status: maps start `ongoing`, concepts start `maturing`, fleeting notes and ideas start `inbox`, and other types default to `inbox` unless `--status` is given.

#### Accepted lifecycle statuses

`inbox`, `maturing`, `active`, `stable`, `ongoing`, `standby`, `waiting`, `to-start`, `done`, `stale`, and `archived`.

Status describes lifecycle; it does not always imply a physical move. In particular, `arpent note status <id> archived` only updates an ordinary note's status. Use `arpent archive <id>` for validated quarterly archival, `todo archive` for a completed todo, and `note dissolve` for a decomposed linear source.

#### Provenance values

- Sources: `manual`, `generated`, `imported`, `captured`, `conversation`, `derived`.
- Authors: `user`, `agent`, `imported`.
- `--tags` accepts a comma-separated list.
- Provenance/link inconsistencies produce warnings during creation rather than blocking the note.

### Deterministic routing

Routing is computed from note metadata:

- `project` and `resource` are mutually exclusive homes;
- `area` can accompany either as context;
- normal precedence is `project > resource > area > inbox`;
- missing slugs or conflicting homes route to `00_inbox/unsure/` with a reason;
- reusable concepts stay global while project-only references stay local;
- special types have explicit routes for fleeting notes, maps, integrations, artefacts, meetings, logs, and agent drafts.

Ordinary filenames use lowercase ASCII `snake_case`. Stable IDs remain in frontmatter so relations survive renames.

The normal and special routes are:

| Condition | Destination |
|---|---|
| `project: migration` | `01_projects/migration/notes/` |
| Project draft | `01_projects/migration/drafts/` |
| Project meeting | `01_projects/migration/meetings/` |
| Project log | `01_projects/migration/sessions/` |
| `resource: concepts` | `03_resources/concepts/` |
| `area: health` only | `02_areas/health/` |
| No home | `00_inbox/` |
| No home and `source: captured` | `00_inbox/captures/` |
| Fleeting | `00_inbox/fleeting/dd-mm-yyyy.md` |
| Map | `03_resources/maps-of-content/` |
| Integration | `03_resources/integrations/` |
| Artefact | `05_tools/artefacts/` |
| Agent-authored draft with no project | `03_resources/agent_wiki/drafts/` |
| Dissolved linear source | `04_archives/linear_notes/` |
| Conflicting or invalid home | `00_inbox/unsure/` plus `<filename>.md_reason.txt` |
| Ordinary archival | `04_archives/<YYYY_qN>/` |

Reserved resource slugs from the routing contract can be created on write. Projects and areas are never invented automatically.

### Progressive context

An agent should not need to load the entire vault to become useful:

- **L0** provides deterministic one-line orientation.
- **L1** stores an optional AI summary tied to the source hash it describes.
- **L2** loads the original source or direct folder contents on demand.

`arpent index` never invokes AI. L1 generation is explicit, and a changed source marks its existing summary stale.

Hashes are semantic for context purposes: ordinary timestamp changes do not invalidate a note summary, while meaningful frontmatter, routing, provenance, or body changes do. A matching summary may be reused after a move when kind and semantic hash remain the same.

### Knowledge extraction and continuity

A `linear` note can hold exploratory or sequential material without pretending to be atomic knowledge. Arpent can extract reusable child notes while preserving lineage, then archive the source after deliberate dissolution.

Projects and instrumented areas carry `_context.md`, the default readable handover surface. An optional `MEMORY.md` can record cross-project session summaries only after explicit `--memory-log` opt-in; it is not a bundled long-term memory provider.

### Memory boundaries

Arpent separates four concerns that are often conflated:

- `me.md` is user-owned orientation: identity, preferences, direction, boundaries, and useful links.
- `_context.md` is project- or area-specific operational state: vision, current state, decisions, resources, and next steps.
- `06_indexes/memory/MEMORY.md` is an optional cross-project log, disabled and unread by default, not a complete personal memory database.
- `06_indexes/memory/wiki/` is agentic research scratch with raw sources and interlinked pages, separate from the clean knowledge base.

Stable personal facts, traits, and reminders may be delegated to an external host memory interface only after explicit opt-in. Arpent does not bundle, select, or synchronize that provider. The queue written by `session end` is inspectable local intent, not proof that an external provider received it.

When deciding where information belongs, ask what role it plays: work product belongs in the vault, current execution state belongs in `_context.md`, user orientation belongs in `me.md`, an explicitly requested cross-project log may use `MEMORY.md`, and provider-managed personal recall remains outside the vault.

### Health and lifecycle

`arpent health` compares reflective output (`manual` or `derived`) with accumulated input (`captured` or `imported`) and reports integrations, maps, stale notes, old maturing material, and unresolved routing.

Installed ephemeral tools can declare lifecycle rules. Sweeps can preview and apply them, but automatic archival is restricted to terminal material and deletion rules become review proposals rather than silent removal.

### Mutation safety

Arpent treats multi-file changes as transactions:

- mutations acquire filesystem locks under `06_indexes/logs/`;
- note moves use no-replace semantics;
- notes, todos, sessions, and sweeps use recovery journals;
- unfinished foreign transactions block overlapping mutation instead of being ignored;
- paths reject absolute vault-relative input, `..` traversal, and symlink escape;
- indexing refuses to publish when source files change during the pass;
- backup refuses to run while a known unfinished transaction exists.

Lock files can remain present because serialization relies on the file lock, not deletion of the lock pathname. Do not remove journals or locks merely because they exist; investigate an explicit error first.

## Search behavior

`arpent search` uses SQLite FTS5 when `search.db` is available and falls back to a live text scan when it is not.

Important scope and freshness rules:

- search covers ID-bearing Markdown notes, not attachments, arbitrary files, infrastructure docs, or append-only fleeting entries;
- `search.db` stores a source signature; when the vault changes or the database is unreadable, search falls back to a live scan instead of serving stale results;
- run `arpent index` after changes to restore indexed search speed and refresh the other derivatives;
- the inventory itself remains broader and includes folders, attachments, binaries, and symlinks without following symlinks.
- FTS5 returns at most 50 ranked matches and combines whitespace-delimited terms;
- the live fallback performs a case-insensitive substring match on the whole query, so edge-case results can differ from indexed search;
- `arpent note find <query>` uses the same backend with different presentation.

`arpent index` rebuilds:

- `06_indexes/index.json` for whole-vault inventory;
- `06_indexes/sidecar.json` for structured note metadata;
- `06_indexes/databases/search.db` for local FTS5 search;
- `06_indexes/context_index.json` for L0/L1/L2 context state.

These are derivatives. The original files remain the durable layer.

### Index scope and exclusions

The inventory records directories, regular files, plain text, binary files, and symlinks without following symlink targets. It excludes `.git`, virtual environments and dependency directories, Python caches, backup/database/log/secrets zones, generated index outputs, and common operating-system noise.

Indexing is a consistency pass rather than a background watcher. It acquires a lock, refuses an active mutation journal, computes the source state, builds temporary outputs, verifies the source has not changed, and only then publishes the new derivatives. A Markdown symlink can cause the structured-note signature phase to refuse indexing even though inventory itself does not follow symlinks.

### When to rebuild

Run `arpent index`:

- after a batch of direct filesystem changes;
- before generating L1 summaries;
- when search repeatedly uses live fallback;
- after restoring a snapshot;
- before handing a large vault to a new agent that relies on progressive context.

Ordinary CLI note changes do not require immediate indexing for correctness because search detects stale derivatives and falls back to live files. Rebuilding restores speed and refreshes all generated views.

## Configuration and automation

Configuration is explicit and currently edited as files:

- `06_indexes/cli/operations.yaml` mirrors the packaged contract; only its explicit `routing_overrides` mapping refines routes;
- `06_indexes/tools.yaml` declares tools and lifecycle rules;
- `06_indexes/cron.json` declares scheduled jobs and notification behavior;
- `06_indexes/schemas/frontmatter_policy.yaml` documents the seeded frontmatter policy.

The universal frontmatter schema is closed during normal use. Unsupported
per-project fields fail CLI validation. Users may freely add or reorder body
sections and create project files/subfolders. Extending the schema is a deliberate
system-development change that must update canonical schema, field order,
validation, policy, documentation, and tests together.

`arpent tools list` and `arpent tools show` inspect the registry. They do not install, enable, or disable tools.

### Configuration authority

The packaged CLI parser remains authoritative for command syntax. `operations.yaml` declares operation inventory and routing contracts, but does not dynamically create `argparse` flags. If documentation, a vault mirror, and `arpent --help` disagree, inspect the installed package version and treat the executable behavior as current.

Do not edit generated index files by hand. Configuration edits should remain reviewable source changes, followed by the command that consumes them. Re-running `arpent init` will add a missing seed but will not overwrite a customized existing configuration.

The static `architecture_template/01_projects/_template_project/_context.md`
does not currently control the code-generated `project create` template. In
normal use, edit each created `_context.md` directly. When developing Arpent,
change both the runtime builder and static template if the generated design is
meant to change.

### Tool registry

```bash
arpent tools list
arpent tools list --category knowledge --status installed
arpent tools show todo
```

Filters are exact values from `06_indexes/tools.yaml`. `tools show` prints the selected declaration as sorted JSON. An installed tool skill must resolve to a real file under `06_indexes/global_skills/`; runtime material under `05_tools/` and symlink escapes are rejected.

The default full vault declares `context_summary` and `todo` as installed. Reader, review, and backup-related tool definitions can be present as planned registry entries without corresponding installed command groups. Registry presence alone does not make a capability executable.

Cron commands are an explicit local-code trust boundary. An enabled job must
declare `"trust": "local-code"`; its command runs with the user's permissions
and inherited environment, so only enable jobs from a vault you fully trust.
Jobs have a bounded timeout and concurrent ticks are serialized.

Arpent does not run a daemon. To evaluate due cron entries, an external scheduler must invoke:

```bash
arpent cron run --tick --allow-local-code
```

For example, a Unix cron installation can run the tick every minute from the vault root:

```cron
* * * * * cd /absolute/path/to/vault && /absolute/path/to/arpent cron run --tick --allow-local-code
```

The built-in schedule matcher uses UTC and supports `*` or comma-separated exact integers in the five standard fields. It does not implement ranges or step syntax.

### Cron execution model

```bash
# Show what is due without launching local code.
arpent cron run --tick --dry-run

# Execute due trusted jobs.
arpent cron run --tick --allow-local-code
```

`--tick` is mandatory. Each enabled job needs a unique ID, a non-empty command, `"trust": "local-code"`, and a timeout from 1 to 86400 seconds; the default timeout is 300 seconds. Due-state and execution use UTC.

Arpent/`arp` jobs run through the installed package with `ARPENT_VAULT_ROOT` set. External commands are tokenized and launched directly from the vault root with the inherited environment; they do not run through an implicit shell. Real local-code execution is disabled on Windows.

The runner serializes concurrent ticks, records `last_started` before dispatch, and records `last_run` only after success. A failed or interrupted job is not replayed in the same minute. One failed job makes the overall tick nonzero after results have been processed. Notifications can go to stdout, `06_indexes/logs/cron.log`, or nowhere according to configuration.

Cron dry-run does not execute the job or update `last_started`/`last_run`, but normal usage/audit state and configured preview notification output can still be written.

## Backup and data safety

`arpent backup` creates a timestamped, atomically published snapshot under
`06_indexes/backup/`. Use `--destination <directory>` to write snapshots to a
different local filesystem directory. A snapshot contains:

- every durable vault file, including attachments, configuration, hidden files,
  local memory/context surfaces, ordinary logs such as `usage.log`, tool data,
  and empty directories;
- every SQLite database detected in the vault through SQLite's consistent backup
  API, including `todo.db`;
- preserved symlinks without following or copying their external targets;
- a versioned manifest, exact payload inventory, SHA-256 checksums, and SQLite
  integrity results.

Rebuildable `index.json`, `sidecar.json`, and `search.db` outputs, runtime locks,
SQLite sidecars, dependency directories, `.git/`, and nested backups are
excluded and recorded in the manifest. `context_index.json` is retained because
it may contain explicitly generated L1 summaries. Known unfinished transaction
journals block backup creation rather than being copied or silently excluded.
Files outside the vault, delegated memory, environment configuration, and Git
history are outside the snapshot boundary.

Verify and restore with:

```bash
arpent backup verify <snapshot>
arpent backup restore <snapshot> --to <new-directory>
```

Verification rejects missing, altered, additional, unsafe, or corrupt content.
Restore verifies first, writes into staging, verifies again, and publishes only
to a target that does not already exist. It never merges into or overwrites an
existing vault.

`backup verify` and `backup restore` work outside an Arpent vault. Restore can create missing parent directories, preserves file/directory modes and timestamps, and restores symlinks without following them. Because `.git/` is excluded, the restored directory has a valid `.arpent` marker but is not a Git repository until `git init` is run.

### Snapshot procedure

1. Resolve any unfinished mutation reported by Arpent.
2. Choose storage outside the vault and outside its primary failure domain.
3. Run `arpent backup --destination <directory>`.
4. Retain the printed snapshot path.
5. Run `arpent backup verify <snapshot>` independently.
6. Periodically perform a test restore to a new temporary directory.
7. Initialize Git and rebuild indexes after a real restore.

Backup creation copies regular durable files, preserves empty directories and symlinks, and uses SQLite's backup API for consistent database copies. It detects source changes during copying and aborts rather than publishing a mixed snapshot. Publication is atomic only within the destination filesystem.

Snapshots under `06_indexes/backup/` remain in the same failure domain as the
vault and are ignored by Git. Prefer `--destination` on separately backed-up
storage. Arpent does not provide retention, compression, encryption, remote
transport, or authenticity against an attacker able to replace both a snapshot
and its manifest.

Avoid manually moving or editing todo records. Todo mutations check that SQLite and Markdown lifecycle states agree before proceeding.

## Command reference

| Command | Purpose |
|---|---|
| `init [path] [--minimal] [--structure FILE]` | Scaffold a vault and optionally seed declared Areas, Resources, and projects |
| `import scan/suggest/review/validate/summary/apply/status` | Plan, confirm, copy, and resume an external filesystem migration |
| `status` | Count ID-bearing notes by bucket and status |
| `triage [--json]` | Inventory inbox items with kinds, ages, hashes, and available dispositions |
| `index` | Inventory the vault and rebuild search and context indexes |
| `search <query>` | Search indexed structured notes by keyword |
| `efforts` | Group active actionables by explicit cadence and effort level |
| `health [--json]` | Report live density and lifecycle signals |
| `backup [--destination <dir>]` | Create a complete, verified logical vault snapshot |
| `backup verify <snapshot>` | Verify manifest, exact payload checksums, and SQLite integrity |
| `backup restore <snapshot> --to <new-dir>` | Atomically restore into a directory that does not exist |
| `project create <name>` | Deliberately create a normalized project and complete canonical context |
| `note new <title>` | Create and deterministically route a note |
| `note edit <id> [--dry-run] [--json] [--plan-hash <hash>]` | Plan or apply metadata/body edits, renames, and routing; bind reviewed plans when applying |
| `note ingest <inbox-path> --title <title>` | Losslessly ingest text, malformed, or binary inbox content |
| `note route <id>` | Replace routing fields and move the note accordingly |
| `note read <id>` | Print a note |
| `note find <query>` | Find structured notes using the same index and fallback behavior as `search` |
| `note status <id> <status>` | Change a note's lifecycle status |
| `note extract <linear-id>` | Extract a typed child from a linear working note |
| `note dissolve <linear-id> --yes` | Validate children and archive a decomposed linear source |
| `archive <id>` | Archive one note by ID without deleting its history |
| `todo add/list/show` | Create and inspect SQLite-backed tasks and Markdown traces |
| `todo edit/done/defer/block` | Update task fields and lifecycle state |
| `todo archive <id>` | Archive a completed task while retaining its SQLite row |
| `context pending/show/set` | Inspect and maintain explicit L0/L1/L2 context |
| `session end` | Update local project/area continuity; queue delegated writes only in full mode |
| `usage report [--since <dd-mm-yyyy>] [--json]` | Report local v2 command metrics and current triage age |
| `tools list/show` | Inspect the tool registry |
| `sweep ephemeral/status` | Preview, apply, and inspect configured lifecycle sweeps |
| `cron run --tick [--dry-run] [--allow-local-code]` | Preview or explicitly authorize due jobs from the cron registry |

Run `arpent <command> --help` for full flags and accepted values.

### Global commands and views

```text
arpent --version
arpent init [path] [--minimal] [--structure FILE]
arpent status
arpent triage [--json]
arpent efforts
arpent health [--json]
arpent index
arpent search <query>
arpent usage report [--since <ISO-date-or-timestamp>] [--json]
```

`status`, `triage`, `efforts`, and `health` scan live files. `usage report` combines local event history with current triage state. `index` rebuilds derivatives. `search` selects current FTS5 state or live fallback automatically.

### Import reference

```text
arpent import scan <source> --output <plan> [--force] [--json]
arpent import suggest <plan> [--json]
arpent import review <plan>
  [--accept-suggestions]
  [--minimum-confidence 0..1]
  [--yes]
  [--json]
arpent import validate <plan> [--sources] [--json]
arpent import summary <plan> [--json]
arpent import apply <plan>
  [--dry-run]
  [--yes]
  [--plan-hash HASH]
  [--stop-on-error]
  [--json]
arpent import status <plan> [--json]
```

| Command | Vault requirement | Full/minimal |
|---|---|---:|
| `scan`, `suggest`, `review`, `summary` | None | Mode-independent |
| `validate` | None; adds destination compatibility checks when a vault is discovered | Both |
| `apply`, `status` | A discovered vault | Both |

`summary` inspects the plan and inventory but does not replace `validate`.
`validate --sources` verifies the inventory, review, and current external hashes;
when a vault is discovered it also checks destination declarations. `apply` runs
normal validation, then verifies each source immediately before copying it.
`status` reads durable state and verifies recorded outputs; it does not scan the
source or inventory. It returns nonzero when `missing_or_changed` outputs exist,
so automation need not infer failure solely from human text.

For JSON-only automation, use `review --accept-suggestions --json` and real
`apply --yes --json`. Interactive review or apply intentionally prints questions
and therefore refuses `--json` without those non-interactive flags. Dry-run JSON
never prompts.

| Command | JSON fields |
|---|---|
| `scan` | `plan`, `inventory`, `import_id`, `files`, `bytes`, `folders` |
| `suggest` | `plan`, `suggestions_changed` |
| `review` | `accepted`, `unresolved`, `completed` |
| `validate` | `valid`, `errors`, `warnings`, `files`, `decision_sha256` |
| `summary` | `import_id`, `source_root`, `files`, `bytes`, `by_role`, `by_kind`, `unresolved_folders`, `review_completed`, `decision_sha256` |
| `apply` | `format`, `version`, `import_id`, `plan_sha256`, `decision_sha256`, `routing_sha256`, `dry_run`, `counts`, `failures`, `previews`, `structure`, `completed_at` |
| `status` | `import_id`, `total`, `complete`, `remaining`, `by_status`, `execution_sha256` |

Apply `counts` is sparse except for the explicit structure count. Dry-run JSON
includes per-item source, kind, role, title, routing fields, destination,
attachment, collision, and routing-reason details. Real apply returns an empty
`previews` list. Scan returns an absolute plan path and the unique sibling
inventory filename.

### Create a project

```text
arpent project create <name>
  [--area SLUG]
  [--effort-cadence heavylift|slowburn]
  [--effort-level low|medium|high]
```

The human name normalizes to a lowercase ASCII kebab-case folder slug. The command creates `_context.md`, `notes/`, `drafts/`, and `attachments/`, refuses collisions, and works identically in full and minimal modes. `--area` must resolve to one existing unambiguous area; project creation never creates the area implicitly.

### Create a note

```text
arpent note new <title>
  [--type TYPE]
  [--status STATUS]
  [--effort-cadence heavylift|slowburn]
  [--effort-level low|medium|high]
  [--project SLUG]
  [--area SLUG]
  [--resource SLUG]
  [--tags CSV]
  [--source SOURCE]
  [--author AUTHOR]
  [--description TEXT]
  [--link VALUE]
  [--chosen-location TEXT]
  [--body TEXT]
  [--stdin]
```

Defaults are `type: note`, `source: manual`, and `author: user`; status depends on type. `--tags` is comma-separated. Creation validates enums, generates a stable ID, writes full frontmatter, computes the route, and refuses destination overwrite. `--chosen-location` records user intent but does not replace the deterministic router.

### Read and find notes

```text
arpent note read <id>
arpent note find <query>
```

`note read` prints title, type, status, path, and body. `note find` uses the same backend and freshness rules as top-level `search`.

### Edit a note

```text
arpent note edit <id>
  [--title TEXT]
  [--description TEXT]
  [--type TYPE]
  [--status STATUS]
  [--effort-cadence heavylift|slowburn]
  [--effort-level low|medium|high]
  [--clear-effort]
  [--tags CSV | --clear-tags]
  [--source SOURCE]
  [--author AUTHOR]
  [--link VALUE | --clear-link]
  [--chosen-location TEXT | --clear-chosen-location]
  [--project SLUG]
  [--area SLUG]
  [--resource SLUG]
  [--clear-project]
  [--clear-area]
  [--clear-resource]
  [--inbox]
  [--body TEXT]
  [--stdin]
  [--dry-run]
  [--json]
```

No flags prints `No changes requested.` A title edit can rename the file; routing-relevant edits can move it. Clear flags win over their corresponding set values, while project/resource and inbox/routing conflicts are rejected. Body replacement happens when `--body` or `--stdin` is supplied. `--dry-run` shows complete before/after frontmatter, source/destination, body-change state, reason, and warnings without domain mutation; `--json` exposes that plan. Existing notes cannot be converted to fleeting, and dissolved linear sources are immutable.

### Ingest an inbox file

```text
arpent note ingest <inbox-path>
  --title TEXT
  [--type TYPE]
  [--status STATUS]
  [--project SLUG]
  [--area SLUG]
  [--resource SLUG]
  [ordinary note metadata options]
  [--attachment]
  [--source-hash SHA256]
  [--dry-run]
  [--json]
```

The source must be a vault-relative file under `00_inbox/`. Text and malformed frontmatter become the full body of a complete structured note. A binary/non-UTF-8 file remains byte-for-byte untouched and cannot contain YAML; `--attachment` moves it transactionally to the selected home's `attachments/` and creates a separate Markdown companion reference note with complete universal frontmatter whose `link` points to the attachment. Without a final home, the original stays in inbox and the companion is untriaged. Dry-run reports exact paths, metadata, warnings, source kind/hash, and whether the result is fully triaged. Applying with `--source-hash` refuses a changed source.

### Route, change status, and archive

```text
arpent note route <id> [--project SLUG] [--area SLUG] [--resource SLUG]
arpent note status <id> <status>
arpent archive <id>
```

`note route` replaces, rather than merges, all routing fields. `note status` changes lifecycle metadata and applies a status route only when one exists. `archive` is the ordinary-note archival operation: it records archived metadata and moves the note to the current quarterly archive. These commands reject todo IDs; linear sources use dissolution rather than ordinary archival.

### Extract and dissolve a linear note

```text
arpent note extract <linear-id>
  --type TYPE
  --title TEXT
  [--status STATUS]
  [--author user|agent|imported]
  [--project SLUG]
  [--area SLUG]
  [--resource SLUG]
  [--inbox]
  [--body TEXT | --stdin]
  [--after EXACT_PASSAGE]

arpent note dissolve <linear-id> [--yes]
```

The extracted child can use any installed note type except fleeting. `--inbox` cannot accompany another route. A missing body defaults to the child title. Dissolution requires `--yes`, an eligible source status, and validated child lineage.

### Context reference

Context commands require full mode and a successful prior index.

```text
arpent context pending
  [--kind folder|note|text]
  [--path RELATIVE_PATH]
  [--json]

arpent context show <path> [--level l0|l1|l2]

arpent context set <path>
  (--summary TEXT | --stdin)
  --source-hash HASH
  [--provider ID]
  [--force]
```

`pending` lists missing or stale L1 summaries and can filter by exact kind or path prefix. `show` defaults to L0; L2 returns full source text, direct folder-child JSON, or metadata for unsupported files. `set` defaults the provider to `agent`, rejects empty input and stale hashes, and requires `--force` to replace a fresh summary.

### Todo reference

Todo commands require full mode.

```text
arpent todo add <content>
  [--priority KEY]
  [--status active|waiting|done]
  [--due dd-mm-yyyy]
  [--do dd-mm-yyyy]
  [--duration KEY]
  [--project ID]
  [--depends-on ID]
  [--optional]
  [--frequency KEY]
  [--list-order KEY]
  [--assignee ID]

arpent todo list
  [--status active|waiting|done]
  [--include-archived]
  [--json]

arpent todo show <id> [--json]
```

Dates are strict calendar dates in `dd-mm-yyyy` form. Priority, duration, project, dependency, frequency, ordering, and assignee are non-empty free-form keys or soft references. `todo list` defaults to active and waiting items; ask explicitly for done or archived records.

```text
arpent todo edit <id>
  [--content TEXT]
  [--priority KEY | --clear-priority]
  [--status active|waiting|done]
  [--due dd-mm-yyyy | --clear-due]
  [--do dd-mm-yyyy | --clear-do]
  [--duration KEY | --clear-duration]
  [--project ID | --clear-project]
  [--depends-on ID | --clear-dependency]
  [--optional | --required]
  [--frequency KEY | --clear-frequency]
  [--list-order KEY | --clear-list-order]
  [--assignee ID | --clear-assignee]

arpent todo done <id>
arpent todo defer <id> --to dd-mm-yyyy
arpent todo block <id> --on <object-id>
arpent todo archive <id>
```

Content edits rename the Markdown trace. Dependencies may reference any object ID except the task itself. `block` sets both dependency and waiting state. `defer` changes the do date, not the due date. Todo schema validation is strict; Arpent refuses foreign, incomplete, obsolete, or manually altered database layouts rather than attempting an implicit migration.

### Session reference

```text
arpent session end
  [--project SLUG]
  [--area SLUG]
  --summary TEXT
  [--decision TEXT ...]
  [--next-step TEXT ...]
  [--memory-log]
  [--observation TEXT ...]
  [--trait TEXT ...]
```

Decision, next-step, observation, and trait flags are repeatable. Project and area are independently optional, but a no-target close requires `--memory-log` or full-mode observation/trait queue writes. Target context is the default transaction-journaled continuity sink in both modes. `--memory-log` explicitly creates or updates the optional log for that invocation; agents must not read it later without user opt-in. Observation/trait queue writes are full-only; minimal mode rejects those flags before mutation.

### Tools, sweep, and cron reference

These groups require full mode.

```text
arpent tools list [--category VALUE] [--status VALUE]
arpent tools show <name>

arpent sweep ephemeral [--dry-run]
arpent sweep status [--json]

arpent cron run --tick [--dry-run] [--allow-local-code]
```

`sweep status` reads the latest valid summary event and tolerates malformed prior JSONL lines. Sweep failures are reported as partial results and return nonzero. Real cron dispatch requires `--allow-local-code`; dry-run does not.

### Backup reference

```text
arpent backup [--destination DIRECTORY]
arpent backup verify <snapshot>
arpent backup restore <snapshot> --to <new-directory>
```

The default parent is `06_indexes/backup/`. A custom destination may be outside the vault but cannot be another arbitrary directory inside it. Creation and restore publish atomically from staging. Verification checks the manifest checksum and structure, exact payload membership, file sizes and SHA-256 hashes, safe paths, symlink shape, and SQLite integrity.

### Placeholder commands

The following parsers exist so planned command names fail clearly, but the tools are not installed:

```text
arpent fleeting [args...]
arpent reader [args...]
arpent calendar [args...]
arpent sport [args...]
arpent journal [args...]
arpent crm [args...]
```

Use `arpent note new "..." --type fleeting` for the implemented fleeting
workflow. There is no generic top-level `review` command; `arpent import review`
is the implemented migration-specific review flow.

### Operational side effects

| Operation | Important write behavior |
|---|---|
| Any parsed vault-scoped command when a vault is known | Best-effort append of a privacy-allowlisted v2 success or failure event to `06_indexes/logs/usage.log` |
| `note edit --dry-run` or `note ingest --dry-run` | Leaves domain files unchanged but can append usage/lock state |
| `import scan` | Writes the requested plan and unique sibling inventory; never changes source files; normal non-overlapping vault telemetry may append |
| `import suggest/review` | Rewrites only the plan; never changes source files; normal non-overlapping vault telemetry may append |
| `import apply --dry-run` | Leaves import destinations and resumable state unchanged; vault-scoped usage telemetry may still append |
| `import apply` | May create declared Areas, Resources, and projects before copying external sources through per-item transactions; writes resumable state/report files |
| `todo list` or `todo show` on first use | May create and validate `todo.db` |
| `index` | Replaces generated inventory, sidecar, search, and context outputs |
| `context set` | Updates `context_index.json` |
| `cron --dry-run` | Can emit configured notification/audit output |
| `sweep --dry-run` | Writes sweep log, usage, lock state, and summary |
| `backup` | Creates a snapshot and temporary staging state |

The CLI does not prompt before ordinary single-item mutation. `import review`
asks hierarchical placement questions, and `import apply` asks one final batch
confirmation unless `--yes` is supplied. `note dissolve --yes` retains its own
explicit destructive boundary. Other preview/announce/confirm behavior comes
from the agent protocol, not a generic parser prompt.

## Design principles

1. **Continuity over recollection.** Projects should carry enough context to resume without reconstructing the past.
2. **Files over applications.** The durable layer stays readable, editable, portable, and user-owned.
3. **AI as leverage.** Agents operate the system; they do not own its memory or determine its lifespan.
4. **Determinism over guessing.** Placement follows explicit metadata, and uncertainty remains visible.
5. **Knowledge over accumulation.** Reusable output matters more than raw capture volume.
6. **Lifecycle over clutter.** Active work stays light while history remains recoverable.
7. **Provenance over opacity.** Sources, authorship, relations, and status are part of the work.
8. **Explicit automation over ambient automation.** No hidden daemon, implicit AI indexing, or lifecycle without configured rules.
9. **Replaceable derivatives.** Search, indexes, and summaries can change without threatening source material.
10. **Human control at meaningful boundaries.** Ambiguous routing, subjective fields, maturity changes, and dissolution remain deliberate decisions.

## Roadmap

| Phase | Focus | State |
|---|---|---|
| **1 - Foundations** | Vault, routing, note lifecycle, context, search, health, continuity, and maintenance | implemented broadly; validation pending |
| **2 - Daily flows** | Fleeting capture, todo, reader, and calendar | todo implemented; validation pending |
| **3 - Instrumented areas** | Journal, sport, CRM, finance, notifications, and health trends | planned |
| **4 - Long-term synthesis** | Progressive compression, cross-area synthesis, and content pipelines | planned |
| **5 - Optional ingestion** | Generic reviewed filesystem import; future sync recipes, voice capture, bots, and MCP access | generic import implemented; connectors planned |

A phase is complete only after at least 14 days of daily use and a written retrospective. Arpent should grow from demonstrated use rather than speculative feature volume.

## License

Arpent is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE). It may be used, modified, and distributed for permitted noncommercial purposes under that license; commercial use requires separate permission.

---

**Build the layer you will own. Rent the intelligence that reads it.**

# COMPASS.md - the path to follow

*The runtime router for an agent receiving information from this Arpent user. Start here to decide what the information is, whether anything should be retained, where it belongs, what capability can handle it, and what must be asked before acting. This installed version points only to files that live inside the vault.*

---

## 1. What this system is

Arpent is a filesystem-native life OS operated with the user. Markdown remains
the durable source of truth; generated indexes and tool databases support it.
The top-level working zones are `00_inbox/` through `06_indexes/`, with
`00_inbox/unsure/` for unresolved placement.

| Information role | Destination | Standard |
|---|---|---|
| Long-form knowledge to open, read, and edit | Vault (`00`-`05`) | Clean and user-legible |
| Action requiring execution, tracking, or completion | Installed todo tool | Structured DB plus readable Markdown trace |
| Stable trait, durable fact, or contextual reminder | Delegated memory | Provider-managed, outside the vault |
| Unsupervised agent research scratch | `06_indexes/memory/wiki/` | Mess tolerated |
| Default cross-session operational continuity | Project or area `_context.md` | Current working state, not canonical memory |
| Optional cross-project session log | `06_indexes/memory/MEMORY.md`, only via explicit `--memory-log` | Disabled by default; never read without user opt-in |
| Unresolved physical placement | `00_inbox/unsure/` plus a reason | Visible uncertainty, never a silent guess |

One user message may produce several destinations. Files are the source of
truth. You are rented; the files outlive you.

Both vault modes provide local continuity through `arpent project create`,
project or area `_context.md`, and `arpent session end`. `MEMORY.md` is disabled
by default in both modes and is not seeded. Minimal mode omits delegated-memory
queue writes, context summaries, todo, tools, cron, sweep, the entire
`06_indexes/memory/` tree, and portable agent infrastructure. Full mode keeps
those optional surfaces; delegated external memory still requires explicit
host-level opt-in.

## 2. Where the law lives

Load only what the current operation requires.

| File | Open when |
|---|---|
| `.agent` | Entering the vault and checking its hard rules |
| `me.md` | Reading the user's approved interaction contract |
| **`COMPASS.md`** | Choosing the next operation and interaction path |
| `06_indexes/global_skills/arpent.skill.md` | Loading the complete installed operating method |
| `06_indexes/docs/architecture/routing.md` | Computing a note destination or handling ambiguity |
| `06_indexes/docs/architecture/frontmatter.md` | Creating, editing, or validating ordinary note metadata |
| `06_indexes/docs/architecture/memory-layers.md` | Distinguishing vault, delegated memory, and memory wiki |
| `06_indexes/docs/architecture/indexing-and-context.md` | Indexes and optional L0/L1/L2 context |
| `06_indexes/docs/architecture/tools.md` | Tool control plane, installation status, and runtime boundary |
| `06_indexes/docs/architecture/cli.md` | CLI architecture; verify exact syntax with `arpent --help` |
| `06_indexes/cli/operations.yaml` | Routing enums, mechanisable routes, and operation inventory; not full CLI syntax |
| `06_indexes/tools.yaml` | Registered tools and declared status; not a command dispatcher |
| `06_indexes/global_skills/<tool>.skill.md` | Exact method for an installed tool only |

## 3. Start with the information, not the marker

1. **Classify first.** Use this route whenever information may need capture,
   action, memory, retrieval, organization, or lifecycle handling. A `.arpent`
   marker helps locate an existing vault; it is not the trigger and is not
   required to decide what should happen.
2. **Locate a target only when needed.** A routing recommendation and a direct
   delegated-memory action need no vault. A vault read or mutation needs this
   vault, a path supplied by the user, or one short clarification. Initialize
   elsewhere with `arpent init <path>` only after an explicit request, then
   verify every path referenced by its `.agent`; missing COMPASS or skill files
   mean the bootstrap is incomplete and must be reported, not guessed around.
3. **Load local context.** To resume in either mode, read in order: root
   `me.md`, then the target project or area `_context.md`, then only the specific
   notes or sources needed. Normal resume must not read `MEMORY.md`; read that
   optional log only when the user explicitly asks for or enables it. Resume is
   this documentary protocol, not a command.
4. **Probe execution.** Try `arpent --version`. When available, prefer the CLI
   for supported state changes. Otherwise use the safe degraded path below.

## 4. Classify the intent

| User intent | Route |
|---|---|
| "Keep this to read, develop, or reuse" | Knowledge note in the vault |
| "I need to do, track, complete, defer, or block this" | Todo |
| "Remember this fact/preference/context" | Delegated memory: observation/profile/buffer |
| "Research this autonomously" | Memory wiki |
| "Find/recall" | Vault search plus one external-memory query |
| "Sort/organize" | Triage and confirmed routing |
| "Develop/archive/close" | Lifecycle operation |
| "Where should this go?" | Recommendation only; do not require a vault or write anything |

A time-bound item is a todo when completion must be tracked. It is a memory
buffer when it is context to recall but no action must be completed.

## 5. Use the same protocol for every operation

1. **Identify** the intent, destinations, and current capability.
2. **Load** only the relevant contract or installed tool skill.
3. **Resolve inputs** using the question policy in section 9.
4. **Preview mutations:** operation, complete proposed metadata or field
   changes, destination, content boundary, and every known side effect.
5. **Confirm once** for the complete batch. Read-only domain queries may run
   immediately; they can still append the CLI usage log.
6. **Execute** with an implemented command. There is no generic `--plan` or
   `--yes`; never claim otherwise. Specific confirmation flags exist for
   `arpent note dissolve` and reviewed `arpent import apply`. Use available
   `--dry-run` flags for note edit, note ingest, import apply, sweep, or cron
   previews, noting that operational logs may still be written even when domain
   files are unchanged.
7. **Verify** the result before reporting success: expected path/state exists,
   frontmatter parses, routing recomputes to the same destination, and required
   side effects are present. Report partial or deferred outcomes explicitly.
8. **Refresh derivatives when needed.** After direct/manual file changes, run
   or propose `arpent index` to restore indexed-search speed and refresh
   context data. Search itself falls back to a live scan when its FTS signature
   is stale.

## 6. Copy-paste frontmatter reference

Use this quick reference when a human or agent needs to paste a complete note
header without opening `06_indexes/docs/architecture/frontmatter.md`. Keep the
field order intact. Replace placeholders, leave unknown optional values as
`null`, and never fill `appreciated` or `importance` for the user.

The universal frontmatter schema is closed during normal use. Do not invent
per-project fields: CLI validation rejects unsupported keys. Users may freely
add or reorder body sections and create project files or subfolders. Extending
the schema is deliberate system development requiring canonical schema, order,
validation, policy, documentation, and test changes together.

```yaml
---
title: <lowercase_ascii_snake_case>
id: <type>-<YYYYMMDD>-<letter>
created: <dd-mm-yyyyTHH:MM:SSZ>
modified: <dd-mm-yyyyTHH:MM:SSZ>

description: <useful standalone summary or null>
type: <note|concept|journal|log|checklist|reference|draft|template|meeting|idea|fleeting|linear|integration|angle|production|map|artefact>
project: <slug or null>
area: <slug or null>
resource: <slug or null>
status: <inbox|maturing|active|stable|ongoing|standby|waiting|to-start|done|stale|archived>
effort_cadence: <heavylift|slowburn|null>
effort_level: <low|medium|high|null>
tags: [<lowercase-hyphen-tag>, <lowercase-hyphen-tag>]
chosen_location: <one-line placement rationale or null>

source: <manual|generated|imported|captured|conversation|derived>
link: <URL, path, external id, session id, or null>
author: <user|agent|imported>

depth: <1|2|3|4|5|null>
appreciated: null
importance: null
pinned: false

expires_at: <dd-mm-yyyyTHH:MM:SSZ or null>

related: []
relations:
  - type: <supports|contradicts|depends_on|derived_from|example_of>
    target: <note_id>
parent: <note_id or null>
observations: []
extracted_to: []
---
```

Field value summary:

| Field | Allowed shape or values |
|---|---|
| `title` | lowercase ASCII `snake_case`; ordinary note filename follows it |
| `id` | `<type>-<YYYYMMDD>-<letter>`; stable graph anchor |
| `created`, `modified` | `dd-mm-yyyyTHH:MM:SSZ`, UTC |
| `description` | useful standalone summary or `null` |
| `type` | `note`, `concept`, `journal`, `log`, `checklist`, `reference`, `draft`, `template`, `meeting`, `idea`, `fleeting`, `linear`, `integration`, `angle`, `production`, `map`, `artefact` |
| `project` | project slug or `null`; mutually exclusive with `resource` |
| `area` | area slug or `null`; may accompany `project` or `resource` as context |
| `resource` | resource slug or `null`; mutually exclusive with `project` |
| `status` | `inbox`, `maturing`, `active`, `stable`, `ongoing`, `standby`, `waiting`, `to-start`, `done`, `stale`, `archived` |
| `effort_cadence` | `heavylift`, `slowburn`, or `null`; active actionables only; never infer |
| `effort_level` | `low`, `medium`, `high`, or `null`; active actionables only; never infer |
| `tags` | list of lowercase hyphenated tags, or `[]` |
| `chosen_location` | one-line placement rationale or `null`; documentary only |
| `source` | `manual`, `generated`, `imported`, `captured`, `conversation`, `derived` |
| `link` | `null`, URL, local path, external identifier, or session identifier; required for `captured` and `imported` |
| `author` | `user`, `agent`, or `imported` |
| `depth` | `1`, `2`, `3`, `4`, `5`, or `null`; do not score if arbitrary |
| `appreciated` | `null` for agents; user-only value |
| `importance` | `null` for agents; user-only value |
| `pinned` | `false` by default; user may set `true` |
| `expires_at` | `dd-mm-yyyyTHH:MM:SSZ` or `null`; mostly for buffer items |
| `related` | list of note IDs for weak/non-qualified links, or `[]` |
| `relations` | list of `{type, target}` objects; relation type is `supports`, `contradicts`, `depends_on`, `derived_from`, or `example_of` |
| `parent` | source note ID or `null`; required for extracted child notes |
| `observations` | memory-provider observation IDs, or `[]` |
| `extracted_to` | extracted child note IDs, or `[]`; maintained during extraction/dissolution |

## 7. Follow the operation branch

### A. Capture knowledge

1. Use complete universal frontmatter for ordinary notes. A fleeting daily file
   is an append-only capture stream and is the explicit exception.
2. Route with `project > resource > area > inbox`. `project` and `resource` are
   mutually exclusive homes; `area` may accompany either as context.
3. Important overrides: `fleeting` -> today's inbox append file; `map` ->
   `03_resources/maps-of-content/` with `ongoing` as its default status;
   `integration` -> `03_resources/integrations/`; `artefact` ->
   `05_tools/artefacts/`; project draft -> project `drafts/`; agent-authored
   draft without a project -> `03_resources/agent_wiki/drafts/`; `meeting` and
   `log` use their declared subfolders.
4. Use `arpent note new`. Fleeting capture is
   `arpent note new <title> --type fleeting`, not the unavailable top-level
   `arpent fleeting` namespace.
5. No routing fields means inbox. `project + resource` or a missing destination
   goes to `00_inbox/unsure/` with a reason. Do not invent a slug.
6. For raw text, malformed frontmatter, or binary/non-UTF-8 inbox files, use
   `arpent note ingest <inbox-path> --title <title> ... [--attachment]
   [--dry-run] [--json]`. Preserve source content; do not hand-convert around
   the ingestion transaction. A binary remains byte-for-byte untouched and
   cannot contain YAML: `--attachment` moves it transactionally to the selected
   home's `attachments/` and creates a separate Markdown reference note with
   complete frontmatter whose `link` points to it. Without a final home, the
   original remains in inbox and the companion reference is untriaged.

### B. Capture an action

Use `arpent todo add`, then `list`, `show`, `edit`, `done`, `defer`, `block`, or
`archive` as requested. Todo records are tool-owned: never edit a `todo-*` note
with generic note commands or update its SQLite and Markdown representations
separately. Todo archive requires `done` status.

### C. Capture memory or research

Pick the logical memory role: stable trait/preference -> profile; discrete fact
-> observation; expiring context -> buffer. Delegated memory is disabled by
default in minimal and full vault modes. Hand information to the host interface
only after explicit user opt-in; interface availability alone is not activation.
Arpent does not discover, select, configure, mirror, or synchronize memory
providers. When delegated memory is not explicitly active, state that the item
was not persisted; do not create a vault note or local queue as a substitute.
Research scratch belongs in the memory wiki, never in the clean vault.

### D. Find or recall

`arpent search <query>` and `arpent note find <query>` search vault notes only.
Query the host's external-memory interface once only when the user has explicitly
enabled it, and label vault versus external-memory results. Provider discovery,
fan-out, and deduplication belong to that external system. If files changed
since the last index, run `arpent index` first or use a live filesystem search.

### E. Organize or edit

Run `arpent triage --json` to inventory every non-fleeting inbox item with its
kind, age, hash, and `edit`, `ingest`, or `leave` actions. It does not move
items. Build one complete plan, preview structured notes with `arpent note edit
<id> ... --dry-run --json` and raw/malformed/binary files with `arpent note
ingest ... --dry-run --json`, show all frontmatter/path/content-boundary
changes, and confirm once. Carry a structured edit's `plan_sha256` into
`--plan-hash` when applying so source or routing changes require a fresh review.
Apply each item as its own transaction, re-run
triage, and report every applied, skipped, and failed item honestly; a batch may
partially succeed. `note route` replaces all three routing fields, so pass the
complete intended `project`, `area`, and `resource` state on every call.

### F. Create or resume a project

Use `arpent project create <name> [--area <slug>] [--effort-cadence
heavylift|slowburn] [--effort-level low|medium|high]` in either mode. The human
name becomes a visible lowercase ASCII kebab-case slug. The command creates a
complete `_context.md` plus `notes/`, `drafts/`, and `attachments/`; it never
creates an area, merges a collision, or makes routing invent a project. Resume
by the ordered file-reading protocol in section 3.

### G. Mature, extract, dissolve, archive

- Change maturity with `arpent note status` or the required `note edit/route`;
  there is no `note promote` command.
- Extract from a linear note with
  `arpent note extract <linear-id> --type <type> --title <title> ...`.
- Dissolve only after at least one verified child and explicit confirmation:
  `arpent note dissolve <linear-id> --yes`.
- `arpent archive <id>` archives one ordinary non-linear note by ID. Use
  `arpent todo archive` for todos and dissolution for linear notes. A project,
  folder, or arbitrary file requires a separately previewed manual procedure.

### H. Inspect, index, summarize context, and report usage

Use `arpent status`, `arpent efforts`, and `arpent health [--json]` for
domain-read-only views. Use `arpent index` for deterministic inventory, hashes,
context state, and search. AI-generated L1 summaries are explicit-only: follow
`06_indexes/global_skills/context_summary.skill.md`, run
`arpent context pending --json`, load a source with
`arpent context show <path> --level l2`, then store it with
`arpent context set <path> --source-hash <hash> (--summary <text>|--stdin)
[--provider <id>]`. Do not regenerate a fresh summary.

Use `arpent usage report [--since <dd-mm-yyyy>] [--json]` for local
privacy-allowlisted v2 command metrics and current triage age. It cannot measure
documentary resume reads, re-explanation avoided, or context quality; record
those in `06_indexes/logs/usage-journal.md`. Ordinary logs are currently
included in logical backups and may also live in a synchronized vault folder.

### I. Operate tools and maintenance

- `arpent tools list/show` inspects the registry; it does not install, enable,
  disable, or dispatch tools.
- Currently installed: `todo` and the explicit `context_summary` workflow.
- Currently planned, not invocable as tool workflows: `reader`, `review`, and
  `z_backup`. The core `arpent backup` commands are available.
- Do not invoke the unavailable top-level `fleeting`, `reader`, `calendar`,
  `sport`, `journal`, or `crm` namespaces. Use ordinary notes as the safe
  fallback when appropriate.
- `arpent sweep ephemeral [--dry-run]` is implemented and only processes
  installed ephemeral tools. `delete-after-review` proposes; it never deletes.
- `arpent sweep status [--json]` reads the latest sweep outcome.
- `arpent backup [--destination <dir>]` creates a manifest-backed logical vault
  snapshot. Use `arpent backup verify <snapshot>` before relying on one and
  `arpent backup restore <snapshot> --to <new-dir>` only with a nonexistent
  target. It excludes rebuildable/runtime state and does not cover Git history,
  delegated memory, remote storage, encryption, or retention.
- Cron has no daemon. Preview with `arpent cron run --tick --dry-run`; execution
  additionally requires `arpent cron run --tick --allow-local-code`.
- Every enabled cron job must declare `trust: local-code`. Treat its command as
  executable code with the user's permissions; never enable jobs from an
  untrusted vault.

### J. End a session

Use `arpent session end --summary <text> [--project <slug>] [--area <slug>]
[--decision <text> ...] [--next-step <text> ...] [--observation <text> ...]
[--trait <text> ...] [--memory-log]`. In both modes the default local write is
the target `_context.md`. `--memory-log` explicitly opts this invocation into
creating or updating the optional cross-project `MEMORY.md`; agents must not
read that log later unless the user explicitly asks for or enables it. A close
without a project or area requires an explicit sink: `--memory-log`, or in full
mode at least one observation/trait queue write. Full mode can queue supplied
observations and traits in `pending_db_writes.yaml`; minimal mode rejects those
flags before mutation and never creates the queue. The full-mode queue is
CLI-owned deferred state, not a memory provider registry for the agent to
inspect or flush. External-memory persistence remains the host system's
responsibility. Every `_context.md` created or updated by the command has the
complete universal frontmatter field set; existing body sections are preserved
and the session block is appended. Report each completed or deferred stage.

## 8. Degraded mode

Without the CLI, ordinary Markdown capture, reading, searching, and confirmed
routing remain safe when the routing and frontmatter contracts are followed.
Do not manually operate todo dual state, linear dissolution, sweep, cron, or
other coordinated DB/multi-file operations. External memory is not part of
Arpent degraded mode: use the host interface or state that persistence was
unavailable, without creating a local fallback. Rebuild derived indexes with
`arpent index` when the CLI returns.

## 9. Ask only when the answer changes the operation

Ask when the target vault is required but unknown; a user-owned value is
required; action vs memory is genuinely unclear; routing has conflicting homes;
a referenced destination is missing and creation was not authorized; source
provenance is incoherent; or extraction, dissolution, manual archival, or a
control-plane change needs consent.

Do not ask for inferable normalization, safe defaults, optional tags,
description, depth, or `chosen_location`. Never infer `appreciated`,
`importance`, or an effort cadence/level. No home fields means inbox; conflicting
homes means `00_inbox/unsure/`. Batch all blocking questions into one interruption. If a
quick capture can safely land in inbox or `00_inbox/unsure/`, prefer that over needless
questioning and state what remains unresolved.

## 10. Invariants

1. Announce and confirm state changes; batch related changes.
2. Never delete user content; archive. Empty-directory cleanup and any reviewed
   deletion proposal still require explicit confirmation.
3. Never silently guess routing; preserve a written reason in `00_inbox/unsure/`.
4. Never fill `appreciated` or `importance`, and never infer effort profiles.
5. Keep full frontmatter on ordinary notes; respect explicit system-file and
   fleeting-stream exceptions.
6. Keep facts out of the vault and unreviewed research out of clean knowledge.
7. Keep tool know-how in `06_indexes/`; `05_tools/` contains declared runtime
   material only.
8. Use one reusable thesis per note; preview a split as one batch.
9. Keep bodies simple and autonomous: no repeated H1, source URL, or decorative
   callouts by default.
10. Never report a capability, external-memory handoff, move, or index as
    successful without verifying it.

*If you remember three things: classify before locating; knowledge, action, and memory are different roles; preview, confirm, execute, then verify.*

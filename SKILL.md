---
name: arpent
description: Operate an Arpent vault - a filesystem-native personal life OS organized into 7 buckets with universal frontmatter, delegated modular memory, a clean shared knowledge base, and deterministic routing. Use this skill whenever the user asks to capture, organize, route, archive, retrieve, mature, or extract any kind of personal information - notes, ideas, meetings, reading, journal entries, observations, traits, habits, fleeting thoughts, drafts, concepts, or any element of their life that should be remembered, structured, or made queryable across time. Use it on casual phrasings: "remember that…", "where should I put this", "find that note about…", "I read something interesting", "I want to keep track of…", "turn this draft into a real note". Prefer this skill over generic file operations whenever the context is an Arpent vault.
---

# Arpent

Arpent is a filesystem-native personal operating system. The durable layer is markdown with deterministic frontmatter, plus tool-owned SQLite where structured state such as todo requires it. It is built for one user. Its goal is to outlive the AI tools that read it - files first, AI rented as a renewable resource.

## Reading order

This SKILL.md gives the operating frame. **Read the relevant contract file before acting** - the files below contain the full rules, schemas, and edge cases. Loading them on demand is correct usage.

| Reference | Read when |
|---|---|
| `references/architecture.md` | Anytime you touch the vault structure, sub-folders, or wonder where something belongs |
| `references/frontmatter.md` | Creating, editing, or validating any note's frontmatter |
| `references/memory-layers.md` | Deciding where memory belongs: the vault, delegated memory, or the memory wiki |
| `references/routing.md` | Determining the destination path of a note |
| `references/lifecycle.md` | Status transitions, maturation, ephemeral sweep, linear note dissolution, maps, end-of-session protocol |
| `references/tools-and-cron.md` | Shipped sub-tool, sweep, backup, and cron behavior |
| `references/indexing-and-context.md` | Inventorying folders/files or using the optional L0/L1/L2 context-summary module |
| `references/ingestion-and-degraded-mode.md` | Safe direct-file operation when the CLI is unavailable |
| `README.md` | Knowing what ships now, current limits, and the roadmap |

If the vault has its own docs at `06_indexes/docs/ARPENT.md` and `06_indexes/docs/mental-model.md`, read those first - they may contain user-specific guidance. They cannot override CLI syntax, packaged enums, or safety invariants. The files in this skill are the canonical operating defaults.

## Trigger

Any of these intents activates this skill:

- Capture: a thought, file, URL, transcript, observation, trait, or preference
- Organize: triage inbox, route a file, choose where something belongs
- Continue: create a project, resume from documentary context, produce useful work, close a session
- Record: a stable user trait, an interaction preference, a discrete fact
- Retrieve: search across the vault and whatever memory is active
- Navigate: build or update a Map of Content; inspect the required-investment profile of active actionables
- Mature: promote a draft, extract typed notes from a linear working note, dissolve the source, or mark reusable knowledge as stable
- Archive: move content to archives without deleting
- Maintain: review status, sweep ephemeral content, run health check, close a session

Trigger on casual language. The user does not need to use Arpent vocabulary.

## Input

A user message containing one of:

- Free-form content to capture
- A file path or directory to triage
- A command-like intent ("create a meeting note for…", "archive this project…", "find my notes on X")
- A retrieval query
- A maturation request ("turn this into a concept", "promote this fleeting note")

## Steps

### 1. Identify the operation

Match intent to operation. Common cases:

| Intent | Operation |
|---|---|
| New knowledge to keep | `note new` (into the vault) |
| Raw, malformed, or binary inbox file | `note ingest` after a dry-run plan |
| Capture or manage an actionable task | `todo add/list/show/edit/done/defer/block/archive` |
| Remember a fact / trait / reminder | use the host's external-memory interface when available |
| Create a navigation map | `note new --type map` (lives in `03_resources/maps-of-content/`) |
| Organize files | `triage --json`, then confirmed per-item `note edit` or `note ingest` |
| Migrate an external folder tree | `import scan`, reviewed folder roles, `import validate`, then `import apply --dry-run` and confirmed apply |
| Create a deliberate project destination | `project create` (full and minimal) |
| Resume project or area work | Read `me.md`, target `_context.md`, then only needed notes/sources; do not read `MEMORY.md` by default |
| Find something | `search` for the vault, then one separate host-memory query when available |
| Estimate required investment | `efforts` (active actionables by cadence and level) |
| Mature a note | `note status` or `note edit --status` |
| Extract typed children from a `linear` note | `note extract` then, when finished, `note dissolve` |
| Archive | `archive` |
| Sweep ephemerals | `sweep ephemeral` |
| Check vault health | `status`, `health` |
| Close a working session | `session end` (ordered context update) |
| Review local adoption evidence | `usage report` plus qualitative `usage-journal.md` |

### 2. Decide where it belongs

Apply the discrimination rule from `references/memory-layers.md`:

- **Vault** - long-form content to open and read. The clean, shared knowledge base.
- **Agentic memory** (delegated, disabled by default) - durable facts, traits,
  and reminders. Logical roles: profile (traits), observations (facts), buffer
  (time-bound). It is used only after explicit user opt-in at the host level.
- **Memory wiki** - unsupervised short/medium-term research scratch, tolerant of mess.

Memory is delegated and modular, and the vault is *not* a memory dump. More than
one destination can apply to one input; route only to explicitly active modes.
Interface availability alone is not activation: check or ask before any external
memory read or write.

### 3. For vault content: determine type and routing

Pick `type` from the enum (full list in `references/frontmatter.md`).

Apply the routing contract: `project` and `resource` are mutually exclusive homes; `area` may accompany either as context. Route with the precedence `project > resource > area > inbox`. A reusable concept stays in `03_resources/concepts/` and projects link to it with wikilinks. Material useful only inside one project carries `project + area`, keeps `resource: null`, and lives in that project's `notes/`. Special routing rules (fleeting, draft, linear) are in `references/routing.md`.

Create a missing authorized project with `arpent project create <name>` rather
than manual `mkdir`. It creates complete canonical context and working folders
in both modes. It does not create areas or allow ordinary note routing to invent
a project.

### 3a. Decide whether to split

Use one reusable thesis per note. If one title cannot state the material's single thesis, or if parts remain understandable and useful independently, propose a split before writing:

- Preview the candidate notes with a title and one-sentence boundary for each.
- Add one short recommendation to split more or less when the boundary is uncertain.
- Ask for one confirmation for the whole batch, not one interruption per note.
- Preserve useful connections with wikilinks or graph relations instead of consolidating distinct theses.
- Use `linear` when the material is intentionally sequential working material that the user will decompose later.

### 3b. Write autonomous, simple content

- **Language settings (edit these two lines to configure the skill):**
  `Primary language: English`
  `Adaptive languages: French`
- Write note-facing prose in the primary language by default. Adapt to a listed language when the user explicitly requests it, the active conversation is contextually in that language, or the source material makes it the natural language for the note. Replace the list with `auto` to allow any contextually appropriate language, or use a comma-separated list such as `French, Spanish` to restrict adaptation.
- Preserve quotations and source-language terminology. Language selection applies to prose, not frontmatter keys, enums, IDs, CLI syntax, or routing paths. Do not add a `language` frontmatter field.
- Extracted `concept`, `idea`, and `integration` bodies must stand on their own. Do not frame them as "point X from the source" or "in this discussion".
- `reference` and `linear` notes may analyze or quote their source because the source is their subject, but never repeat its URL in the body.
- Put the source URL only in frontmatter `link`.
- Use ordinary Obsidian-compatible Markdown: paragraphs, useful headings, lists, and native blockquotes. Do not add callouts, decorative containers, or elaborate formatting unless the user asks.
- Do not repeat the note title as an H1 in the body. The filename and `title` property already carry it.

### 4. Build the frontmatter

Every note has the same shape, same field order. The full schema with policies (system / agent / user / agent-forbidden) is in `references/frontmatter.md`. Critical rules:

- **The universal schema is closed during normal use.** Never invent per-project fields; CLI validation rejects unsupported keys. Users may freely add or reorder body sections and create project files/subfolders. Schema extension is deliberate system development requiring canonical schema, order, validation, policy, docs, and tests to change together.

- **Never fill** `appreciated`, `importance`. User-only.
- **Default `pinned: false`**, user toggles.
- **`author: agent`** when the agent creates without explicit user request.
- **`source` and `link`** must be coherent (see `references/frontmatter.md`).
- **`title` and filename** use lowercase ASCII `snake_case`, with no date or ID. Renaming `title` renames the file.
- **`description`** is `null` when it merely repeats the title or body.
- **`depth`** is a conservative 1-5 development scale: 1 ordinary, 3 already in-depth, 5 exhaustive; leave `null` if scoring adds no value.
- **Statuses are semantic:** `active` for current efforts/actionable content, `stable` for established reusable knowledge, `ongoing` for permanent evolving material, and `stale`/`done` for terminal content eligible for tool-driven archival.
- **Active actionables may carry an explicit effort profile:** `effort_cadence: heavylift|slowburn` and `effort_level: low|medium|high`. Never infer missing values; leave them `null` and let `efforts` show `unclassified`.
- **`relations`** is for typed semantic graph edges only. Valid `relations[].type`: `supports`, `contradicts`, `depends_on`, `derived_from`, `example_of`. Use `related` for weak/non-qualified links.
- **Dates are day-first:** use `dd-mm-yyyy` for dates and `dd-mm-yyyyTHH:MM:SSZ` for note-facing UTC timestamps. Existing ISO timestamps remain readable, but new note metadata uses the day-first format. IDs keep their opaque `<type>-<YYYYMMDD>-<letter>` contract.

### 5. Announce before acting

Before any state change, show:

- The full proposed frontmatter
- The destination path
- Side effects (DB writes, related note updates)

Wait for confirmation. `note dissolve` and reviewed `import apply` expose explicit
`--yes` flags for their own destructive or batch confirmation boundaries; do not
invent a generic confirmation flag for other commands.

### 6. Execute via CLI when available

If `arpent` CLI is available, prefer it. Use `arpent <command> --help` for current syntax and `references/tools-and-cron.md` for behavior. If unavailable, operate in degraded mode per `references/ingestion-and-degraded-mode.md`.

For triage, run `arpent triage --json`, prepare one complete plan, preview
structured notes with `note edit --dry-run --json` and raw inputs with `note
ingest --dry-run --json`, then ask once. Carry `plan_sha256` into `--plan-hash`
for each structured-note apply. Apply each item transaction separately,
re-run triage, and report partial results without claiming batch atomicity.

For an external tree, never move it into the vault manually. Run `import scan`
with the plan outside the source, inspect deterministic suggestions, and use
interactive `import review` for uncovered folder roots. Validate with `--sources`
when practical, preview `import apply --dry-run --json`, obtain one final batch
confirmation, then apply. The source and vault must not overlap. Import is
copy-only, resumable, and per-item atomic; report every collision or failed item.

### 7. Confirm and summarize

Report what was created/moved/modified, where it lives now, related entries, and follow-up suggestions (e.g., "this is `maturing` - review in 14 days").

## Output

Natural-language summary plus structured action confirmation. For single notes:

```
✓ Created: <id>
  Path:    <relative path from vault root>
  Type:    <type>
  Status:  <status>
  Effort:  <cadence/level|unclassified>  # only when status is active
  Routing: <project|area|resource>=<slug>
  Author:  <user|agent>
```

For batch operations (triage, dissolve, sweep), produce a table of changes.

## Method - the non-negotiable rules

These rules govern every action. They are immutable invariants.

### Files first

Markdown, SQLite, JSON only. No proprietary formats. The vault must be readable with `cat` and editable in any text editor. No daemon, no server, no browser dependency.

### Routing is deterministic

Given a complete frontmatter, the destination is a pure function. If two paths are possible, the file goes to `00_inbox/unsure/` with a reason. Never silently pick.

### Never delete

Arpent archives. The only deletion allowed: truly empty directories, after explicit confirmation. Replaced or dissolved notes survive in `04_archives/` (by quarter) or `04_archives/linear_notes/` (dissolved sources).

### Announce every move

Before rename, move, or modification, show the diff and wait for confirmation. Exception: explicit `--yes` on a specific command.

### Ask, don't hallucinate

Ambiguous routing → `00_inbox/unsure/`. Unknown non-subjective field → ask user. Subjective field (`appreciated`, `importance`) → leave null. Never guess.

### Subjective fields are user-only

`appreciated`, `importance`, `pinned` are user decisions. Agents leave `appreciated` and `importance` null. `pinned` defaults to `false`. Filling these by inference is a policy violation.

### Titles are stable paths, IDs are stable graph anchors

For ordinary notes, `title` and the filename contain the same lowercase ASCII `snake_case` value. The file carries no date or ID. The immutable `id` remains in frontmatter so graph edges survive automatic file renames. Never overwrite a same-named file; ask for a semantic qualifier. Reserved system files such as `_context.md` and append-only fleeting day files keep their prescribed filenames.

### Provenance must be coherent

`source` and `link` follow the cross-table in `references/frontmatter.md`. Mismatch → warn, don't silently accept.

### Memory is delegated; the vault is not a memory dump

Memory is modular and lives *beside* the vault, not inside it. Delegated memory
is disabled by default in minimal and full vault modes. Durable facts, traits,
and reminders go to the host's external-memory interface only after explicit
user opt-in. Unsupervised research scratch goes to the **memory wiki**
(`06_indexes/memory/wiki/`, tolerant of mess). The **vault** holds long-form
knowledge to read and edit, and must stay clean and comprehensible. Arpent does
not discover or operate a native memory provider. Don't dump facts into the
vault. Details are in `references/memory-layers.md`.

### `chosen_location` is an optional rationale, never required

A note may carry an optional `chosen_location` - one line explaining what it does in this place in the system. It is purely documentary, helps when a note's home isn't self-evident, and never affects routing. Leave it null unless it adds clarity.

### Tools have homes

All sub-tool know-how lives in `06_indexes/`: skills, CLI contracts, schemas, migrations, documentation, registry, and centralized databases. `05_tools/` is runtime-only and may contain only artifacts, queues, captures, caches, or outputs declared by an installed tool's `writes_to`. Area-bound user content lives in its area; transversal runtime content may live in `05_tools/<tool>/`. Never place a `SKILL.md` or creation instructions in `05_tools/`. Disposable demo, illustration, and temporary script/file notes use `type: artefact` and route to `05_tools/artefacts/`.

### Ephemeral content rotates

Installed tools marked `ephemeral: true` in `tools.yaml` use statuses for lifecycle. `active`, `stable`, and `ongoing` content remains in place. The cron job `ephemeral-sweep` may archive only `done` or `stale` content according to the tool rule. Details are in `references/lifecycle.md`.

### Maturity is a status, not a location

A maturing note lives at its final destination with `status: maturing`. Don't route through a "drafts" folder unless `type: draft` tied to a project. Maturity transitions are user-confirmed, with system suggestions in weekly review.

### Linear notes dissolve, they don't multiply

A `type: linear` note is sequential working material intended to be worked through and optionally decomposed. It may be an annotated source, a reflection across concepts, exploratory thinking, or rough material for several drafts. Extracted children can use any note type and route from their own frontmatter. When extraction is complete, the source migrates to `04_archives/linear_notes/` with `status: archived` and `extracted_to: [child_ids]`. Children carry `parent: <source_id>`. Wikilinks `[[child]]` exist only in the source's body.

### Maps of Content are permanent and evolving

A `type: map` note is a navigation map - an annotated, sectioned set of wikilinks created at a "mental squeeze point" when a topic has too many notes to navigate. Maps live in `03_resources/maps-of-content/`, default to `status: ongoing`, never rotate, and are never swept. A map is distinct from `related` and `relations`: it's an organized narration of relationships. Details are in `references/routing.md` and `references/lifecycle.md`.

### Projects belong to areas

Every project and project-local note may declare its owning area directly with `area: <area-slug>`. `project` determines the physical route and `area` provides context. Global resources may also carry an area, but never a project; projects connect to reusable global concepts with wikilinks and backlinks. `arpent efforts` lists all `active` actionables by explicit cadence and level; it never uses timestamps.

### Default continuity lives in `_context.md`

Every project and instrumented area carries a `_context.md` (vision, current state, key resources, next steps), maintained by the agent and read first when entering that project/area. Every context created by `project create` or created/updated by `session end` has the complete universal frontmatter field set. Users may extend or reorder its body; `session end` preserves those sections and appends a session block.

Resume in either mode by reading root `me.md`, then the target `_context.md`,
then only the specific notes or sources needed. There is no dedicated resume
command. `06_indexes/memory/MEMORY.md` is an optional cross-project log disabled
by default; never read it during normal resume unless the user explicitly asks
for or enables it.

### End every session with the ordered update

At the end of a working session, `arpent session end` appends a session block to
the project/area `_context.md` by default in full and minimal modes. Passing
`--memory-log` explicitly opts that invocation into creating or updating the
optional cross-project `MEMORY.md`; its existence does not opt agents into later
reads. In full mode only, supplied observations and traits can be appended to
the CLI-owned deferred queue. Minimal mode rejects those flags before mutation
and never creates the queue. A no-target close requires an explicit sink:
`--memory-log`, or in full mode at least one observation/trait. The queue has no
flush command and is not an external-memory provider. Persist durable facts
separately only through an explicitly enabled host interface. Details are in
`references/lifecycle.md`.

### Binary files have Markdown companions, not embedded YAML

A binary or non-text file remains byte-for-byte untouched and cannot contain
frontmatter. `note ingest --attachment` moves it transactionally to the selected
home's `attachments/` and creates a separate Markdown reference note with the
complete universal frontmatter set; `link` points to the attachment. Without a
final home, the original remains in inbox and the companion reference note is
untriaged.

### Production is semantic, not a command namespace

The produce stage means broad useful work: a decision, plan, analysis, draft,
concept, integration, or finished output. Use `type: production` only when that
is the result's correct semantic type. Do not invoke or imply a dedicated
resume, capture, production, or specialized content-pipeline command.

### Usage evidence stays local and honest

Use `arpent usage report [--since <dd-mm-yyyy>] [--json]` for privacy-allowlisted
v2 command outcomes, durations, state changes, session closes, and current
triage age. It cannot observe documentary resume reads or context quality;
record those in `06_indexes/logs/usage-journal.md`. Current logical backups
include ordinary logs, and a local vault may itself be synchronized.

### Agent-authored content is separate

Notes created by the agent without explicit user request live in `03_resources/agent_wiki/` with `author: agent` and `agent_wiki_status: draft`. They can be promoted to their final location after user review (`agent_wiki_status: integrated`). They keep `author: agent` even after promotion - lineage is preserved.

### Density over volume

Vault health is measured by useful output relative to accumulated input, not note count. The `health` command reports the ratio of `source: manual + derived` (output) to `source: captured + imported` (input), plus integration, map, stale, old-maturing, and unresolved-routing signals. A small dense vault beats a vast shallow one.

### Index broadly, load context progressively

`arpent index` inventories folders, notes, attachments, and other non-note files, computes exact and semantic hashes, then refreshes `index.json`, `sidecar.json`, `context_index.json`, and FTS5 search. Context uses three levels: L0 is deterministic one-line orientation, L1 is an optional AI summary tied to a source hash, and L2 is the original source or direct folder children loaded on demand. Indexing never invokes AI. Use `06_indexes/global_skills/context_summary.skill.md` only after an explicit user request; process only `missing` or `stale` entries and never regenerate a `fresh` L1.

### Retrieval is rented, never the source of truth

`arpent search` currently uses FTS5 with a live text fallback. A later release may add a replaceable semantic backend without changing the durable markdown layer. No semantic backend, background sync, or autonomous dream cycle is shipped now.

### Zero Python dependencies for the core

Arpent core uses only Python stdlib. Sub-tools may declare optional dependencies. System binaries (khal, singlefile, exiftool) are acceptable as soft deps - Python pip dependencies are not, except via opt-in extras.

### Vault skills vs portable agent infrastructure

A skill that operates the vault (`06_indexes/global_skills/`) is distinct from the portable roles, skills, workflows, prompts, templates, styles, and capability declarations in `03_resources/agent_infrastructure/`. The test: does it operate the vault, or define how an agent performs a task in the user's life? Vault skills are coupled to Arpent; agent infrastructure is portable. Canonical definitions live under `03_resources/`; `06_indexes/agent_infrastructure_index.yaml` only indexes them.

### Pattern fiche process for every SKILL.md

Every SKILL.md in this vault - including sub-tool skills, agent_infrastructure skills, and this one - follows: Trigger / Input / Steps / Output / Method. This is the imposed shape.

## Hard rules summary

These are non-negotiable invariants. Any agent operating the vault must respect them:

1. Never fill `appreciated` or `importance` - user-only fields.
2. Never delete files - archive only.
3. Never silently route an ambiguous file - use `00_inbox/unsure/` with reason.
4. Never bypass the CLI for state changes when available.
5. Never put dates or IDs in filenames; normalize titles to lowercase ASCII `snake_case`.
6. Never repeat source links in note bodies or make extracted knowledge depend on source framing.
7. Never invent frontmatter fields outside the closed schema. Tool-specific structured data belongs in the tool's database or body format. Extending the universal schema requires coordinated canonical schema/order/validation/policy/docs/tests changes.
8. Never invent `relations[].type` values outside the schema enum.
9. Never write to a memory destination the user didn't ask about, unless intent clearly requires more than one; and never dump facts into the vault.
10. Never extract child notes from a linear note or dissolve it without confirming with the user; decomposition is a deliberate act.

## Quick verification

After reading this skill, you should be able to answer without re-reading:

- The 7 buckets and their prefixes
- Where memory lives (vault / delegated agentic memory / memory wiki) - and that the vault is not a memory dump; `_context.md` is default continuity while optional `MEMORY.md` is disabled and unread by default
- What makes frontmatter valid for routing (`project` xor `resource`, with optional contextual `area`)
- Why `00_inbox/unsure/` exists
- Difference between `archive` and `archive-with-trace`
- Lifecycle of a `type: linear` note from consumption to dissolution
- Why a `type: map` never rotates
- The default and explicitly opted-in sinks of the end-of-session protocol
- Where agent-authored notes live before user review

If you cannot answer confidently, re-read the relevant reference before acting.

## When in doubt

Ask the user. Arpent privileges honest uncertainty over confident error. The vault is a long-term collaboration between the user and a series of AI agents - only the user has continuity across all interactions. Defer to them on anything touching identity, preferences, or the meaning of content.

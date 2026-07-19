# Arpent

Arpent is a local continuity and administration layer for people who work with
changing AI agents. It keeps projects, context, notes, tasks, and archives in an
inspectable filesystem, then gives agents deterministic rules for reading and
changing that state.

This repository is the first Arpent release. The product is a filesystem-native
vault plus an optional local CLI.

## Why Arpent

Agents are replaceable; the work must not be. Arpent makes the handoff durable:

- `me.md` carries user-authored orientation.
- Project and area `_context.md` files carry current operational context.
- Typed Markdown carries readable documents and provenance.
- `todo.db` coordinates actionable task state with readable Markdown records.
- Deterministic routing exposes uncertainty instead of guessing.
- Local indexing, imports, lifecycle operations, usage reporting, and backups
  administer the vault without taking ownership away from the user.

## Continuity Loop

Arpent follows one composed loop. `resume` and `produce` are activities, not
synthetic commands.

1. **Capture:** create a typed note, append a fleeting entry, ingest an inbox
   source, or add a todo.
2. **Resume:** read `me.md`, then the target `_context.md`, then only the notes
   or sources needed for the current work.
3. **Produce:** continue useful work in the semantically correct document and
   lifecycle state.
4. **Close:** append a concise handoff to the target `_context.md`.

```bash
arpent note new "Decision record" --type note --project my-project \
  --body "The decision and its rationale." --json

arpent session end --project my-project \
  --summary "Implemented the first pass." \
  --next-step "Review the edge cases."
```

In full mode, `session end --memory-log` may additionally create or update the
optional cross-project `06_indexes/memory/MEMORY.md` log for that explicit
request. The file is absent by default and is never part of normal resume.

## Install

Arpent requires Python 3.9 or newer and has no runtime dependencies outside the
standard library.

```bash
git clone https://github.com/swftmdsn/arpent-skill.git
cd arpent-skill
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

This installs `arpent` and its `arp` alias.

### Install the agent skill

Choose the exact skill destination required by your agent host; Arpent does not
guess a host or append a host-specific directory. By default the destination
must not already exist, and no vault is required:

```bash
arpent skill install --to /absolute/destination/chosen-for-this-host/arpent
```

To update an existing installation explicitly, add `--replace`. Arpent prepares
and verifies the new bundle before replacing the existing directory, restores
the previous directory if publication fails, and still refuses symlinks or a
non-directory destination.

This copies the complete `SKILL.md` and `references/` bundle. Add `--json` for a
versioned result containing every installed file and SHA-256 hash.

Create a full vault:

```bash
arpent init ~/arpent-vault
cd ~/arpent-vault
arpent project create "My project"
```

Create a direct-file minimal vault instead:

```bash
arpent init --minimal ~/arpent-vault
```

The checked-in `architecture_template/` is also a complete zero-install minimal
vault template. Copy it as a directory, fill `me.md`, and follow its `.agent`
entry point. Minimal mode keeps ordinary capture, reading, routing, archival,
and continuity usable as files; coordinated database and multi-file operations
require promotion with `arpent mode full`.

An optional initial structure can declare areas, resources, and projects:

```json
{
  "areas": ["Work"],
  "resources": ["Design references"],
  "projects": [
    {"name": "Website refresh", "area": "work"}
  ]
}
```

```bash
arpent init ~/arpent-vault --structure structure.json
```

## Everyday Use

### Notes

```bash
arpent note new "Actionability gradient" --type concept \
  --resource concepts --body "A useful idea..." --json

arpent note new "Actionability gradient" --type concept \
  --resource concepts --body "A useful idea..." --dry-run --json

arpent note new "Actionability gradient" --type concept \
  --resource concepts --body "A useful idea..." \
  --plan-hash <plan_sha256> --json
```

The CLI normalizes the stored title and filename to lowercase ASCII
`snake_case`. Use `note edit` to change content or routing together, `note
route` to replace all routing fields, and `note status` to change lifecycle
state.

Every ordinary note keeps the complete 27-field canonical frontmatter schema.
Optional values remain explicit as `null`, `[]`, or `false`; they are not
removed from the note. Mutations validate field types, IDs, timestamps, enums,
relations, and user-only ratings. An unsupported key is rejected rather than
silently discarded, while existing user values in `appreciated` and
`importance` are preserved. Archive operations may add the paired lifecycle
extensions `archived_at` and `archived_from`. See
[`references/contracts/frontmatter.md`](references/contracts/frontmatter.md)
for the compact contract.

Create global current guidance with:

```bash
arpent note new "Rotate credentials without downtime" --type howto \
  --source derived --body "..." --json
```

The guide routes to `03_resources/how-tos/`, defaults to `ongoing`, and is
revised in place after an explicit review. Use a MOC for broader subject
navigation and linked notes for detailed reasoning and superseded guidance.

### Fleeting Capture

```bash
arpent note new "Check the deployment assumption" --type fleeting --json
```

This appends one `## HH:MM` block to
`00_inbox/fleeting/dd-mm-yyyy.md`. Entries are append-only capture fragments,
not individual structured notes or todo items.

### Todo

Anything that must be executed, tracked, completed, deferred, or blocked is a
todo:

```bash
arpent todo add "Review the migration plan" --json
arpent todo list
arpent todo done <todo-id>
arpent todo archive <todo-id>
```

Todo is full-mode coordinated state. In minimal mode, a task can only be
captured as a clearly labeled **untracked** inbox note.

### Inbox And Ingestion

`triage` inventories the inbox; it does not move anything itself.

```bash
arpent triage --json-page --all
arpent note ingest 00_inbox/interview.txt --title "Interview notes" \
  --dry-run --json
arpent note ingest 00_inbox/interview.txt --title "Interview notes" \
  --source-hash <source_sha256>
```

Text and malformed frontmatter are preserved as body content. Binary files stay
byte-for-byte intact and use a separate Markdown companion when ingested as an
attachment.

### Search And Context

```bash
arpent search "routing decision"
arpent note find "routing decision"
arpent index
arpent context pending --json-page --all
arpent context show 01_projects/my-project --level l0
```

`index` deterministically rebuilds inventory, sidecar, and context derivatives.
When SQLite exposes FTS5 it also creates `search.db`; otherwise search uses a
live text fallback and no `search.db` is published. Indexing never invokes AI.
Optional L1 summaries are created only by an explicit agent workflow and remain
tied to the exact semantic source hash.

### Import

External trees use a reviewed, resumable, copy-only pipeline:

```bash
arpent import scan ~/legacy --output ~/migration/legacy-plan.json
arpent import suggest ~/migration/legacy-plan.json
arpent import review ~/migration/legacy-plan.json
arpent import validate ~/migration/legacy-plan.json --sources
arpent import apply ~/migration/legacy-plan.json --dry-run --json
arpent import apply ~/migration/legacy-plan.json \
  --plan-hash <plan_sha256> --yes --json
arpent import status ~/migration/legacy-plan.json
```

The external source is never modified. Application is atomic per item, so a
batch can partially succeed and then resume.

### Maintenance

```bash
arpent status
arpent efforts
arpent health --json
arpent usage report --json

arpent sweep ephemeral --dry-run
arpent sweep ephemeral
arpent sweep status --json

arpent backup
arpent backup verify <snapshot>
arpent backup restore <snapshot> --to <new-directory>

arpent tools list
arpent tools show todo
arpent cron run --tick --dry-run
```

The tools registry is inspectable but not an installer. Sweep processes only
ephemeral entries declared with `status: installed`. Cron is an explicit tick,
not a daemon; executing a due local command also requires
`--allow-local-code`.

## Data Authority

Authority is specific to the kind of state:

- Markdown is canonical for documents, project/area context, readable todo
  records, and user-facing history.
- Original attachments are canonical source material.
- `todo.db` is authoritative for the todo module's coordinated structured
  state. Its Markdown records are durable readable counterparts and must remain
  consistent with it.
- The installed CLI parser is authoritative for current command syntax.
- The packaged operation contract is authoritative for enums and default
  routing; a vault may contain only the supported routing overlay.
- Generated inventory, search, sidecar, and context indexes are derivatives.

Do not manually edit tool-owned todo records or generated indexes.

## Routing And Resources

Ordinary home precedence is `project > resource > area > inbox`. `project` and
`resource` are mutually exclusive; `area` is optional contextual metadata and
may accompany either.

The routing contract reserves these resource homes:

`concepts`, `maps-of-content`, `how-tos`, `integrations`, `templates`, `agent_wiki`,
`books`, `articles`, `portraits`, and `productions`.

They are valid declared destinations even if a fresh or customized vault has
not materialized every directory. The first write to a reserved home may create
that directory. This is not arbitrary folder invention: any other missing
resource, project, or area is unresolved and routes to `00_inbox/unsure/` with a
reason until it is deliberately created or corrected.

`type: map` navigates a broad subject. `type: howto` stores one explicitly
reviewed current answer to a practical problem and always routes to
`03_resources/how-tos/`; its detailed reasoning and superseded guidance remain
in linked notes.

## Status, Location, And Archive

Lifecycle status and filesystem location are deliberately decoupled. A status
describes state; it does not assert an absolute path. For example, `inbox`
usually accompanies an untriaged capture but is not a path alias, and changing
an ordinary note to `archived` with `note status` does not move it.

Use explicit lifecycle operations for moves:

```bash
arpent archive <note-id>
arpent todo archive <todo-id>
arpent note dissolve <linear-id> --yes
```

`archived` is the lifecycle status. `archived_at` and `archived_from` are
archive-event metadata recording when and from where an explicit archival move
occurred. They are lifecycle-only schema extensions, never statuses.

No project-folder closure command is delivered. `session end` closes a working
session into context; it does not close or archive a project.

## Todo, Reminder, And Memory

- An action to execute or follow is a todo, including “remember to ...”.
- A todo records execution state; it does not by itself deliver a notification.
- Context worth recalling without execution state may go to an external
  provider's opt-in buffer role.
- Stable traits or discrete facts may go to an explicitly enabled external
  memory provider.
- Durable readable material belongs in a note; current work belongs in
  `_context.md`; user-authored orientation belongs in `me.md`.

Arpent does not ship a memory provider. If the current host has no explicitly
enabled provider, provider-bound information was **not persisted**. Do not claim
otherwise and do not invent fallback persistence.

## Safety Model

Arpent prevents silent loss rather than forbidding all mutation:

- Existing destinations are not silently replaced or destroyed.
- Explicit edits use checked atomic publication and may replace the source as
  the requested transaction commits.
- Moves validate the current source, destination collision, vault confinement,
  and stale plans.
- Ambiguous routing remains visible under `00_inbox/unsure/` with a reason.
- Binary source bytes are preserved.
- Batch operations report partial outcomes instead of claiming all-or-nothing
  success.

Local snapshots are unencrypted and are not remote backup, sync, Git history,
or external-memory backup. Use a separate storage policy for those concerns.

## Documentation Map

- [`SKILL.md`](SKILL.md): compact operational instructions for an agent.
- [`references/workflows/`](references/workflows/): small operation workflows.
- [`references/contracts/`](references/contracts/): compact metadata, routing,
  and provenance contracts.
- [`references/architecture.md`](references/architecture.md): explanatory vault
  architecture.
- [`references/lifecycle.md`](references/lifecycle.md): explanatory lifecycle
  and archive behavior.
- [`references/tools-and-cron.md`](references/tools-and-cron.md): delivered tool
  registry, cron, sweep, and backup behavior.
- [`references/appendices/complete-reference-index.md`](references/appendices/complete-reference-index.md): long-form and historical reference map.

When documentation and `arpent <command> --help` disagree about command syntax,
the installed executable is current.

# Tools and cron

This document describes the tool registry, cron registry, and commands that
exist in the current CLI. Future sub-tools and adapters are parked in
`developement/roadmap/future-tools-design.md`.

## Rule

The skill-facing documentation describes what is invocable now.

Designs for later phases belong in `developement/`, not in the operational
surface loaded by agents.

## Current tool registry

Vault path: `06_indexes/tools.yaml`.

The registry is read-only. The CLI can list and show registered tools, but it
cannot install, uninstall, enable, or disable tools yet.

All tool know-how is centralized in `06_indexes/`: skills, CLI contracts,
schemas, migrations, documentation, registry entries, and databases.
`05_tools/` is runtime-only and is created from an installed tool's
`writes_to`; it never contains `SKILL.md` or maintenance instructions. The full
contract is installed at `06_indexes/docs/architecture/tools.md`.

Implemented commands:

```bash
arpent tools list
arpent tools list --category <category>
arpent tools list --status <status>
arpent tools show <name>
```

Current seed entries:

- `context_summary` - installed, explicit-only AI generation of cached L1 summaries
- `todo` - installed daily-flow tool backed by `todo.db` and Markdown lifecycle records
- `reader` - transversal, planned, writes to `05_tools/reader/`
- `review` - transversal, planned, writes to `05_tools/review/`
- `z_backup` - transversal, planned, writes to `06_indexes/backup/`

`planned` entries describe proposed boundaries only. Their runtime directories
are not created until explicit installation changes the tool to `installed`.

`fleeting`, `reader`, `calendar`, `sport`, `journal`, and `crm` are not installed
commands. Their top-level CLI stubs exist only to fail clearly with "not installed".

## Todo

The installed todo tool stores structured properties in
`06_indexes/databases/todo.db` and readable lifecycle records under
`02_areas/area__perso__todo__active/<status>/`. The database is initialized
lazily from the schema packaged with the installed CLI. The copy at
`06_indexes/schemas/todo_schema.sql` is a reviewable seed, not runtime authority.

The runtime accepts only the packaged schema version 2. Existing databases with
another or unversioned schema are rejected rather than migrated.

```bash
arpent todo add "<content>" [--priority <key>] [--status active|waiting|done]
  [--due dd-mm-yyyy] [--do dd-mm-yyyy] [--duration <key>]
  [--project <id>] [--depends-on <id>]
  [--optional] [--frequency <key>] [--list-order <key>] [--assignee <id>]
arpent todo list [--status active|waiting|done] [--include-archived] [--json]
arpent todo show <id> [--json]
arpent todo edit <id> [field options and matching --clear-* flags]
arpent todo done <id>
arpent todo defer <id> --to dd-mm-yyyy
arpent todo block <id> --on <object-id>
arpent todo archive <id>
```

`archive` requires `status: done`, moves the Markdown record into the current
quarter under `04_archives/<quarter>/todo/done/`, and retains the SQLite row.
Generic `note edit/status/route` and top-level `archive` reject `todo-*` IDs so
the two representations cannot drift.

## Optional context-summary module

`arpent index` inventories folders and files and refreshes deterministic L0/L2
context. It never invokes an AI model. The transversal module at
`06_indexes/global_skills/context_summary.skill.md` generates L1 summaries only after an
explicit user request.

Implemented commands:

```bash
arpent context pending [--path <relative-path>] [--kind folder|note|text] [--json]
arpent context show <relative-path> --level l0|l1|l2
arpent context set <relative-path> --source-hash <hash> --summary "..." --provider <id>
arpent context set <relative-path> --source-hash <hash> --stdin --provider <id>
```

Every L1 stores the semantic source hash it summarizes. A subsequent
`arpent index` keeps it `fresh` when the hash matches and marks it `stale` when
the content changes. The volatile `created` and `modified` timestamps are excluded from the semantic hash.

## Current cron registry

Vault path: `06_indexes/cron.json`.

Arpent does not run a daemon. The only cron execution path implemented in
Phase 1 is an explicit tick:

```bash
arpent cron run --tick --dry-run
arpent cron run --tick --allow-local-code
```

The runner reads enabled jobs from `06_indexes/cron.json`, checks whether each
job is due for the current minute, then executes the configured command.

`command` is trusted local code, not a declarative Arpent operation. It runs
with the current user's permissions and inherited environment. Every enabled
job must therefore declare `"trust": "local-code"`, and every non-dry tick must
also receive the out-of-vault `--allow-local-code` CLI confirmation; never
enable a job from an untrusted or merely synced vault. `timeout_seconds` must remain
between 1 and 86400 and defaults to 300. Arpent serializes ticks so the same due
minute cannot be dispatched concurrently. A durable `last_started` claim is
written before launch, so a crash cannot replay the same job in the same
minute. Internal `arpent` commands are
resolved from the installed package rather than from Python files in the
vault. Do not place secrets in command arguments or notification text.
Execution is currently disabled on Windows because Arpent cannot yet guarantee
termination of the full descendant process tree there; dry runs remain
available.

The Phase 1 seed contains one disabled job:

```json
{
  "id": "ephemeral-sweep",
  "enabled": false,
  "schedule": "0 6 * * *",
  "command": "arpent sweep ephemeral",
  "trust": "local-code",
  "timeout_seconds": 300,
  "notify_channel": null,
  "tags": ["lifecycle", "ephemeral"],
  "last_run": null,
  "description": "Apply lifecycle rules from tools.yaml."
}
```

## Notification channels

Implemented now:

- `stdout` - print notification text
- `file` - append to `06_indexes/logs/cron.log`
- `null` / omitted - no notification

Not implemented in Phase 1: Telegram, Signal, Mattermost, macOS notifications,
or any other adapter.

## Current maintenance commands

Implemented:

```bash
arpent backup
arpent backup --destination /path/to/backup-parent
arpent backup verify <snapshot>
arpent backup restore <snapshot> --to <new-directory>
arpent sweep ephemeral
arpent sweep ephemeral --dry-run
arpent sweep status [--json]
arpent health [--json]
arpent usage report [--since <ISO-date-or-timestamp>] [--json]
```

`arpent backup` snapshots all durable vault files and consistent copies of
SQLite databases into `06_indexes/backup/<timestamp-id>/`, or into the parent
given by `--destination`. It preserves symlinks without following their targets,
records exclusions and SHA-256 checksums in a versioned manifest, verifies the
staging snapshot, and publishes it atomically. Rebuildable indexes such as
`search.db`, transaction journals, locks, SQLite sidecars, `.git/`, dependency
directories, and nested backups are not copied.

`backup verify` rejects missing, additional, altered, unsafe, or corrupt payloads.
`backup restore` accepts only a nonexistent target, restores through staging,
verifies the result, and never merges with an existing vault. Local snapshots
are unencrypted and do not include delegated memory, Git history, or external
files.

`arpent sweep ephemeral` reads every installed tool marked `ephemeral: true`,
scans its `writes_to` roots, and applies the first due lifecycle rule to each
frontmatter note. `active`, `stable`, `ongoing`, linear notes, maps, and
`_context.md` are always protected. Automatic transitions may only target
`stale`; automatic archival accepts only `done` or `stale` content.

Lifecycle rules use this shape:

```yaml
lifecycle:
  - from: inbox
    after_days: 14
    to: stale
  - from: stale
    after_days: 7
    action: archive
```

Supported actions are `archive`, `archive-with-trace`, and
`delete-after-review`. Trace archival records the complete note in the tool's
configured SQLite database before moving it. `delete-after-review` only logs a
proposal; it never deletes automatically. Every run appends JSONL events and a
summary to `06_indexes/logs/sweep.log`.

`arpent health` computes its metrics directly from current files: output is
`source: manual|derived`, input is `source: captured|imported`, and the command
also reports integrations, maps, stale notes, old maturing notes, and unresolved
items in `00_inbox/unsure/`.

`arpent usage report` reads the append-only local
`06_indexes/logs/usage.log`, accepts historical unversioned v1 records, and
reports v2 command success/failure, active days, duration percentiles,
allowlisted outcomes/state changes, session closes, and current triage age.
Malformed lines are skipped and counted. Events exclude content, titles,
summaries, queries, paths, project/area names, URLs, errors, and command
payloads. Documentary resume activity and context quality are unavailable
metrics; record them qualitatively in `06_indexes/logs/usage-journal.md`.
Ordinary logs are included by the current logical backup policy, and the vault
itself may live in a synchronized folder.

## Contract file

The CLI operation and routing contract is `scripts/operations.yaml` in the
codebase and `06_indexes/cli/operations.yaml` inside initialized vaults.

Routing enums and mechanisable routing rules are loaded from this contract by
`scripts/routing.py`. Narrative explanations live in `routing.md`; the routing
tables do not.

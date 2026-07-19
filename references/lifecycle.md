# Lifecycle

This document explains the lifecycle implemented by the current release.
Operational syntax comes from `SKILL.md`, the compact workflows, and
`arpent <command> --help`. Future reader, calendar, journal, sport, CRM, and
review lifecycle designs are planned/in construction and are not invocable;
they are outside the current operational contract.

## Statuses

```text
inbox      maturing    active    stable    ongoing    standby
waiting    to-start    done      stale     archived
```

| Status | Meaning |
|---|---|
| `inbox` | Captured but not yet triaged. |
| `maturing` | Routed content still being developed. |
| `active` | Currently used or actionable content. |
| `stable` | Finalized reusable knowledge. |
| `ongoing` | Permanent, evolving reference or responsibility. |
| `standby` | Intentionally set aside for possible return. |
| `waiting` | Blocked on an external dependency. |
| `to-start` | Planned to begin, not yet active. |
| `done` | Accomplished terminal work. |
| `stale` | No longer current and eligible for a declared lifecycle rule. |
| `archived` | Retained as archive material. |

## Status Is Not Location

Status and filesystem location are deliberately decoupled. Status describes
lifecycle state; routing fields, type, provenance, and explicit lifecycle
operations determine location.

- `inbox` is not an alias for an absolute path. New untriaged captures commonly
  have both `status: inbox` and an inbox route, but neither fact defines the
  other.
- `maturing` does not mean a drafts directory.
- `arpent note status <id> archived` changes an ordinary note's status but does
  not perform quarterly archival.
- An archived linear note has an explicit status/type route because dissolution
  is a dedicated lifecycle operation.

Change an ordinary note's status with:

```bash
arpent note status <id> <new-status>
```

Most transitions are user-requested. This release does not run a general
automatic maturity engine or weekly-review workflow.

## Delivered Event Transitions

The current coordinated operations perform these bounded transitions:

| Event | Result |
|---|---|
| Todo completed with `todo done` | Todo becomes `done`. |
| Todo archived with `todo archive` | A `done` todo remains represented in `todo.db`; its Markdown record moves to the current quarterly archive. |
| Eligible linear note dissolved with `note dissolve` | Source becomes `archived` and moves to `04_archives/linear_notes/`. |
| Ordinary note archived with top-level `archive` | Note becomes `archived` and moves to the current quarterly archive. |
| Installed ephemeral sweep rule becomes due | The first matching declared transition or archive action is applied. |

There is no delivered project-close transition. `session end` closes a working
session into `_context.md`; it does not set project notes to `archived`, move a
project folder, or infer project completion.

## Knowledge Maturation

A common documentary arc is:

```text
inbox -> maturing -> stable
                  -> active -> standby
                  -> archived (explicitly)
```

This is guidance, not a mandatory state machine. A finalized concept may become
`stable`; an actionable draft may become `active`; a permanent evolving map or
how-to is normally `ongoing`. The user decides when knowledge is stable. `health` can
surface old maturing notes, but does not promote or archive them.

## Linear Notes

A `linear` note is sequential working material that may be decomposed into
independent typed children. Use a final semantic type directly when the material
already has one identity.

Extract a child:

```bash
arpent note extract <linear-id> --type concept \
  --title "Actionability gradient" --resource concepts --body "..."
```

Extraction creates the child with `parent: <linear-id>`, appends its ID to the
source's `extracted_to`, and adds a source-body link. Every child routes from its
own metadata.

After at least one child exists and both directions of lineage validate:

```bash
arpent note dissolve <linear-id> --yes
```

Dissolution is explicit. It sets `status: archived`, adds archive-event
metadata, and moves the source to `04_archives/linear_notes/`. A dissolved
source is immutable through ordinary note edit, route, and status commands.

## Archive Events

`archived` is the lifecycle status. The following keys are lifecycle-only
extensions added by an explicit archive event:

```yaml
archived_at: 19-07-2026-16-00
archived_from: 03_resources/concepts/actionability_gradient.md
```

They mean “when this archival move happened” and “where the item moved from.”
They are metadata, not additional statuses, and they are not part of ordinary
capture frontmatter.

Archive operations are record-specific:

```bash
arpent archive <ordinary-note-id>
arpent todo archive <done-todo-id>
arpent note dissolve <linear-id> --yes
```

A project folder or arbitrary file has no automatic archive command in this
release.

## Ephemeral Sweep

`arpent sweep ephemeral` reads `06_indexes/tools.yaml` and considers only tools
that are both `ephemeral: true` and `status: installed`. A planned tool is never
processed. The release seed therefore operates the installed todo lifecycle;
planned reader rules are design only and cannot be invoked today.

```bash
arpent sweep ephemeral --dry-run
arpent sweep ephemeral
arpent sweep status --json
```

A run applies at most the first due rule per note. Protected content includes
`active`, `stable`, and `ongoing` notes, maps, how-tos, linear notes, and `_context.md`.
Automatic archival accepts only `done` or `stale` content.

A how-to is revised in place only after an explicit review. Its ID remains
stable, the current body replaces superseded guidance, and useful removed
material is first retained in linked notes. `modified` alone never attests that
the guidance was reviewed.

Supported rule forms include a status transition:

```yaml
- from: inbox
  after_days: 14
  to: stale
```

and an archive action:

```yaml
- from: done
  after_days: 30
  action: archive-with-trace
```

`archive` moves retained Markdown. `archive-with-trace` first records the
complete note in the tool's configured database. `delete-after-review` records
a proposal only; it does not delete content automatically. Every run records a
summary in `06_indexes/logs/sweep.log`.

The seeded cron job for sweep is disabled. Arpent has no daemon; an external
scheduler must invoke `arpent cron run --tick`, and actual local-code execution
requires `--allow-local-code`.

## Session Close And Resume

Resume is documentary in both modes:

1. Read `me.md`.
2. Read the target project or area `_context.md`.
3. Read only the notes or sources required for the current work.

There is no resume command. Optional `MEMORY.md` is absent by default and is not
part of normal resume.

Close full-mode work into a target context:

```bash
arpent session end --project <slug> --summary "..." \
  --decision "..." --next-step "..."
```

or:

```bash
arpent session end --area <slug> --summary "..."
```

The command preserves existing body sections, updates `modified`, and appends a
timestamped session block. Minimal mode performs and verifies the equivalent
direct-file update. Closing a session is not project closure.

An explicit full-mode `--memory-log` flag additionally creates or updates the
optional cross-project `06_indexes/memory/MEMORY.md` log. It is absent by
default, is not read during normal resume, and each later read requires a
separate explicit request.

An explicitly enabled external memory provider remains a separate host
capability. Actionable reminders belong in todo. Non-actionable recall context
may use a provider buffer only when that provider is enabled; otherwise it was
not persisted and no fallback store should be claimed.

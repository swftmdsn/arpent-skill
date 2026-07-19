# Import and migration

Arpent imports an arbitrary external filesystem tree through a reviewed,
deterministic pipeline. The source is scanned read-only and remains unchanged;
the target vault receives copies only after folder roles and destinations have
been confirmed.

## Workflow

```bash
arpent import scan ~/Documents/legacy --output ~/migration/legacy-plan.json
arpent import suggest ~/migration/legacy-plan.json
arpent import review ~/migration/legacy-plan.json
arpent import validate ~/migration/legacy-plan.json --sources
arpent import summary ~/migration/legacy-plan.json
arpent import apply ~/migration/legacy-plan.json --dry-run --json
arpent import apply ~/migration/legacy-plan.json --plan-hash <execution_sha256>
arpent import status ~/migration/legacy-plan.json
```

`scan`, `suggest`, `review`, and `summary` can run outside a vault. `apply` and
`status` operate on the vault discovered from the current directory or
`ARPENT_VAULT_ROOT`. `validate` additionally checks destination compatibility
when run inside a vault.

## Files produced by scan

The plan path must be outside the scanned source tree. Scan writes:

```text
legacy-plan.json
legacy-plan.<import-id>.inventory.jsonl
```

The JSON plan contains folder statistics, deterministic suggestions, decisions,
source metadata, and the inventory SHA-256. The JSONL inventory has one compact
record per regular file, including relative path, full-file kind, size,
modification time, and content SHA-256. Symlinks, Windows reparse-point
junctions, special files, common dependency trees, and OS cruft are skipped
rather than followed. The output parent must already exist; `--force` publishes
a new unique inventory before replacing an existing plan. The prior inventory
remains beside the plan until it is removed manually.

## Folder roles

| Role | Meaning |
|---|---|
| `project` | Create or reuse one canonical project and import descendants there |
| `area` | Create or reuse an Area folder and import descendants there |
| `resource` | Create or reuse a Resource folder and import descendants there |
| `group` | Organizational container; review its child folders separately |
| `inbox` | Import descendants without a final PARA destination |
| `ignore` | Deliberately leave descendants outside the import |

Decisions are inherited. Once a folder is mapped to a Project, Area, Resource,
Inbox, or Ignore, descendants do not require individual folder decisions. A
`group` delegates classification to its children; files directly inside a group
use the plan's `root_files` default, which is `inbox`. Files directly at the
source root use the same fixed default and are not asked about individually.

## Deterministic suggestions

Suggestions use inspectable filesystem signals rather than an opaque provider:

- recognized organizational containers such as Projects, Areas, or Resources;
- the parent container role;
- folder-name signals associated with finite work, ongoing responsibility, or reference material;
- working filenames such as roadmap, milestones, deliverables, or todo;
- binary/reference density;
- whether a folder is a leaf or contains lower-level groups.

Every suggestion records a confidence and reason. It never applies itself.
Interactive review asks only about uncovered folder roots and shows file counts,
kind counts, confidence, and reasons before requesting a role. For automation:

```bash
arpent import review legacy-plan.json \
  --accept-suggestions --minimum-confidence 0.8
```

Lower-confidence folders remain unresolved and make validation fail. The plan is
ordinary JSON and can also be reviewed or edited explicitly.

## Application semantics

Application is sequential and atomic per imported item, not atomic for the whole
batch. Before applying, Arpent validates the plan, inventory checksum, review
state, destination declarations, and source/vault separation. Actual application
rehashes each source before copying it.

Declared Areas, Resources, and projects are created before item processing and
reported separately, even if all later items fail. Text and Markdown become complete Arpent notes with the source content preserved
verbatim. Existing source frontmatter is not trusted or merged automatically; it
is preserved visibly in the imported body. Binary and non-UTF-8 files with a
Project, Area, or Resource destination are copied to that home's `attachments/`
and receive a companion reference note. Inbox binaries remain in the owned
`00_inbox/captures/.arpent-import-<import-id>/` staging tree with a companion
inbox note. Imported notes use `source: imported`, `author: imported`, and an
import identifier for provenance.

Filename collisions and different source paths that normalize to one destination
are reported and never overwritten. Nested source paths qualify generated note
titles to reduce flattening collisions; arbitrary source folders are not recreated
as destination folders. Project notes follow the vault's current routing contract
rather than a hard-coded folder assumption.

## Confirmation and unattended operation

Interactive `review` asks for each uncovered folder role, destination name, and
optional contextual Area for projects. `apply` follows the vault confirmation
policy. Under `always` or `explicit-intent`, import is high-impact and requires
the reviewed apply boundary. Under `never`, it proceeds without a second
approval. A reviewed non-interactive application uses:

```bash
arpent import apply legacy-plan.json --yes
```

For a plan/apply review bound to both folder decisions and the current routing
contract, carry `plan_sha256` from the JSON dry run into `--plan-hash`. A routing
or decision change then forces a fresh preview. This hash is not a current-source
snapshot; use `validate --sources` immediately before apply to prehash the whole
tree. Apply also rechecks each source immediately before copying it.

`--dry-run` does not create destination folders, notes, attachments, state, or
import lock files. With `--json`, it includes per-item predicted destinations and
collisions; human output remains aggregate to avoid retaining a very large
preview in memory.

## Resume and state

Completed state is stored under:

```text
06_indexes/imports/<import-id>/state.jsonl
06_indexes/imports/<import-id>/report.json
```

This generated state is excluded from normal indexing and Git. Re-running apply
verifies recorded note, attachment, and retained-inbox hashes before skipping
applied items, skips ignored items, retries failures, and recognizes outputs
committed immediately before an interrupted state append. `status` verifies
recorded outputs but does not rehash the external source or inventory. A torn
final state line is repaired; malformed committed lines remain an error. Changing
folder decisions or routing after application starts is refused because durable
state is bound to the execution hash. Create a fresh scan plan for a different
migration strategy.

## Safety boundaries

- Source and vault must not contain one another.
- Plan and inventory must remain outside the source tree.
- Source symlinks and Windows junctions are not followed.
- The source must remain stable during scan and apply; hostile concurrent path replacement is outside the portable stdlib threat model.
- Source files are copied, never removed.
- Source hashes are checked again before each item.
- Existing destinations are never overwritten.
- Partial failures are reported honestly and return a nonzero CLI status.
- No external AI provider or format-specific connector is used.

The import pipeline is available in full and minimal vaults. It does not rewrite
links between imported documents, preserve arbitrary source folder trees as vault
folders, infer subjective frontmatter, or provide Obsidian/Notion/application
connectors in this phase.

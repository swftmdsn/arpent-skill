# Routing

Routing is the deterministic mapping from frontmatter to a filesystem path.
The mechanisable rules live in `scripts/operations.yaml`, and initialized
vaults receive the same contract at `06_indexes/cli/operations.yaml`.

`scripts/routing.py` interprets that contract. This document explains the
intent and the ambiguity policy; it does not duplicate routing tables.

## Core contract

A routed vault note uses two mutually exclusive homes and one contextual dimension:

- `project`
- `area`
- `resource`

Routing uses this precedence:

- `project` -> `01_projects/<project>/`; ordinary content goes in `notes/`
- otherwise `resource` -> `03_resources/<resource>/`
- otherwise `area` -> `02_areas/<area>/`
- none -> `00_inbox/`

`project` and `resource` must never both be set. `area` may accompany either:

- `project + area`: project-local note, physically in the project
- `resource + area`: global resource associated with an area, physically in resources
- `area` only: area-local note

Area folders may use direct lowercase slugs or the structured template form,
such as `area__perso__sport__active`. In both cases, frontmatter uses the short
semantic slug, for example `area: sport`.

## Global knowledge versus project material

A concept belongs in `03_resources/concepts/` when it is understandable and reusable outside the project where it emerged. Projects reference it with ordinary Obsidian wikilinks and backlinks; the concept does not set `project`.

Material belongs in `01_projects/<project>/notes/` when it exists only to execute or document that project. It sets `project + area` and leaves `resource: null`. This keeps global resources Zettelkasten-like without hiding project-specific material among them.

## Ambiguity policy

The router never chooses between plausible destinations.

If no routing field is set, the note goes to the inbox route declared in
`operations.yaml`. Captured material can use the captured inbox route.

If `project` and `resource` are both set, the note goes to `00_inbox/unsure/` and the CLI writes a reason file next to it. `area` combined with either is valid and must not be treated as ambiguous.

If a routing slug points to a missing folder, the note goes to `00_inbox/unsure/`
with a reason. The user decides whether to create the missing folder or correct
the slug. An authorized project is created deliberately with `arpent project
create <name>` in either vault mode; routing never creates one implicitly. Area
creation remains manual.

## Type and status refinements

Type-specific and status-specific refinements are data, not prose. Examples:

- append-only fleeting capture files
- map and integration destinations
- type-specific subfolders such as meetings or sessions
- archived linear notes

To change those rules, edit `scripts/operations.yaml` and update tests. Do not
add a second table here.

## Triage behavior

`arpent triage [--json]` inventories every non-fleeting inbox item without
moving it. JSON output classifies structured notes, raw text, malformed
frontmatter, and binary files independently and includes safe previews, age,
source hash, reason, and available `edit`, `ingest`, or `leave` actions. It does
not silently repair ambiguous frontmatter or act as a second routing engine.

An agent builds one complete plan and asks once. Preview structured mutations
with `arpent note edit <id> ... --dry-run --json`; preview raw-file conversion
with `arpent note ingest <inbox-path> --title <title> ... --dry-run --json`.
Carry the structured edit's `plan_sha256` into `--plan-hash` when applying.
Apply each item as an atomic transaction, re-run triage, and report partial
batch outcomes honestly.

Acceptable outcomes:

- route to a project, area, or global resource
- losslessly ingest raw text, malformed frontmatter, or a binary attachment
- leave in inbox
- move to `00_inbox/unsure/` with a reason
- archive instead of deleting

For binary/non-text ingestion, frontmatter belongs only to a separate Markdown
companion reference note. The binary remains byte-for-byte untouched and cannot
contain YAML. `note ingest --attachment` transactionally moves it to the chosen
home's `attachments/`, with the companion note's `link` pointing there. Without
a final home, the original stays in inbox and the companion remains untriaged.

## Invariant

Routing quality is verified by behavior:

- `scripts/routing.py` must read its mechanisable rules from `operations.yaml`.
- Tests must cover the contract cases that matter.
- This document may explain the reasoning, but it must not become a competing
  source of routing truth.

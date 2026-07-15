# Routing

Routing is a pure function of frontmatter.

- `project` set -> `01_projects/<project>/`
- `area` set -> `02_areas/<area>/`
- `resource` set -> `03_resources/<resource>/`
- all three null -> `00_inbox/`
- `project + area` -> the project home; `area` remains contextual metadata
- `resource + area` -> the resource home; `area` remains contextual metadata
- `project + resource` -> `00_inbox/unsure/` with a reason

Special types may override subfolders:

- `fleeting` -> `00_inbox/fleeting/dd-mm-yyyy.md`
- `map` -> `03_resources/maps-of-content/`
- `integration` -> `03_resources/integrations/`
- `linear` source notes archive to `04_archives/linear_notes/` after dissolution

Create an authorized project deliberately with `arpent project create <name>`;
routing never invents one. `arpent triage --json` inventories structured, text,
malformed, and binary inbox items without moving them. Preview a structured
disposition with `arpent note edit --dry-run --json` and carry its
`plan_sha256` into `--plan-hash`, or preview a raw disposition with
`arpent note ingest --dry-run --json`, confirm one complete plan, apply each
item transaction, and report partial batch outcomes honestly.

A binary/non-text source remains byte-for-byte untouched and cannot contain
YAML. `note ingest --attachment` moves it transactionally to the selected home's
`attachments/` and creates a separate Markdown companion reference note with
complete frontmatter and a `link` to the attachment. Without a final home, the
original remains in inbox and the companion is untriaged.

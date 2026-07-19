# Routing

Routing is a pure function of frontmatter.

Lifecycle status and physical location are decoupled. Status alone does not
assert a path or perform a move.

- `project` set -> `01_projects/<project>/notes/`; use `drafts/` for drafts,
  `meetings/` for meetings, and `sessions/` for logs
- `area` set -> the exact area folder, or one unambiguous
  `area__*__<slug>__*`; meetings/logs use configured subfolders
- `resource` set -> `03_resources/<resource>/`
- all three null -> `00_inbox/`, except captured sources go to
  `00_inbox/captures/`
- `project + area` -> the project home; `area` remains contextual metadata
- `resource + area` -> the resource home; `area` remains contextual metadata
- `project + resource` -> `00_inbox/unsure/` with a reason

Special types may override subfolders:

- `fleeting` -> `00_inbox/fleeting/dd-mm-yyyy.md`
- `map` -> `03_resources/maps-of-content/`
- `howto` -> `03_resources/how-tos/`
- `integration` -> `03_resources/integrations/`
- `artefact` -> `05_tools/artefacts/`
- an agent-authored draft without a project -> `03_resources/agent_wiki/drafts/`
- `linear` source notes archive to `04_archives/linear_notes/` after dissolution

Routing never invents a missing home. Full creates a deliberate project with
`arpent project create <name>`. Minimal follows the direct project procedure in
the local Arpent skill.

Reserved resource homes (`concepts`, `maps-of-content`, `how-tos`, `integrations`,
`templates`, `agent_wiki`, `books`, `articles`, `portraits`, `productions`) are
declared by the contract and may materialize on first write. Any other missing
resource, project, or area remains unresolved and routes to `unsure/`.

Triage and transactional ingestion are full-only CLI operations. In minimal,
inventory inbox files directly, preserve raw sources, and do not claim an atomic
multi-file disposition. In full, `arpent triage --json` inventories structured,
text, malformed, and binary items; use reviewed `note edit` or `note ingest`
plans and report partial batch outcomes honestly.

A binary/non-text source remains byte-for-byte untouched and cannot contain
YAML. In full, `note ingest --attachment` moves it transactionally to the
selected home's `attachments/` and creates a separate Markdown companion
reference note with complete frontmatter and a `link` to the attachment. Without
a final home, the original remains in inbox and the companion is untriaged.

Minimal archive preserves one non-linear note, sets `status: archived`, updates
`modified`, adds lifecycle-event metadata `archived_at` and `archived_from`, and
moves without silently replacing a destination to
`04_archives/<YYYY_qN>/<title>.md`. `archived` is the status; the two extension
fields record when and from where the move happened. Inspect source and
destination immediately before the move and verify afterward. Extraction and
linear dissolution remain full-only because they coordinate multiple notes.

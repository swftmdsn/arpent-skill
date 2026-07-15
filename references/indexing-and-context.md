# Indexing and Context

The operational contract for whole-vault inventory and context-efficient
loading.

## Core rule

`arpent index` is deterministic and local. It inventories the vault, computes
hashes, rebuilds search data, and refreshes L0/L2 context. It never invokes an
AI model.

AI-generated L1 summaries belong to the explicit `context_summary` module. The
module runs only after a user request and only for entries reported as missing
or stale.

## Generated outputs

| Output | Content |
|---|---|
| `06_indexes/index.json` | Every indexed folder and file, including non-note files, counts, types, sizes, and hashes |
| `06_indexes/sidecar.json` | Frontmatter metadata for recognized notes |
| `06_indexes/databases/search.db` | FTS5 index of note titles, descriptions, tags, and bodies |
| `06_indexes/context_index.json` | L0/L1/L2 context cache keyed by relative path |

These files are derivatives. Markdown and original files remain the source of
truth.

## Inventory scope

The inventory includes the vault root, bucket folders, nested folders, notes,
plain-text files, binary files, attachments, symlinks, and infrastructure files.
It does not follow symlinks.

Generated or sensitive runtime zones are excluded:

- `.git/`, `.venv/`, `__pycache__/`, and `node_modules/`
- `06_indexes/backup/`, `databases/`, `logs/`, and `secrets/`
- generated `index.json`, `sidecar.json`, and `context_index.json`
- operating-system noise such as `.DS_Store`

## Hashes

Each file has an exact SHA-256 in `index.json`. Context invalidation uses a
separate `context_hash`:

- Notes hash their body and all frontmatter except volatile timestamps
  (`created`, `modified`). Status, routing, provenance, and
  relations therefore invalidate summaries when they change.
- Other text and binary files use their exact content SHA-256.
- Folders use a recursive hash of their path and direct child names/hashes.

An unchanged context hash preserves its L1 summary. A changed hash marks the L1
as `stale`; it is not regenerated automatically.

## Context levels

### L0 - orientation

A deterministic one-line description generated during every index pass. It is
cheap enough to load broadly. Notes use title plus description or preview;
folders use recursive child counts; other files use name plus a short preview
or file metadata.

### L1 - optional intelligent summary

A compact AI-generated summary stored with the exact context hash it describes.
Its status is:

- `missing`: no summary exists
- `fresh`: summary hash matches current content
- `stale`: source changed since generation
- `unsupported`: binary file or symlink

L1 generation is never part of `arpent index`, cron, or an autonomous process.

### L2 - source on demand

For a file, L2 points to and loads the original source. For a folder, it returns
the direct child paths. L2 content is not duplicated into the context index.

## Commands

```bash
arpent index
arpent context pending --json
arpent context pending --path 01_projects/example --kind note
arpent context show 01_projects/example --level l0
arpent context show 01_projects/example --level l2
arpent context set 01_projects/example --source-hash <hash-from-pending> --stdin --provider <agent-or-model-id>
```

The workflow for generating L1 summaries is defined in
`06_indexes/global_skills/context_summary.skill.md`.

`--source-hash` prevents a delayed worker from attaching a summary of an older
source version to newer content.

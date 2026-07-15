# Indexing and Context

## Core rule

`arpent index` is deterministic and local. It inventories folders and files,
computes hashes, rebuilds search data, and refreshes L0/L2 context. It never
invokes an AI model.

AI-generated L1 summaries belong to the explicit `context_summary` module. The
module runs only after a user request and only for entries reported as missing
or stale.

## Generated outputs

| Output | Content |
|---|---|
| `06_indexes/index.json` | Every indexed folder and file, including non-note files, counts, types, sizes, and hashes |
| `06_indexes/sidecar.json` | Frontmatter metadata for recognized notes |
| `06_indexes/databases/search.db` | FTS5 note search index |
| `06_indexes/context_index.json` | L0/L1/L2 context cache keyed by relative path |

## Hashes

Files have an exact SHA-256. Notes additionally hash their body and all
frontmatter except volatile timestamps (`created`, `modified`). Folders use a recursive hash of their path and children.

An unchanged context hash preserves its L1. A changed hash marks it `stale` but
does not trigger generation.

## Levels

- L0: deterministic one-line orientation, safe to load broadly.
- L1: optional AI summary tied to a semantic source hash.
- L2: original source or direct folder children, loaded only on demand.

L1 statuses are `missing`, `fresh`, `stale`, and `unsupported`.

## Commands

```bash
arpent index
arpent context pending [--path <path>] [--kind folder|note|text] [--json]
arpent context show <path> --level l0|l1|l2
arpent context set <path> --source-hash <hash> --summary "..." --provider <id>
arpent context set <path> --source-hash <hash> --stdin --provider <id>
```

See `06_indexes/global_skills/context_summary.skill.md` for the explicit AI workflow.

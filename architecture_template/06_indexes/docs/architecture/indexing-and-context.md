# Indexing and Context

## Core rule

`arpent index` is deterministic and local. It inventories folders and files,
computes hashes, rebuilds search data, and refreshes L0/L2 context. It never
invokes an AI model.

AI-generated L1 summaries run only after a user request and only for entries
reported as missing or stale.

## Generated outputs

| Output | Content |
|---|---|
| `06_indexes/index.json` | Complete folder and file inventory with sizes and hashes |
| `06_indexes/sidecar.json` | Frontmatter metadata for recognized notes |
| `06_indexes/databases/search.db` | FTS5 note search across titles, descriptions, tags, links, and bodies; live fallback without FTS5 |
| `06_indexes/context_index.json` | L0/L1/L2 context cache keyed by relative path |

Generated derivatives remain complete. Agents use bounded query commands rather
than byte-truncating those JSON artifacts. Markdown remains canonical for
documents; `todo.db` remains authoritative for coordinated todo state.

Use the maintained search index as the first-pass overview for durable-note
prior art. Search validates freshness and falls back to live text when stale;
ordinary capture does not rebuild indexes.

## Hashes and levels

Files have an exact SHA-256. Notes additionally hash their body and all
frontmatter except volatile timestamps. Folders use a recursive child hash.

- L0: deterministic one-line orientation, safe to load broadly.
- L1: optional AI summary tied to a semantic source hash.
- L2: original source or direct folder children, loaded on demand.

An unchanged context hash preserves its L1. A changed hash marks it stale.

## Commands

```bash
arpent index [--yes]
arpent context pending --json-page --limit 100
arpent context show <path> --level l0|l1
arpent context show <path> --level l2 --json-page --max-bytes 32768
arpent context set <path> --source-hash <hash> --stdin --provider <id> [--yes]
```

Every page reports total or total bytes, source/snapshot hash, completeness, and
the next cursor. Follow all same-hash chunks before summarizing a complete
source. Use `--all` for complete collections and `--full` for complete content.

See `06_indexes/global_skills/context_summary.skill.md` for the explicit AI workflow.

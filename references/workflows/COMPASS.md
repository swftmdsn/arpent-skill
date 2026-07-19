# COMPASS - operation router

Use this workflow to select the smallest sufficient Arpent contract before
acting. It is the compact operational companion to the complete installed
`COMPASS.md`; detailed rationale remains available through the reference index.

## Start here

1. Identify the intent: capture, action, retrieval, organization, lifecycle,
   project continuity, import, or maintenance.
2. Decide the information layer: readable knowledge in the vault; actionable
   work in todo when installed; facts and traits only in explicitly enabled host
   memory; agent research scratch in the memory wiki.
3. Locate the vault only when a vault read or mutation is required.
4. Let CLI commands apply and report the local confirmation policy. In
   filesystem mode or before a batch, read the `confirmation` section in
   `06_indexes/cli/operations.yaml`; an older contract without it uses `always`.
5. Use the CLI adapter when available. Otherwise use the filesystem adapter.
6. Load one operation workflow. Load detailed contracts only for fields or
   edge cases that operation actually uses.

## Hot paths

| Intent | Workflow |
|---|---|
| Keep a normal thought, source, meeting, idea, or reference | `capture-note.md` |
| Record an actionable task | `capture-todo.md` |
| Append a quick temporary thought | `capture-fleeting.md` |
| Organize inbox material | `../routing.md` and the triage sections of the complete method |
| Import an external tree | `../import-and-migration.md` |
| Resume or close work | `../lifecycle.md` |
| Search or load context | `../indexing-and-context.md` |

## Confirmation policy

| Mode | Rule |
|---|---|
| `always` | Require approval before every mutation; use a structured plan when available. |
| `explicit-intent` | Execute an explicit, bounded request directly. Confirm high-impact operations, expanded side effects, or batches at or above `bulk_threshold`. |
| `never` | Do not ask for a second approval. Keep validation, collision, confinement, transaction, and stale-plan checks. |

Clarification is separate from confirmation. Ask for missing meaning when it is
needed to satisfy the request. If a physical route remains uncertain, use
`00_inbox/unsure/` with a reason rather than inventing a destination.

## Execution modes

### CLI

Use stable command syntax from the selected workflow. Do not run global help,
status, triage, index, search, or note rereads after an ordinary capture unless
the task requires them. Prefer versioned JSON plans/results when a preview is
needed.

### Filesystem

Operate directly on canonical Markdown. Preserve complete frontmatter, routing,
body conventions, visible uncertainty, collision checks, and post-write
verification. This mode is intentionally easy to inspect and use. Generated
indexes may be rebuilt later because Markdown remains canonical.

For coordinated database or transactional operations, state the boundary clearly:

> Attention: this feature is not supported in filesystem mode because it needs
> coordinated database or multi-file state. The current files remain readable
> and unchanged; use the CLI adapter for that operation.

## Invariants always in context

- Never overwrite or delete user content. Archive when lifecycle requires it.
- Never invent frontmatter keys or relation types.
- Never infer `appreciated`, `importance`, or missing effort values.
- Keep title and filename in lowercase ASCII `snake_case`; IDs stay in metadata.
- Keep source URLs in `link`, not duplicated in the body.
- Never silently create a missing project, area, or resource destination.
- External memory requires explicit host-level opt-in.
- Report actual changes and paths; do not claim unavailable side effects.

## Detailed references

Use `../appendices/complete-reference-index.md` to locate the complete
architecture, schemas, lifecycle rationale, examples, and edge cases. Those
documents are retained as the long-form source, not compressed away.

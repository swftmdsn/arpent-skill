# COMPASS - operation router

Use this workflow to select the smallest sufficient Arpent contract before
acting. It is the compact operational companion to the complete vault-local
`COMPASS.md`; detailed rationale remains available through the reference index.

## Start here

1. Identify the intent: capture, action, retrieval, organization, lifecycle,
   project continuity, import, or maintenance.
2. Locate the vault and read its `.arpent` marker.
3. Decide the information layer. Actionable reminders are todo; non-actionable
   recall context may use an explicitly enabled external provider buffer.
   Minimal keeps user-provided orientation in `me.md`, current work in
   `_context.md`, and durable readable material in notes. Full may additionally
   use CLI-mediated todo. External memory is a separate host capability and is
   available only after explicit provider opt-in and confirmed persistence.
4. Let full-mode commands apply and report the local confirmation policy. In
   minimal mode or before a batch, read the `confirmation` section in
   `06_indexes/cli/operations.yaml`.
5. Read the compact procedure for the selected mode.
6. Load one operation workflow. Load detailed contracts only for fields or
   edge cases that operation actually uses.

## Hot paths

| Intent | Workflow |
|---|---|
| Keep a normal thought, source, meeting, idea, or reference | `capture-note.md` |
| Maintain the current practical answer to a recurring problem | `maintain-howto.md` |
| Record an actionable task | `capture-todo.md` |
| Append a quick temporary thought | `capture-fleeting.md` |
| Organize inbox material | `../routing.md` and the triage sections of the complete method |
| Import an external tree | `../import-and-migration.md` |
| Resume or close work | `../lifecycle.md` |
| Search or load context | `../indexing-and-context.md` |

## Confirmation policy

| Policy | Rule |
|---|---|
| `always` | Require confirmation before every registered domain change; use a structured preview when available. |
| `explicit-intent` | Execute an explicit, bounded request directly. Confirm high-impact operations or batches at or above `bulk_threshold`. |
| `never` | Do not ask for additional confirmation. Keep validation, collision, confinement, transaction, and stale-plan checks. |

Clarification is separate from confirmation. Ask for missing meaning when it is
needed to satisfy the request. If a physical route remains uncertain, use
`00_inbox/unsure/` with a reason rather than inventing a destination.

Direct CLI invocation is presumed explicit and bounded. The agent establishes
that condition before calling the CLI. Preview, review, confirmation, and plan
hash are separate: the hash proves plan identity, not human review.

## Modes

### Full

Use stable command syntax from the selected workflow. Do not run global help,
status, triage, index, search, or note rereads after an ordinary capture unless
the task requires them. Prefer versioned JSON plans/results when a preview is
needed.

### Minimal

Operate directly on canonical Markdown. Preserve complete frontmatter, routing,
body conventions, visible uncertainty, collision checks, and post-write
verification. This mode is intentionally easy to inspect and use. Generated
indexes may be rebuilt later because Markdown remains canonical.

For coordinated database or transactional operations, state the boundary clearly:

> Attention: this feature is not supported in minimal mode because it needs
> coordinated database or multi-file state. The current files remain readable
> and unchanged; switch the vault to full mode for that operation.

## Invariants always in context

- Prevent silent loss: do not silently replace a destination or destroy user
  content. Explicit edits may use checked atomic replacement; archive when
  lifecycle requires it.
- Never invent frontmatter keys or relation types.
- Never infer `appreciated`, `importance`, or missing effort values.
- Keep title and filename in lowercase ASCII `snake_case`; IDs stay in metadata.
- Keep source URLs in `link`, not duplicated in the body.
- Reserved resource homes may materialize on first write; never invent another
  missing project, area, or resource destination.
- External memory requires provider opt-in at the host level.
- Report actual changes and paths; do not claim unavailable side effects.

## Detailed references

Use `../appendices/complete-reference-index.md` to locate the complete
architecture, schemas, lifecycle rationale, examples, and edge cases. Those
documents are retained as the long-form source, not compressed away.

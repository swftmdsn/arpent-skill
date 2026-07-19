# Minimal mode

Minimal mode is Arpent's direct-file path: inspect and manipulate the
canonical Markdown tree directly while preserving typing, categories, routing,
frontmatter, and visible uncertainty. Mode-gated CLI commands require vault-mode
promotion before they can run.

## Everyday operations

- Capture complete typed Markdown notes.
- Read notes and project/area context.
- Search filenames, frontmatter, and bodies.
- Move a note after updating its routing metadata.
- Archive by preserving content and updating lifecycle metadata.
- Create the standard project folders and `_context.md` when the requested
  structure is fully known.
- Append fleeting entries when the file tool can preserve the existing stream.

## Write discipline

1. Discover the vault from `.arpent` and stay inside it.
2. Read the relevant compact workflow and contract.
3. Inspect the destination and any source immediately before writing.
4. Preserve user-owned metadata and body sections.
5. Never replace an existing destination.
6. Write the smallest complete change.
7. Read back the result and verify path, frontmatter, and body.
8. Leave generated indexes alone; they can be rebuilt from canonical files.

For ordinary capture, load `../contracts/frontmatter.md`,
`../contracts/routing.md`, and `../contracts/provenance-and-body.md`. A copied
zero-install vault uses its local `06_indexes/schemas/frontmatter_policy.yaml`
and `06_indexes/cli/operations.yaml` instead. Generate IDs as
`<type>-<UTC YYYYMMDD>-<a..z,aa..>` after scanning every existing frontmatter ID.

For an operation that depends on coordinated database or multi-file state, say:

> Attention: this feature is not supported in minimal mode because it needs
> coordinated database or multi-file state. The current files remain readable
> and unchanged; switch the vault to full mode for that operation.

This message describes a mode boundary, not a failed attempt. Continue to offer
the useful direct-file actions that remain available, such as capture,
reading, searching, routing, or preserving the source in inbox.

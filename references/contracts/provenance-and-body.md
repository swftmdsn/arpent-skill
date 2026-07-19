# Provenance and body contract

## Source and link

| Source | Link |
|---|---|
| `manual` | `null`; warn when a link is supplied |
| `captured` | External URL required |
| `imported` | External URL, source path, or external identifier required |
| `generated` | `null` or an internal path |
| `conversation` | `null` or a session identifier |
| `derived` | `null` |

Full mode reports mismatches as warnings. Minimal mode surfaces the same
warning before writing. Captured material without an external URL should use a
source value that describes its actual origin rather than a fabricated link.

## Body

- Keep one reusable thesis per note.
- Do not repeat the title as H1.
- Put a source URL only in frontmatter `link`.
- Concepts, ideas, and integrations must stand on their own.
- References and linear notes may discuss or quote their source.
- Use ordinary Obsidian-compatible Markdown without decorative callouts unless
  requested.
- Preserve quotations and source-language terminology.

### How-to body

A `howto` contains only the explicitly reviewed, currently applicable answer to
one practical problem. Use `Current conclusion`, `Why`, `How`, `Examples`,
`Applicability and limits`, and `Linked notes`. Record the last explicit review
timestamp in the body. Keep detailed development, raw research, alternatives,
and superseded conclusions in annotated linked notes, not in the current guide.

A `map` navigates a subject; a `howto` prescribes what to do now. A subject map
may link several how-tos. Revising a how-to preserves its ID and first preserves
any useful removed material in a linked note.

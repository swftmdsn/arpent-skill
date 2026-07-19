# Historical COMPASS

This appendix preserves the rationale behind Arpent's operation router. It is a
historical/explanatory document, not an operational contract and not a command
reference.

Current authority is intentionally split:

| Need | Current authority |
|---|---|
| Start operating a vault | Root `SKILL.md`, then marker-selected mode document |
| Select a less common operation | `references/workflows/COMPASS.md` |
| Metadata, routing, provenance | `references/contracts/` |
| Exact CLI syntax | Installed `arpent <command> --help` |
| Default routing enums and operation inventory | Packaged `scripts/operations.yaml` |
| Explanatory architecture and lifecycle | `references/architecture.md`, `references/lifecycle.md` |

Do not use older examples from this appendix to infer a command, provider,
installer, persistence mechanism, or tool capability.

## Retained Rationale

Arpent was designed around replaceable agents and durable local state. The
smallest useful context should survive a handoff without requiring one model to
remember everything.

The core distinctions remain:

| Information role | Destination |
|---|---|
| Readable document | Typed Markdown note |
| Action to execute or follow | Todo |
| Current project or area work | `_context.md` |
| Human-authored orientation | `me.md` |
| Non-actionable recall context | External provider buffer, only after opt-in |
| Unresolved physical placement | `00_inbox/unsure/` plus a reason |

“Remember to do X” is a todo because it has execution state. A buffer is only
context to recall without completion state. If no external provider is enabled,
provider-bound information was not persisted and no fallback store substitutes
for it.

The routing rationale is likewise unchanged:

- Prefer `project > resource > area > inbox`.
- Keep `project` and `resource` mutually exclusive; `area` is optional context.
- Treat reserved resource homes as contract-declared and materializable on
  first write.
- Never invent any other missing home.
- Make ambiguity visible instead of choosing silently.

Lifecycle status and location are separate. `archived` is a status;
`archived_at` and `archived_from` are event metadata. Explicit archive
operations perform moves. No automatic project closure is delivered.

## Historical Safety Principle

The original broad safety shorthand meant “never silently lose user
content.” The current, more precise rule permits explicitly requested checked
atomic edits while forbidding silent destination replacement, destruction, and
unreported partial outcomes.

## Loading Principle

The former monolithic COMPASS accumulated schema, command, lifecycle, memory,
and tool detail in one file. Current Arpent deliberately replaces that pattern
with progressive loading:

1. Read `.arpent` and the compact skill.
2. Select one mode and one operation.
3. Load one compact contract.
4. Consult a long explanatory document only for rationale or an edge case.

This appendix remains only to explain why those boundaries exist.

# Arpent Mental Model

When information arrives, decide which role it plays:

| Information | Destination |
|---|---|
| Long-form content to open, read, and edit | Vault |
| User-provided orientation | `me.md` in both modes |
| Durable readable knowledge | Vault note in both modes |
| Action or reminder to execute, follow, complete, defer, or block | Todo (coordinated in full; clearly untracked inbox note in minimal) |
| Personal trait or fact for opportunistic recall | External profile/observation only when a host provider is explicitly enabled |
| Time-bound operational context | target `_context.md` in both modes |
| Temporary recall context without execution state | External buffer only when a host provider is explicitly enabled |
| Unsupervised agent research scratch | `06_indexes/memory/wiki/` in full; retained dormant in minimal |
| Default cross-session operational continuity | project/area `_context.md` |
| Optional cross-project log | `06_indexes/memory/MEMORY.md`, only after explicit full-mode `session end --memory-log` |

External-memory destinations require provider opt-in and confirmed persistence;
vault mode does not enable them. When no provider is enabled, report that
provider-bound information was not persisted; do not silently substitute a note
or fallback store.

“Remember to do X” is a todo, not a buffer. Use a buffer only when no action or
completion state must be tracked.

The vault is a clean shared document and continuity layer, not an automatic
memory log. Markdown is canonical for documents; `todo.db` is authoritative for
coordinated todo state.

`MEMORY.md` is unseeded. The delivered `session end` command writes it only when
`--memory-log` is explicitly passed. Normal resume reads `me.md`, then the target
`_context.md`, then only needed notes/sources; reading the optional log requires
a separate explicit request.

`me.md` is a root-level orientation file. It is read early by agents, but it is not a dump for inferred traits or automatic memory writes.

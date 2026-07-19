# Arpent Mental Model

When information arrives, decide which role it plays:

| Information | Destination |
|---|---|
| Long-form content to open, read, and edit | Vault |
| User-provided orientation | `me.md` in both modes |
| Durable readable knowledge | Vault note in both modes |
| Personal trait or fact for opportunistic recall | Delegated profile/observation only when the full-mode integration is enabled |
| Time-bound operational context | target `_context.md` in both modes |
| Time-bound personal reminder | Delegated buffer only when the full-mode integration is enabled |
| Unsupervised agent research scratch | `06_indexes/memory/wiki/` in full; retained dormant in minimal |
| Default cross-session operational continuity | project/area `_context.md` |
| Optional cross-project log | `06_indexes/memory/MEMORY.md`, only after a one-use full-mode write request |

Delegated-memory destinations require full mode and provider opt-in. When the
integration is not enabled, report that provider-bound information was not
persisted; do not silently substitute a note or local queue.

The vault is not memory. It is the clean shared knowledge base.

`MEMORY.md` is disabled and unseeded by default. Normal resume reads `me.md`,
then the target `_context.md`, then only needed notes/sources; reading the
optional log requires a separate explicit read request.

`me.md` is a root-level orientation file. It is read early by agents, but it is not a dump for inferred traits or automatic memory writes.

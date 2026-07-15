# Arpent Mental Model

When information arrives, decide which role it plays:

| Information | Destination |
|---|---|
| Long-form content to open, read, and edit | Vault |
| Stable trait or preference | Delegated memory: profile |
| Durable fact or observation | Delegated memory: observations |
| Time-bound reminder or commitment | Delegated memory: buffer |
| Unsupervised agent research scratch | `06_indexes/memory/wiki/` |
| Default cross-session operational continuity | project/area `_context.md` |
| Optional cross-project log | `06_indexes/memory/MEMORY.md`, only after explicit opt-in |
| User-approved orientation for agents | `me.md` |

Delegated-memory destinations apply only after explicit user opt-in at the host
level. They are disabled by default in minimal and full vault modes.

The vault is not memory. It is the clean shared knowledge base.

`MEMORY.md` is disabled and unseeded by default. Normal resume reads `me.md`,
then the target `_context.md`, then only needed notes/sources; it must not read
the optional log without explicit user opt-in.

`me.md` is a root-level orientation file. It is read early by agents, but it is not a dump for inferred traits or automatic memory writes.

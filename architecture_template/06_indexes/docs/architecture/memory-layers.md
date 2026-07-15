# Memory Layers

Memory is delegated through an optional host interface.

Delegated `profile`, `observations`, and `buffer` memory is disabled by default
in minimal and full vault modes. It becomes active only after explicit user
opt-in at the host level; interface availability alone is not activation.

Local surfaces:

- memory wiki for agent research scratch
- project/area `_context.md` for default operational continuity
- optional `MEMORY.md`, disabled and unseeded by default, only for explicitly requested cross-project logging

Resume by reading `me.md`, then the target `_context.md`, then only needed
notes/sources. Never read `MEMORY.md` unless the user explicitly asks for or
enables it. Minimal mode supports context and `session end` but does not seed
`06_indexes/memory/`.

When explicitly enabled, durable profile, observation, and buffer records belong
to the host memory interface. Arpent does not discover, configure, mirror, or
flush a native memory store. Otherwise, report that the item was not persisted.

# Memory Layers

Memory is delegated through an optional host interface.

Delegated `profile`, `observations`, and `buffer` memory is optional and requires
full mode. The integration is enabled only after provider opt-in at the host
level; interface presence alone does not enable it.

Local surfaces:

- memory wiki for agent research scratch
- project/area `_context.md` for default operational continuity
- optional `MEMORY.md`, disabled and unseeded by default, only for a one-use full-mode write request

Resume by reading `me.md`, then the target `_context.md`, then only needed
notes/sources. Reading `MEMORY.md` requires a separate explicit read request.
Minimal keeps user-provided orientation in `me.md`, working state in `_context.md`,
and durable readable information in notes. Memory surfaces remain retained and
dormant.

When explicitly enabled, durable profile, observation, and buffer records belong
to the host memory interface. Arpent does not discover, configure, mirror, or
flush a native memory store. Otherwise, report that the item was not persisted.

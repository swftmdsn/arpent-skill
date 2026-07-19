# Memory Layers

Arpent ships no memory provider. A host may expose one independently.

External `profile`, `observations`, and `buffer` memory is available only after
provider opt-in at the host level and confirmed provider persistence. Vault mode
and interface presence do not enable it.

Local surfaces:

- memory wiki for agent research scratch
- project/area `_context.md` for default operational continuity
- optional `MEMORY.md`, absent by default and written only by an explicit
  full-mode `session end --memory-log` request

Actions to execute or follow are todo, including “remember to ...”. The buffer
role is only for temporary recall context with no execution state.

Resume by reading `me.md`, then the target `_context.md`, then only needed
notes/sources. `MEMORY.md` is not part of normal resume, and a later read
requires a separate explicit request.
Minimal keeps user-provided orientation in `me.md`, working state in `_context.md`,
and durable readable information in notes.

When explicitly enabled, durable profile, observation, and buffer records belong
to the host memory interface. Arpent does not discover, configure, mirror, or
synchronize a native memory store. Otherwise, report that the item was not
persisted. Do not create or claim fallback storage as a substitute.

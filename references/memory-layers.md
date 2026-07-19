# Memory Boundaries

This explanatory document distinguishes Arpent's local continuity surfaces from
optional host memory. It is not a provider setup guide and does not make an
external provider available.

Arpent ships no memory provider. A host may expose one, but provider persistence
is available only after explicit opt-in. Interface presence, full vault mode, or
an agent's intention does not prove that anything was stored.

## Decide By Responsibility

| Information | Destination |
|---|---|
| Action that must be executed, followed, completed, deferred, or blocked | Todo |
| Current project or area state needed for the next session | Target `_context.md` |
| User-authored identity, collaboration preferences, or boundaries | Root `me.md` |
| Durable document to open, read, edit, or reuse | Typed Markdown note |
| Stable trait or discrete fact for opportunistic recall | External profile/observation role, only when explicitly enabled |
| Context to recall temporarily, with no execution state | External buffer role, only when explicitly enabled |
| Agent research scratch that may remain messy | `06_indexes/memory/wiki/` |

The decisive reminder rule is:

- “Remember to submit the form” is a todo because completion must be tracked.
- “Remember that the venue entrance is on the east side until next week” may be
  buffer context because nothing must be completed.

When wording is ambiguous, ask whether the user expects execution state. Do not
route an action to memory merely because the sentence begins with “remember.”

## Local Continuity

Default continuity is entirely local and documentary:

1. Read human-owned `me.md`.
2. Read the target project or area `_context.md`.
3. Read only the sources needed for the current work.

`me.md` is not a profile inferred by agents. `_context.md` is not a general
memory store. It records current state, decisions, next steps, and concise
session handoffs for one project or area.

The optional `06_indexes/memory/MEMORY.md` is absent by default and is not part
of normal resume. In full mode, `session end --memory-log` creates or updates it
only for that explicit request. Its possible presence does not authorize a later
read without a separate explicit request.

## External Provider Boundary

Logical provider roles are:

- `profile`: stable user-authored or user-confirmed traits and preferences.
- `observations`: discrete facts for later retrieval.
- `buffer`: expiring context without task execution state.

These are roles, not Arpent databases. The provider owns storage, retrieval,
consolidation, expiry, and contradiction behavior. Arpent does not discover,
select, configure, mirror, or synchronize a provider.

If the host has no explicitly enabled provider:

1. State that provider-bound information was not persisted.
2. Do not claim success from an intended handoff.
3. Do not create an ad hoc vault note or fallback store as a substitute.
4. Offer a todo when execution tracking is actually needed, or a durable note
   when the user wants a readable document.

## Memory Wiki

`06_indexes/memory/wiki/` is a filesystem surface for agent research scratch.
It may contain source clippings and interlinked working pages. It is not a
canonical personal fact store and is not queried automatically during normal
resume.

It differs from `03_resources/agent_wiki/`:

- `memory/wiki/` may remain messy and agent-oriented.
- `agent_wiki/` contains document drafts intended for user review and possible
  promotion into the clean document vault.

Durable conclusions should become ordinary typed documents only when the user
wants readable, maintained knowledge.

## Authority

- Markdown is canonical for documents and local continuity.
- `todo.db` is authoritative for coordinated structured todo state; readable
  Markdown todo records remain consistency-bound counterparts.
- An enabled external provider is authoritative only for records it confirms it
  persisted.
- No provider means no external-memory persistence.

# arpent-use

*Orchestration layer for an agent whose primary surface is an Arpent vault. The compact root skill carries common mechanics; load detailed contracts only when needed.*

**What it is.** A filesystem-native continuity and administration layer: a
clean document vault, deterministic routing, local project/area context, and a
human-owned `me.md`. Markdown is canonical for documents; `todo.db` is
authoritative for coordinated todo state. You are the renewable agent operating
user-owned state.

**When to use it.** Use Arpent for durable capture, lookup, organization,
project/area continuity, and actionable todo work. Skip ephemeral chat and
one-off computation.

**Three things to keep in mind:**
1. **Everything has a deterministic place** - route, don't guess; prevent silent loss; apply the local confirmation policy; park ambiguity in `00_inbox/unsure/`.
2. **Action and recall are different** - work to execute is todo; non-actionable context may use an external buffer only after provider opt-in. Without a provider, do not claim or invent persistence.
3. **You're renting; the user owns** - read `me.md` early, keep files legible for the next agent, and defer to the user on identity and meaning.

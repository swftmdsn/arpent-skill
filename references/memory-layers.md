# Memory

Memory in Arpent is **delegated and modular**, described here at a purely logical level. Arpent does not, by default, keep its own separate log of memories in SQL or text. The job of this document is to make clear - for any agent or human following the system - *what kinds of memory exist*, *where each kind belongs*, and *how the vault relates to memory*. The actual wiring of a memory system to a host runs at the Arpent/host level and is out of scope here; the skill only needs the logical map.

This is a deliberate reversal of the earlier design. The role of the PARA-like vault is to be a **clean, shared, human-and-agent knowledge base** for long-term construction - not a place to dump remembered facts. Opportunistic recall of stable traits and discrete facts lives *beside* the vault, while explicit project continuity remains in `_context.md`. This keeps remembered facts from polluting the context the user reads.

## The three roles of memory information

The discrimination that matters has not changed - what changed is *where each kind belongs*:

> When information arrives, ask: do I want to **open this and read it** (the vault), **remember it as a durable fact or trait** (the agentic memory system), or is it **agentic research scratch that may stay messy** (the memory wiki)?

| Kind of information | Belongs to |
|---|---|
| Long-form content to read and edit | the **vault** (markdown in the 7 buckets) |
| Stable trait / interaction preference | the **agentic memory** (role: profile) |
| Discrete fact, retrievable later | the **agentic memory** (role: observations) |
| Time-bound commitment that expires | the **agentic memory** (role: buffer) |
| Unsupervised short/medium-term research | the **memory wiki** (`06_indexes/memory/wiki/`) |
| Default cross-session operational continuity | project/area **`_context.md`** |
| Optional cross-project session log | **MEMORY.md** (`06_indexes/memory/MEMORY.md`), only after a one-use full-mode write request |
| User-provided orientation for agents | **`me.md`** at vault root |

"Profile", "observations" and "buffer" survive as **logical roles**, not as databases Arpent maintains. Where they physically live is the memory system's concern, not the vault's.

`me.md` is a special root file, not a memory store. It is the user's explicit orientation manual for agents: identity, collaboration preferences, current north star, boundaries, and useful links. Agents read it early, may propose edits, and must not rewrite it from inference. Stable traits and observations route to the host's external-memory interface only when the delegated-memory integration is enabled.

## Where memory can live

Arpent defines logical roles but does not discover, configure, mirror, or
synchronize memory providers. The host may expose one external-memory
interface; that interface owns its persistence and retrieval behavior.

Delegated external memory for `profile`, `observations`, and `buffer` is
**disabled by default in both minimal and full vault modes**. The integration
can be enabled only in full mode after provider opt-in at the host level. The
existence of a host interface does not enable the integration; minimal retains
the contracts but never operates it.

### Delegated agentic memory

When the integration is enabled, a **modular agentic memory system** runs beside Arpent
on the host, of the kind exemplified by **Hindsight** or **Supermemory**. It can
be local, cloud, or hybrid. It holds canonical facts, traits, and continuity,
and brings its own consolidation, decay, contradiction handling, and temporal
reasoning, exactly the work Arpent would otherwise reimplement by hand.

Arpent directs memory there only after provider opt-in has enabled that host
integration. Otherwise, the agent reports that the item was not persisted. It
does not create a vault note or an ad hoc local queue as a substitute. The seeded
`pending_db_writes.yaml` file is different: full-mode `session end` may record
explicit deferred observation/trait intent there, but no command flushes it and
its presence never proves provider persistence. Minimal never appends to it.

### The memory wiki

A **mini-LLM-Wiki** under `06_indexes/memory/wiki/`, where the agent does **short-to-medium-term research without direct user supervision**, with a **high tolerance for pollution and drafts**. This is the compounding-knowledge ("LLM wiki") pattern, *contained*: knowledge the agent writes and maintains for itself, that does not have to be clean.

It is explicitly **not** the clean vault. The rest of the architecture stays tidy and comprehensible to the user; the memory wiki is the one sanctioned messy zone. It is also distinct from `03_resources/agent_wiki/`: `agent_wiki/` holds agent **drafts headed for user review and promotion into the clean vault**, whereas the memory wiki holds the agent's **private compounding research** that may stay messy or be distilled later.

Logically it has three parts: immutable source clippings the agent reads but never edits, agent-written interlinked pages, and a small note of the conventions the agent follows when writing there. The exact shape is the agent's to manage.

The wiki is a filesystem surface, not a second canonical fact store. Durable
facts and traits still belong to the host memory interface.

## The vault is not memory

The most important consequence: **the vault stops being a place where the model logs memories.** The 7 buckets are the clean, shared knowledge base - concepts, projects, areas, references, maps - built up by the user and the agent together for the long term. The agent does not dump facts and observations into the vault; those go to the memory system. This keeps the vault legible and prevents memory churn from polluting the context the user actually reads.

What still lives in the vault: documents (`type: note/concept/journal/reference/...`) and explicit project/area continuity in `_context.md`. What leaves the vault for memory is opportunistic recall of discrete personal facts, stable traits, and time-bound reminders, not the documentary handoff.

## The "dinner with Claire" example

User says: *"I had dinner with Claire tonight, she said she's vegetarian, and I want to invite her to my cooking event next month."*

With the delegated-memory integration enabled:

1. **Vault** - a journal note (clean knowledge): `type: journal`, `area: journal`. The human-readable account.
2. **Agentic memory** - two memory writes, directed to the host memory system: a durable observation (*"Claire is vegetarian"*) and a time-bound item (*"invite Claire to cooking event", expiring next month*). Arpent does **not** keep these itself by default.

The journal note is knowledge (vault). The fact and the reminder are memory
(the system beside the vault). Three pieces of information, two destinations.

## The memory zone

Everything memory-adjacent gathers under one zone, so the rest of the architecture stays clean:

```
06_indexes/memory/
├── MEMORY.md     # optional cross-project log; absent by default
└── wiki/         # agentic research scratch
```

`MEMORY.md` is disabled by default. In full, `arpent session end --memory-log`
records a one-use memory-log write request for that invocation. It does not
permit later reads. The file is disposable working state, distinct from
canonical memory and the research wiki.

Default continuity lives in each target project or area `_context.md`. Resume by
reading `me.md`, then that `_context.md`, then only the specific notes or sources
needed. Minimal supports this flow directly in files. It retains the memory tree
and skills but does not operate them.

## What is not memory

Infrastructure is not memory: code, schemas, skills, external docs, configuration. These are the engine, not what it remembers, and they live elsewhere in `06_indexes/`.

`me.md` is also not canonical memory. It is user-owned orientation. Use it as context, not as a target for automatic memory writes.

## Cross-layer reading

When asked "what do I know about X", search the vault, query the host's
external-memory interface once when the integration is enabled, and label each
result by source:

```
"claire"
  From the vault:           journal entries, a social-cooking concept…
  From agentic memory:      "Claire is vegetarian"; "invite Claire" (expires …)
  From the memory wiki:     a research page mentioning Claire
```

The retrieval *quality* of each store is the store's own business: the vault uses keyword search now and can gain semantic search later; the agentic memory system brings its own retrieval. The skill only needs to know to consult all enabled sources.

## When the user says "remember"

Routing is unchanged in intent - only the destination follows the role:

| User phrase | Role | Belongs to |
|---|---|---|
| "Remember I prefer X" | profile | agentic memory |
| "Remember [person] is [trait]" | observation | agentic memory |
| "Remember to [do something]" | buffer | agentic memory |
| "Remember this insight" | knowledge | the vault (`type: concept`/`integration`) |
| "Go research X for me" (unsupervised) | research scratch | the memory wiki |

When ambiguous, ask. Don't guess.

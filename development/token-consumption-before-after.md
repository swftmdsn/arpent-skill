# Token consumption before and after skill refactor

Measurements use UTF-8 bytes divided by four as a provider-neutral token
estimate. Exact tokenization and host system prompts vary. API input processed,
context-window occupancy, cached input, and financial cost are separate metrics.

## Before

The original ordinary-capture reading path loaded the portable skill, four
large references, and the live-vault bootstrap.

| Material | Bytes | Estimated tokens |
|---|---:|---:|
| Original portable `SKILL.md` | 26,896 | 6,724 |
| Architecture + frontmatter + memory + routing references | 61,446 | 15,362 |
| Live-vault bootstrap excluding user `me.md` | 30,098 | 7,525 |
| Typical subtotal | 118,440 | 29,610 |

Optional lifecycle, tools, README, bulk JSON, or full-note reads could move a
capture above 40k tokens. Normal `note new` and `todo add` stdout was only tens
of bytes; documentation loading was the dominant cost.

## After

Measured repository sizes after the refactor:

| Material | Bytes | Estimated tokens |
|---|---:|---:|
| Compact root `SKILL.md` | 6,984 | 1,746 |
| Compact `.agent` | 1,573 | 393 |
| Host-skill hot-path subtotal: root skill + `.agent` | 8,557 | 2,139 |
| Local `operations.yaml`, loaded for filesystem/batch policy | 6,504 | 1,626 |
| Local skill, only when no host skill is active | 2,126 | 532 |
| Compact note workflow | 2,135 | 534 |
| Filesystem adapter | 1,653 | 413 |
| Three compact note contracts | 3,525 | 881 |

An ordinary CLI capture uses the root hot path and lets the command apply the
local policy, so it does not need to load the operation registry, workflow, or
complete references. A filesystem capture can load the note
workflow, adapter, and compact contracts while remaining around 4k to 5.5k
Arpent tokens depending on whether `operations.yaml` is already present.

## Typical capture requests

The unchanged context prefix is sent to the model again on each model request,
even though it appears only once in the conversation history. Prompt caching may
reduce cost but does not make those input tokens disappear from usage reports.

Assuming 2.1k to 4k Arpent context tokens after loading and about 1k of capture
history:

| Scenario | Model requests | Estimated Arpent input processed |
|---|---:|---:|
| First direct capture after skill load | 2 plus the initial skill-load request | roughly 6k to 10k after loading |
| Second direct capture | 2 | roughly 7k to 11k |
| Reviewed capture with user confirmation | 4 | roughly 16k to 24k |
| Same operation with an unnecessary extra reference read | 3 or more | add one full context pass per read cycle |

These estimates exclude the host's system/developer instructions, `me.md`, and
the user's captured content. OpenCode may report current context size, cumulative
API input, and cached input differently.

## Why hot paths stay in the root skill

Splitting every action into a separate file would reduce static text but add a
tool/model cycle to read a card. Since each cycle resends the current context,
the common note, todo, and fleeting syntax remains directly in `SKILL.md`.
Detailed workflows are loaded for ambiguity, filesystem operation, or unusual
fields.

## Regression budgets

The test suite enforces provider-neutral byte budgets:

| Surface | Budget |
|---|---:|
| Root skill | 8 KiB |
| Root skill + `.agent` + local operations contract | 16 KiB |
| Filesystem note bundle | 24 KiB |
| One note or todo creation plan JSON | 4 KiB for representative input |

Bulk result pagination and structured content chunks prevent accidental output
spikes. Complete reading remains available through cursors, `--all`, and
`--full` rather than silent truncation.

# Arpent benchmark harness

This directory contains a dependency-free, deterministic evaluation harness for
the Arpent operating skill. It evaluates observable traces, not prose quality:
reads, commands, writes, claims, and final response size are checked against
strict regular-expression goldens. It never calls an LLM judge or provider SDK.

All harness code, corpus data, ideal traces, tests, and the committed baseline
live below this directory. Runtime reports are written only to the output path
provided by the caller.

## Commands

Run these from the repository root with Python 3.9 or later:

```bash
python3 tests/benchmarks/run.py validate
python3 tests/benchmarks/run.py baseline-check
python3 tests/benchmarks/run.py offline --output build/benchmarks/offline
python3 tests/benchmarks/run.py live --adapter replay --output build/benchmarks/replay
python3 tests/benchmarks/run.py live --adapter stateful-cli \
  --scenario full_first_capture --output build/benchmarks/stateful
python3 tests/benchmarks/run.py live --adapter command-jsonl \
  --adapter-command "python3 path/to/adapter.py" \
  --output build/benchmarks/live
python3 tests/benchmarks/run.py performance \
  --sizes 10,100,1000,5000 --repeat 3 \
  --output build/benchmarks/performance
python3 tests/benchmarks/run.py compare \
  --baseline tests/benchmarks/baselines/offline/report.json \
  --candidate build/benchmarks/offline/report.json \
  --output build/benchmarks/comparison
python3 -m unittest discover -s tests/benchmarks -p 'test_*.py'
```

`validate` and `offline` validate the checked-in corpus, goldens, traces, and
scorer. They do not execute or validate an agent. `live --adapter replay`
exercises the same static traces through the adapter interface.

`stateful-cli` initializes a real temporary vault, materializes fixture documents,
executes each declared `arpent`/`arp` command without a shell, captures its actual
exit code and output, and applies declared direct write events. It deliberately
replays requests, reads, claims, and finals, so it validates CLI state transitions
without claiming to be a model. Reports identify the mode as `stateful`, not as an
agent run. Its pass/fail verdict uses only executed command/write checks and
observed postconditions; replayed checks remain visible but cannot make a
stateful scenario pass. Select only scenarios marked `stateful_eligible` with
repeated `--scenario` options; other selections are rejected before execution.

A real agent evaluation requires the external `command-jsonl` adapter. It is one
long-running subprocess; it receives and emits one JSON object per line and must
flush every response. Any scenario failure makes evaluation exit 1. Invalid data,
adapter failure, or CLI misuse exits 2. Comparison exits 1 on regression.

Each evaluation output contains:

- `report.json`: complete scores, check origins, static metrics, trace hashes,
  and the resolved-document SHA-256 manifest;
- `events.jsonl`: run events, every auditable trace event, and results;
- `report.md`: human-readable summary;
- `junit.xml`: CI-compatible scenario failures.

Comparison writes `comparison.json` and `comparison.md`.
It treats lower scores, new failures, larger input/document byte loads, extra
requests/tools/CLI calls, and reduced stable-prefix reuse as regressions. Use
`--score-tolerance` and `--byte-tolerance` only for explicitly accepted drift.

## Command-JSONL protocol

The harness sends this strict request shape on stdin:

```json
{"protocol_version":1,"type":"evaluate","scenario":{"schema_version":1,"id":"...","title":"...","category":"...","description":"...","conversation_id":"...","turn_index":1,"prompt":"...","fixture":{"vault_mode":"full","skill_loaded":false,"confirmation":"explicit-intent","documents":[{"path":".arpent","content":"..."}]},"tags":["..."],"stateful_eligible":true}}
```

The adapter returns exactly one line per request:

```json
{"protocol_version":1,"type":"trace","scenario_id":"...","provider_usage":{"input_tokens":1200,"output_tokens":80,"total_tokens":1280,"cached_input_tokens":900,"cache_read_input_tokens":null,"cache_creation_input_tokens":null,"provider_reported_cost":0.0042,"currency":"USD","source":"host-usage","raw":{}},"events":[{"type":"request","content":"exact model request"},{"type":"read","path":"SKILL.md"},{"type":"command","command":"arpent note new ... --json","output":"{}","exit_code":0},{"type":"claim","text":"Created the note."},{"type":"final","text":"Created ..."}]}
```

`provider_usage` may be `null`. Within a usage object every token/cache field may
be null; `source` and provider-specific `raw` data are retained. The three cache
fields remain separate because hosts use different semantics.
`provider_reported_cost` and `currency` must be set or null together. Only send a
cost actually reported by the provider or host; the harness never derives it
from byte estimates or a pricing table.

Event objects are closed schemas:

| Type | Required keys |
|---|---|
| `request` | `type`, `content` |
| `read` | `type`, `path` |
| `command` | `type`, `command`, `output`, `exit_code` |
| `write` | `type`, `path`, `content` |
| `claim` | `type`, `text` |
| `final` | `type`, `text` |

A trace requires at least one request, exactly one final event at the end, and
the final request content must contain the scenario prompt verbatim. Read paths
resolve first against fixture documents and then against the repository root.
This lets byte accounting use real, current UTF-8 source documents without
embedding copies in traces.

## Strict data schemas

`corpus/scenarios.jsonl` has one closed-shape scenario per line. Scenario IDs are
lowercase underscore slugs; turns are ordered within a conversation; fixture
paths are safe relative POSIX paths. Required coverage tags are enforced by the
validator. `stateful_eligible` is true only for scenarios whose initialized vault
and fixture documents are sufficient to execute every declared mutation.

Each `goldens/<scenario_id>.json` supports these closed-schema keys:

```json
{
  "schema_version": 1,
  "scenario_id": "example",
  "required_reads": [],
  "forbidden_reads": [],
  "required_commands": [],
  "forbidden_commands": [],
  "required_claims": [],
  "forbidden_claims": [],
  "required_writes": [],
  "forbidden_writes": [],
  "command_results": [{"command": "^arpent note new", "exit_code": 0, "output_json": {"format": "arpent-note-new-result", "version": 1}}],
  "command_bindings": [{"source_command": "--dry-run", "source_json_field": "plan_sha256", "target_command": "--plan-hash", "target_option": "--plan-hash"}],
  "write_results": [{"path": "^00_inbox/result.md$", "content": null, "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}],
  "postconditions": [{"kind": "command_json_path_exists", "command": "^arpent note new", "field": "path"}],
  "final_size": {"min_utf8_bytes": 1, "max_utf8_bytes": 500},
  "hard_failures": ["forbidden_read", "forbidden_command", "forbidden_claim", "forbidden_write", "missing_final", "command_failure", "write_mismatch"]
}
```

These four result/binding/postcondition lists are optional. Required commands and
command-result expectations are matched in order. Every command event must exit
zero; a declared command result cannot waive that rule. Declared JSON outputs must
include a versioned `format`/`version`; nested declared values are matched as a
strict subset of the parsed output. Bindings require an apply argument to equal a
field from an earlier preview JSON result. Declared writes compare exact content,
UTF-8 SHA-256, or both. Stateful postconditions can check literal paths, JSON
fields, and paths returned by actual command JSON.

All patterns use Python `re.search`. Every pattern and final-size bound is one
equally weighted objective assertion. Any failed assertion fails the scenario.
A configured hard failure forces the score to zero; otherwise the score is the
percentage of assertions passed.

Each `ideal_traces/<scenario_id>.jsonl` starts with strict metadata:

```json
{"schema_version":1,"type":"trace","scenario_id":"example","provider_usage":null}
```

Subsequent lines are strict event objects. `validate` rejects unknown keys,
duplicate JSON keys, blank JSONL lines, missing peers, unsafe paths, malformed
regexes, unresolved ideal reads, coverage gaps, and ideal traces that do not
score 100.

## Static metrics

Every `*_utf8_bytes` metric is computed from actual UTF-8 encoding. Document
bytes include every read; `unique_document_utf8_bytes` counts each distinct
`(path, content hash)` once per ordered evaluation run, and each scenario records
the first occurrence or repetition it contributed. `repeated_document_utf8_bytes`
is the remainder. `cumulative_input_proxy_utf8_bytes` is the sum of exact request
event payload bytes. It is a deterministic context proxy, not billable input.

`utf8_byte_quarter_estimate` is explicitly the ceiling of cumulative request
bytes divided by four. It is the only token-like estimate and is never copied
into provider usage. `stable_prefix_utf8_bytes` sums the bytewise common prefix
between consecutive request payloads in the same conversation, including across
ordered scenarios. Counts distinguish model requests, all tool events, command
events, and commands invoking `arpent`/`arp` (`cli_count`).

Aggregate provider values sum only reported data and remain null when no adapter
reports them. `provider_usage_scenario_count` exposes coverage, so partial usage
cannot be mistaken for a complete estimate.

## Product performance

`performance` materializes isolated deterministic vaults, then measures `status`,
`index`, `search`, `context pending`, and `triage`. It reports p50/p95 latency,
result bytes, fixture size, and correctness at every requested scale. Fixture
construction is excluded from operation timings. Absolute timings vary by
machine, so this report is intended for trend analysis and remains non-blocking
in CI.

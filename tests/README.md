# Arpent tests and benchmarks

All maintained test infrastructure, fixtures, scenarios, traces, and baselines
live under this directory. The suite uses only the Python standard library.

## Test suites

```text
tests/tests/       focused unit and contract tests
tests/smoke/       package, parser, scaffold, and JSON-contract smoke tests
tests/e2e/         subprocess-driven user lifecycle tests
tests/regression/  safety, recovery, privacy, schema, and concurrency tests
tests/benchmarks/  model-trace, token/context, and product-scale benchmarks
tests/support/     shared isolated CLI and filesystem helpers
```

Run everything, including benchmark corpus validation:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tests/run.py all
```

Run one deterministic layer:

```bash
python3 tests/run.py unit
python3 tests/run.py smoke
python3 tests/run.py e2e
python3 tests/run.py regression
python3 tests/run.py benchmark-offline
```

Every test creates isolated temporary state. No test requires network access or
an LLM provider.

## Model and token benchmarks

The benchmark harness scores observable reads, commands, writes, claims, and
response sizes. Ideal replay traces validate the corpus and scorer; a generic
JSONL adapter can connect a real model host without adding a provider dependency.

```bash
python3 tests/benchmarks/run.py validate
python3 tests/benchmarks/run.py offline --output build/benchmarks/offline
python3 tests/benchmarks/run.py live --adapter replay \
  --output build/benchmarks/replay
python3 tests/benchmarks/run.py live --adapter command-jsonl \
  --adapter-command "python3 /absolute/path/to/adapter.py" \
  --output build/benchmarks/live
```

The live adapter may report input/output tokens, three separate cache counters,
raw provider usage, and provider-reported cost. Missing values remain `null`.
`utf8_byte_quarter_estimate` is deliberately labeled as an offline byte proxy,
not as real token usage.

Compare a deterministic result with the committed baseline:

```bash
python3 tests/benchmarks/run.py compare \
  --baseline tests/benchmarks/baselines/offline/report.json \
  --candidate build/benchmarks/offline/report.json \
  --output build/benchmarks/comparison
```

Live results are informative and non-blocking. Only deterministic tests,
contracts, safety invariants, corpus validation, and accepted static budgets
should block ordinary CI.

## Product-scale benchmarks

Use the short scale set during development and the full set for release evidence:

```bash
python3 tests/benchmarks/run.py performance \
  --sizes 10,100,1000 --repeat 3 \
  --output build/benchmarks/performance

python3 tests/benchmarks/run.py performance \
  --sizes 10,100,1000,5000 --repeat 5 \
  --output build/benchmarks/performance-release
```

These runs check result completeness while measuring p50/p95 latency and output
size for status, indexing, search, pending context, and triage. Absolute timings
depend on the host machine and are not CI gates.

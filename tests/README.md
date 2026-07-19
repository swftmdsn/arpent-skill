# Arpent tests and benchmarks

All maintained test infrastructure, fixtures, scenarios, traces, and baselines
live under this directory. Runtime tests and benchmarks use only the Python
standard library; wheel and coverage checks use the optional `dev` extra.

## Test suites

```text
tests/tests/       focused unit and contract tests
tests/smoke/       package, parser, scaffold, and JSON-contract smoke tests
tests/e2e/         subprocess-driven user lifecycle tests
tests/regression/  safety, recovery, privacy, schema, and concurrency tests
tests/benchmarks/  model-trace, token/context, and product-scale benchmarks
tests/release/     offline sdist/wheel, entrypoint, package-data, and install checks
tests/support/     shared isolated CLI and filesystem helpers
```

Run every standard-library layer, including benchmark corpus validation:

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
python3 tests/run.py release
```

Every test creates isolated temporary state. No test requires network access or
an LLM provider.

## Model and token benchmarks

The benchmark harness scores observable reads, commands, writes, claims, and
response sizes. `validate`, `offline`, and ideal replay validate the corpus,
goldens, traces, and scorer only; they do not run or validate an agent. The
stateful CLI adapter executes declared CLI commands in isolated temporary vaults,
but replays non-command events and therefore also does not pretend to be a model.
Its verdict uses executed checks and observed postconditions only; replayed
claims and finals remain separately labeled evidence. A generic JSONL adapter connects a real
agent/model host without adding a provider dependency; real agent validation
requires that external adapter.

```bash
python3 tests/benchmarks/run.py validate
python3 tests/benchmarks/run.py offline --output build/benchmarks/offline
python3 tests/benchmarks/run.py live --adapter replay \
  --output build/benchmarks/replay
python3 tests/benchmarks/run.py live --adapter stateful-cli \
  --scenario full_first_capture \
  --output build/benchmarks/stateful
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

## Coverage and release

Runtime dependencies remain empty. Install optional development tools only when
needed, then run coverage with the committed `pyproject.toml` configuration:

```bash
python3 -m pip install '.[dev]'
coverage run tests/run.py all
coverage report
```

`python3 tests/run.py release` copies the build inputs to a temporary directory,
builds an sdist and wheel without build isolation or an index, rebuilds the wheel
from the sdist, checks metadata and package data, installs it offline into a new
venv with system site packages disabled, and executes both installed entrypoints,
`init`, and a SQLite-backed `todo add`. The test itself never accesses the network.

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

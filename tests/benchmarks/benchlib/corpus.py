from pathlib import Path

from .errors import ValidationError
from .jsonio import load_json, load_jsonl, sha256_json
from .schema import validate_golden, validate_scenario, validate_trace


REQUIRED_COVERAGE = {
    "cold-global-comprehension",
    "first-capture",
    "second-capture-loaded",
    "reviewed-capture",
    "routing-ambiguity",
    "todo-routing",
    "note-routing",
    "fleeting-routing",
    "full-mode",
    "minimal-mode",
    "forbidden-post-capture-ritual",
    "source-selection",
    "lifecycle",
    "import",
}


class Bundle:
    def __init__(self, scenarios, goldens, traces, digest):
        self.scenarios = scenarios
        self.goldens = goldens
        self.traces = traces
        self.digest = digest


def _load_trace(path, scenario):
    records = load_jsonl(path)
    metadata = records[0]
    expected_keys = {"schema_version", "type", "scenario_id", "provider_usage"}
    if not isinstance(metadata, dict) or set(metadata) != expected_keys:
        raise ValidationError("%s: trace metadata keys differ" % path)
    if metadata["type"] != "trace":
        raise ValidationError("%s: first JSONL record must have type trace" % path)
    trace = {
        "schema_version": metadata["schema_version"],
        "scenario_id": metadata["scenario_id"],
        "provider_usage": metadata["provider_usage"],
        "events": records[1:],
    }
    return validate_trace(trace, scenario, str(path))


def load_bundle(benchmark_dir, require_traces=True):
    benchmark_dir = Path(benchmark_dir)
    scenario_path = benchmark_dir / "corpus" / "scenarios.jsonl"
    scenario_values = load_jsonl(scenario_path)
    scenarios = []
    scenario_by_id = {}
    coverage = set()
    conversation_turns = {}
    for index, value in enumerate(scenario_values):
        scenario = validate_scenario(value, "%s:%d" % (scenario_path, index + 1))
        if scenario["id"] in scenario_by_id:
            raise ValidationError("duplicate scenario id: %s" % scenario["id"])
        scenario_by_id[scenario["id"]] = scenario
        scenarios.append(scenario)
        coverage.update(scenario["tags"])
        turns = conversation_turns.setdefault(scenario["conversation_id"], [])
        turns.append(scenario["turn_index"])
    missing_coverage = sorted(REQUIRED_COVERAGE - coverage)
    if missing_coverage:
        raise ValidationError("corpus is missing required coverage tags: %s" % missing_coverage)
    for conversation_id, turns in conversation_turns.items():
        if turns != sorted(turns) or len(turns) != len(set(turns)):
            raise ValidationError("conversation %s has duplicate or unordered turns" % conversation_id)

    golden_dir = benchmark_dir / "goldens"
    goldens = {}
    for path in sorted(golden_dir.glob("*.json")):
        golden = validate_golden(load_json(path), str(path))
        scenario_id = golden["scenario_id"]
        if path.stem != scenario_id:
            raise ValidationError("%s filename must match scenario_id" % path)
        if scenario_id in goldens:
            raise ValidationError("duplicate golden for %s" % scenario_id)
        goldens[scenario_id] = golden
    if set(goldens) != set(scenario_by_id):
        raise ValidationError(
            "golden/scenario ids differ; missing=%s extra=%s" % (
                sorted(set(scenario_by_id) - set(goldens)),
                sorted(set(goldens) - set(scenario_by_id)),
            )
        )

    traces = {}
    trace_dir = benchmark_dir / "ideal_traces"
    trace_paths = sorted(trace_dir.glob("*.jsonl"))
    if require_traces:
        for path in trace_paths:
            if path.stem not in scenario_by_id:
                raise ValidationError("%s has no matching scenario" % path)
            traces[path.stem] = _load_trace(path, scenario_by_id[path.stem])
        if set(traces) != set(scenario_by_id):
            raise ValidationError(
                "ideal trace/scenario ids differ; missing=%s extra=%s" % (
                    sorted(set(scenario_by_id) - set(traces)),
                    sorted(set(traces) - set(scenario_by_id)),
                )
            )

    digest = sha256_json({
        "scenarios": scenarios,
        "goldens": goldens,
        "traces": traces if require_traces else None,
    })
    return Bundle(scenarios, goldens, traces, digest)

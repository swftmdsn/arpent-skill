import hashlib
import re
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
    def __init__(self, scenarios, goldens, traces, document_manifest, digest):
        self.scenarios = scenarios
        self.goldens = goldens
        self.traces = traces
        self.document_manifest = document_manifest
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


def _document_manifest(repository_root, scenarios, traces):
    documents = []
    seen = set()
    for scenario in scenarios:
        state = {
            document["path"]: (document["content"], "fixture")
            for document in scenario["fixture"]["documents"]
        }
        for event in traces[scenario["id"]]["events"]:
            if event["type"] == "write":
                state[event["path"]] = (event["content"], "trace_write")
                continue
            if event["type"] != "read":
                continue
            if event["path"] in state:
                content, source = state[event["path"]]
            elif event["path"] == "06_indexes/cli/operations.yaml":
                content = (repository_root / "scripts" / "operations.yaml").read_text(encoding="utf-8")
                policy = scenario["fixture"]["confirmation"]
                if policy in ("always", "explicit-intent", "never"):
                    content = re.sub(r"(?m)^(  policy: ).+$", r"\g<1>" + policy, content, count=1)
                source = "package_data"
            else:
                path = (repository_root / event["path"]).resolve()
                try:
                    path.relative_to(repository_root)
                except ValueError as exc:
                    raise ValidationError("read path escapes repository: %s" % event["path"]) from exc
                if not path.is_file():
                    raise ValidationError("read event cannot be resolved: %s" % event["path"])
                try:
                    content = path.read_text(encoding="utf-8")
                except (OSError, UnicodeError) as exc:
                    raise ValidationError("read event is not a UTF-8 document: %s" % event["path"]) from exc
                source = "repository"
            encoded = content.encode("utf-8")
            digest = hashlib.sha256(encoded).hexdigest()
            identity = (scenario["id"], event["path"], digest)
            if identity in seen:
                continue
            seen.add(identity)
            documents.append({
                "scenario_id": scenario["id"],
                "path": event["path"],
                "source": source,
                "utf8_bytes": len(encoded),
                "sha256": digest,
            })
    return {"sha256": sha256_json(documents), "documents": documents}


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

    repository_root = benchmark_dir.parent.parent.resolve()
    document_manifest = _document_manifest(repository_root, scenarios, traces) if require_traces else {
        "sha256": sha256_json([]), "documents": [],
    }
    digest = sha256_json({
        "scenarios": scenarios,
        "goldens": goldens,
        "traces": traces if require_traces else None,
        "document_manifest": document_manifest,
    })
    return Bundle(scenarios, goldens, traces, document_manifest, digest)

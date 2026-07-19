from .jsonio import sha256_json
from .metrics import MetricState, calculate_metrics
from .reports import build_report
from .scoring import score_trace


STATEFUL_EXECUTED_KINDS = {
    "required_command", "forbidden_command", "command_exit_code",
    "command_result", "command_binding", "required_write", "forbidden_write",
    "write_result",
}
CHECK_ORIGINS = ("executed", "observed", "replayed", "reported")


def _check_summary(checks):
    return {
        origin: sum(1 for check in checks if check["origin"] == origin)
        for origin in CHECK_ORIGINS
    }


def evaluate(bundle, adapter, repository_root, mode, scenario_ids=None):
    results = []
    traces = []
    metric_state = MetricState()
    selected = set(scenario_ids) if scenario_ids is not None else None
    for scenario in bundle.scenarios:
        if selected is not None and scenario["id"] not in selected:
            continue
        trace = adapter.evaluate(scenario)
        scoring = score_trace(trace, bundle.goldens[scenario["id"]])
        checks = scoring["checks"]
        if mode == "stateful":
            for check in checks:
                check["origin"] = "executed" if check["kind"] in STATEFUL_EXECUTED_KINDS else "replayed"
            observed = adapter.observe_postconditions(bundle.goldens[scenario["id"]], trace)
            for check in observed:
                check["origin"] = "observed"
            checks.extend(observed)
            verdict_checks = [check for check in checks if check["origin"] in ("executed", "observed")]
            has_postcondition = bool(observed)
            passed = has_postcondition and all(check["passed"] for check in verdict_checks)
            hard_failures = [check for check in verdict_checks if check["hard"]]
            passed_count = sum(1 for check in verdict_checks if check["passed"])
            score = round(100.0 * passed_count / len(verdict_checks), 2) if verdict_checks else 0.0
            if hard_failures:
                score = 0.0
            verdict_basis = "executed_commands_and_observed_postconditions"
        else:
            origin = "replayed" if adapter.name == "replay" else "reported"
            for check in checks:
                check["origin"] = origin
            passed = scoring["passed"]
            hard_failures = scoring["hard_failures"]
            score = scoring["score"]
            verdict_basis = "replayed_ideal_trace" if origin == "replayed" else "reported_agent_trace"
        metrics = calculate_metrics(scenario, trace, repository_root, metric_state)
        result = {
            "scenario_id": scenario["id"],
            "title": scenario["title"],
            "category": scenario["category"],
            "score": score,
            "passed": passed,
            "hard_failures": hard_failures,
            "checks": checks,
            "check_summary": _check_summary(checks),
            "verdict_basis": verdict_basis,
            "metrics": metrics,
            "provider_usage": trace["provider_usage"],
            "trace_sha256": sha256_json(trace),
        }
        results.append(result)
        traces.append((scenario["id"], trace))
    result_ids = {result["scenario_id"] for result in results}
    documents = [
        document for document in bundle.document_manifest["documents"]
        if document["scenario_id"] in result_ids
    ]
    document_manifest = {"sha256": sha256_json(documents), "documents": documents}
    report = build_report(
        mode, adapter.name, bundle.digest, document_manifest, results,
    )
    return report, traces

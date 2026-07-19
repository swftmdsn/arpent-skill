from .jsonio import sha256_json
from .metrics import MetricState, calculate_metrics
from .reports import build_report
from .scoring import score_trace


def evaluate(bundle, adapter, repository_root, mode):
    results = []
    traces = []
    metric_state = MetricState()
    for scenario in bundle.scenarios:
        trace = adapter.evaluate(scenario)
        scoring = score_trace(trace, bundle.goldens[scenario["id"]])
        metrics = calculate_metrics(scenario, trace, repository_root, metric_state)
        result = {
            "scenario_id": scenario["id"],
            "title": scenario["title"],
            "category": scenario["category"],
            "score": scoring["score"],
            "passed": scoring["passed"],
            "hard_failures": scoring["hard_failures"],
            "checks": scoring["checks"],
            "metrics": metrics,
            "provider_usage": trace["provider_usage"],
            "trace_sha256": sha256_json(trace),
        }
        results.append(result)
        traces.append((scenario["id"], trace))
    report = build_report(mode, adapter.name, bundle.digest, results)
    return report, traces

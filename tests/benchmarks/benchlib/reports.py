import json
from pathlib import Path
from xml.etree import ElementTree

from . import BENCHMARK_VERSION, SCHEMA_VERSION
from .errors import ValidationError
from .jsonio import atomic_write_text, canonical_json, load_json, sha256_json


def aggregate_metrics(results):
    if not results:
        return {}
    metric_keys = results[0]["metrics"].keys()
    aggregate = {}
    nullable = {
        "provider_input_tokens", "provider_output_tokens", "provider_total_tokens",
        "provider_cached_input_tokens", "provider_cache_read_input_tokens",
        "provider_cache_creation_input_tokens", "provider_reported_cost",
        "provider_reported_cost_currency",
    }
    for key in metric_keys:
        values = [result["metrics"][key] for result in results]
        if key == "provider_reported_cost_currency":
            currencies = sorted(set(value for value in values if value is not None))
            aggregate[key] = currencies[0] if len(currencies) == 1 else None
        elif key == "provider_reported_cost":
            currencies = set(
                result["metrics"]["provider_reported_cost_currency"]
                for result in results
                if result["metrics"]["provider_reported_cost"] is not None
            )
            known = [value for value in values if value is not None]
            aggregate[key] = sum(known) if known and len(currencies) == 1 else None
        elif key in nullable:
            known = [value for value in values if value is not None]
            aggregate[key] = sum(known) if known else None
        else:
            aggregate[key] = sum(values)
    aggregate["provider_usage_scenario_count"] = sum(
        1 for result in results
        if any(result["metrics"][key] is not None for key in (
            "provider_input_tokens", "provider_output_tokens", "provider_total_tokens",
            "provider_cached_input_tokens", "provider_cache_read_input_tokens",
            "provider_cache_creation_input_tokens", "provider_reported_cost",
        ))
    )
    return aggregate


def build_report(mode, adapter, bundle_digest, results):
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark_version": BENCHMARK_VERSION,
        "mode": mode,
        "adapter": adapter,
        "bundle_sha256": bundle_digest,
        "summary": {
            "scenario_count": len(results),
            "passed": sum(1 for result in results if result["passed"]),
            "failed": sum(1 for result in results if not result["passed"]),
            "hard_failure_count": sum(len(result["hard_failures"]) for result in results),
            "mean_score": round(sum(result["score"] for result in results) / len(results), 2) if results else 0.0,
            "metrics": aggregate_metrics(results),
        },
        "scenarios": results,
    }


def _markdown(report):
    summary = report["summary"]
    lines = [
        "# Arpent Benchmark Report",
        "",
        "- Mode: `%s`" % report["mode"],
        "- Adapter: `%s`" % report["adapter"],
        "- Scenarios: %d" % summary["scenario_count"],
        "- Passed: %d" % summary["passed"],
        "- Mean score: %.2f" % summary["mean_score"],
        "- Hard failures: %d" % summary["hard_failure_count"],
        "",
        "| Scenario | Score | Pass | Hard failures | Requests | Tools | CLI | Input proxy bytes |",
        "|---|---:|:---:|---:|---:|---:|---:|---:|",
    ]
    for result in report["scenarios"]:
        metrics = result["metrics"]
        lines.append(
            "| `%s` | %.2f | %s | %d | %d | %d | %d | %d |" % (
                result["scenario_id"], result["score"], "yes" if result["passed"] else "no",
                len(result["hard_failures"]), metrics["request_count"], metrics["tool_count"],
                metrics["cli_count"], metrics["cumulative_input_proxy_utf8_bytes"],
            )
        )
    metrics = summary["metrics"]
    lines.extend([
        "",
        "## Static Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ])
    for key in sorted(metrics):
        lines.append("| `%s` | %s |" % (key, "null" if metrics[key] is None else metrics[key]))
    lines.extend([
        "",
        "`utf8_byte_quarter_estimate` is the ceiling of cumulative exact request UTF-8 bytes divided by four. It is not provider token usage.",
        "",
    ])
    return "\n".join(lines)


def _junit(report):
    summary = report["summary"]
    suite = ElementTree.Element(
        "testsuite",
        name="arpent-benchmarks",
        tests=str(summary["scenario_count"]),
        failures=str(summary["failed"]),
        errors="0",
        skipped="0",
    )
    for result in report["scenarios"]:
        case = ElementTree.SubElement(
            suite,
            "testcase",
            classname="benchmarks.%s" % result["category"],
            name=result["scenario_id"],
        )
        if not result["passed"]:
            failed = [check for check in result["checks"] if not check["passed"]]
            failure = ElementTree.SubElement(case, "failure", message="score %.2f" % result["score"])
            failure.text = "\n".join(
                "%s %r: %s" % (check["kind"], check["pattern"], check["detail"])
                for check in failed
            )
        output = ElementTree.SubElement(case, "system-out")
        output.text = canonical_json(result["metrics"])
    return ElementTree.tostring(suite, encoding="unicode", xml_declaration=True) + "\n"


def write_report(output_dir, report, traces):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output / "report.json", json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    events = [{
        "schema_version": SCHEMA_VERSION,
        "type": "benchmark_started",
        "mode": report["mode"],
        "adapter": report["adapter"],
        "scenario_count": len(report["scenarios"]),
    }]
    result_by_id = {result["scenario_id"]: result for result in report["scenarios"]}
    for scenario_id, trace in traces:
        for index, event in enumerate(trace["events"]):
            events.append({
                "schema_version": SCHEMA_VERSION,
                "type": "trace_event",
                "scenario_id": scenario_id,
                "event_index": index,
                "event": event,
            })
        result = result_by_id[scenario_id]
        events.append({
            "schema_version": SCHEMA_VERSION,
            "type": "scenario_result",
            "scenario_id": scenario_id,
            "score": result["score"],
            "passed": result["passed"],
            "hard_failure_count": len(result["hard_failures"]),
            "metrics": result["metrics"],
            "provider_usage": result.get("provider_usage"),
        })
    events.append({
        "schema_version": SCHEMA_VERSION,
        "type": "benchmark_completed",
        "summary": report["summary"],
    })
    atomic_write_text(output / "events.jsonl", "".join(canonical_json(event) + "\n" for event in events))
    atomic_write_text(output / "report.md", _markdown(report))
    atomic_write_text(output / "junit.xml", _junit(report))


def compare_reports(baseline_path, candidate_path, score_tolerance=0.0, byte_tolerance=0):
    baseline = load_json(baseline_path)
    candidate = load_json(candidate_path)
    required = {"schema_version", "benchmark_version", "summary", "scenarios"}
    if not isinstance(baseline, dict) or not required.issubset(baseline):
        raise ValidationError("baseline is not a benchmark report")
    if not isinstance(candidate, dict) or not required.issubset(candidate):
        raise ValidationError("candidate is not a benchmark report")
    baseline_map = {item["scenario_id"]: item for item in baseline["scenarios"]}
    candidate_map = {item["scenario_id"]: item for item in candidate["scenarios"]}
    if set(baseline_map) != set(candidate_map):
        raise ValidationError("baseline and candidate scenario ids differ")
    scenarios = []
    regressions = []
    for scenario_id in sorted(baseline_map):
        old = baseline_map[scenario_id]
        new = candidate_map[scenario_id]
        score_delta = round(new["score"] - old["score"], 2)
        reasons = []
        if score_delta < -score_tolerance:
            reasons.append("score decreased by %.2f" % (-score_delta))
        if old["passed"] and not new["passed"]:
            reasons.append("scenario changed from pass to fail")
        if len(new["hard_failures"]) > len(old["hard_failures"]):
            reasons.append("hard failure count increased")
        metric_deltas = {}
        for key in (
            "cumulative_input_proxy_utf8_bytes", "document_utf8_bytes",
            "request_count", "tool_count", "cli_count", "stable_prefix_utf8_bytes",
        ):
            old_value = old["metrics"][key]
            new_value = new["metrics"][key]
            metric_deltas[key] = new_value - old_value
        for key in ("cumulative_input_proxy_utf8_bytes", "document_utf8_bytes"):
            if metric_deltas[key] > byte_tolerance:
                reasons.append("%s increased by %d" % (key, metric_deltas[key]))
        for key in ("request_count", "tool_count", "cli_count"):
            if metric_deltas[key] > 0:
                reasons.append("%s increased by %d" % (key, metric_deltas[key]))
        if metric_deltas["stable_prefix_utf8_bytes"] < -byte_tolerance:
            reasons.append(
                "stable_prefix_utf8_bytes decreased by %d" % (-metric_deltas["stable_prefix_utf8_bytes"])
            )
        item = {
            "scenario_id": scenario_id,
            "baseline_score": old["score"],
            "candidate_score": new["score"],
            "score_delta": score_delta,
            "metric_deltas": metric_deltas,
            "regressions": reasons,
        }
        scenarios.append(item)
        if reasons:
            regressions.append(item)
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark_version": BENCHMARK_VERSION,
        "baseline_sha256": sha256_json(baseline),
        "candidate_sha256": sha256_json(candidate),
        "score_tolerance": score_tolerance,
        "byte_tolerance": byte_tolerance,
        "regression_count": len(regressions),
        "mean_score_delta": round(
            candidate["summary"]["mean_score"] - baseline["summary"]["mean_score"], 2
        ),
        "scenarios": scenarios,
    }


def write_comparison(output_dir, comparison):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output / "comparison.json", json.dumps(comparison, sort_keys=True, indent=2) + "\n")
    lines = [
        "# Arpent Benchmark Comparison",
        "",
        "- Regressions: %d" % comparison["regression_count"],
        "- Mean score delta: %+.2f" % comparison["mean_score_delta"],
        "- Score tolerance: %.2f" % comparison["score_tolerance"],
        "- Byte tolerance: %d" % comparison["byte_tolerance"],
        "",
        "| Scenario | Baseline | Candidate | Score delta | Input-byte delta | Tool delta | Regression |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in comparison["scenarios"]:
        lines.append("| `%s` | %.2f | %.2f | %+.2f | %+d | %+d | %s |" % (
            item["scenario_id"], item["baseline_score"], item["candidate_score"],
            item["score_delta"], item["metric_deltas"]["cumulative_input_proxy_utf8_bytes"],
            item["metric_deltas"]["tool_count"], "; ".join(item["regressions"]) or "no",
        ))
    lines.append("")
    atomic_write_text(output / "comparison.md", "\n".join(lines))

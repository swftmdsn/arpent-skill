import json
from pathlib import Path
from xml.etree import ElementTree

from . import BENCHMARK_VERSION, SCHEMA_VERSION
from .errors import ValidationError
from .jsonio import atomic_write_text, canonical_json, load_json, sha256_json
from .metrics import METRIC_KEYS
from .schema import validate_usage


REPORT_KEYS = {
    "schema_version", "benchmark_version", "mode", "adapter", "bundle_sha256",
    "document_manifest", "validation_scope", "summary", "scenarios",
}
SUMMARY_KEYS = {
    "scenario_count", "passed", "failed", "hard_failure_count", "mean_score",
    "check_summary", "metrics",
}
RESULT_KEYS = {
    "scenario_id", "title", "category", "score", "passed", "hard_failures",
    "checks", "check_summary", "verdict_basis", "metrics", "provider_usage",
    "trace_sha256",
}
CHECK_KEYS = {"kind", "pattern", "passed", "hard", "detail", "origin"}
CHECK_ORIGINS = ("executed", "observed", "replayed", "reported")
DOCUMENT_MANIFEST_KEYS = {"sha256", "documents"}
DOCUMENT_KEYS = {"scenario_id", "path", "source", "utf8_bytes", "sha256"}


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


def _check_summary(results):
    return {
        origin: sum(result["check_summary"][origin] for result in results)
        for origin in CHECK_ORIGINS
    }


def _summary(results):
    return {
        "scenario_count": len(results),
        "passed": sum(1 for result in results if result["passed"]),
        "failed": sum(1 for result in results if not result["passed"]),
        "hard_failure_count": sum(len(result["hard_failures"]) for result in results),
        "mean_score": round(sum(result["score"] for result in results) / len(results), 2) if results else 0.0,
        "check_summary": _check_summary(results),
        "metrics": aggregate_metrics(results),
    }


def _validation_scope(mode, adapter):
    if mode == "stateful":
        return "Declared CLI/write execution and observed vault postconditions; agent behavior is not evaluated."
    if adapter == "replay":
        return "Checked-in ideal trace replay; no agent or CLI execution is evaluated."
    return "Adapter-reported agent trace; tool events are reported by the adapter, not re-executed by this harness."


def build_report(mode, adapter, bundle_digest, document_manifest, results):
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark_version": BENCHMARK_VERSION,
        "mode": mode,
        "adapter": adapter,
        "bundle_sha256": bundle_digest,
        "document_manifest": document_manifest,
        "validation_scope": _validation_scope(mode, adapter),
        "summary": _summary(results),
        "scenarios": results,
    }


def _markdown(report):
    summary = report["summary"]
    lines = [
        "# Arpent Benchmark Report",
        "",
        "- Mode: `%s`" % report["mode"],
        "- Adapter: `%s`" % report["adapter"],
        "- Scope: %s" % report["validation_scope"],
        "- Scenarios: %d" % summary["scenario_count"],
        "- Passed: %d" % summary["passed"],
        "- Mean score: %.2f" % summary["mean_score"],
        "- Hard failures: %d" % summary["hard_failure_count"],
        "- Executed/observed/replayed/reported checks: %d/%d/%d/%d" % (
            summary["check_summary"]["executed"], summary["check_summary"]["observed"],
            summary["check_summary"]["replayed"], summary["check_summary"]["reported"],
        ),
        "",
        "| Scenario | Score | Pass | Verdict basis | Executed | Observed | Replayed | Requests | Tools | CLI | Input proxy bytes |",
        "|---|---:|:---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in report["scenarios"]:
        metrics = result["metrics"]
        lines.append(
            "| `%s` | %.2f | %s | `%s` | %d | %d | %d | %d | %d | %d | %d |" % (
                result["scenario_id"], result["score"], "yes" if result["passed"] else "no",
                result["verdict_basis"], result["check_summary"]["executed"],
                result["check_summary"]["observed"], result["check_summary"]["replayed"],
                metrics["request_count"], metrics["tool_count"],
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
    validate_report(report)
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
            "verdict_basis": result["verdict_basis"],
            "check_summary": result["check_summary"],
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


def _require_exact_keys(value, expected, where):
    if not isinstance(value, dict):
        raise ValidationError("%s must be an object" % where)
    actual = set(value)
    if actual != expected:
        raise ValidationError(
            "%s keys differ; missing=%s extra=%s" % (
                where, sorted(expected - actual), sorted(actual - expected),
            )
        )


def _digest(value, where):
    if not isinstance(value, str) or len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValidationError("%s must be a lowercase SHA-256 digest" % where)


def validate_report(report, where="report"):
    _require_exact_keys(report, REPORT_KEYS, where)
    if report["schema_version"] != SCHEMA_VERSION:
        raise ValidationError(where + ".schema_version is unsupported")
    if report["benchmark_version"] != BENCHMARK_VERSION:
        raise ValidationError(where + ".benchmark_version is unsupported")
    for key in ("mode", "adapter", "validation_scope"):
        if not isinstance(report[key], str) or not report[key]:
            raise ValidationError("%s.%s must be a non-empty string" % (where, key))
    _digest(report["bundle_sha256"], where + ".bundle_sha256")

    manifest = report["document_manifest"]
    _require_exact_keys(manifest, DOCUMENT_MANIFEST_KEYS, where + ".document_manifest")
    _digest(manifest["sha256"], where + ".document_manifest.sha256")
    if not isinstance(manifest["documents"], list):
        raise ValidationError(where + ".document_manifest.documents must be a list")
    manifest_identities = set()
    for index, document in enumerate(manifest["documents"]):
        document_where = "%s.document_manifest.documents[%d]" % (where, index)
        _require_exact_keys(document, DOCUMENT_KEYS, document_where)
        for key in ("scenario_id", "path", "source"):
            if not isinstance(document[key], str) or not document[key]:
                raise ValidationError("%s.%s must be a non-empty string" % (document_where, key))
        if document["source"] not in ("repository", "fixture", "trace_write", "package_data"):
            raise ValidationError(document_where + ".source is invalid")
        if type(document["utf8_bytes"]) is not int or document["utf8_bytes"] < 0:
            raise ValidationError(document_where + ".utf8_bytes must be non-negative")
        _digest(document["sha256"], document_where + ".sha256")
        identity = (document["scenario_id"], document["path"], document["sha256"])
        if identity in manifest_identities:
            raise ValidationError(where + ".document_manifest contains duplicate documents")
        manifest_identities.add(identity)
    if manifest["sha256"] != sha256_json(manifest["documents"]):
        raise ValidationError(where + ".document_manifest.sha256 does not match documents")

    if not isinstance(report["scenarios"], list):
        raise ValidationError(where + ".scenarios must be a list")
    scenario_ids = set()
    for index, result in enumerate(report["scenarios"]):
        result_where = "%s.scenarios[%d]" % (where, index)
        _require_exact_keys(result, RESULT_KEYS, result_where)
        for key in ("scenario_id", "title", "category", "verdict_basis"):
            if not isinstance(result[key], str) or not result[key]:
                raise ValidationError("%s.%s must be a non-empty string" % (result_where, key))
        if result["scenario_id"] in scenario_ids:
            raise ValidationError("%s has duplicate scenario id: %s" % (where, result["scenario_id"]))
        scenario_ids.add(result["scenario_id"])
        if isinstance(result["score"], bool) or not isinstance(result["score"], (int, float)):
            raise ValidationError(result_where + ".score must be a number")
        if not 0 <= result["score"] <= 100:
            raise ValidationError(result_where + ".score must be between 0 and 100")
        if type(result["passed"]) is not bool:
            raise ValidationError(result_where + ".passed must be a boolean")
        if not isinstance(result["checks"], list):
            raise ValidationError(result_where + ".checks must be a list")
        for check_index, check in enumerate(result["checks"]):
            check_where = "%s.checks[%d]" % (result_where, check_index)
            _require_exact_keys(check, CHECK_KEYS, check_where)
            if not isinstance(check["kind"], str) or not check["kind"]:
                raise ValidationError(check_where + ".kind must be a non-empty string")
            if check["pattern"] is not None and not isinstance(check["pattern"], str):
                raise ValidationError(check_where + ".pattern must be null or a string")
            if type(check["passed"]) is not bool or type(check["hard"]) is not bool:
                raise ValidationError(check_where + ".passed and hard must be booleans")
            if check["hard"] and check["passed"]:
                raise ValidationError(check_where + ".hard cannot be true for a passing check")
            if not isinstance(check["detail"], str):
                raise ValidationError(check_where + ".detail must be a string")
            if check["origin"] not in CHECK_ORIGINS:
                raise ValidationError(check_where + ".origin is invalid")
        expected_check_summary = {
            origin: sum(1 for check in result["checks"] if check["origin"] == origin)
            for origin in CHECK_ORIGINS
        }
        if result["check_summary"] != expected_check_summary:
            raise ValidationError(result_where + ".check_summary does not match checks")
        if not isinstance(result["hard_failures"], list) or any(
            failure not in result["checks"] or not failure["hard"]
            for failure in result["hard_failures"]
        ):
            raise ValidationError(result_where + ".hard_failures does not match hard checks")
        _require_exact_keys(result["metrics"], METRIC_KEYS, result_where + ".metrics")
        for key, metric in result["metrics"].items():
            metric_where = "%s.metrics.%s" % (result_where, key)
            if key == "provider_reported_cost_currency":
                if metric is not None and (not isinstance(metric, str) or not metric):
                    raise ValidationError(metric_where + " must be null or a non-empty string")
            elif key == "provider_reported_cost":
                if metric is not None and (
                    isinstance(metric, bool) or not isinstance(metric, (int, float)) or metric < 0
                ):
                    raise ValidationError(metric_where + " must be null or non-negative")
            elif key.startswith("provider_"):
                if metric is not None and (
                    isinstance(metric, bool) or not isinstance(metric, int) or metric < 0
                ):
                    raise ValidationError(metric_where + " must be null or a non-negative integer")
            elif isinstance(metric, bool) or not isinstance(metric, int) or metric < 0:
                raise ValidationError(metric_where + " must be a non-negative integer")
        validate_usage(result["provider_usage"], result_where + ".provider_usage")
        _digest(result["trace_sha256"], result_where + ".trace_sha256")

    _require_exact_keys(report["summary"], SUMMARY_KEYS, where + ".summary")
    expected_summary = _summary(report["scenarios"])
    if report["summary"] != expected_summary:
        raise ValidationError(where + ".summary does not match scenarios")
    unknown_manifest_ids = {
        document["scenario_id"] for document in manifest["documents"]
    } - scenario_ids
    if unknown_manifest_ids:
        raise ValidationError(
            where + ".document_manifest has unknown scenario ids: %s" % sorted(unknown_manifest_ids)
        )
    return report


def compare_reports(baseline_path, candidate_path, score_tolerance=0.0, byte_tolerance=0):
    baseline = load_json(baseline_path)
    candidate = load_json(candidate_path)
    validate_report(baseline, "baseline")
    validate_report(candidate, "candidate")
    for key in (
        "schema_version", "benchmark_version", "bundle_sha256",
        "document_manifest", "mode", "adapter",
    ):
        if baseline[key] != candidate[key]:
            raise ValidationError("baseline and candidate %s differ" % key)
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

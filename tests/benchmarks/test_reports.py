import copy
import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree

from .benchlib.jsonio import sha256_json
from .benchlib.reports import build_report, compare_reports, validate_report, write_report
from .benchlib.errors import ValidationError


def metrics():
    return {
        "prompt_utf8_bytes": 1,
        "request_utf8_bytes": 1,
        "document_utf8_bytes": 0,
        "unique_document_utf8_bytes": 0,
        "repeated_document_utf8_bytes": 0,
        "command_utf8_bytes": 0,
        "command_output_utf8_bytes": 0,
        "write_utf8_bytes": 0,
        "claim_utf8_bytes": 0,
        "final_utf8_bytes": 2,
        "cumulative_input_proxy_utf8_bytes": 1,
        "utf8_byte_quarter_estimate": 1,
        "stable_prefix_utf8_bytes": 0,
        "request_count": 1,
        "tool_count": 0,
        "command_count": 0,
        "cli_count": 0,
        "provider_input_tokens": None,
        "provider_output_tokens": None,
        "provider_total_tokens": None,
        "provider_cached_input_tokens": None,
        "provider_cache_read_input_tokens": None,
        "provider_cache_creation_input_tokens": None,
        "provider_reported_cost": None,
        "provider_reported_cost_currency": None,
    }


def result():
    checks = [{
        "kind": "final_present", "pattern": None, "passed": True,
        "hard": False, "detail": "one final event", "origin": "replayed",
    }]
    return {
        "scenario_id": "case",
        "title": "Case",
        "category": "unit",
        "score": 100.0,
        "passed": True,
        "hard_failures": [],
        "checks": checks,
        "check_summary": {"executed": 0, "observed": 0, "replayed": 1, "reported": 0},
        "verdict_basis": "replayed_ideal_trace",
        "metrics": metrics(),
        "provider_usage": None,
        "trace_sha256": "0" * 64,
    }


def manifest():
    documents = []
    return {"sha256": sha256_json(documents), "documents": documents}


class ReportTests(unittest.TestCase):
    def test_all_report_formats_are_written_and_parseable(self):
        report = build_report("offline", "replay", "a" * 64, manifest(), [result()])
        trace = {"events": [{"type": "request", "content": "x"}, {"type": "final", "text": "ok"}]}
        with tempfile.TemporaryDirectory() as root:
            write_report(root, report, [("case", trace)])
            output = Path(root)
            self.assertEqual(1, json.loads((output / "report.json").read_text())["summary"]["passed"])
            self.assertEqual(5, len((output / "events.jsonl").read_text().splitlines()))
            self.assertIn("Static Metrics", (output / "report.md").read_text())
            ElementTree.parse(str(output / "junit.xml"))

    def test_comparison_detects_score_regression(self):
        baseline = build_report("offline", "replay", "a" * 64, manifest(), [result()])
        changed = result()
        changed["score"] = 90.0
        changed["passed"] = False
        candidate = build_report("offline", "replay", "a" * 64, manifest(), [changed])
        with tempfile.TemporaryDirectory() as root:
            baseline_path = Path(root) / "baseline.json"
            candidate_path = Path(root) / "candidate.json"
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            comparison = compare_reports(baseline_path, candidate_path)
        self.assertEqual(1, comparison["regression_count"])
        self.assertEqual(-10.0, comparison["mean_score_delta"])

    def test_comparison_detects_static_metric_regression(self):
        baseline = build_report("offline", "replay", "a" * 64, manifest(), [result()])
        changed = result()
        changed["metrics"]["tool_count"] = 1
        candidate = build_report("offline", "replay", "a" * 64, manifest(), [changed])
        with tempfile.TemporaryDirectory() as root:
            baseline_path = Path(root) / "baseline.json"
            candidate_path = Path(root) / "candidate.json"
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            comparison = compare_reports(baseline_path, candidate_path)
        self.assertEqual(1, comparison["regression_count"])
        self.assertIn("tool_count increased by 1", comparison["scenarios"][0]["regressions"])

    def test_comparison_rejects_incompatible_report_identity(self):
        for key, incompatible in (
            ("bundle_sha256", "b" * 64),
            ("benchmark_version", 999),
            ("mode", "live"),
            ("adapter", "command-jsonl"),
        ):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as root:
                baseline = build_report("offline", "replay", "a" * 64, manifest(), [result()])
                candidate = copy.deepcopy(baseline)
                candidate[key] = incompatible
                baseline_path = Path(root) / "baseline.json"
                candidate_path = Path(root) / "candidate.json"
                baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
                candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
                with self.assertRaisesRegex(ValidationError, key):
                    compare_reports(baseline_path, candidate_path)

    def test_report_schema_is_closed(self):
        report = build_report("offline", "replay", "a" * 64, manifest(), [result()])
        report["unexpected"] = True
        with self.assertRaisesRegex(ValidationError, "extra=.*unexpected"):
            validate_report(report)

    def test_duplicate_scenario_ids_are_rejected(self):
        report = build_report(
            "offline", "replay", "a" * 64, manifest(), [result(), copy.deepcopy(result())],
        )
        with self.assertRaisesRegex(ValidationError, "duplicate scenario id"):
            validate_report(report)

    def test_summary_is_recalculated_and_verified(self):
        report = build_report("offline", "replay", "a" * 64, manifest(), [result()])
        report["summary"]["passed"] = 0
        with self.assertRaisesRegex(ValidationError, "summary does not match"):
            validate_report(report)


if __name__ == "__main__":
    unittest.main()

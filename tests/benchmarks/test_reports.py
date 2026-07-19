import copy
import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree

from .benchlib.reports import build_report, compare_reports, write_report


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
    return {
        "scenario_id": "case",
        "title": "Case",
        "category": "unit",
        "score": 100.0,
        "passed": True,
        "hard_failures": [],
        "checks": [],
        "metrics": metrics(),
        "trace_sha256": "0" * 64,
    }


class ReportTests(unittest.TestCase):
    def test_all_report_formats_are_written_and_parseable(self):
        report = build_report("offline", "replay", "a" * 64, [result()])
        trace = {"events": [{"type": "request", "content": "x"}, {"type": "final", "text": "ok"}]}
        with tempfile.TemporaryDirectory() as root:
            write_report(root, report, [("case", trace)])
            output = Path(root)
            self.assertEqual(1, json.loads((output / "report.json").read_text())["summary"]["passed"])
            self.assertEqual(5, len((output / "events.jsonl").read_text().splitlines()))
            self.assertIn("Static Metrics", (output / "report.md").read_text())
            ElementTree.parse(str(output / "junit.xml"))

    def test_comparison_detects_score_regression(self):
        baseline = build_report("offline", "replay", "a" * 64, [result()])
        candidate = copy.deepcopy(baseline)
        candidate["scenarios"][0]["score"] = 90.0
        candidate["scenarios"][0]["passed"] = False
        candidate["summary"]["mean_score"] = 90.0
        with tempfile.TemporaryDirectory() as root:
            baseline_path = Path(root) / "baseline.json"
            candidate_path = Path(root) / "candidate.json"
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            comparison = compare_reports(baseline_path, candidate_path)
        self.assertEqual(1, comparison["regression_count"])
        self.assertEqual(-10.0, comparison["mean_score_delta"])

    def test_comparison_detects_static_metric_regression(self):
        baseline = build_report("offline", "replay", "a" * 64, [result()])
        candidate = copy.deepcopy(baseline)
        candidate["scenarios"][0]["metrics"]["tool_count"] = 1
        with tempfile.TemporaryDirectory() as root:
            baseline_path = Path(root) / "baseline.json"
            candidate_path = Path(root) / "candidate.json"
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            comparison = compare_reports(baseline_path, candidate_path)
        self.assertEqual(1, comparison["regression_count"])
        self.assertIn("tool_count increased by 1", comparison["scenarios"][0]["regressions"])


if __name__ == "__main__":
    unittest.main()

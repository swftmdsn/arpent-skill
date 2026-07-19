import json
import os
import shlex
import sys
import tempfile
import textwrap
import unittest

from pathlib import Path

from .benchlib.adapters import CommandJsonlAdapter, StatefulCliAdapter
from .benchlib.corpus import load_bundle
from .benchlib.runner import evaluate
from .benchlib.scoring import score_trace
from .run import BenchmarkError, _validate_stateful_selection


class CommandAdapterTests(unittest.TestCase):
    def test_jsonl_round_trip_and_nullable_usage(self):
        program = textwrap.dedent(
            """
            import json
            import sys

            for line in sys.stdin:
                request = json.loads(line)
                scenario = request["scenario"]
                response = {
                    "protocol_version": 1,
                    "type": "trace",
                    "scenario_id": scenario["id"],
                    "provider_usage": None,
                    "events": [
                        {"type": "request", "content": scenario["prompt"]},
                        {"type": "final", "text": "adapter result"},
                    ],
                }
                print(json.dumps(response, separators=(",", ":")), flush=True)
            """
        )
        descriptor, path = tempfile.mkstemp(suffix=".py", text=True)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(program)
            command = "%s %s" % (shlex.quote(sys.executable), shlex.quote(path))
            adapter = CommandJsonlAdapter(command, timeout_seconds=5)
            scenario = {"id": "adapter_case", "prompt": "exact prompt"}
            trace = adapter.evaluate(scenario)
            adapter.close()
        finally:
            os.unlink(path)
        self.assertEqual("adapter_case", trace["scenario_id"])
        self.assertIsNone(trace["provider_usage"])
        self.assertEqual("adapter result", trace["events"][-1]["text"])

    def test_stateful_cli_executes_declared_command_in_an_isolated_vault(self):
        scenario = {
            "id": "stateful_case",
            "fixture": {
                "vault_mode": "full", "confirmation": "explicit-intent", "documents": [],
            },
        }
        traces = {"stateful_case": {
            "schema_version": 1,
            "events": [
                {"type": "request", "content": "capture"},
                {
                    "type": "command",
                    "command": 'arpent note new "Stateful check" --type note --body "written" --json',
                    "output": "ignored declaration",
                    "exit_code": 0,
                },
                {"type": "final", "text": "captured"},
            ],
        }}
        adapter = StatefulCliAdapter(traces, Path(__file__).resolve().parents[2], timeout_seconds=10)
        try:
            trace = adapter.evaluate(scenario)
            command = trace["events"][1]
            self.assertEqual(0, command["exit_code"])
            result = json.loads(command["output"])
            self.assertEqual(("arpent-note-new-result", 1), (result["format"], result["version"]))
            self.assertTrue((adapter.last_vault_root / result["path"]).is_file())
            golden = {
                "required_reads": [], "forbidden_reads": [],
                "required_commands": ["^arpent note new"], "forbidden_commands": [],
                "required_claims": [], "forbidden_claims": [],
                "required_writes": [], "forbidden_writes": [],
                "command_results": [{
                    "command": "^arpent note new", "exit_code": 0,
                    "output_json": {"format": "arpent-note-new-result", "version": 1},
                }],
                "write_results": [],
                "final_size": {"min_utf8_bytes": 1, "max_utf8_bytes": 100},
                "hard_failures": ["command_failure", "write_mismatch", "missing_final"],
            }
            self.assertTrue(score_trace(trace, golden)["passed"])
        finally:
            adapter.close()

    def test_stateful_selection_rejects_incomplete_fixtures_before_execution(self):
        bundle = load_bundle(Path(__file__).resolve().parent)
        with self.assertRaisesRegex(BenchmarkError, "not stateful-eligible.*reviewed_import"):
            _validate_stateful_selection(bundle, ["reviewed_import"])

    def test_stateful_report_uses_executed_postconditions_not_replayed_final(self):
        benchmark_dir = Path(__file__).resolve().parent
        bundle = load_bundle(benchmark_dir)
        adapter = StatefulCliAdapter(
            bundle.traces, benchmark_dir.parents[1], timeout_seconds=10,
        )
        try:
            report, traces = evaluate(
                bundle, adapter, benchmark_dir.parents[1], "stateful", ["reviewed_capture"],
            )
        finally:
            adapter.close()
        result = report["scenarios"][0]
        self.assertTrue(result["passed"])
        self.assertGreater(result["check_summary"]["observed"], 0)
        self.assertGreater(result["check_summary"]["replayed"], 0)
        self.assertEqual(
            {"replayed"},
            {check["origin"] for check in result["checks"] if check["kind"].startswith("final_")},
        )
        self.assertIn("agent behavior is not evaluated", report["validation_scope"])
        commands = [event for event in traces[0][1]["events"] if event["type"] == "command"]
        preview_hash = json.loads(commands[0]["output"])["plan_sha256"]
        self.assertIn("--plan-hash %s" % preview_hash, commands[1]["command"])


if __name__ == "__main__":
    unittest.main()

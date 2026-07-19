import json
import os
import shlex
import sys
import tempfile
import textwrap
import unittest

from .benchlib.adapters import CommandJsonlAdapter


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


if __name__ == "__main__":
    unittest.main()

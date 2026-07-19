import copy
import shlex
import unittest
from pathlib import Path

from scripts import cli
from .benchlib.corpus import load_bundle
from .benchlib.errors import ValidationError
from .benchlib.jsonio import parse_json
from .benchlib.schema import validate_golden, validate_scenario, validate_trace, validate_usage


BENCHMARK_DIR = Path(__file__).resolve().parent


class SchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = load_bundle(BENCHMARK_DIR)

    def test_checked_in_bundle_is_complete(self):
        self.assertEqual(17, len(self.bundle.scenarios))
        self.assertEqual(set(self.bundle.goldens), set(self.bundle.traces))
        self.assertEqual({
            "full_first_capture", "full_second_capture_loaded", "reviewed_capture",
            "todo_capture", "durable_note_capture", "fleeting_capture",
            "minimal_note_capture", "current_guidance_capture",
        }, {
            scenario["id"] for scenario in self.bundle.scenarios
            if scenario["stateful_eligible"]
        })
        self.assertTrue(self.bundle.document_manifest["documents"])

    def test_every_ideal_cli_command_uses_the_current_parser_surface(self):
        parser = cli.build_parser()
        for scenario_id, trace in self.bundle.traces.items():
            for event in trace["events"]:
                if event["type"] != "command":
                    continue
                arguments = shlex.split(event["command"])
                if not arguments or arguments[0] not in {"arpent", "arp"}:
                    continue
                with self.subTest(scenario=scenario_id, command=event["command"]):
                    parsed = parser.parse_args(arguments[1:])
                    self.assertTrue(callable(parsed.func))

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaisesRegex(ValidationError, "duplicate JSON key"):
            parse_json('{"id":"one","id":"two"}', "fixture")

    def test_unknown_scenario_key_is_rejected(self):
        scenario = copy.deepcopy(self.bundle.scenarios[0])
        scenario["unexpected"] = True
        with self.assertRaisesRegex(ValidationError, "keys differ"):
            validate_scenario(scenario)

    def test_stateful_eligible_must_be_boolean(self):
        scenario = copy.deepcopy(self.bundle.scenarios[0])
        scenario["stateful_eligible"] = "yes"
        with self.assertRaisesRegex(ValidationError, "stateful_eligible"):
            validate_scenario(scenario)

    def test_trace_requires_prompt_in_final_request(self):
        scenario = self.bundle.scenarios[0]
        trace = {
            "schema_version": 1,
            "scenario_id": scenario["id"],
            "provider_usage": None,
            "events": [
                {"type": "request", "content": "different prompt"},
                {"type": "final", "text": "result"},
            ],
        }
        with self.assertRaisesRegex(ValidationError, "prompt verbatim"):
            validate_trace(trace, scenario)

    def test_provider_usage_keeps_cache_and_raw_provider_semantics(self):
        usage = {
            "input_tokens": 120,
            "output_tokens": 30,
            "total_tokens": 150,
            "cached_input_tokens": 80,
            "cache_read_input_tokens": None,
            "cache_creation_input_tokens": None,
            "provider_reported_cost": 0.002,
            "currency": "USD",
            "source": "test-host",
            "raw": {"cache_discount": "provider-specific"},
        }
        self.assertIs(validate_usage(usage), usage)

    def test_versioned_command_output_contract_requires_format_and_version(self):
        value = copy.deepcopy(self.bundle.goldens["full_first_capture"])
        value["command_results"][0]["output_json"].pop("version")
        with self.assertRaisesRegex(ValidationError, "output_json.version"):
            validate_golden(value)

    def test_command_result_contract_cannot_accept_nonzero_exit(self):
        value = copy.deepcopy(self.bundle.goldens["full_first_capture"])
        value["command_results"][0]["exit_code"] = 2
        with self.assertRaisesRegex(ValidationError, "exit_code must be 0"):
            validate_golden(value)

    def test_write_contract_requires_content_or_sha256(self):
        value = copy.deepcopy(self.bundle.goldens["minimal_note_capture"])
        value["write_results"] = [{"path": "^note\\.md$", "content": None, "sha256": None}]
        with self.assertRaisesRegex(ValidationError, "must declare"):
            validate_golden(value)

    def test_command_binding_requires_a_long_target_option(self):
        value = copy.deepcopy(self.bundle.goldens["reviewed_capture"])
        value["command_bindings"][0]["target_option"] = "plan-hash"
        with self.assertRaisesRegex(ValidationError, "long option"):
            validate_golden(value)


if __name__ == "__main__":
    unittest.main()

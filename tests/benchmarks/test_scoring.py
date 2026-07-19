import copy
import hashlib
import unittest

from .benchlib.scoring import score_trace


def golden():
    return {
        "required_reads": ["^SKILL\\.md$"],
        "forbidden_reads": ["^development/"],
        "required_commands": ["^arpent note new"],
        "forbidden_commands": ["arpent status"],
        "required_claims": ["created"],
        "forbidden_claims": ["deleted"],
        "required_writes": [],
        "forbidden_writes": ["^outside/"],
        "command_results": [{
            "command": "^arpent note new",
            "exit_code": 0,
            "output_json": {"format": "arpent-note-new-result", "version": 1},
        }],
        "write_results": [],
        "final_size": {"min_utf8_bytes": 5, "max_utf8_bytes": 100},
        "hard_failures": [
            "forbidden_read", "forbidden_command", "forbidden_claim",
            "forbidden_write", "missing_final", "command_failure", "write_mismatch",
        ],
    }


def trace():
    return {
        "events": [
            {"type": "request", "content": "request"},
            {"type": "read", "path": "SKILL.md"},
            {"type": "command", "command": "arpent note new x", "output": "{\"format\":\"arpent-note-new-result\",\"version\":1}", "exit_code": 0},
            {"type": "final", "text": "created note"},
        ]
    }


class ScoringTests(unittest.TestCase):
    def test_objective_trace_scores_one_hundred(self):
        result = score_trace(trace(), golden())
        self.assertTrue(result["passed"])
        self.assertEqual(100.0, result["score"])

    def test_forbidden_command_is_a_zero_score_hard_failure(self):
        value = copy.deepcopy(trace())
        value["events"].insert(-1, {
            "type": "command", "command": "arpent status", "output": "", "exit_code": 0,
        })
        result = score_trace(value, golden())
        self.assertFalse(result["passed"])
        self.assertEqual(0.0, result["score"])
        self.assertEqual("forbidden_command", result["hard_failures"][0]["kind"])

    def test_missing_requirement_reduces_score_without_hiding_other_checks(self):
        value = copy.deepcopy(trace())
        value["events"] = [event for event in value["events"] if event["type"] != "read"]
        result = score_trace(value, golden())
        self.assertFalse(result["passed"])
        self.assertGreater(result["score"], 0.0)
        self.assertLess(result["score"], 100.0)

    def test_nonzero_command_exit_is_always_a_hard_failure(self):
        value = copy.deepcopy(trace())
        value["events"][2]["exit_code"] = 2
        expected = golden()
        expected["hard_failures"].remove("command_failure")
        result = score_trace(value, expected)
        self.assertFalse(result["passed"])
        self.assertEqual(0.0, result["score"])
        self.assertIn("command_exit_code", {item["kind"] for item in result["hard_failures"]})

    def test_declared_nonzero_exit_cannot_bypass_failure(self):
        value = copy.deepcopy(trace())
        value["events"][2]["exit_code"] = 3
        expected = golden()
        expected["command_results"][0]["exit_code"] = 3
        result = score_trace(value, expected)
        self.assertFalse(result["passed"])
        self.assertEqual(0.0, result["score"])

    def test_declared_versioned_json_mismatch_fails(self):
        value = copy.deepcopy(trace())
        value["events"][2]["output"] = '{"format":"arpent-note-new-result","version":2}'
        result = score_trace(value, golden())
        self.assertFalse(result["passed"])
        self.assertIn("command_result", {item["kind"] for item in result["hard_failures"]})

    def test_declared_write_content_and_hash_are_checked(self):
        value = copy.deepcopy(trace())
        value["events"].insert(-1, {"type": "write", "path": "result.txt", "content": "exact\n"})
        expected = golden()
        expected["write_results"] = [{
            "path": "^result\\.txt$",
            "content": "exact\n",
            "sha256": hashlib.sha256(b"exact\n").hexdigest(),
        }]
        self.assertTrue(score_trace(value, expected)["passed"])
        value["events"][-2]["content"] = "changed\n"
        result = score_trace(value, expected)
        self.assertFalse(result["passed"])
        self.assertIn("write_result", {item["kind"] for item in result["hard_failures"]})

    def test_required_commands_must_appear_in_declared_order(self):
        value = copy.deepcopy(trace())
        value["events"].insert(2, {
            "type": "command", "command": "arpent apply", "output": "{}", "exit_code": 0,
        })
        value["events"].insert(3, {
            "type": "command", "command": "arpent preview", "output": "{}", "exit_code": 0,
        })
        expected = golden()
        expected["required_commands"] = ["^arpent preview$", "^arpent apply$"]
        expected["command_results"] = []
        result = score_trace(value, expected)
        self.assertFalse(result["passed"])
        failed = [check for check in result["checks"] if check["kind"] == "required_command" and not check["passed"]]
        self.assertEqual(1, len(failed))

    def test_apply_plan_hash_must_match_the_preview_output(self):
        digest = "a" * 64
        value = copy.deepcopy(trace())
        value["events"][2:3] = [
            {
                "type": "command", "command": "arpent note new x --dry-run --json",
                "output": '{"plan_sha256":"%s"}' % digest, "exit_code": 0,
            },
            {
                "type": "command", "command": "arpent note new x --plan-hash %s --json" % digest,
                "output": '{"format":"arpent-note-new-result","version":1}', "exit_code": 0,
            },
        ]
        expected = golden()
        expected["required_commands"] = ["--dry-run", "--plan-hash"]
        expected["command_results"] = [{
            "command": "--plan-hash", "exit_code": 0,
            "output_json": {"format": "arpent-note-new-result", "version": 1},
        }]
        expected["command_bindings"] = [{
            "source_command": "--dry-run", "source_json_field": "plan_sha256",
            "target_command": "--plan-hash", "target_option": "--plan-hash",
        }]
        self.assertTrue(score_trace(value, expected)["passed"])
        value["events"][3]["command"] = "arpent note new x --plan-hash %s --json" % ("b" * 64)
        result = score_trace(value, expected)
        self.assertFalse(result["passed"])
        self.assertIn("command_binding", {item["kind"] for item in result["hard_failures"]})


if __name__ == "__main__":
    unittest.main()

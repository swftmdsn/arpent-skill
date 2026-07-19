import copy
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
        "final_size": {"min_utf8_bytes": 5, "max_utf8_bytes": 100},
        "hard_failures": [
            "forbidden_read", "forbidden_command", "forbidden_claim",
            "forbidden_write", "missing_final",
        ],
    }


def trace():
    return {
        "events": [
            {"type": "request", "content": "request"},
            {"type": "read", "path": "SKILL.md"},
            {"type": "command", "command": "arpent note new x", "output": "{}", "exit_code": 0},
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


if __name__ == "__main__":
    unittest.main()

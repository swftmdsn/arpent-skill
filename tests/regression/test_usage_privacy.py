from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import usage
from scripts.vault import init_vault
from tests.regression._support import run_cli


class UsagePrivacyRegressionTests(unittest.TestCase):
    def test_usage_event_contains_allowlisted_categories_not_private_arguments(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = init_vault(Path(temporary) / "vault", minimal=False).root
            private_values = (
                "Confidential launch title",
                "secret body sentence",
                "https://private.test/path",
            )
            result = run_cli(
                root,
                "note", "new", private_values[0],
                "--type", "production",
                "--status", "done",
                "--body", private_values[1],
                "--link", private_values[2],
                extra_env={"ARPENT_SESSION_ID": "opaque-session-42"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            event = json.loads(
                (root / usage.USAGE_RELPATH).read_text(encoding="utf-8").splitlines()[-1]
            )
            serialized = json.dumps(event)
            for value in private_values:
                self.assertNotIn(value, serialized)
            self.assertEqual(event["command"], "note new")
            self.assertEqual(event["subject_type"], "production")
            self.assertEqual(event["status_after"], "done")
            self.assertEqual(event["session_id"], "opaque-session-42")
            self.assertNotIn("argv", event)
            self.assertNotIn("error", event)

    def test_blocked_minimal_command_does_not_create_usage_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = init_vault(Path(temporary) / "vault", minimal=True).root
            result = run_cli(root, "status")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not available in minimal mode", result.stderr)
            self.assertFalse((root / usage.USAGE_RELPATH).exists())

    def test_reader_skips_malformed_and_semantically_incomplete_events(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=True)
            log = vault.root / usage.USAGE_RELPATH
            log.write_text(
                "\n".join((
                    '{"timestamp":"2030-01-01T00:00:00Z","command":"status","exit_code":0}',
                    '{"schema_version":2,"timestamp":"2030-01-02T00:00:00Z",'
                    '"command":"health","exit_code":0}',
                    '{"schema_version":2',
                )) + "\n",
                encoding="utf-8",
            )

            result = usage.read_usage(vault)

            self.assertEqual(len(result["events"]), 1)
            self.assertEqual(result["v1_count"], 1)
            self.assertEqual(result["v2_count"], 0)
            self.assertEqual(result["malformed_lines"], 2)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.e2e._support import initialize, json_result, require_success, run_cli


DERIVATIVES = (
    "06_indexes/index.json",
    "06_indexes/sidecar.json",
    "06_indexes/context_index.json",
    "06_indexes/databases/search.db",
)


class CaptureBoundaryE2ETests(unittest.TestCase):
    def test_ordinary_capture_has_no_ritual_post_capture_side_effects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = initialize(Path(temporary))
            require_success(run_cli(root, "project", "create", "Quiet Capture"))
            context = root / "01_projects/quiet-capture/_context.md"
            context_before = context.read_bytes()

            created = json_result(run_cli(
                root,
                "note", "new", "Boundary source",
                "--type", "reference",
                "--project", "quiet-capture",
                "--source", "captured",
                "--link", "https://example.test/boundary",
                "--body", "Captured without follow-up maintenance.",
                "--json",
            ))

            self.assertTrue((root / created["path"]).is_file())
            self.assertEqual(context.read_bytes(), context_before)
            for relpath in DERIVATIVES:
                self.assertFalse((root / relpath).exists(), relpath)
            self.assertFalse((root / "06_indexes/memory/MEMORY.md").exists())

            events = [
                json.loads(line)
                for line in (root / "06_indexes/logs/usage.log").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(events[-1]["command"], "note new")
            self.assertEqual(events[-1]["outcome"], "captured")
            self.assertTrue(events[-1]["changed"])
            self.assertTrue({"status", "index", "search"}.isdisjoint(
                event["command"] for event in events
            ))

    def test_fleeting_capture_is_append_only_without_per_entry_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = initialize(Path(temporary))

            first = json_result(run_cli(
                root, "note", "new", "First quick spark", "--type", "fleeting", "--json",
            ))
            second = json_result(run_cli(
                root, "note", "new", "Second quick spark", "--type", "fleeting", "--json",
            ))

            self.assertEqual(first["format"], "arpent-fleeting-result")
            self.assertEqual(first["path"], second["path"])
            self.assertNotIn("id", first)
            self.assertNotIn("frontmatter", first)
            self.assertRegex(first["captured_time"], r"^\d{2}:\d{2}$")
            stream = (root / first["path"]).read_text(encoding="utf-8")
            self.assertIn("First quick spark", stream)
            self.assertIn("Second quick spark", stream)
            self.assertEqual(len(list((root / "00_inbox/fleeting").glob("*.md"))), 1)
            for relpath in DERIVATIVES:
                self.assertFalse((root / relpath).exists(), relpath)


if __name__ == "__main__":
    unittest.main()

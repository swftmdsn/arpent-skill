from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import frontmatter
from tests.e2e._support import initialize, json_result, require_success, run_cli


class FullLifecycleE2ETests(unittest.TestCase):
    def test_project_capture_context_index_search_and_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = initialize(Path(temporary))

            require_success(run_cli(root, "project", "create", "Field Guide"))
            created = json_result(run_cli(
                root,
                "note", "new", "Launch rationale",
                "--type", "production",
                "--status", "active",
                "--project", "field-guide",
                "--body", "The copper-orbit decision remains reproducible.",
                "--json",
            ))
            note_path = root / created["path"]
            self.assertEqual(created["format"], "arpent-note-new-result")
            self.assertEqual(created["path"], "01_projects/field-guide/notes/launch_rationale.md")

            before_read = note_path.read_bytes()
            read = require_success(run_cli(root, "note", "read", created["id"]))
            self.assertIn("copper-orbit", read.stdout)
            self.assertEqual(note_path.read_bytes(), before_read)

            session = require_success(run_cli(
                root,
                "session", "end",
                "--project", "field-guide",
                "--summary", "Recorded the launch rationale.",
                "--decision", "Keep the copper-orbit decision.",
                "--next-step", "Validate the archived handoff.",
            ))
            self.assertIn("Updated context", session.stdout)
            context_path = root / "01_projects/field-guide/_context.md"
            context_text = context_path.read_text(encoding="utf-8")
            self.assertIn("Recorded the launch rationale.", context_text)
            self.assertFalse((root / "06_indexes/memory/MEMORY.md").exists())

            indexed = require_success(run_cli(root, "index"))
            self.assertIn("Indexed", indexed.stdout)
            pending = json_result(run_cli(
                root, "context", "pending", "--path", created["path"], "--json",
            ))
            note_pending = next(row for row in pending if row["path"] == created["path"])
            require_success(run_cli(
                root,
                "context", "set", created["path"],
                "--source-hash", note_pending["source_hash"],
                "--summary", "A reproducible launch decision and its rationale.",
                "--provider", "deterministic-test",
            ))
            summary = require_success(run_cli(
                root, "context", "show", created["path"], "--level", "l1",
            ))
            self.assertEqual(summary.stdout.strip(), "A reproducible launch decision and its rationale.")

            search = require_success(run_cli(root, "search", "copper-orbit"))
            self.assertIn(created["id"], search.stdout)
            status = require_success(run_cli(root, "status"))
            self.assertIn("Notes:", status.stdout)

            archived = require_success(run_cli(root, "archive", created["id"]))
            self.assertIn("Archived", archived.stdout)
            self.assertFalse(note_path.exists())
            matches = list((root / "04_archives").glob("*_q*/launch_rationale.md"))
            self.assertEqual(len(matches), 1)
            metadata, body = frontmatter.read_note(matches[0])
            self.assertEqual(metadata["id"], created["id"])
            self.assertEqual(metadata["status"], "archived")
            self.assertIn("copper-orbit", body)

            events = [
                json.loads(line)
                for line in (root / "06_indexes/logs/usage.log").read_text(encoding="utf-8").splitlines()
            ]
            commands = {event["command"] for event in events}
            self.assertTrue({"note new", "session end", "index", "search", "archive"} <= commands)


if __name__ == "__main__":
    unittest.main()

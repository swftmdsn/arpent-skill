from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import frontmatter
from tests.e2e._support import initialize, json_result, require_success, run_cli


class LinearToolsCronAndSweepE2ETests(unittest.TestCase):
    def test_linear_extraction_and_confirmed_dissolution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = initialize(Path(temporary))
            source = json_result(run_cli(
                root,
                "note", "new", "Reading thread",
                "--type", "linear", "--status", "maturing",
                "--body", "A useful passage.\n\nMore working notes.",
                "--json",
            ))
            source_path = root / source["path"]

            require_success(run_cli(
                root,
                "note", "extract", source["id"],
                "--type", "concept",
                "--title", "Actionability gradient",
                "--resource", "concepts",
                "--body", "Actionability increases with concrete context.",
                "--after", "A useful passage.",
                "--yes",
            ))
            child_path = root / "03_resources/concepts/actionability_gradient.md"
            child, child_body = frontmatter.read_note(child_path)
            updated, source_body = frontmatter.read_note(source_path)
            self.assertEqual(child["parent"], source["id"])
            self.assertEqual(child["source"], "derived")
            self.assertEqual(updated["extracted_to"], [child["id"]])
            self.assertIn("[[03_resources/concepts/actionability_gradient]]", source_body)
            self.assertEqual(child_body, "Actionability increases with concrete context.")

            before = source_path.read_bytes()
            refused = run_cli(root, "note", "dissolve", source["id"])
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("--yes", refused.stderr)
            self.assertEqual(source_path.read_bytes(), before)

            require_success(run_cli(root, "note", "dissolve", source["id"], "--yes"))
            archived = root / "04_archives/linear_notes/reading_thread.md"
            self.assertTrue(archived.is_file())
            self.assertFalse(source_path.exists())
            metadata, archived_body = frontmatter.read_note(archived)
            self.assertEqual(metadata["status"], "archived")
            self.assertEqual(metadata["extracted_to"], [child["id"]])
            self.assertIn("[[03_resources/concepts/actionability_gradient]]", archived_body)

    def test_tools_cron_preview_and_todo_sweep(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = initialize(Path(temporary))
            tools = require_success(run_cli(root, "tools", "list"))
            self.assertIn("todo", tools.stdout)
            shown = json_result(run_cli(root, "tools", "show", "todo"))
            self.assertEqual(shown["status"], "installed")
            self.assertTrue(shown["ephemeral"])

            cron_path = root / "06_indexes/cron.json"
            cron_data = {
                "version": "0.1.0",
                "jobs": [{
                    "id": "status-preview",
                    "enabled": True,
                    "schedule": "* * * * *",
                    "command": "arpent status",
                    "trust": "local-code",
                    "timeout_seconds": 10,
                    "notify_channel": "file",
                    "tags": ["test"],
                    "last_started": None,
                    "last_run": None,
                }],
            }
            cron_path.write_text(json.dumps(cron_data), encoding="utf-8")
            preview = require_success(run_cli(root, "cron", "run", "--tick", "--dry-run"))
            self.assertIn("status-preview: dry-run", preview.stdout)
            self.assertEqual(json.loads(cron_path.read_text(encoding="utf-8")), cron_data)
            self.assertIn("DRY RUN status-preview", (
                root / "06_indexes/logs/cron.log"
            ).read_text(encoding="utf-8"))

            added = json_result(run_cli(root, "todo", "add", "Sweep completed item", "--json"))
            todo_id = added["id"]
            require_success(run_cli(root, "todo", "done", todo_id))
            done = json_result(run_cli(root, "todo", "show", todo_id, "--json"))
            done_path = root / done["path"]
            metadata, body = frontmatter.read_note(done_path)
            metadata["modified"] = "01-01-2000-00-00"
            frontmatter.write_note(done_path, metadata, body)

            dry_sweep = require_success(run_cli(root, "sweep", "ephemeral", "--dry-run"))
            self.assertIn("DRY RUN", dry_sweep.stdout)
            self.assertTrue(done_path.is_file())
            require_success(run_cli(root, "sweep", "ephemeral", "--yes"))
            swept = json_result(run_cli(root, "todo", "show", todo_id, "--json"))
            self.assertEqual(swept["status"], "done")
            self.assertEqual(swept["lifecycle_status"], "archived")
            with sqlite3.connect(root / "06_indexes/databases/todo.db") as connection:
                traces = connection.execute(
                    "SELECT COUNT(*) FROM sweep_archive_history WHERE note_id = ?", (todo_id,),
                ).fetchone()[0]
            self.assertEqual(traces, 1)
            sweep_status = json_result(run_cli(root, "sweep", "status", "--json"))
            self.assertEqual(sweep_status["traced"], 1)


if __name__ == "__main__":
    unittest.main()

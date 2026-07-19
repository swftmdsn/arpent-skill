from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import frontmatter
from tests.e2e._support import initialize, json_result, require_success, run_cli


class TodoLifecycleE2ETests(unittest.TestCase):
    def test_complete_lifecycle_keeps_markdown_and_sqlite_consistent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = initialize(Path(temporary))
            added = json_result(run_cli(
                root,
                "todo", "add", "Validate launch plan",
                "--priority", "high",
                "--due", "31-12-2030-23-45",
                "--do", "30-12-2030-08-05",
                "--duration", "30m",
                "--project", "project-launch",
                "--optional",
                "--frequency", "once",
                "--list-order", "next",
                "--assignee", "person-owner",
                "--json",
            ))
            todo_id = added["id"]
            item = added["todo"]
            self.assertEqual(item["due_date"], "31-12-2030-23-45")
            self.assertEqual(item["do_date"], "30-12-2030-08-05")
            self.assertRegex(item["created_at"], r"^\d{2}-\d{2}-\d{4}-\d{2}-\d{2}$")
            self._assert_record(root, item, markdown_status="active")

            rows = json_result(run_cli(root, "todo", "list", "--json"))
            self.assertEqual([row["id"] for row in rows], [todo_id])
            shown = json_result(run_cli(root, "todo", "show", todo_id, "--json"))
            self.assertEqual(shown, item)

            require_success(run_cli(root, "todo", "block", todo_id, "--on", "todo-external"))
            blocked = json_result(run_cli(root, "todo", "show", todo_id, "--json"))
            self.assertEqual(blocked["status"], "waiting")
            self.assertEqual(blocked["depends_on_id"], "todo-external")
            self._assert_record(root, blocked, markdown_status="waiting")

            require_success(run_cli(root, "todo", "edit", todo_id, "--clear-dependency"))
            require_success(run_cli(
                root,
                "todo", "edit", todo_id,
                "--content", "Validate final launch plan",
                "--priority", "urgent",
                "--required",
            ))
            active = json_result(run_cli(root, "todo", "show", todo_id, "--json"))
            self.assertEqual(active["status"], "active")
            self.assertIsNone(active["depends_on_id"])
            self.assertFalse(active["is_optional"])
            self._assert_record(root, active, markdown_status="active")

            premature = run_cli(root, "todo", "archive", todo_id)
            self.assertNotEqual(premature.returncode, 0)
            self.assertIn("must be done", premature.stderr)
            require_success(run_cli(root, "todo", "done", todo_id))
            done = json_result(run_cli(root, "todo", "show", todo_id, "--json"))
            self._assert_record(root, done, markdown_status="done")

            require_success(run_cli(root, "todo", "archive", todo_id))
            archived = json_result(run_cli(root, "todo", "show", todo_id, "--json"))
            self.assertEqual(archived["status"], "done")
            self.assertEqual(archived["lifecycle_status"], "archived")
            self.assertIn("/todo/done/validate_final_launch_plan.md", archived["path"])
            self._assert_record(root, archived, markdown_status="archived")

            generic = run_cli(root, "note", "status", todo_id, "active")
            self.assertNotEqual(generic.returncode, 0)
            self.assertIn("tool-owned", generic.stderr)

    def _assert_record(self, root: Path, item: dict, *, markdown_status: str) -> None:
        metadata, body = frontmatter.read_note(root / item["path"])
        self.assertEqual(metadata["id"], item["id"])
        self.assertEqual(metadata["type"], "checklist")
        self.assertEqual(metadata["status"], markdown_status)
        self.assertEqual(body.strip(), item["content"])
        self.assertRegex(metadata["created"], r"^\d{2}-\d{2}-\d{4}-\d{2}-\d{2}$")

        with sqlite3.connect(root / "06_indexes/databases/todo.db") as connection:
            row = connection.execute(
                """
                SELECT content, priority, status, due_date, do_date, depends_on_id,
                       is_optional, created_at
                FROM todos WHERE id = ?
                """,
                (item["id"],),
            ).fetchone()
        self.assertEqual(row[0], item["content"])
        self.assertEqual(row[1], item["priority"])
        self.assertEqual(row[2], item["status"])
        self.assertEqual(row[3], "2030-12-31T23:45:00Z")
        self.assertEqual(row[4], "2030-12-30T08:05:00Z")
        self.assertEqual(row[5], item["depends_on_id"])
        self.assertEqual(bool(row[6]), item["is_optional"])
        self.assertRegex(row[7], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d+(?:\.\d+)?Z$")


if __name__ == "__main__":
    unittest.main()

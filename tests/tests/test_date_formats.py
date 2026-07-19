import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts import frontmatter
from scripts import todo
from scripts.vault import init_vault


class DateFormatTests(unittest.TestCase):
    def test_public_timestamp_is_utc_at_minute_precision(self):
        value = datetime(
            2026, 7, 19, 16, 5, 59,
            tzinfo=timezone(timedelta(hours=2)),
        )

        rendered = frontmatter.format_note_timestamp(value)

        self.assertEqual(rendered, "19-07-2026-14-05")
        self.assertEqual(
            frontmatter.parse_note_timestamp(rendered),
            datetime(2026, 7, 19, 14, 5, tzinfo=timezone.utc),
        )

    def test_legacy_note_timestamps_remain_readable(self):
        expected = datetime(2026, 7, 19, 14, 5, tzinfo=timezone.utc)

        self.assertEqual(
            frontmatter.parse_note_timestamp("19-07-2026T14:05:00Z"),
            expected,
        )
        self.assertEqual(
            frontmatter.parse_note_timestamp("2026-07-19T14:05:00Z"),
            expected,
        )
        self.assertEqual(
            frontmatter.parse_note_timestamp("19-07-2026"),
            datetime(2026, 7, 19, tzinfo=timezone.utc),
        )

    def test_todo_uses_public_timestamp_and_sortable_internal_value(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)

            item = todo.add_todo(
                vault,
                "Timed task",
                due_date="19-07-2026-14-05",
            )

            self.assertEqual(item["due_date"], "19-07-2026-14-05")
            with sqlite3.connect(vault.root / todo.DATABASE_RELPATH) as connection:
                stored = connection.execute(
                    "SELECT due_date FROM todos WHERE id = ?", (item["id"],)
                ).fetchone()[0]
            self.assertEqual(stored, "2026-07-19T14:05:00Z")

            with self.assertRaisesRegex(ValueError, frontmatter.NOTE_TIMESTAMP_LABEL):
                todo.add_todo(vault, "Date only", due_date="19-07-2026")
            with self.assertRaisesRegex(ValueError, frontmatter.NOTE_TIMESTAMP_LABEL):
                todo.add_todo(vault, "Invalid hour", due_date="19-07-2026-24-00")

    def test_v2_todo_dates_migrate_to_utc_midnight(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            database = vault.root / todo.DATABASE_RELPATH
            with sqlite3.connect(database) as connection:
                connection.executescript(
                    """
                    CREATE TABLE todos (
                      id TEXT PRIMARY KEY, content TEXT NOT NULL, priority TEXT,
                      status TEXT NOT NULL, due_date TEXT, do_date TEXT, duration TEXT,
                      linked_project_id TEXT, depends_on_id TEXT,
                      is_optional INTEGER NOT NULL DEFAULT 0, frequency TEXT,
                      list_order TEXT, assignee_id TEXT, created_at TEXT NOT NULL
                    );
                    CREATE INDEX todos_status_idx ON todos (status);
                    CREATE INDEX todos_due_date_idx ON todos (due_date);
                    CREATE INDEX todos_do_date_idx ON todos (do_date);
                    CREATE INDEX todos_linked_project_idx ON todos (linked_project_id);
                    CREATE INDEX todos_depends_on_idx ON todos (depends_on_id);
                    CREATE INDEX todos_assignee_idx ON todos (assignee_id);
                    CREATE INDEX todos_list_order_idx ON todos (list_order);
                    CREATE TRIGGER todos_created_at_immutable
                    BEFORE UPDATE OF created_at ON todos BEGIN SELECT RAISE(ABORT, 'immutable'); END;
                    INSERT INTO todos (
                      id, content, status, due_date, do_date, created_at
                    ) VALUES (
                      'todo-20260719-a', 'Existing task', 'active',
                      '2026-07-20', '2026-07-19', '2026-07-01T00:00:00Z'
                    );
                    PRAGMA user_version = 2;
                    """
                )

            todo.ensure_database(vault)

            with sqlite3.connect(database) as connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                dates = connection.execute(
                    "SELECT due_date, do_date FROM todos WHERE id = 'todo-20260719-a'"
                ).fetchone()
            self.assertEqual(version, todo.SCHEMA_VERSION)
            self.assertEqual(dates, ("2026-07-20T00:00:00Z", "2026-07-19T00:00:00Z"))


if __name__ == "__main__":
    unittest.main()

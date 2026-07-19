from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import todo
from tests.regression._support import initialized


V2_SCHEMA = """
CREATE TABLE todos (
  id TEXT PRIMARY KEY,
  content TEXT NOT NULL,
  priority TEXT,
  status TEXT NOT NULL,
  due_date TEXT,
  do_date TEXT,
  duration TEXT,
  linked_project_id TEXT,
  depends_on_id TEXT,
  is_optional INTEGER NOT NULL DEFAULT 0 CHECK (is_optional IN (0, 1)),
  frequency TEXT,
  list_order TEXT,
  assignee_id TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX todos_status_idx ON todos (status);
CREATE INDEX todos_due_date_idx ON todos (due_date);
CREATE INDEX todos_do_date_idx ON todos (do_date);
CREATE INDEX todos_linked_project_idx ON todos (linked_project_id);
CREATE INDEX todos_depends_on_idx ON todos (depends_on_id);
CREATE INDEX todos_assignee_idx ON todos (assignee_id);
CREATE INDEX todos_list_order_idx ON todos (list_order);
CREATE TRIGGER todos_created_at_immutable
BEFORE UPDATE OF created_at ON todos
FOR EACH ROW
WHEN NEW.created_at IS NOT OLD.created_at
BEGIN
  SELECT RAISE(ABORT, 'todos.created_at is immutable');
END;
PRAGMA user_version = 2;
"""


class DatabaseResilienceRegressionTests(unittest.TestCase):
    def test_v2_database_migrates_dates_to_current_minute_timestamps(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            database = vault.root / todo.DATABASE_RELPATH
            with sqlite3.connect(database) as connection:
                connection.executescript(V2_SCHEMA)
                connection.execute(
                    """
                    INSERT INTO todos (
                      id, content, status, due_date, do_date, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "todo-20300101-a", "Migrate me", "active",
                        "2030-02-03", "2030-02-02", "2030-01-01T10:11:12Z",
                    ),
                )

            todo.ensure_database(vault)

            with sqlite3.connect(database) as connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                row = connection.execute(
                    "SELECT due_date, do_date, created_at FROM todos"
                ).fetchone()
            self.assertEqual(version, todo.SCHEMA_VERSION)
            self.assertEqual(row, (
                "2030-02-03T00:00:00Z",
                "2030-02-02T00:00:00Z",
                "2030-01-01T10:11:12Z",
            ))

    def test_unsupported_schema_is_rejected_without_migration(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            database = vault.root / todo.DATABASE_RELPATH
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE legacy (value TEXT)")
                connection.execute("INSERT INTO legacy VALUES ('preserved')")
                connection.execute("PRAGMA user_version = 1")

            with self.assertRaisesRegex(ValueError, "schema version 1"):
                todo.ensure_database(vault)

            with sqlite3.connect(database) as connection:
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT value FROM legacy").fetchone()[0], "preserved")

    def test_corrupt_database_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            database = vault.root / todo.DATABASE_RELPATH
            corrupt = b"not a sqlite database\x00private"
            database.write_bytes(corrupt)

            with self.assertRaises(sqlite3.DatabaseError):
                todo.ensure_database(vault)

            self.assertEqual(database.read_bytes(), corrupt)

    def test_current_version_with_foreign_trigger_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            database = todo.ensure_database(vault)
            with sqlite3.connect(database) as connection:
                connection.executescript(
                    """
                    CREATE TRIGGER foreign_todo_trigger
                    AFTER INSERT ON todos
                    BEGIN
                      DELETE FROM todos WHERE id = NEW.id;
                    END;
                    """
                )

            with self.assertRaisesRegex(
                ValueError, f"does not match schema version {todo.SCHEMA_VERSION}",
            ):
                todo.ensure_database(vault)


if __name__ == "__main__":
    unittest.main()

-- Version 2 schema for 06_indexes/databases/todo.db.
-- Selection values are tool-defined TEXT keys so the available options can
-- evolve without a database migration.
-- Relation columns contain stable Arpent IDs. They are intentionally soft
-- references because their targets are Markdown objects outside this database.

CREATE TABLE IF NOT EXISTS todos (
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
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  CHECK (
    due_date IS NULL OR (
      length(due_date) = 10
      AND due_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
      AND date(due_date) = due_date
    )
  ),
  CHECK (
    do_date IS NULL OR (
      length(do_date) = 10
      AND do_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
      AND date(do_date) = do_date
    )
  )
);

CREATE INDEX IF NOT EXISTS todos_status_idx ON todos (status);
CREATE INDEX IF NOT EXISTS todos_due_date_idx ON todos (due_date);
CREATE INDEX IF NOT EXISTS todos_do_date_idx ON todos (do_date);
CREATE INDEX IF NOT EXISTS todos_linked_project_idx ON todos (linked_project_id);
CREATE INDEX IF NOT EXISTS todos_depends_on_idx ON todos (depends_on_id);
CREATE INDEX IF NOT EXISTS todos_assignee_idx ON todos (assignee_id);
CREATE INDEX IF NOT EXISTS todos_list_order_idx ON todos (list_order);

CREATE TRIGGER IF NOT EXISTS todos_created_at_immutable
BEFORE UPDATE OF created_at ON todos
FOR EACH ROW
WHEN NEW.created_at IS NOT OLD.created_at
BEGIN
  SELECT RAISE(ABORT, 'todos.created_at is immutable');
END;

PRAGMA user_version = 2;

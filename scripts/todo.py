"""SQLite-backed todo operations with durable Markdown records."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from . import file_transaction
from . import frontmatter as fmlib
from . import notes as notes_mod
from . import routing


_REFERENCE_CONNECT = sqlite3.connect
DATABASE_RELPATH = "06_indexes/databases/todo.db"
TRANSACTION_RELPATH = "06_indexes/logs/todo-transaction.json"
SCHEMA_PATH = Path(__file__).with_name("todo_schema.sql")
TODO_ROOT = "02_areas/area__perso__todo__active"
TODO_STATUSES = ("active", "waiting", "done")
SCHEMA_VERSION = 3
SCHEMA_OBJECT_NAMES = (
    "todos",
    "todos_assignee_idx",
    "todos_created_at_immutable",
    "todos_depends_on_idx",
    "todos_do_date_idx",
    "todos_due_date_idx",
    "todos_linked_project_idx",
    "todos_list_order_idx",
    "todos_status_idx",
)
ALLOWED_AUXILIARY_SCHEMA_OBJECTS = {"sweep_archive_history"}
SCHEMA_COLUMNS = (
    "id",
    "content",
    "priority",
    "status",
    "due_date",
    "do_date",
    "duration",
    "linked_project_id",
    "depends_on_id",
    "is_optional",
    "frequency",
    "list_order",
    "assignee_id",
    "created_at",
)
EDITABLE_COLUMNS = SCHEMA_COLUMNS[1:-1]
UNSET = object()


def is_todo_id(value) -> bool:
    return isinstance(value, str) and value.startswith("todo-")


def schema_text() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def ensure_database(vault) -> Path:
    """Create or validate todo.db and return its safe path."""
    with vault.exclusive_lock("mutations"):
        path = vault.safe_output_path(DATABASE_RELPATH)
        connection = sqlite3.connect(path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            _initialize_connection(connection)
            _recover_transaction(vault, connection)
        finally:
            connection.close()
        return path


@contextmanager
def _connect(vault):
    with vault.exclusive_lock("mutations"):
        path = vault.safe_output_path(DATABASE_RELPATH)
        connection = sqlite3.connect(path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            _initialize_connection(connection)
            _recover_transaction(vault, connection)
            yield connection
        finally:
            connection.close()


def _initialize_connection(connection) -> None:
    connection.execute("PRAGMA busy_timeout = 5000")
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version == 0:
        existing = connection.execute(
            "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' LIMIT 1"
        ).fetchone()
        if existing is not None:
            raise ValueError(
                f"Unsupported unversioned todo database; expected schema version {SCHEMA_VERSION}."
            )
        connection.executescript(schema_text())
    elif version == 2:
        _migrate_v2_to_v3(connection)
    elif version != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported todo database schema version {version}; expected {SCHEMA_VERSION}."
        )
    columns = _table_columns(connection)
    if columns != list(SCHEMA_COLUMNS):
        raise ValueError(f"todo.db does not match schema version {SCHEMA_VERSION}.")
    if _schema_signature(connection) != _expected_schema_signature():
        raise ValueError(f"todo.db does not match schema version {SCHEMA_VERSION}.")
    if _unexpected_schema_objects(connection):
        raise ValueError(f"todo.db does not match schema version {SCHEMA_VERSION}.")
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported todo database schema version {version}; expected {SCHEMA_VERSION}."
        )


def _migrate_v2_to_v3(connection) -> None:
    """Add UTC minute precision to todo dates while preserving v2 values."""
    if _table_columns(connection) != list(SCHEMA_COLUMNS) or _unexpected_schema_objects(connection):
        raise ValueError("todo.db does not match schema version 2.")
    actual_objects = {
        (row[0], row[1])
        for row in connection.execute(
            "SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        )
        if row[1] not in ALLOWED_AUXILIARY_SCHEMA_OBJECTS
    }
    expected_objects = {
        ("table", "todos"),
        *(("index", name) for name in SCHEMA_OBJECT_NAMES if name.endswith("_idx")),
        ("trigger", "todos_created_at_immutable"),
    }
    if actual_objects != expected_objects:
        raise ValueError("todo.db does not match schema version 2.")

    columns = ", ".join(SCHEMA_COLUMNS)
    migrated_values = ", ".join(
        (
            f"CASE WHEN {column} IS NULL THEN NULL "
            f"ELSE {column} || 'T00:00:00Z' END AS {column}"
            if column in {"due_date", "do_date"}
            else column
        )
        for column in SCHEMA_COLUMNS
    )
    version_pragma = f"PRAGMA user_version = {SCHEMA_VERSION};"
    current_schema = schema_text()
    if not current_schema.rstrip().endswith(version_pragma):
        raise RuntimeError("todo schema is missing its version pragma")
    schema_without_version = current_schema[:current_schema.rfind(version_pragma)]
    try:
        connection.executescript(
            f"""
            BEGIN IMMEDIATE;
            ALTER TABLE todos RENAME TO todos_v2;
            CREATE TEMP TABLE todos_v3_values AS
            SELECT {migrated_values} FROM todos_v2;
            DROP TABLE todos_v2;
            {schema_without_version}
            INSERT INTO todos ({columns})
            SELECT {columns} FROM todos_v3_values;
            DROP TABLE todos_v3_values;
            {version_pragma}
            COMMIT;
            """
        )
    except sqlite3.Error:
        connection.rollback()
        raise


def _table_columns(connection) -> list[str]:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'todos'"
    ).fetchone()
    if not exists:
        return []
    return [row[1] for row in connection.execute("PRAGMA table_info(todos)")]


def _schema_signature(connection) -> tuple:
    placeholders = ", ".join("?" for _ in SCHEMA_OBJECT_NAMES)
    return tuple(
        tuple(row)
        for row in connection.execute(
            f"""
            SELECT type, name, sql
            FROM sqlite_master
            WHERE name IN ({placeholders})
            ORDER BY type, name
            """,
            SCHEMA_OBJECT_NAMES,
        )
    )


def _unexpected_schema_objects(connection) -> list[str]:
    allowed = (*SCHEMA_OBJECT_NAMES, *sorted(ALLOWED_AUXILIARY_SCHEMA_OBJECTS))
    placeholders = ", ".join("?" for _ in allowed)
    return [
        row[0]
        for row in connection.execute(
            f"""
            SELECT name FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%'
              AND name NOT IN ({placeholders})
            ORDER BY name
            """,
            allowed,
        )
    ]


@lru_cache(maxsize=1)
def _expected_schema_signature() -> tuple:
    reference = _REFERENCE_CONNECT(":memory:")
    try:
        reference.executescript(schema_text())
        return _schema_signature(reference)
    finally:
        reference.close()


def _start_transaction(vault, todo_id: str, expected_db: dict, relpaths: list[str], *,
                       commit_detectable=True, expected_files=None) -> dict:
    expected_files = expected_files or {}
    snapshots = [
        _snapshot_file(
            vault, relpath, expected_content=expected_files.get(relpath),
        )
        for relpath in dict.fromkeys(relpaths)
    ]
    return file_transaction.prepare(
        vault,
        TRANSACTION_RELPATH,
        snapshots,
        metadata={
            "todo_id": todo_id,
            "expected_db": expected_db,
            "commit_detectable": commit_detectable,
        },
    )


def _commit_transaction(vault, journal: dict) -> None:
    file_transaction.commit(vault, TRANSACTION_RELPATH, journal)


def _rollback_transaction(vault, journal: dict) -> None:
    file_transaction.rollback(vault, TRANSACTION_RELPATH, journal)


def _recover_transaction(vault, connection) -> None:
    vault.refuse_foreign_transactions(TRANSACTION_RELPATH)
    try:
        file_transaction.recover(
            vault,
            TRANSACTION_RELPATH,
            prepared_is_committed=lambda journal: _database_commit_detected(
                connection, journal,
            ),
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"Cannot recover interrupted todo transaction: {exc}") from exc


def _database_commit_detected(connection, journal: dict) -> bool:
    """Keep this SQLite-specific commit decision local to todo operations."""
    if not journal.get("commit_detectable"):
        return False
    row = connection.execute(
        "SELECT * FROM todos WHERE id = ?", (journal.get("todo_id"),)
    ).fetchone()
    expected = journal.get("expected_db")
    if not isinstance(expected, dict):
        raise ValueError("invalid todo transaction database state")
    return row is not None and all(row[key] == value for key, value in expected.items())


def _snapshot_file(vault, relpath: str, *, expected_content=None) -> dict:
    return file_transaction.snapshot_file(
        vault, relpath, expected_content=expected_content,
    )


def _restore_files(vault, snapshots: list[dict]) -> None:
    file_transaction.restore_files(vault, snapshots)


def _remove_transaction(vault) -> None:
    file_transaction.remove_journal(vault, TRANSACTION_RELPATH)


def add_todo(
    vault,
    content,
    *,
    priority=None,
    status=None,
    due_date=None,
    do_date=None,
    duration=None,
    linked_project_id=None,
    depends_on_id=None,
    is_optional=False,
    frequency=None,
    list_order=None,
    assignee_id=None,
    planned_id=None,
    expected_destination=None,
) -> dict:
    content = _required_text(content, "content")
    priority = _optional_text(priority, "priority")
    due_date = _optional_date(due_date, "due date")
    do_date = _optional_date(do_date, "do date")
    duration = _optional_text(duration, "duration")
    linked_project_id = _optional_text(linked_project_id, "linked project")
    depends_on_id = _optional_text(depends_on_id, "dependency")
    frequency = _optional_text(frequency, "frequency")
    list_order = _optional_text(list_order, "list order")
    assignee_id = _optional_text(assignee_id, "assignee")
    status = status or ("waiting" if depends_on_id else "active")
    _validate_status(status)
    if not isinstance(is_optional, bool):
        raise ValueError("optional must be a boolean")

    with _connect(vault) as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing_ids = vault.existing_ids()
        existing_ids.update(row[0] for row in connection.execute("SELECT id FROM todos"))
        if planned_id is not None:
            if planned_id in existing_ids:
                raise ValueError("Todo creation plan is stale; review a fresh dry run.")
            todo_id = planned_id
        else:
            todo_id = routing.new_id("todo", existing_ids)
        if depends_on_id == todo_id:
            raise ValueError("A todo cannot depend on itself.")

        frontmatter = notes_mod.build_frontmatter(
            vault,
            title=content,
            ntype="checklist",
            status=status,
            area="todo",
            source="generated",
            author="user",
        )
        frontmatter["id"] = todo_id
        relpath = _record_relpath(status, frontmatter["title"])
        if expected_destination is not None and relpath != expected_destination:
            raise ValueError("Todo destination changed after planning; review a fresh dry run.")
        expected_db = {
            "content": content,
            "priority": priority,
            "status": status,
            "due_date": due_date,
            "do_date": do_date,
            "duration": duration,
            "linked_project_id": linked_project_id,
            "depends_on_id": depends_on_id,
            "is_optional": int(is_optional),
            "frequency": frequency,
            "list_order": list_order,
            "assignee_id": assignee_id,
        }
        record_content = fmlib.compose_note(frontmatter, content + "\n")
        journal = _start_transaction(
            vault,
            todo_id,
            expected_db,
            [relpath],
            expected_files={relpath: record_content},
        )
        try:
            created_path = vault.atomic_create_text(relpath, record_content)
            connection.execute(
                """
                INSERT INTO todos (
                  id, content, priority, status, due_date, do_date,
                  duration, linked_project_id, depends_on_id, is_optional,
                  frequency, list_order, assignee_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    todo_id,
                    content,
                    priority,
                    status,
                    due_date,
                    do_date,
                    duration,
                    linked_project_id,
                    depends_on_id,
                    int(is_optional),
                    frequency,
                    list_order,
                    assignee_id,
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            _rollback_transaction(vault, journal)
            raise
        _commit_transaction(vault, journal)
        row = _get_row(connection, todo_id)
    return _decorate(row, (created_path, frontmatter, content + "\n"), vault)


def plan_todo_add(
    vault,
    content,
    *,
    priority=None,
    status=None,
    due_date=None,
    do_date=None,
    duration=None,
    linked_project_id=None,
    depends_on_id=None,
    is_optional=False,
    frequency=None,
    list_order=None,
    assignee_id=None,
    expected_plan_hash=None,
) -> dict:
    """Build a complete todo-add plan without opening or creating todo.db."""
    content = _required_text(content, "content")
    values = {
        "content": content,
        "priority": _optional_text(priority, "priority"),
        "status": status or ("waiting" if depends_on_id else "active"),
        "due_date": _optional_date(due_date, "due date"),
        "do_date": _optional_date(do_date, "do date"),
        "duration": _optional_text(duration, "duration"),
        "linked_project_id": _optional_text(linked_project_id, "linked project"),
        "depends_on_id": _optional_text(depends_on_id, "dependency"),
        "is_optional": is_optional,
        "frequency": _optional_text(frequency, "frequency"),
        "list_order": _optional_text(list_order, "list order"),
        "assignee_id": _optional_text(assignee_id, "assignee"),
    }
    _validate_status(values["status"])
    if not isinstance(is_optional, bool):
        raise ValueError("optional must be a boolean")
    existing_ids = vault.existing_ids()
    database_path = vault.root / DATABASE_RELPATH
    if database_path.exists() or database_path.is_symlink():
        safe_database = vault.safe_source_path(DATABASE_RELPATH)
        connection = None
        try:
            connection = sqlite3.connect(f"{safe_database.as_uri()}?mode=ro", uri=True)
            existing_ids.update(row[0] for row in connection.execute("SELECT id FROM todos"))
        except sqlite3.Error as exc:
            raise ValueError(f"Cannot inspect existing todo IDs: {exc}") from exc
        finally:
            if connection is not None:
                connection.close()
    todo_id = routing.new_id("todo", existing_ids)
    if values["depends_on_id"] == todo_id:
        raise ValueError("A todo cannot depend on itself.")
    frontmatter = notes_mod.build_frontmatter(
        vault,
        title=content,
        ntype="checklist",
        status=values["status"],
        area="todo",
        source="generated",
        author="user",
    )
    frontmatter["id"] = todo_id
    relpath = _record_relpath(values["status"], frontmatter["title"])
    plan = {
        "format": "arpent-todo-add-plan",
        "version": 1,
        "todo": {"id": todo_id, **values},
        "frontmatter": frontmatter,
        "destination_path": relpath,
        "side_effects": [f"create:{relpath}", f"insert:{DATABASE_RELPATH}"],
    }
    plan["plan_sha256"] = _todo_add_plan_hash(plan)
    if expected_plan_hash is not None and expected_plan_hash != plan["plan_sha256"]:
        raise ValueError("Todo creation plan no longer matches --plan-hash; review a fresh dry run.")
    return plan


def _todo_add_plan_hash(plan: dict) -> str:
    todo = dict(plan["todo"])
    frontmatter = dict(plan["frontmatter"])
    for field in ("created", "modified"):
        frontmatter.pop(field, None)
    payload = {
        "todo": todo,
        "frontmatter": frontmatter,
        "destination_path": plan["destination_path"],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def public_todo_add_plan(plan: dict) -> dict:
    public = json.loads(json.dumps(plan))
    public["todo"]["due_date"] = _display_date(public["todo"]["due_date"])
    public["todo"]["do_date"] = _display_date(public["todo"]["do_date"])
    public["frontmatter"].pop("created", None)
    public["frontmatter"].pop("modified", None)
    public["apply_generated_fields"] = ["created", "modified", "created_at"]
    return public


def apply_todo_add(vault, plan: dict) -> dict:
    """Apply the normalized values and ID from a reviewed todo-add plan."""
    values = plan["todo"]
    return add_todo(
        vault,
        values["content"],
        priority=values["priority"],
        status=values["status"],
        due_date=_display_date(values["due_date"]),
        do_date=_display_date(values["do_date"]),
        duration=values["duration"],
        linked_project_id=values["linked_project_id"],
        depends_on_id=values["depends_on_id"],
        is_optional=values["is_optional"],
        frequency=values["frequency"],
        list_order=values["list_order"],
        assignee_id=values["assignee_id"],
        planned_id=values["id"],
        expected_destination=plan["destination_path"],
    )


def list_todos(vault, *, status=None, include_archived=False) -> list[dict]:
    if status is not None:
        _validate_status(status)
    with _connect(vault) as connection:
        if status:
            rows = connection.execute(
                """
                SELECT * FROM todos WHERE status = ?
                ORDER BY COALESCE(do_date, due_date, '9999-12-31T23:59:59Z'),
                         COALESCE(list_order, ''), created_at, id
                """,
                (status,),
            ).fetchall()
        elif include_archived:
            rows = connection.execute(
                """
                SELECT * FROM todos
                ORDER BY COALESCE(do_date, due_date, '9999-12-31T23:59:59Z'),
                         COALESCE(list_order, ''), created_at, id
                """
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT * FROM todos WHERE status IN ('active', 'waiting')
                ORDER BY COALESCE(do_date, due_date, '9999-12-31T23:59:59Z'),
                         COALESCE(list_order, ''), created_at, id
                """
            ).fetchall()

    records = _todo_records(vault)
    result = []
    for row in rows:
        record = _unique_record(records, row["id"], required=False)
        item = _decorate(row, record, vault)
        if not include_archived and item["lifecycle_status"] == "archived":
            continue
        result.append(item)
    return result


def show_todo(vault, todo_id) -> dict:
    with _connect(vault) as connection:
        row = _get_row(connection, todo_id)
    record = _unique_record(_todo_records(vault), todo_id, required=False)
    return _decorate(row, record, vault)


def edit_todo(
    vault,
    todo_id,
    *,
    content=UNSET,
    priority=UNSET,
    status=UNSET,
    due_date=UNSET,
    do_date=UNSET,
    duration=UNSET,
    linked_project_id=UNSET,
    depends_on_id=UNSET,
    is_optional=UNSET,
    frequency=UNSET,
    list_order=UNSET,
    assignee_id=UNSET,
) -> dict:
    requested = {
        "content": content,
        "priority": priority,
        "status": status,
        "due_date": due_date,
        "do_date": do_date,
        "duration": duration,
        "linked_project_id": linked_project_id,
        "depends_on_id": depends_on_id,
        "is_optional": is_optional,
        "frequency": frequency,
        "list_order": list_order,
        "assignee_id": assignee_id,
    }
    supplied = {key: value for key, value in requested.items() if value is not UNSET}
    if not supplied:
        raise ValueError("No todo changes requested.")

    with _connect(vault) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = _get_row(connection, todo_id)
        record = _unique_record(_todo_records(vault), todo_id, required=True)
        source_path, frontmatter, body = record
        _ensure_mutable_record(todo_id, row, frontmatter)
        original_text = source_path.read_text(encoding="utf-8")
        values = _row_dict(row)

        for key, value in supplied.items():
            if key == "content":
                values[key] = _required_text(value, "content")
            elif key in {"due_date", "do_date"}:
                values[key] = _optional_date(value, key.replace("_", " "))
            elif key == "status":
                _validate_status(value)
                values[key] = value
            elif key == "is_optional":
                if not isinstance(value, bool):
                    raise ValueError("optional must be a boolean")
                values[key] = value
            else:
                values[key] = _optional_text(value, key.replace("_id", "").replace("_", " "))

        if values["depends_on_id"] == todo_id:
            raise ValueError("A todo cannot depend on itself.")
        if depends_on_id is None and row["status"] == "waiting" and status is UNSET:
            values["status"] = "active"

        changed = {
            key: values[key]
            for key in EDITABLE_COLUMNS
            if values[key] != _row_dict(row)[key]
        }
        if not changed:
            connection.rollback()
            result = _decorate(row, record, vault)
            result["changed"] = False
            return result

        updated_frontmatter = dict(frontmatter)
        updated_frontmatter["status"] = values["status"]
        if "content" in changed:
            updated_frontmatter["title"] = routing.slugify(values["content"])
            body = values["content"] + "\n"
        updated_frontmatter["modified"] = fmlib.now_note_timestamp()
        notes_mod.validate_frontmatter_values(updated_frontmatter)
        destination_rel = _record_relpath(
            updated_frontmatter["status"], updated_frontmatter["title"]
        )
        destination = _replace_record_and_update(
            vault,
            connection,
            source_path,
            original_text,
            destination_rel,
            updated_frontmatter,
            body,
            todo_id,
            changed,
        )
        updated_row = _get_row(connection, todo_id)
    result = _decorate(updated_row, (destination, updated_frontmatter, body), vault)
    result["changed"] = True
    return result


def done_todo(vault, todo_id) -> dict:
    return edit_todo(vault, todo_id, status="done")


def defer_todo(vault, todo_id, to_date) -> dict:
    return edit_todo(vault, todo_id, do_date=to_date)


def block_todo(vault, todo_id, dependency_id) -> dict:
    dependency_id = _required_text(dependency_id, "dependency")
    if dependency_id == todo_id:
        raise ValueError("A todo cannot depend on itself.")
    return edit_todo(
        vault,
        todo_id,
        depends_on_id=dependency_id,
        status="waiting",
    )


def archive_todo(vault, todo_id, *, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    with _connect(vault) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = _get_row(connection, todo_id)
        record = _unique_record(_todo_records(vault), todo_id, required=True)
        source_path, frontmatter, body = record
        if frontmatter.get("status") == "archived":
            raise ValueError(f"Todo '{todo_id}' is already archived.")
        if row["status"] != "done" or frontmatter.get("status") != "done":
            raise ValueError(f"Todo '{todo_id}' must be done before archival.")

        original_text = source_path.read_text(encoding="utf-8")
        source_rel = source_path.relative_to(vault.root).as_posix()
        quarter = f"{now.year}_q{(now.month - 1) // 3 + 1}"
        destination_rel = f"04_archives/{quarter}/todo/done/{source_path.name}"
        destination = vault.safe_output_path(destination_rel)
        if destination.exists():
            raise ValueError(f"Todo archive destination already exists: {destination_rel}")

        archived = dict(frontmatter)
        archived["status"] = "archived"
        archived["modified"] = fmlib.format_note_timestamp(now)
        archived["archived_at"] = archived["modified"]
        archived["archived_from"] = source_rel
        notes_mod.validate_frontmatter_values(archived)
        archived_content = fmlib.compose_note(archived, body)
        journal = _start_transaction(
            vault,
            todo_id,
            {},
            [source_rel, destination_rel],
            commit_detectable=False,
            expected_files={
                source_rel: archived_content,
                destination_rel: archived_content,
            },
        )
        try:
            if source_path.read_text(encoding="utf-8") != original_text:
                raise ValueError("Todo changed during archival; retry with the current record.")
            vault.atomic_write_text(source_rel, archived_content)
            vault.atomic_move_no_replace(source_rel, destination_rel)
            connection.commit()
        except Exception:
            connection.rollback()
            _rollback_transaction(vault, journal)
            raise
        _commit_transaction(vault, journal)
    return _decorate(row, (destination, archived, body), vault)


def _replace_record_and_update(
    vault,
    connection,
    source_path,
    original_text,
    destination_rel,
    frontmatter,
    body,
    todo_id,
    changed,
):
    source_rel = source_path.relative_to(vault.root).as_posix()
    destination = vault.safe_output_path(destination_rel)
    moved = destination_rel != source_rel
    if moved and destination.exists():
        raise ValueError(f"A todo record already exists at {destination_rel}.")
    if source_path.read_text(encoding="utf-8") != original_text:
        raise ValueError("Todo changed during update; retry with the current record.")

    content = fmlib.compose_note(frontmatter, body)
    journal = _start_transaction(
        vault,
        todo_id,
        {
            column: int(value) if column == "is_optional" else value
            for column, value in changed.items()
        },
        [source_rel, destination_rel] if moved else [source_rel],
        expected_files={
            source_rel: content,
            **({destination_rel: content} if moved else {}),
        },
    )
    try:
        vault.atomic_write_text(source_rel, content)
        if moved:
            vault.atomic_move_no_replace(source_rel, destination_rel)

        assignments = ", ".join(f"{column} = ?" for column in changed)
        parameters = [int(value) if column == "is_optional" else value for column, value in changed.items()]
        connection.execute(
            f"UPDATE todos SET {assignments} WHERE id = ?",
            (*parameters, todo_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        _rollback_transaction(vault, journal)
        raise
    _commit_transaction(vault, journal)
    return destination


def _get_row(connection, todo_id):
    row = connection.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    if row is None:
        raise ValueError(f"No todo with id '{todo_id}'.")
    return row


def validate_database_status(vault, todo_id, expected_status) -> None:
    """Reject lifecycle automation when the Markdown and SQLite states differ."""
    with _connect(vault) as connection:
        row = _get_row(connection, todo_id)
    if row["status"] != expected_status:
        raise ValueError(
            f"Todo '{todo_id}' is out of sync: SQLite={row['status']}, "
            f"Markdown={expected_status}."
        )


def _todo_records(vault) -> dict[str, list[tuple]]:
    records = {}
    for path, frontmatter, body in vault.iter_notes():
        todo_id = frontmatter.get("id")
        if is_todo_id(todo_id):
            records.setdefault(todo_id, []).append((path, frontmatter, body))
    return records


def _unique_record(records, todo_id, *, required):
    matches = records.get(todo_id) or []
    if len(matches) > 1:
        raise ValueError(f"Duplicate Markdown records for todo '{todo_id}'.")
    if not matches:
        if required:
            raise ValueError(f"Todo '{todo_id}' has no Markdown record.")
        return None
    return matches[0]


def _ensure_mutable_record(todo_id, row, frontmatter) -> None:
    lifecycle_status = frontmatter.get("status")
    if lifecycle_status == "archived":
        raise ValueError(f"Todo '{todo_id}' is archived and immutable.")
    if lifecycle_status != row["status"]:
        raise ValueError(
            f"Todo '{todo_id}' is out of sync: SQLite={row['status']}, "
            f"Markdown={lifecycle_status}."
        )


def _decorate(row, record, vault) -> dict:
    result = _row_dict(row)
    result["due_date"] = _display_date(result["due_date"])
    result["do_date"] = _display_date(result["do_date"])
    if result["created_at"]:
        result["created_at"] = fmlib.format_note_timestamp(
            datetime.fromisoformat(result["created_at"].replace("Z", "+00:00"))
        )
    if record is None:
        result.update({"lifecycle_status": "missing-markdown", "path": None})
    else:
        path, frontmatter, _ = record
        result.update({
            "lifecycle_status": frontmatter.get("status"),
            "path": path.relative_to(vault.root).as_posix(),
        })
    return result


def _row_dict(row) -> dict:
    result = {key: row[key] for key in SCHEMA_COLUMNS}
    result["is_optional"] = bool(result["is_optional"])
    return result


def _record_relpath(status, title) -> str:
    _validate_status(status)
    return f"{TODO_ROOT}/{status}/{routing.slugify(title)}.md"


def _validate_status(status) -> None:
    if status not in TODO_STATUSES:
        raise ValueError(f"unknown todo status '{status}'. Valid: {', '.join(TODO_STATUSES)}")


def _required_text(value, field) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_text(value, field):
    if value is None:
        return None
    return _required_text(value, field)


def _optional_date(value, field):
    if value is None:
        return None
    value = _required_text(value, field)
    try:
        parsed = datetime.strptime(value, fmlib.NOTE_TIMESTAMP_FORMAT).replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ValueError(
            f"{field} must be a valid UTC timestamp in {fmlib.NOTE_TIMESTAMP_LABEL} format"
        ) from exc
    if fmlib.format_note_timestamp(parsed) != value:
        raise ValueError(
            f"{field} must be a valid UTC timestamp in {fmlib.NOTE_TIMESTAMP_LABEL} format"
        )
    return parsed.strftime("%Y-%m-%dT%H:%M:00Z")


def _display_date(value):
    if value is None:
        return None
    return fmlib.format_note_timestamp(
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    )

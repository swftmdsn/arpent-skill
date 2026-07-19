import copy
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from scripts import frontmatter
from scripts import cli
from scripts import cron
from scripts import notes
from scripts import operations
from scripts import sweep
from scripts import todo
from scripts import tools
from scripts.vault import init_vault

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

TODO_V3_SCHEMA = """
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
PRAGMA user_version = 3;
"""
TODO_V2_SCHEMA = TODO_V3_SCHEMA.replace("PRAGMA user_version = 3", "PRAGMA user_version = 2")


def _subprocess_env():
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(REPOSITORY_ROOT) if not existing else f"{REPOSITORY_ROOT}{os.pathsep}{existing}"
    )
    return env


class CaptureContractTests(unittest.TestCase):
    def test_durable_capture_requires_prior_art_reconciliation(self):
        skill = (REPOSITORY_ROOT / "SKILL.md").read_text(encoding="utf-8")
        workflow = (
            REPOSITORY_ROOT / "references/workflows/capture-note.md"
        ).read_text(encoding="utf-8")
        local_skill = (
            REPOSITORY_ROOT
            / "architecture_template/06_indexes/global_skills/arpent.skill.md"
        ).read_text(encoding="utf-8")
        indexing = (
            REPOSITORY_ROOT / "references/indexing-and-context.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Before a durable note, search", skill)
        self.assertIn("never silently edit instead of a requested creation", skill)
        self.assertIn("Before every durable note (`fleeting` exempt)", workflow)
        self.assertIn("Tags or emotions alone are", workflow)
        self.assertIn("Journals, logs, and meetings remain separate", workflow)
        self.assertIn("arpent search", workflow)
        self.assertIn("Before durable notes, search", local_skill)
        self.assertIn("maintained search index", indexing)

    def test_note_plan_is_non_mutating_and_routes_captured_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)

            plan = notes.plan_note_new(
                vault,
                title="Captured article",
                ntype="reference",
                body="Useful source.",
                source="captured",
                link="https://example.com/article",
            )

            self.assertEqual(plan["destination_path"], "00_inbox/captures/captured_article.md")
            self.assertFalse((vault.root / plan["destination_path"]).exists())
            self.assertEqual(len(plan["plan_sha256"]), 64)
            self.assertEqual(plan["frontmatter"]["appreciated"], None)
            self.assertEqual(plan["frontmatter"]["importance"], None)

    def test_note_plan_hash_applies_the_reviewed_semantics(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            command = [
                sys.executable,
                "-m",
                "scripts.cli",
                "note",
                "new",
                "A durable idea",
                "--type",
                "idea",
                "--body",
                "A concise body.",
                "--dry-run",
                "--json",
            ]
            preview = subprocess.run(
                command,
                cwd=vault.root,
                env=_subprocess_env(),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(preview.returncode, 0, preview.stderr)
            plan = json.loads(preview.stdout)
            self.assertFalse((vault.root / plan["destination_path"]).exists())

            apply = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.cli",
                    "note",
                    "new",
                    "A durable idea",
                    "--type",
                    "idea",
                    "--body",
                    "A concise body.",
                    "--plan-hash",
                    plan["plan_sha256"],
                    "--json",
                ],
                cwd=vault.root,
                env=_subprocess_env(),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(apply.returncode, 0, apply.stderr)
            result = json.loads(apply.stdout)
            self.assertEqual(result["plan_sha256"], plan["plan_sha256"])
            self.assertEqual(result["id"], plan["frontmatter"]["id"])
            metadata, body = frontmatter.read_note(vault.root / result["path"])
            self.assertEqual(metadata["type"], "idea")
            self.assertEqual(body.strip(), "A concise body.")

    def test_stale_note_plan_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            with self.assertRaisesRegex(ValueError, "no longer matches"):
                notes.plan_note_new(
                    vault,
                    title="Changed body",
                    ntype="note",
                    body="new",
                    expected_plan_hash="0" * 64,
                )

    def test_note_apply_rejects_route_changed_after_planning(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            plan = notes.plan_note_new(
                vault,
                title="Route snapshot",
                ntype="note",
                body="Bound destination.",
            )
            contract = vault.operations_path()
            contract.write_text(
                contract.read_text(encoding="utf-8").replace(
                    "routing_overrides: {}",
                    "routing_overrides:\n  zero_field_routes:\n    default: 03_resources/concepts",
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "routing changed"):
                notes.apply_note_new(vault, plan)

    def test_note_apply_binds_unsure_reason_even_when_path_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            plan = notes.plan_note_new(
                vault,
                title="Ambiguous route",
                ntype="note",
                area="focus",
            )
            self.assertEqual(plan["destination_path"], "00_inbox/unsure/ambiguous_route.md")
            vault.safe_ensure_directory("02_areas/area__one__focus__active")
            vault.safe_ensure_directory("02_areas/area__two__focus__active")

            with self.assertRaisesRegex(ValueError, "routing changed"):
                notes.apply_note_new(vault, plan)

    def test_howto_contract_routes_globally_and_rejects_local_homes(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            metadata = notes.build_frontmatter(
                vault,
                title="Rotate API keys without downtime",
                ntype="howto",
                source="derived",
            )

            self.assertRegex(metadata["id"], r"^howto-\d{8}-[a-z]+$")
            self.assertEqual(metadata["status"], "ongoing")
            self.assertIsNone(metadata["project"])
            self.assertIsNone(metadata["resource"])

            path, _ = notes.create_note(vault, metadata, "## Current conclusion\n\nRotate in two phases.")
            self.assertEqual(
                path.relative_to(vault.root).as_posix(),
                "03_resources/how-tos/rotate_api_keys_without_downtime.md",
            )

            for home in ({"project": "local-project"}, {"resource": "concepts"}):
                with self.subTest(home=home), self.assertRaisesRegex(
                    ValueError, "howto notes are global",
                ):
                    notes.build_frontmatter(
                        vault,
                        title="Invalid local guide",
                        ntype="howto",
                        **home,
                    )

    def test_howto_is_protected_from_ephemeral_sweep_by_type(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            metadata = notes.build_frontmatter(
                vault,
                title="Protected current guidance",
                ntype="howto",
                status="stale",
            )
            path, _ = notes.create_note(vault, metadata, "## Current conclusion\n\nKeep this guide.")
            (vault.root / "06_indexes/tools.yaml").write_text(
                """version: 0.2.0
tools:
  howto_test:
    category: transversal
    ephemeral: true
    skill: 06_indexes/global_skills/arpent.skill.md
    writes_to:
      - 03_resources/how-tos
    database: null
    status: installed
    lifecycle:
      - from: stale
        after_days: 0
        action: archive
""",
                encoding="utf-8",
            )

            summary = sweep.run_ephemeral(
                vault,
                now=datetime(2030, 1, 1, tzinfo=timezone.utc),
            )

            self.assertTrue(path.exists())
            self.assertEqual(summary["archived"], 0)
            self.assertEqual(summary["tools"]["howto_test"]["skipped"], 1)

    def test_agent_note_mutations_preserve_user_subjective_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            plan = notes.plan_note_new(
                vault,
                title="Agent research",
                ntype="note",
                status="active",
                author="agent",
            )
            path, _, metadata = notes.apply_note_new(vault, plan)
            metadata["appreciated"] = True
            metadata["importance"] = 4
            frontmatter.write_note(path, metadata, "User-rated content.")

            edit = notes.plan_note_edit(
                vault,
                metadata["id"],
                changes={"description": "A routing-neutral edit."},
            )
            updated_path, _ = notes.apply_note_edit(vault, edit)
            updated, _ = frontmatter.read_note(updated_path)
            self.assertIs(updated["appreciated"], True)
            self.assertEqual(updated["importance"], 4)

            with self.assertRaisesRegex(ValueError, "user-only fields"):
                notes.plan_note_edit(
                    vault,
                    metadata["id"],
                    changes={"importance": 5},
                )
            with self.assertRaisesRegex(ValueError, "user-only fields"):
                notes.plan_note_edit(
                    vault,
                    metadata["id"],
                    clear_fields=("appreciated",),
                )

            _, archived_path = notes.archive_note(vault, metadata["id"])
            archived, _ = frontmatter.read_note(archived_path)
            self.assertIs(archived["appreciated"], True)
            self.assertEqual(archived["importance"], 4)

    def test_agent_cannot_supply_subjective_values_at_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            metadata = notes.build_frontmatter(
                vault,
                title="Agent-rated creation",
                ntype="note",
                author="agent",
            )
            metadata["importance"] = "high"

            with self.assertRaisesRegex(ValueError, "user-only fields"):
                notes.create_note(vault, metadata)

    def test_frontmatter_validation_enforces_closed_typed_schema(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            valid = notes.build_frontmatter(
                vault,
                title="Typed schema",
                ntype="note",
            )

            for field in frontmatter.KEY_ORDER:
                invalid = copy.deepcopy(valid)
                invalid.pop(field)
                with self.subTest(missing=field), self.assertRaisesRegex(ValueError, "missing required"):
                    notes.validate_frontmatter_values(invalid)

            for field in ("id", "observations"):
                incomplete = copy.deepcopy(valid)
                incomplete.pop(field)
                with self.subTest(new_note_missing=field), self.assertRaisesRegex(
                    ValueError, "missing required",
                ):
                    notes.create_note(vault, incomplete)

            invalid_values = (
                ("title", "Not canonical"),
                ("id", "note-invalid"),
                ("project", ["project"]),
                ("tags", "tag"),
                ("pinned", 1),
                ("appreciated", {"score": 1}),
            )
            for field, value in invalid_values:
                invalid = copy.deepcopy(valid)
                invalid[field] = value
                with self.subTest(field=field), self.assertRaises(ValueError):
                    notes.validate_frontmatter_values(invalid)

            invalid = copy.deepcopy(valid)
            invalid["relations"] = [{
                "type": "supports",
                "target": "note-20260719-a",
                "label": "extra",
            }]
            with self.assertRaisesRegex(ValueError, "exactly type and target"):
                notes.validate_frontmatter_values(invalid)
            invalid["relations"] = None
            with self.assertRaisesRegex(ValueError, "relations must be a list"):
                notes.validate_frontmatter_values(invalid)

            for timestamp in (
                "19-07-2026T14:05:00Z",
                "2026-07-19T14:05:00Z",
                "19-07-2026",
            ):
                legacy = copy.deepcopy(valid)
                legacy["created"] = timestamp
                legacy["modified"] = timestamp
                notes.validate_frontmatter_values(legacy)

            invalid = copy.deepcopy(valid)
            invalid["archived_at"] = valid["modified"]
            invalid["archived_from"] = "00_inbox/typed_schema.md"
            with self.assertRaisesRegex(ValueError, "only for archived"):
                notes.validate_frontmatter_values(invalid)

            archived = copy.deepcopy(invalid)
            archived["status"] = "archived"
            notes.validate_frontmatter_values(archived)

            archived.pop("archived_from")
            with self.assertRaisesRegex(ValueError, "supplied together"):
                notes.validate_frontmatter_values(archived)

    def test_frontmatter_policy_models_archive_event_extensions(self):
        policy = frontmatter.parse_frontmatter_block(
            (
                REPOSITORY_ROOT
                / "architecture_template/06_indexes/schemas/frontmatter_policy.yaml"
            ).read_text(encoding="utf-8")
        )

        event = policy["lifecycle_extensions"]["archive_event"]
        self.assertEqual(event["applies_when_status"], "archived")
        self.assertIs(event["capture_required"], False)
        self.assertEqual(set(event["fields"]), {"archived_at", "archived_from"})
        self.assertIn("archived", policy["enums"]["status"])
        self.assertNotIn("archived_at", policy["enums"]["status"])
        self.assertNotIn("archived_from", policy["enums"]["status"])

    def test_todo_dry_run_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.cli",
                    "todo",
                    "add",
                    "Prepare review",
                    "--dry-run",
                    "--json",
                ],
                cwd=vault.root,
                env=_subprocess_env(),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual(plan["format"], "arpent-todo-add-plan")
            self.assertFalse((vault.root / "06_indexes/databases/todo.db").exists())
            self.assertFalse((vault.root / plan["destination_path"]).exists())

    def test_todo_plan_hash_applies_reviewed_todo(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            base = [
                sys.executable,
                "-m",
                "scripts.cli",
                "todo",
                "add",
                "Prepare review",
                "--due",
                "20-07-2026-09-30",
            ]
            preview = subprocess.run(
                [*base, "--dry-run", "--json"],
                cwd=vault.root,
                env=_subprocess_env(),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(preview.returncode, 0, preview.stderr)
            plan = json.loads(preview.stdout)

            apply = subprocess.run(
                [*base, "--plan-hash", plan["plan_sha256"], "--json"],
                cwd=vault.root,
                env=_subprocess_env(),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(apply.returncode, 0, apply.stderr)
            result = json.loads(apply.stdout)
            self.assertEqual(plan["todo"]["due_date"], "20-07-2026-09-30")
            self.assertEqual(result["todo"]["due_date"], "20-07-2026-09-30")
            self.assertEqual(result["id"], plan["todo"]["id"])
            self.assertTrue((vault.root / result["path"]).is_file())
            self.assertTrue((vault.root / "06_indexes/databases/todo.db").is_file())

    def test_todo_schema_creation_is_transactional_and_constrained(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            malformed = "BEGIN IMMEDIATE; CREATE TABLE partial (value TEXT); INVALID SQL; COMMIT;"
            with mock.patch.object(todo, "schema_text", return_value=malformed):
                with self.assertRaises(sqlite3.Error):
                    todo.ensure_database(vault)

            database = vault.root / todo.DATABASE_RELPATH
            with sqlite3.connect(database) as connection:
                tables = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            self.assertEqual(tables, [])

            todo.ensure_database(vault)
            with sqlite3.connect(database) as connection:
                self.assertEqual(
                    connection.execute("PRAGMA user_version").fetchone()[0],
                    todo.SCHEMA_VERSION,
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO todos (id, content, status) VALUES (?, ?, ?)",
                        ("invalid-id", "Invalid ID", "active"),
                    )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO todos (id, content, status) VALUES (?, ?, ?)",
                        ("todo-20260719-a", "Invalid status", "stale"),
                    )

    def test_todo_v3_database_migrates_to_constrained_v4(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            database = vault.root / todo.DATABASE_RELPATH
            connection = sqlite3.connect(database)
            try:
                connection.executescript(TODO_V3_SCHEMA)
                connection.execute(
                    "INSERT INTO todos (id, content, status) VALUES (?, ?, ?)",
                    ("todo-20260719-a", "Preserved todo", "waiting"),
                )
                connection.commit()
            finally:
                connection.close()

            todo.ensure_database(vault)

            connection = sqlite3.connect(database)
            try:
                self.assertEqual(
                    connection.execute("PRAGMA user_version").fetchone()[0],
                    todo.SCHEMA_VERSION,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT content, status FROM todos WHERE id = ?",
                        ("todo-20260719-a",),
                    ).fetchone(),
                    ("Preserved todo", "waiting"),
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "UPDATE todos SET status = 'stale' WHERE id = ?",
                        ("todo-20260719-a",),
                    )
            finally:
                connection.close()

    def test_todo_v2_date_migration_is_preserved_by_v4(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            database = vault.root / todo.DATABASE_RELPATH
            connection = sqlite3.connect(database)
            try:
                connection.executescript(TODO_V2_SCHEMA)
                connection.execute(
                    """
                    INSERT INTO todos (id, content, status, due_date, do_date)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "todo-20260719-a", "Legacy dates", "active",
                        "2026-07-21", "2026-07-20",
                    ),
                )
                connection.commit()
            finally:
                connection.close()

            todo.ensure_database(vault)

            connection = sqlite3.connect(database)
            try:
                self.assertEqual(
                    connection.execute("PRAGMA user_version").fetchone()[0],
                    todo.SCHEMA_VERSION,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT due_date, do_date FROM todos WHERE id = ?",
                        ("todo-20260719-a",),
                    ).fetchone(),
                    ("2026-07-21T00:00:00Z", "2026-07-20T00:00:00Z"),
                )
            finally:
                connection.close()

    def test_todo_plan_reads_database_from_uri_sensitive_vault_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(
                Path(temporary) / "vault # question ? unicode é",
                minimal=False,
            )
            first = todo.add_todo(vault, "First todo")

            plan = todo.plan_todo_add(vault, "Second todo")

            self.assertNotEqual(plan["todo"]["id"], first["id"])

    def test_always_mode_requires_review_before_note_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            contract = vault.operations_path()
            contract.write_text(
                contract.read_text(encoding="utf-8").replace(
                    "policy: explicit-intent", "policy: always",
                ),
                encoding="utf-8",
            )
            base = [
                sys.executable,
                "-m",
                "scripts.cli",
                "note",
                "new",
                "Review first",
                "--json",
            ]
            preview = subprocess.run(
                base,
                cwd=vault.root,
                env=_subprocess_env(),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(preview.returncode, 0, preview.stderr)
            plan = json.loads(preview.stdout)
            self.assertTrue(plan["confirmation_required"])
            self.assertFalse((vault.root / plan["destination_path"]).exists())

            apply = subprocess.run(
                [*base, "--plan-hash", plan["plan_sha256"]],
                cwd=vault.root,
                env=_subprocess_env(),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(apply.returncode, 0, apply.stderr)
            self.assertEqual(json.loads(apply.stdout)["format"], "arpent-note-new-result")

    def test_always_mode_gates_existing_note_mutations(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            plan = notes.plan_note_new(vault, title="Policy target", ntype="note")
            _, _, metadata = notes.apply_note_new(vault, plan)
            contract = vault.operations_path()
            contract.write_text(
                contract.read_text(encoding="utf-8").replace(
                    "policy: explicit-intent", "policy: always",
                ),
                encoding="utf-8",
            )
            command = [
                sys.executable, "-m", "scripts.cli", "note", "status",
                metadata["id"], "stable",
            ]
            blocked = subprocess.run(
                command,
                cwd=vault.root,
                env=_subprocess_env(),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("requires confirmation", blocked.stderr)

            applied = subprocess.run(
                [*command, "--yes"],
                cwd=vault.root,
                env=_subprocess_env(),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)

    def test_fleeting_json_contract_has_no_per_entry_frontmatter_or_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            command = [
                sys.executable, "-m", "scripts.cli", "note", "new",
                "Quick thought", "--type", "fleeting", "--json",
            ]
            result = subprocess.run(
                command,
                cwd=vault.root,
                env=_subprocess_env(),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["format"], "arpent-fleeting-result")
            self.assertNotIn("id", payload)
            self.assertNotIn("frontmatter", payload)
            self.assertRegex(
                payload["path"], r"^00_inbox/fleeting/\d{2}-\d{2}-\d{4}\.md$"
            )
            self.assertRegex(payload["captured_time"], r"^\d{2}:\d{2}$")

    def test_confirmation_policies_and_configurable_threshold(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "operations.yaml"
            packaged = operations.default_operations_text()

            source.write_text(packaged, encoding="utf-8")
            self.assertFalse(
                operations.requires_confirmation("note_new", count=1, path=source)
            )
            self.assertTrue(
                operations.requires_confirmation("note_new", count=5, path=source)
            )
            self.assertTrue(
                operations.requires_confirmation("import_apply", count=1, path=source)
            )

            source.write_text(
                packaged.replace("policy: explicit-intent", "policy: never"),
                encoding="utf-8",
            )
            self.assertFalse(
                operations.requires_confirmation("import_apply", count=100, path=source)
            )

            source.write_text(
                packaged.replace("policy: explicit-intent", "policy: never").replace(
                    "high_impact: true", "high_impact: invalid", 1,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "must be a boolean"):
                operations.requires_confirmation("import_apply", count=100, path=source)

            source.write_text(
                packaged.replace("policy: explicit-intent", "policy: always"),
                encoding="utf-8",
            )
            self.assertTrue(
                operations.requires_confirmation("note_new", count=1, path=source)
            )

    def test_reserved_resources_are_contract_driven_and_materialize_on_first_write(self):
        expected = {
            "concepts", "maps-of-content", "how-tos", "integrations", "templates",
            "agent_wiki", "books", "articles", "portraits", "productions",
        }
        self.assertEqual(set(operations.routing_contract()["reserved_resources"]), expected)

        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            self.assertFalse((vault.root / "03_resources/books").exists())
            self.assertTrue(expected <= set(vault.resource_slugs()))
            metadata = notes.build_frontmatter(
                vault, title="Contract resource", ntype="reference", resource="books",
            )
            path, _ = notes.create_note(vault, metadata, "Contract-driven home.")
            self.assertEqual(path.parent, vault.root / "03_resources/books")

            source = Path(temporary) / "operations.yaml"
            source.write_text(
                operations.default_operations_text().replace(
                    "reserved_resources: [concepts,",
                    "reserved_resources: [../escape, concepts,",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "stay inside the vault"):
                operations.routing_contract(source)

    def test_registry_lifecycle_validation_matches_sweep_safety(self):
        invalid = (
            ({"from": "active", "after_days": 1, "to": "stale"}, "protected status"),
            ({"from": "archived", "after_days": 1, "to": "stale"}, "reactivate archived"),
            ({"from": "inbox", "after_days": 1, "action": "archive"}, "only done or stale"),
        )
        for rule, message in invalid:
            with self.subTest(rule=rule), self.assertRaisesRegex(ValueError, message):
                tools._validate_lifecycle_rule("test", rule)

        with self.assertRaisesRegex(ValueError, "Markdown and database states"):
            tools._validate_lifecycle_rule(
                "todo",
                {"from": "waiting", "after_days": 1, "to": "stale"},
                database="06_indexes/databases/todo.db",
            )
        tools._validate_lifecycle_rule(
            "test", {"from": "done", "after_days": 1, "action": "archive"},
        )

    def test_cron_notify_channel_contract(self):
        job = {
            "id": "test", "enabled": False, "schedule": "* * * * *",
            "command": "arpent status",
        }
        for channel in (None, "stdout", "file"):
            with self.subTest(channel=channel):
                cron._validate_job({**job, "notify_channel": channel})
        with self.assertRaisesRegex(ValueError, "null, 'stdout', or 'file'"):
            cron._validate_job({**job, "notify_channel": "email"})

    def test_contract_without_confirmation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "operations.yaml"
            lines = operations.default_operations_text().splitlines()
            source.write_text("\n".join(lines[:2] + lines[5:]) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "requires a confirmation section"):
                operations.confirmation_policy(source)

    def test_legacy_confirmation_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "operations.yaml"
            packaged = operations.default_operations_text()

            source.write_text(
                packaged.replace(
                    "  policy: explicit-intent",
                    "  policy: explicit-intent\n  mode: explicit-intent",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "confirmation.mode is unsupported"):
                operations.confirmation_policy(source)

            source.write_text(
                packaged.replace(
                    "    high_impact: true",
                    "    confirmation: high-impact\n    high_impact: true",
                    1,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "confirmation is unsupported"):
                operations.operation_is_high_impact("import_apply", source)

    def test_old_operation_contract_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "operations.yaml"
            source.write_text(
                operations.default_operations_text().replace("version: 0.9.0", "version: 0.8.0"),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "older contracts are unsupported"):
                operations.load_operations(source)

    def test_backup_yes_is_preserved_before_or_after_restore_subcommand(self):
        parser = cli.build_parser()
        before = parser.parse_args([
            "backup", "--yes", "restore", "snapshot", "--to", "target",
        ])
        after = parser.parse_args([
            "backup", "restore", "snapshot", "--to", "target", "--yes",
        ])

        self.assertTrue(before.backup_yes)
        self.assertTrue(after.yes)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import shutil
import unittest

from tests.support import CliTestCase, load_json, load_json_text


class JsonAndWorkflowSmokeTests(CliTestCase):
    @unittest.skipUnless(shutil.which("git"), "full-mode workflows require git")
    def test_note_todo_and_sqlite_contracts(self):
        vault = self.initVault()

        note_plan_result = self.assertCliSuccess(self.cli(
            "note", "new", "Smoke Contract", "--body", "A stable body.",
            "--dry-run", "--json", cwd=vault,
        ))
        note_plan = load_json_text(note_plan_result.stdout)
        self.assertEqual((note_plan["format"], note_plan["version"]), ("arpent-note-new-plan", 1))
        self.assertRegex(note_plan["plan_sha256"], r"^[a-f0-9]{64}$")
        self.assertEqual(note_plan["apply_generated_fields"], ["created", "modified"])

        note_result = load_json_text(self.assertCliSuccess(self.cli(
            "note", "new", "Smoke Contract", "--body", "A stable body.",
            "--plan-hash", note_plan["plan_sha256"], "--json", cwd=vault,
        )).stdout)
        self.assertEqual((note_result["format"], note_result["version"]), ("arpent-note-new-result", 1))
        note_id = note_result["id"]
        self.assertFileContains(vault, note_result["path"], "A stable body.")

        note_page = load_json_text(self.assertCliSuccess(self.cli(
            "note", "read", note_id, "--json-page", "--full", cwd=vault,
        )).stdout)
        self.assertEqual(
            (note_page["format"], note_page["version"], note_page["view"]),
            ("arpent-content-page", 1, "note-read"),
        )
        self.assertEqual(note_page["content"].strip(), "A stable body.")
        self.assertCliSuccess(self.cli("note", "find", "stable", "--json-page", "--all", cwd=vault))
        self.assertCliSuccess(self.cli("note", "status", note_id, "active", "--yes", cwd=vault))
        self.assertCliSuccess(self.cli(
            "note", "edit", note_id, "--description", "Edited in smoke test",
            "--dry-run", "--json", cwd=vault,
        ))
        self.assertCliSuccess(self.cli("note", "route", note_id, "--yes", cwd=vault))

        raw = vault / "00_inbox" / "raw capture.txt"
        raw.write_text("raw input\n", encoding="utf-8")
        ingest = load_json_text(self.assertCliSuccess(self.cli(
            "note", "ingest", "00_inbox/raw capture.txt", "--title", "Raw Capture",
            "--dry-run", "--json", cwd=vault,
        )).stdout)
        self.assertEqual(ingest["source_path"], "00_inbox/raw capture.txt")
        self.assertCliSuccess(self.cli("archive", note_id, "--yes", cwd=vault))

        due = "20-07-2026-12-30"
        todo_plan = load_json_text(self.assertCliSuccess(self.cli(
            "todo", "add", "Smoke todo", "--due", due, "--dry-run", "--json", cwd=vault,
        )).stdout)
        self.assertEqual((todo_plan["format"], todo_plan["version"]), ("arpent-todo-add-plan", 1))
        self.assertEqual(todo_plan["todo"]["due_date"], due)
        self.assertEqual(todo_plan["apply_generated_fields"], ["created", "modified", "created_at"])

        todo_result = load_json_text(self.assertCliSuccess(self.cli(
            "todo", "add", "Smoke todo", "--due", due,
            "--plan-hash", todo_plan["plan_sha256"], "--json", cwd=vault,
        )).stdout)
        self.assertEqual((todo_result["format"], todo_result["version"]), ("arpent-todo-add-result", 1))
        todo_id = todo_result["id"]
        self.assertEqual(todo_result["todo"]["due_date"], due)
        self.assertRegex(todo_result["todo"]["created_at"], r"^\d{2}-\d{2}-\d{4}-\d{2}-\d{2}$")

        database = vault / "06_indexes" / "databases" / "todo.db"
        self.assertSqliteIntegrity(database)
        self.assertSqliteScalar(database, "PRAGMA user_version", 4)
        self.assertSqliteRows(
            database,
            "SELECT content, due_date FROM todos WHERE id = ?",
            [("Smoke todo", "2026-07-20T12:30:00Z")],
            (todo_id,),
        )

        shown = load_json_text(self.assertCliSuccess(self.cli(
            "todo", "show", todo_id, "--json", cwd=vault,
        )).stdout)
        self.assertEqual(shown["due_date"], due)
        self.assertCliSuccess(self.cli(
            "todo", "edit", todo_id, "--content", "Edited smoke todo", "--yes", cwd=vault,
        ))
        self.assertCliSuccess(self.cli(
            "todo", "defer", todo_id, "--to", "21-07-2026-08-15", "--yes", cwd=vault,
        ))
        self.assertCliSuccess(self.cli("todo", "block", todo_id, "--on", "object-1", "--yes", cwd=vault))
        self.assertCliSuccess(self.cli("todo", "done", todo_id, "--yes", cwd=vault))
        self.assertCliSuccess(self.cli("todo", "archive", todo_id, "--yes", cwd=vault))
        todo_page = load_json_text(self.assertCliSuccess(self.cli(
            "todo", "list", "--include-archived", "--json-page", "--all", cwd=vault,
        )).stdout)
        self.assertEqual(
            (todo_page["format"], todo_page["version"], todo_page["view"]),
            ("arpent-page", 1, "todo-list"),
        )
        self.assertEqual(todo_page["summary"]["total"], 1)

    @unittest.skipUnless(shutil.which("git"), "full-mode workflows require git")
    def test_index_context_and_miscellaneous_handlers(self):
        vault = self.initVault()
        self.assertCliSuccess(self.cli("project", "create", "Smoke Project", "--yes", cwd=vault))
        self.assertCliSuccess(self.cli(
            "session", "end", "--project", "smoke-project", "--summary", "Smoke close",
            "--decision", "Keep tests small", "--yes", cwd=vault,
        ))
        self.assertCliSuccess(self.cli("index", "--yes", cwd=vault))

        index = self.assertJsonFile(vault, "06_indexes/index.json", {"version": 2})
        self.assertIn(index["search_backend"], {"fts5", "text-fallback"})
        self.assertJsonFile(vault, "06_indexes/context_index.json", {"version": 1})

        pending = load_json_text(self.assertCliSuccess(self.cli(
            "context", "pending", "--json-page", "--all", cwd=vault,
        )).stdout)
        self.assertEqual((pending["format"], pending["version"], pending["view"]), ("arpent-page", 1, "context-pending"))
        self.assertTrue(pending["items"])
        first = pending["items"][0]
        self.assertCliSuccess(self.cli(
            "context", "set", first["path"], "--summary", "Smoke summary.",
            "--source-hash", first["source_hash"], "--yes", cwd=vault,
        ))
        summary = self.assertCliSuccess(self.cli(
            "context", "show", first["path"], "--level", "l1", cwd=vault,
        ))
        self.assertEqual(summary.stdout.strip(), "Smoke summary.")

        folder_page = load_json_text(self.assertCliSuccess(self.cli(
            "context", "show", ".", "--level", "l2", "--json-page", "--full", cwd=vault,
        )).stdout)
        self.assertEqual((folder_page["format"], folder_page["version"]), ("arpent-page", 1))
        for command in (
            ("triage", "--json-page", "--all"),
            ("efforts", "--json-page", "--all"),
            ("search", "smoke", "--json-page", "--all"),
        ):
            page = load_json_text(self.assertCliSuccess(self.cli(*command, cwd=vault)).stdout)
            self.assertEqual((page["format"], page["version"]), ("arpent-page", 1))

        health = load_json_text(self.assertCliSuccess(self.cli("health", "--json", cwd=vault)).stdout)
        self.assertIn("ratio", health)
        self.assertCliSuccess(self.cli("tools", "list", cwd=vault))
        tool = load_json_text(self.assertCliSuccess(self.cli("tools", "show", "todo", cwd=vault)).stdout)
        self.assertEqual(tool["status"], "installed")
        self.assertCliSuccess(self.cli("cron", "run", "--tick", "--dry-run", cwd=vault))
        self.assertCliSuccess(self.cli("sweep", "ephemeral", "--dry-run", cwd=vault))
        sweep = load_json_text(self.assertCliSuccess(self.cli("sweep", "status", "--json", cwd=vault)).stdout)
        self.assertTrue(sweep["dry_run"])
        usage = load_json_text(self.assertCliSuccess(self.cli("usage", "report", "--json", cwd=vault)).stdout)
        self.assertIn("commands", usage)

        minimal = load_json_text(self.assertCliSuccess(self.cli(
            "mode", "minimal", "--yes", "--json", cwd=vault,
        )).stdout)
        self.assertEqual(minimal["mode"], "minimal")
        full = load_json_text(self.assertCliSuccess(self.cli(
            "mode", "full", "--yes", "--json", cwd=vault,
        )).stdout)
        self.assertEqual(full["mode"], "full")

    @unittest.skipUnless(shutil.which("git"), "full-mode workflows require git")
    def test_import_plan_report_and_status_contracts(self):
        source = self.isolated.path("source material with spaces")
        source.mkdir()
        (source / "source.txt").write_text("Imported smoke content.\n", encoding="utf-8")
        plan_path = self.isolated.path("plans with spaces") / "plan.json"
        plan_path.parent.mkdir()

        scan = load_json_text(self.assertCliSuccess(self.cli(
            "import", "scan", source, "--output", plan_path, "--json",
        )).stdout)
        self.assertEqual(scan["files"], 1)
        plan = load_json(plan_path)
        self.assertEqual((plan["format"], plan["version"]), ("arpent-import-plan", 1))
        self.assertCliSuccess(self.cli("import", "suggest", plan_path, "--json"))
        review = load_json_text(self.assertCliSuccess(self.cli(
            "import", "review", plan_path, "--accept-suggestions", "--yes", "--json",
        )).stdout)
        self.assertTrue(review["completed"])
        validated = load_json_text(self.assertCliSuccess(self.cli(
            "import", "validate", plan_path, "--sources", "--json",
        )).stdout)
        self.assertTrue(validated["valid"])
        summary = load_json_text(self.assertCliSuccess(self.cli(
            "import", "summary", plan_path, "--json",
        )).stdout)
        self.assertEqual(summary["import_id"], plan["import_id"])
        self.assertRegex(summary["decision_sha256"], r"^[a-f0-9]{64}$")

        vault = self.initVault()
        preview = load_json_text(self.assertCliSuccess(self.cli(
            "import", "apply", plan_path, "--dry-run", "--json-page", "--all", cwd=vault,
        )).stdout)
        self.assertEqual((preview["format"], preview["version"], preview["view"]), ("arpent-page", 1, "import-preview"))
        self.assertEqual((preview["report"]["format"], preview["report"]["version"]), ("arpent-import-report", 1))

        report = load_json_text(self.assertCliSuccess(self.cli(
            "import", "apply", plan_path, "--yes", "--json", cwd=vault,
        )).stdout)
        self.assertEqual((report["format"], report["version"]), ("arpent-import-report", 1))
        status = load_json_text(self.assertCliSuccess(self.cli(
            "import", "status", plan_path, "--json", cwd=vault,
        )).stdout)
        self.assertEqual(status["remaining"], 0)
        self.assertEqual((source / "source.txt").read_text(encoding="utf-8"), "Imported smoke content.\n")

    @unittest.skipUnless(shutil.which("git"), "full-mode workflows require git")
    def test_backup_manifest_verify_and_restore(self):
        vault = self.initVault()
        destination = self.isolated.path("backup destination with spaces")
        self.assertCliSuccess(self.cli(
            "backup", "--destination", destination, "--yes", cwd=vault,
        ))
        snapshots = sorted(path for path in destination.iterdir() if path.is_dir())
        self.assertEqual(len(snapshots), 1)
        snapshot = snapshots[0]
        manifest = load_json(snapshot / "manifest.json")
        self.assertEqual((manifest["format"], manifest["version"]), ("arpent-backup", 1))
        self.assertCliSuccess(self.cli("backup", "verify", snapshot))

        restored = self.isolated.path("restored vault with spaces")
        self.assertCliSuccess(self.cli(
            "backup", "restore", snapshot, "--to", restored, "--yes",
        ))
        self.assertJsonFile(restored, ".arpent", {"version": 2, "mode": "full"})

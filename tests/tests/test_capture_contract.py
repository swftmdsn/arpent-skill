import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import frontmatter
from scripts import cli
from scripts import notes
from scripts import operations
from scripts import todo
from scripts.vault import init_vault

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _subprocess_env():
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(REPOSITORY_ROOT) if not existing else f"{REPOSITORY_ROOT}{os.pathsep}{existing}"
    )
    return env


class CaptureContractTests(unittest.TestCase):
    def test_note_plan_is_non_mutating_and_routes_captured_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=True)

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
            vault = init_vault(Path(temporary) / "vault", minimal=True)
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
            vault = init_vault(Path(temporary) / "vault", minimal=True)
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
            vault = init_vault(Path(temporary) / "vault", minimal=True)
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
            vault = init_vault(Path(temporary) / "vault", minimal=True)
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
                "20-07-2026",
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
            self.assertEqual(result["todo"]["due_date"], "20-07-2026")
            self.assertEqual(result["id"], plan["todo"]["id"])
            self.assertTrue((vault.root / result["path"]).is_file())
            self.assertTrue((vault.root / "06_indexes/databases/todo.db").is_file())

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
            vault = init_vault(Path(temporary) / "vault", minimal=True)
            contract = vault.operations_path()
            contract.write_text(
                contract.read_text(encoding="utf-8").replace(
                    "mode: explicit-intent", "mode: always",
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
            vault = init_vault(Path(temporary) / "vault", minimal=True)
            plan = notes.plan_note_new(vault, title="Policy target", ntype="note")
            _, _, metadata = notes.apply_note_new(vault, plan)
            contract = vault.operations_path()
            contract.write_text(
                contract.read_text(encoding="utf-8").replace(
                    "mode: explicit-intent", "mode: always",
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
            self.assertIn("requires approval", blocked.stderr)

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
            vault = init_vault(Path(temporary) / "vault", minimal=True)
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
            self.assertRegex(payload["captured_time"], r"^\d{2}:\d{2}$")

    def test_confirmation_modes_and_configurable_threshold(self):
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
                packaged.replace("mode: explicit-intent", "mode: never"),
                encoding="utf-8",
            )
            self.assertFalse(
                operations.requires_confirmation("import_apply", count=100, path=source)
            )

            source.write_text(
                packaged.replace("mode: explicit-intent", "mode: never").replace(
                    "confirmation: high-impact", "confirmation: invalid", 1,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "must be one of"):
                operations.requires_confirmation("import_apply", count=100, path=source)

            source.write_text(
                packaged.replace("mode: explicit-intent", "mode: always"),
                encoding="utf-8",
            )
            self.assertTrue(
                operations.requires_confirmation("note_new", count=1, path=source)
            )

    def test_legacy_contract_without_confirmation_defaults_to_always(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "operations.yaml"
            lines = operations.default_operations_text().splitlines()
            source.write_text("\n".join(lines[:2] + lines[5:]) + "\n", encoding="utf-8")

            self.assertEqual(operations.confirmation_policy(source)["mode"], "always")

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

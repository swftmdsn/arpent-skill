import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import file_transaction
from scripts import frontmatter
from scripts import import_executor
from scripts import import_manifest
from scripts import routing
from scripts import usage
from scripts.vault import init_vault


class ImportPipelineTests(unittest.TestCase):
    def test_scan_review_apply_and_resume_preserve_external_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            project = source / "Projects" / "Website"
            project.mkdir(parents=True)
            original = "Legacy project notes.\n"
            (project / "Readme.md").write_text(original, encoding="utf-8")
            plan_path = base / "import-plan.json"

            plan = import_manifest.scan_source(source, plan_path)
            review = import_manifest.review_plan(plan, accept_suggestions=True)
            import_manifest.save_plan(plan_path, plan)

            self.assertTrue(review["completed"])
            self.assertEqual(plan["inventory"]["files"], 1)
            self.assertTrue(import_manifest.validate_plan(plan_path, plan)["valid"])

            vault = init_vault(base / "vault", minimal=True)
            preview = import_executor.apply_import(vault, plan_path, plan, dry_run=True)
            self.assertEqual(preview["counts"]["planned"], 1)
            self.assertFalse((vault.root / "01_projects" / "website").exists())

            report = import_executor.apply_import(vault, plan_path, plan)
            self.assertEqual(report["counts"]["applied"], 1)
            destination = vault.root / "01_projects" / "website" / "notes" / "readme.md"
            metadata, body = frontmatter.read_note(destination)
            self.assertEqual(metadata["project"], "website")
            self.assertEqual(metadata["source"], "imported")
            self.assertEqual(body.strip(), original.strip())
            self.assertEqual((project / "Readme.md").read_text(encoding="utf-8"), original)

            resumed = import_executor.apply_import(vault, plan_path, plan)
            self.assertEqual(resumed["counts"]["already_complete"], 1)
            status = import_executor.import_status(vault, plan)
            self.assertEqual(status["complete"], 1)
            self.assertEqual(status["remaining"], 0)

    def test_binary_resource_is_copied_as_attachment(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            books = source / "Books"
            books.mkdir(parents=True)
            payload = b"%PDF-1.7\x00legacy"
            (books / "Guide.pdf").write_bytes(payload)
            plan_path = base / "import-plan.json"

            plan = import_manifest.scan_source(source, plan_path)
            import_manifest.review_plan(plan, accept_suggestions=True)
            import_manifest.save_plan(plan_path, plan)
            vault = init_vault(base / "vault", minimal=True)

            report = import_executor.apply_import(vault, plan_path, plan)

            self.assertEqual(report["counts"]["applied"], 1)
            attachment = vault.root / "03_resources" / "books" / "attachments" / "guide.pdf"
            self.assertEqual(attachment.read_bytes(), payload)
            self.assertEqual((books / "Guide.pdf").read_bytes(), payload)
            metadata, _ = frontmatter.read_note(
                vault.root / "03_resources" / "books" / "guide.md"
            )
            self.assertEqual(metadata["resource"], "books")
            self.assertEqual(metadata["link"], "03_resources/books/attachments/guide.pdf")

    def test_changed_source_fails_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            folder = source / "Books"
            folder.mkdir(parents=True)
            path = folder / "Notes.txt"
            path.write_text("before", encoding="utf-8")
            plan_path = base / "import-plan.json"
            plan = import_manifest.scan_source(source, plan_path)
            import_manifest.review_plan(plan, accept_suggestions=True)
            import_manifest.save_plan(plan_path, plan)
            path.write_text("after", encoding="utf-8")
            vault = init_vault(base / "vault", minimal=True)

            report = import_executor.apply_import(vault, plan_path, plan)

            self.assertEqual(report["counts"]["failed"], 1)
            self.assertEqual(report["counts"]["structure_created"], 1)
            self.assertIn("changed after scan", report["failures"][0]["error"])
            self.assertFalse((vault.root / "03_resources" / "books" / "notes.md").exists())

    def test_structured_markdown_is_preserved_verbatim(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            folder = source / "Books"
            folder.mkdir(parents=True)
            structured = "---\ntitle: old\nid: note-20200101-a\n---\n\nOld body.\n"
            (folder / "Old.md").write_text(structured, encoding="utf-8")
            plan_path = base / "import-plan.json"
            plan = import_manifest.scan_source(source, plan_path)
            import_manifest.review_plan(plan, accept_suggestions=True)
            import_manifest.save_plan(plan_path, plan)
            vault = init_vault(base / "vault", minimal=True)

            report = import_executor.apply_import(vault, plan_path, plan)

            self.assertEqual(report["counts"]["applied"], 1)
            _, body = frontmatter.read_note(vault.root / "03_resources" / "books" / "old.md")
            self.assertIn("note-20200101-a", body)
            self.assertIn("Old body.", body)

    def test_confidence_threshold_keeps_review_incomplete(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            folder = source / "Misc"
            folder.mkdir(parents=True)
            (folder / "note.txt").write_text("content", encoding="utf-8")
            plan_path = base / "import-plan.json"
            plan = import_manifest.scan_source(source, plan_path)

            result = import_manifest.review_plan(
                plan,
                accept_suggestions=True,
                minimum_confidence=0.8,
            )

            self.assertFalse(result["completed"])
            self.assertEqual(result["unresolved"], ["Misc"])

    def test_scan_skips_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            source.mkdir()
            target = base / "outside.txt"
            target.write_text("outside", encoding="utf-8")
            try:
                (source / "linked.txt").symlink_to(target)
            except OSError:
                self.skipTest("symlinks unavailable")
            plan_path = base / "import-plan.json"

            plan = import_manifest.scan_source(source, plan_path)

            self.assertEqual(plan["inventory"]["files"], 0)
            self.assertEqual(plan["inventory"]["skipped"]["symlink"], 1)

    def test_binary_detection_covers_content_after_first_sample(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            books = source / "Books"
            books.mkdir(parents=True)
            payload = b"a" * 8192 + b"\xff"
            (books / "late-binary.dat").write_bytes(payload)
            plan_path = base / "plan.json"
            plan = import_manifest.scan_source(source, plan_path)
            record = next(import_manifest.iter_inventory(plan_path, plan))
            import_manifest.review_plan(plan, accept_suggestions=True)
            import_manifest.save_plan(plan_path, plan)
            vault = init_vault(base / "vault", minimal=True)

            report = import_executor.apply_import(vault, plan_path, plan)

            self.assertEqual(record["kind"], "binary")
            self.assertEqual(report["counts"]["applied"], 1)
            self.assertEqual(
                vault.root.joinpath(
                    "03_resources/books/attachments/late_binary.dat"
                ).read_bytes(),
                payload,
            )

    def test_utf8_character_crossing_old_sample_boundary_stays_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            books = source / "Books"
            books.mkdir(parents=True)
            content = "a" * 8191 + "é and text"
            (books / "unicode.txt").write_text(content, encoding="utf-8")
            plan_path = base / "plan.json"
            plan = import_manifest.scan_source(source, plan_path)
            import_manifest.review_plan(plan, accept_suggestions=True)
            import_manifest.save_plan(plan_path, plan)
            vault = init_vault(base / "vault", minimal=True)

            report = import_executor.apply_import(vault, plan_path, plan)

            self.assertEqual(report["counts"]["applied"], 1)
            _, body = frontmatter.read_note(vault.root / "03_resources/books/unicode.md")
            self.assertEqual(body, content)

    def test_scan_rejects_symlinked_or_in_source_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            source.mkdir()
            (source / "note.txt").write_text("content", encoding="utf-8")
            victim = base / "victim.json"
            victim.write_text("unchanged", encoding="utf-8")
            linked = base / "plan.json"
            try:
                linked.symlink_to(victim)
            except OSError:
                self.skipTest("symlinks unavailable")

            with self.assertRaisesRegex(ValueError, "symlinked import output"):
                import_manifest.scan_source(source, linked, overwrite=True)
            self.assertEqual(victim.read_text(encoding="utf-8"), "unchanged")
            with self.assertRaisesRegex(ValueError, "outside the source tree"):
                import_manifest.scan_source(source, source / "plan.json")

    def test_forced_rescan_publishes_a_new_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            source.mkdir()
            (source / "note.txt").write_text("first", encoding="utf-8")
            plan_path = base / "plan.json"
            first = import_manifest.scan_source(source, plan_path)
            first_inventory = base / first["inventory"]["path"]
            first_bytes = first_inventory.read_bytes()
            (source / "second.txt").write_text("second", encoding="utf-8")

            second = import_manifest.scan_source(source, plan_path, overwrite=True)

            self.assertNotEqual(first["inventory"]["path"], second["inventory"]["path"])
            self.assertEqual(first_inventory.read_bytes(), first_bytes)
            self.assertTrue((base / second["inventory"]["path"]).is_file())

    def test_group_direct_files_use_root_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            group = source / "Projects"
            (group / "Website").mkdir(parents=True)
            (group / "README.md").write_text("overview", encoding="utf-8")
            (group / "Website" / "notes.md").write_text("work", encoding="utf-8")
            plan_path = base / "plan.json"
            plan = import_manifest.scan_source(source, plan_path)

            result = import_manifest.review_plan(plan, accept_suggestions=True)
            import_manifest.save_plan(plan_path, plan)

            self.assertTrue(result["completed"])
            summary = import_manifest.summarize_plan(plan_path, plan)
            self.assertEqual(summary["by_role"], {"inbox": 1, "project": 1})

    def test_dry_run_marks_internal_collisions_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            books = source / "Books"
            (books / "A").mkdir(parents=True)
            (books / "a-b.md").write_text("one", encoding="utf-8")
            (books / "A" / "B.md").write_text("two", encoding="utf-8")
            plan_path = base / "plan.json"
            plan = import_manifest.scan_source(source, plan_path)
            import_manifest.review_plan(plan, accept_suggestions=True)
            import_manifest.save_plan(plan_path, plan)
            vault = init_vault(base / "vault", minimal=True)
            before = _tree_snapshot(vault.root)

            report = import_executor.apply_import(
                vault, plan_path, plan, dry_run=True, include_previews=True,
            )

            self.assertEqual(report["counts"]["collisions"], 1)
            self.assertEqual(_tree_snapshot(vault.root), before)

    def test_missing_source_and_overlapping_vault_do_not_create_destinations(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            project = source / "Projects" / "Website"
            project.mkdir(parents=True)
            (project / "note.md").write_text("work", encoding="utf-8")
            plan_path = base / "plan.json"
            plan = import_manifest.scan_source(source, plan_path)
            import_manifest.review_plan(plan, accept_suggestions=True)
            import_manifest.save_plan(plan_path, plan)
            vault = init_vault(base / "vault", minimal=True)
            source.rename(base / "moved")

            with self.assertRaisesRegex(ValueError, "source root is unavailable"):
                import_executor.apply_import(vault, plan_path, plan)
            self.assertFalse((vault.root / "01_projects" / "website").exists())

            overlapping_source = vault.root / "external"
            overlapping_source.mkdir()
            (overlapping_source / "note.txt").write_text("content", encoding="utf-8")
            overlap_plan_path = base / "overlap.json"
            overlap_plan = import_manifest.scan_source(overlapping_source, overlap_plan_path)
            import_manifest.review_plan(overlap_plan, accept_suggestions=True)
            import_manifest.save_plan(overlap_plan_path, overlap_plan)
            with self.assertRaisesRegex(ValueError, "must not contain one another"):
                import_executor.apply_import(vault, overlap_plan_path, overlap_plan)

    def test_torn_final_state_line_is_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            books = source / "Books"
            books.mkdir(parents=True)
            (books / "note.txt").write_text("content", encoding="utf-8")
            plan_path = base / "plan.json"
            plan = import_manifest.scan_source(source, plan_path)
            import_manifest.review_plan(plan, accept_suggestions=True)
            import_manifest.save_plan(plan_path, plan)
            vault = init_vault(base / "vault", minimal=True)
            import_executor.apply_import(vault, plan_path, plan)
            state = (
                vault.root / "06_indexes" / "imports" / plan["import_id"] / "state.jsonl"
            )
            with state.open("ab") as stream:
                stream.write(b'{"path":')
                stream.flush()
                os.fsync(stream.fileno())

            resumed = import_executor.apply_import(vault, plan_path, plan)
            status = import_executor.import_status(vault, plan)

            self.assertEqual(resumed["counts"]["already_complete"], 1)
            self.assertEqual(status["complete"], 1)
            self.assertTrue(state.read_bytes().endswith(b"\n"))

    def test_id_suffixes_are_not_limited_to_two_letters(self):
        generated = routing._letters()
        values = [next(generated) for _ in range(703)]

        self.assertEqual(values[0], "a")
        self.assertEqual(values[701], "zz")
        self.assertEqual(values[702], "aaa")

    def test_cli_noninteractive_workflow(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            books = source / "Books"
            books.mkdir(parents=True)
            (books / "note.txt").write_text("content", encoding="utf-8")
            plan = base / "plan.json"
            vault = init_vault(base / "vault", minimal=True)
            env = dict(os.environ)
            env["ARPENT_VAULT_ROOT"] = str(vault.root)

            commands = [
                ["import", "scan", str(source), "--output", str(plan)],
                ["import", "review", str(plan), "--accept-suggestions"],
                ["import", "validate", str(plan), "--sources"],
                ["import", "apply", str(plan), "--dry-run", "--json"],
                ["import", "apply", str(plan), "--yes"],
                ["import", "status", str(plan), "--json"],
            ]
            results = []
            for arguments in commands:
                results.append(subprocess.run(
                    [sys.executable, "-m", "scripts.cli", *arguments],
                    capture_output=True,
                    text=True,
                    check=False,
                    env=env,
                ))

            for result in results:
                self.assertEqual(result.returncode, 0, result.stderr)
            status = json.loads(results[-1].stdout)
            self.assertEqual(status["complete"], 1)
            self.assertTrue(vault.root.joinpath("03_resources/books/note.md").is_file())

    def test_crlf_text_body_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            books = source / "Books"
            books.mkdir(parents=True)
            original = b"first\r\nsecond\r\n"
            (books / "windows.txt").write_bytes(original)
            plan_path = base / "plan.json"
            plan = import_manifest.scan_source(source, plan_path)
            import_manifest.review_plan(plan, accept_suggestions=True)
            import_manifest.save_plan(plan_path, plan)
            vault = init_vault(base / "vault", minimal=True)

            import_executor.apply_import(vault, plan_path, plan)

            imported = vault.root.joinpath("03_resources/books/windows.md").read_bytes()
            self.assertIn(original, imported)

    def test_reviewed_execution_hash_binds_routing(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            project = source / "Projects" / "Website"
            project.mkdir(parents=True)
            (project / "note.md").write_text("content", encoding="utf-8")
            plan_path = base / "plan.json"
            plan = import_manifest.scan_source(source, plan_path)
            import_manifest.review_plan(plan, accept_suggestions=True)
            import_manifest.save_plan(plan_path, plan)
            vault = init_vault(base / "vault", minimal=True)
            preview = import_executor.apply_import(vault, plan_path, plan, dry_run=True)
            operations = vault.operations_path()
            content = operations.read_text(encoding="utf-8")
            operations.write_text(
                content.replace(
                    "routing_overrides: {}",
                    "routing_overrides:\n  type_subfolders:\n    note: imported",
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "no longer matches --plan-hash"):
                import_executor.apply_import(
                    vault,
                    plan_path,
                    plan,
                    expected_execution_hash=preview["plan_sha256"],
                )
            self.assertFalse((vault.root / "01_projects" / "website").exists())

    def test_usage_is_suppressed_when_source_contains_vault(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            source.mkdir()
            vault = init_vault(source / "vault", minimal=True)
            previous = os.environ.get("ARPENT_VAULT_ROOT")
            os.environ["ARPENT_VAULT_ROOT"] = str(vault.root)
            args = type("Args", (), {
                "command": "import",
                "import_cmd": "scan",
                "source": str(source),
            })()
            try:
                root = usage._usage_root(args)
            finally:
                if previous is None:
                    os.environ.pop("ARPENT_VAULT_ROOT", None)
                else:
                    os.environ["ARPENT_VAULT_ROOT"] = previous

            self.assertIsNone(root)

    def test_interrupted_ingest_is_recovered_before_structure_preflight(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            books = source / "Books"
            books.mkdir(parents=True)
            (books / "note.txt").write_text("content", encoding="utf-8")
            plan_path = base / "plan.json"
            plan = import_manifest.scan_source(source, plan_path)
            import_manifest.review_plan(plan, accept_suggestions=True)
            import_manifest.save_plan(plan_path, plan)
            vault = init_vault(base / "vault", minimal=True)

            with mock.patch.object(file_transaction, "commit", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    import_executor.apply_import(vault, plan_path, plan)
            self.assertTrue(
                vault.root.joinpath("06_indexes/logs/note-ingest-transaction.json").is_file()
            )

            report = import_executor.apply_import(vault, plan_path, plan)

            self.assertEqual(report["counts"]["applied"], 1)
            self.assertFalse(
                vault.root.joinpath("06_indexes/logs/note-ingest-transaction.json").exists()
            )
            self.assertTrue(vault.root.joinpath("03_resources/books/note.md").is_file())

    def test_status_detects_deleted_completed_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            books = source / "Books"
            books.mkdir(parents=True)
            (books / "note.txt").write_text("content", encoding="utf-8")
            plan_path = base / "plan.json"
            plan = import_manifest.scan_source(source, plan_path)
            import_manifest.review_plan(plan, accept_suggestions=True)
            import_manifest.save_plan(plan_path, plan)
            vault = init_vault(base / "vault", minimal=True)
            import_executor.apply_import(vault, plan_path, plan)
            vault.root.joinpath("03_resources/books/note.md").unlink()

            status = import_executor.import_status(vault, plan)
            env = dict(os.environ)
            env["ARPENT_VAULT_ROOT"] = str(vault.root)
            cli_status = subprocess.run(
                [
                    sys.executable, "-m", "scripts.cli", "import", "status",
                    str(plan_path), "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            self.assertEqual(status["complete"], 0)
            self.assertEqual(status["by_status"]["missing_or_changed"], 1)
            self.assertEqual(cli_status.returncode, 1)
            self.assertEqual(
                json.loads(cli_status.stdout)["by_status"]["missing_or_changed"], 1,
            )

    def test_reapply_refuses_modified_completed_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "legacy"
            books = source / "Books"
            books.mkdir(parents=True)
            (books / "note.txt").write_text("original", encoding="utf-8")
            plan_path = base / "plan.json"
            plan = import_manifest.scan_source(source, plan_path)
            import_manifest.review_plan(plan, accept_suggestions=True)
            import_manifest.save_plan(plan_path, plan)
            vault = init_vault(base / "vault", minimal=True)
            import_executor.apply_import(vault, plan_path, plan)
            destination = vault.root / "03_resources/books/note.md"
            destination.write_text(
                destination.read_text(encoding="utf-8") + "\nUser change.\n",
                encoding="utf-8",
            )

            report = import_executor.apply_import(vault, plan_path, plan)

            self.assertEqual(report["counts"]["failed"], 1)
            self.assertIn("Recorded import output changed", report["failures"][0]["error"])
            self.assertIn("User change.", destination.read_text(encoding="utf-8"))


def _tree_snapshot(root: Path):
    snapshot = {}
    for path in sorted(root.rglob("*")):
        relpath = path.relative_to(root).as_posix()
        if path.is_file() and not path.is_symlink():
            snapshot[relpath] = path.read_bytes()
        elif path.is_dir() and not path.is_symlink():
            snapshot[relpath] = None
    return snapshot


if __name__ == "__main__":
    unittest.main()

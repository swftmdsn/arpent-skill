from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts import cli, frontmatter, notes, operations, routing
from tests.regression._support import initialized


class ConcurrencyAndIdentityRegressionTests(unittest.TestCase):
    def test_concurrent_note_creation_serializes_ids_and_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))

            def create(index: int) -> tuple[str, Path]:
                metadata = notes.build_frontmatter(
                    vault, title=f"Concurrent note {index}", ntype="note"
                )
                path, _ = notes.create_note(vault, metadata, f"body {index}")
                return metadata["id"], path

            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                created = list(pool.map(create, range(10)))

            self.assertEqual(len({note_id for note_id, _ in created}), 10)
            self.assertTrue(all(path.is_file() for _, path in created))
            self.assertEqual(len(list((vault.root / "00_inbox").glob("concurrent_note_*.md"))), 10)

    def test_stale_ingest_plan_cannot_publish_a_duplicate_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            first = vault.root / "00_inbox/first.txt"
            second = vault.root / "00_inbox/second.txt"
            first.write_text("first", encoding="utf-8")
            second.write_text("second", encoding="utf-8")
            first_plan = notes.plan_ingest(vault, "00_inbox/first.txt", title="First import")
            second_plan = notes.plan_ingest(vault, "00_inbox/second.txt", title="Second import")
            self.assertEqual(first_plan["id"], second_plan["id"])

            notes.apply_ingest(vault, first_plan)
            with self.assertRaisesRegex(ValueError, "no longer unique"):
                notes.apply_ingest(vault, second_plan)

            self.assertEqual(second.read_text(encoding="utf-8"), "second")
            self.assertFalse((vault.root / second_plan["destination_path"]).exists())

    def test_duplicate_existing_ids_block_mutation_without_rewriting_either_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            plan = notes.plan_note_new(vault, title="Original", ntype="note", body="one")
            original, _, metadata = notes.apply_note_new(vault, plan)
            duplicate = vault.root / "00_inbox/duplicate.md"
            duplicate_metadata = dict(metadata)
            duplicate_metadata["title"] = "duplicate"
            frontmatter.write_note(duplicate, duplicate_metadata, "two")
            before = {original: original.read_bytes(), duplicate: duplicate.read_bytes()}

            with self.assertRaisesRegex(ValueError, "Duplicate note id"):
                notes.set_status(vault, metadata["id"], "active")

            self.assertEqual({path: path.read_bytes() for path in before}, before)


class ParserOperationContractRegressionTests(unittest.TestCase):
    def test_every_installed_parser_operation_has_a_registry_contract(self):
        parser_paths: list[tuple[tuple[str, ...], str]] = []

        def walk(parser: argparse.ArgumentParser, path: tuple[str, ...] = ()) -> None:
            function = parser._defaults.get("func")
            if function is not None:
                parser_paths.append((path, function.__name__))
            for action in parser._actions:
                if isinstance(action, argparse._SubParsersAction):
                    for name, child in action.choices.items():
                        walk(child, (*path, name))

        walk(cli.build_parser())
        covered = set()
        for path, function_name in parser_paths:
            key = "_".join(path)
            if key == "backup":
                covered.update({"backup", "backup_create"})
            elif key == "backup_verify":
                covered.add("backup")
            else:
                covered.add(key)

        registered = set(operations.default_operations()["operations"])
        self.assertEqual(covered, registered)

    def test_routing_enums_and_confirmation_calls_match_the_operation_contract(self):
        contract = operations.routing_contract()
        self.assertEqual(contract["types"], routing.TYPES)
        self.assertEqual(contract["statuses"], routing.STATUSES)
        self.assertEqual(contract["sources"], routing.SOURCES)
        self.assertEqual(contract["authors"], routing.AUTHORS)

        parser = cli.build_parser()
        parsed = parser.parse_args([
            "todo", "add", "Timestamp contract", "--due", "31-12-2030-23-45"
        ])
        self.assertEqual(parsed.due_date, "31-12-2030-23-45")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args([
                "note", "extract", "linear-id", "--type", "fleeting", "--title", "bad"
            ])

        registered = operations.default_operations()["operations"]
        for operation in (
            "mode_full", "mode_minimal", "index", "context_set", "backup_create",
            "backup_restore", "note_new", "note_route", "note_status", "note_edit",
            "note_ingest", "note_extract", "note_dissolve", "archive", "project_create",
            "session_end", "cron_run", "sweep_ephemeral", "todo_add", "todo_edit",
            "todo_done", "todo_defer", "todo_block", "todo_archive",
        ):
            with self.subTest(operation=operation):
                self.assertIn(operation, registered)
                self.assertIsInstance(
                    operations.operation_is_high_impact(operation),
                    bool,
                )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import argparse
import contextlib
import errno
import hashlib
import io
import json
import os
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from scripts import cli, context, cron, frontmatter, import_executor, index, notes, tools, usage, views
from scripts import vault as vault_mod
from tests.regression._support import initialized, run_cli


class ViewsAndRegistryHardeningTests(unittest.TestCase):
    def test_import_staging_markdown_is_excluded_without_hiding_normal_captures(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            normal = notes.build_frontmatter(
                vault, title="Normal capture", ntype="note", source="captured",
            )
            normal_path = vault.root / "00_inbox/captures/normal_capture.md"
            normal_path.write_text(
                frontmatter.compose_note(normal, "visible"), encoding="utf-8",
            )
            staging = vault.root / "00_inbox/captures/.arpent-import-crashed/nested"
            staging.mkdir(parents=True)
            staged = dict(normal)
            staged["id"] = "note-20990101-z"
            staged_path = staging / "staged.md"
            staged_path.write_text(
                frontmatter.compose_note(staged, "must stay hidden"), encoding="utf-8",
            )

            discovered = list(vault.iter_notes())
            self.assertIn(normal["id"], vault.existing_ids())
            self.assertNotIn(staged["id"], vault.existing_ids())
            self.assertEqual(
                [path for path, _, _ in discovered if path == normal_path],
                [normal_path],
            )
            built = index.build_index(vault)
            self.assertIn("00_inbox/captures/normal_capture.md", built["paths"])
            self.assertNotIn(
                "00_inbox/captures/.arpent-import-crashed/nested/staged.md",
                built["paths"],
            )
            triage_paths = {item["path"] for item in views.triage_items(vault)}
            self.assertIn("00_inbox/captures/normal_capture.md", triage_paths)
            self.assertNotIn(
                "00_inbox/captures/.arpent-import-crashed/nested/staged.md",
                triage_paths,
            )

    def test_efforts_excludes_fresh_templates_and_linked_projects(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            vault = initialized(parent)
            outside = parent / "outside-project"
            outside.mkdir()
            (outside / "_context.md").write_text(
                "---\nstatus: active\neffort_cadence: heavylift\neffort_level: high\n---\nsecret",
                encoding="utf-8",
            )
            linked = vault.root / "01_projects/linked"
            try:
                linked.symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")

            regular = vault.root / "01_projects/regular"
            regular.mkdir()
            (regular / "_context.md").symlink_to(outside / "_context.md")

            self.assertEqual(views.efforts(vault), [])

    def test_tools_registry_rejects_invalid_shapes_and_symlinked_source(self):
        invalid = (
            "version: 0.2.0\ntools: []\n",
            "tools: {}\n",
            "version: 9.9.9\ntools: {}\n",
            "version: 0.2.0\ntools:\n  bad:\n    category: test\n",
            vault_mod.TOOLS_STUB.replace("ephemeral: false", "ephemeral: sometimes", 1),
            vault_mod.TOOLS_STUB.replace(
                "    category: transversal\n",
                "    category: transversal\n    unexpected: true\n",
                1,
            ),
            vault_mod.TOOLS_STUB.replace(
                "      - 06_indexes/context_index.json",
                "      - CON/context_index.json",
                1,
            ),
            vault_mod.TOOLS_STUB.replace(
                "06_indexes/global_skills/context_summary.skill.md",
                "06_indexes//global_skills/context_summary.skill.md",
                1,
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            vault = initialized(parent)
            registry = vault.root / "06_indexes/tools.yaml"
            for text in invalid:
                with self.subTest(text=text):
                    registry.write_text(text, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        tools.load_tools(vault)

            outside = parent / "outside-tools.yaml"
            outside.write_text(vault_mod.TOOLS_STUB, encoding="utf-8")
            registry.unlink()
            try:
                registry.symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            with self.assertRaisesRegex(ValueError, "symlink"):
                tools.load_tools(vault)


class CronHardeningTests(unittest.TestCase):
    def _job(self, schedule):
        return {
            "id": "test",
            "enabled": False,
            "schedule": schedule,
            "command": "arpent status",
        }

    def test_invalid_cron_grammar_and_ranges_fail_at_load(self):
        invalid = (None, "* * * *", "60 * * * *", "* 24 * * *", "* * 0 * *", "* * * 13 *", "* * * * 8", "*/0 * * * *", "1--2 * * * *")
        for schedule in invalid:
            with self.subTest(schedule=schedule), self.assertRaises(ValueError):
                cron._validate_job(self._job(schedule))
        wrong_type = self._job("* * * * *")
        wrong_type["enabled"] = "false"
        with self.assertRaisesRegex(ValueError, "boolean"):
            cron._validate_job(wrong_type)

        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            registry = vault.root / "06_indexes/cron.json"
            registry.write_text(json.dumps({"jobs": [self._job("never")]}) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "schedule"):
                cron.run_tick(vault, dry_run=True)

    def test_ranges_steps_and_standard_dom_dow_or_semantics(self):
        now = datetime(2026, 7, 20, 6, 15, tzinfo=timezone.utc)  # Monday, DOM 20.
        for schedule in (
            "*/15 6-7 * 7 1-5",
            "5/10 6 * 7 1",
            "15 6 21 7 1",
            "15 6 20 7 2",
            "15 6 * 7 1",
        ):
            with self.subTest(schedule=schedule):
                job = self._job(schedule)
                cron._validate_job(job)
                self.assertTrue(cron._is_due(job, now))
        self.assertFalse(cron._is_due(self._job("15 6 21 7 2"), now))
        self.assertFalse(cron._is_due(self._job("15 6 */2 7 2"), now))


class PortableFilesystemTests(unittest.TestCase):
    def test_import_stage_copy_falls_back_when_hardlinks_are_unsupported(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            vault = initialized(parent)
            source = parent / "source.md"
            source.write_bytes(b"portable import\r\n")
            stage_rel = "00_inbox/captures/.arpent-import-test/source.md"
            unsupported = OSError(errno.ENOTSUP, "hardlinks unsupported")

            with mock.patch.object(vault_mod.os, "link", side_effect=unsupported):
                import_executor._copy_to_stage(
                    vault, source, stage_rel, hashlib.sha256(source.read_bytes()).hexdigest(),
                )

            self.assertEqual((vault.root / stage_rel).read_bytes(), source.read_bytes())

    def test_create_and_move_fall_back_when_hardlinks_are_unsupported(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            unsupported = OSError(errno.ENOTSUP, "hardlinks unsupported")
            with mock.patch.object(vault_mod.os, "link", side_effect=unsupported):
                created = vault.atomic_create_text("00_inbox/fallback.txt", "complete")
                self.assertEqual(created.read_text(encoding="utf-8"), "complete")
                with self.assertRaises(FileExistsError):
                    vault.atomic_create_text("00_inbox/fallback.txt", "replacement")
                self.assertEqual(created.read_text(encoding="utf-8"), "complete")

                source = vault.root / "00_inbox/source.bin"
                source.write_bytes(b"\x00portable\xff")
                destination = vault.atomic_move_no_replace(
                    "00_inbox/source.bin", "00_inbox/destination.bin",
                )
                self.assertFalse(source.exists())
                self.assertEqual(destination.read_bytes(), b"\x00portable\xff")

                second_source = vault.root / "00_inbox/second-source.txt"
                second_destination = vault.root / "00_inbox/second-destination.txt"
                second_source.write_text("source", encoding="utf-8")
                second_destination.write_text("destination", encoding="utf-8")
                with self.assertRaises(FileExistsError):
                    vault.atomic_move_no_replace(
                        "00_inbox/second-source.txt", "00_inbox/second-destination.txt",
                    )
                self.assertEqual(second_source.read_text(encoding="utf-8"), "source")
                self.assertEqual(second_destination.read_text(encoding="utf-8"), "destination")

    def test_move_fallback_rolls_back_destination_when_source_removal_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            source = vault.root / "00_inbox/source.txt"
            source.write_text("recoverable", encoding="utf-8")
            destination = vault.root / "00_inbox/destination.txt"
            original_unlink = Path.unlink

            def guarded_unlink(path, *args, **kwargs):
                if path == source:
                    raise OSError("injected unlink failure")
                return original_unlink(path, *args, **kwargs)

            with mock.patch.object(vault_mod.os, "link", side_effect=OSError(errno.ENOTSUP, "unsupported")), mock.patch.object(Path, "unlink", guarded_unlink):
                with self.assertRaisesRegex(OSError, "injected"):
                    vault.atomic_move_no_replace(
                        "00_inbox/source.txt", "00_inbox/destination.txt",
                    )
            self.assertTrue(source.is_file())
            self.assertFalse(destination.exists())

    def test_note_creation_rejects_windows_device_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            for title in ("CON", "com1", "LPT9"):
                with self.subTest(title=title):
                    plan = notes.plan_note_new(
                        vault, title=title, ntype="note", body="blocked",
                    )
                    with self.assertRaisesRegex(ValueError, "Windows-reserved"):
                        notes.apply_note_new(vault, plan)
                    self.assertFalse(
                        (vault.root / f"00_inbox/{title.casefold()}.md").exists()
                    )


class CliAndSessionBoundaryTests(unittest.TestCase):
    def test_project_create_reports_existing_as_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            vault_mod.set_vault_mode(vault, "full")
            first = run_cli(vault.root, "project", "create", "Idempotent project")
            second = run_cli(vault.root, "project", "create", "Idempotent project")

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn("Created project", first.stdout)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("already exists", second.stdout)
            events = [
                json.loads(line)
                for line in (vault.root / usage.USAGE_RELPATH).read_text(encoding="utf-8").splitlines()
                if json.loads(line)["command"] == "project create"
            ]
            self.assertEqual(events[-1]["outcome"], "no_change")
            self.assertFalse(events[-1]["changed"])
            self.assertEqual(events[-1]["count"], 0)

    def test_expected_cli_error_has_stable_code_and_no_traceback(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            vault_mod.set_vault_mode(vault, "full")
            (vault.root / "00_inbox/broken.md").write_text(
                "---\ntitle:\n   invalid: indentation\n---\n",
                encoding="utf-8",
            )
            result = run_cli(vault.root, "status")
            self.assertEqual(result.returncode, 1)
            self.assertIn("arpent:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_cli_does_not_mask_unexpected_debug_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            vault_mod.set_vault_mode(vault, "full")
            with mock.patch.dict(os.environ, {"ARPENT_VAULT_ROOT": str(vault.root)}), mock.patch.object(cli.views, "status", side_effect=RuntimeError("debug failure")), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, "debug failure"):
                    cli.main(["status"])

    def test_pending_memory_queue_is_not_seeded_and_cli_flags_are_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            self.assertFalse((vault.root / "06_indexes/pending_db_writes.yaml").exists())
            self.assertFalse((vault.root / "06_indexes/cli/pyproject.toml").exists())
            self.assertFalse((vault.root / "06_indexes/cli/arpent/__init__.py").exists())
            schema = (vault.root / "06_indexes/schemas/todo_schema.sql").read_text(
                encoding="utf-8"
            )
            self.assertIn("Version 4 schema", schema)
            self.assertIn("PRAGMA user_version = 4", schema)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                cli.build_parser().parse_args([
                    "session", "end", "--summary", "close", "--observation", "not shipped",
                ])
            self.assertEqual(raised.exception.code, 2)


class IndexAndUsageConcurrencyTests(unittest.TestCase):
    def test_context_show_l1_refuses_a_live_stale_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            index.build_index(vault)
            entry = context.get_entry(vault, "me.md")
            context.set_summary(
                vault,
                "me.md",
                "Summary that must not outlive its source.",
                expected_hash=entry["source_hash"],
            )
            vault_mod.set_vault_mode(vault, "full")
            source = vault.root / "me.md"
            source.write_text(
                source.read_text(encoding="utf-8") + "\nlive change\n",
                encoding="utf-8",
            )

            result = run_cli(vault.root, "context", "show", "me.md", "--level", "l1")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("stale", result.stderr)
            self.assertNotIn("Summary that must not", result.stdout)

    def test_context_set_holds_the_source_mutation_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            index.build_index(vault)
            entry = context.get_entry(vault, "me.md")
            original = index.current_context_hash

            def checked_hash(*args, **kwargs):
                held = getattr(vault_mod._LOCK_STATE, "held", {})
                self.assertIn((vault.root, "mutations"), held)
                return original(*args, **kwargs)

            with mock.patch.object(index, "current_context_hash", side_effect=checked_hash):
                stored = context.set_summary(
                    vault, "me.md", "Serialized summary.", expected_hash=entry["source_hash"],
                )
            self.assertEqual(stored["l1"]["status"], "fresh")

    def test_incomplete_index_generation_is_detected_and_rebuild_heals_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            first = index.build_index(vault)
            original_replace = index.os.replace

            def fail_commit(source, destination):
                if Path(destination) == vault.root / "06_indexes/index.json":
                    raise OSError("injected index commit failure")
                return original_replace(source, destination)

            with mock.patch.object(index.os, "replace", side_effect=fail_commit):
                with self.assertRaisesRegex(OSError, "injected"):
                    index.build_index(vault)
            current_index = json.loads(
                (vault.root / "06_indexes/index.json").read_text(encoding="utf-8")
            )
            self.assertEqual(current_index["generation"], first["generation"])
            with self.assertRaisesRegex(ValueError, "generation"):
                context.load_context_index(vault)

            rebuilt = index.build_index(vault)
            context_data = context.load_context_index(vault)
            self.assertEqual(context_data["generation"], rebuilt["generation"])

    def test_index_signature_tracks_sources_without_counting_its_staging_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            source = vault.root / "me.md"
            before = index._inventory_source_signature(vault)
            source.write_text(source.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
            self.assertNotEqual(index._inventory_source_signature(vault), before)

            first = index.build_index(vault)
            second = index.build_index(vault)
            self.assertNotEqual(first["generation"], second["generation"])
            self.assertEqual(
                context.load_context_index(vault)["generation"], second["generation"],
            )

    def test_usage_append_waits_for_mutations_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            vault_mod.set_vault_mode(vault, "full")
            args = argparse.Namespace(command="status")
            started = threading.Event()
            finished = threading.Event()

            def append():
                started.set()
                usage.append_usage(args)
                finished.set()

            with mock.patch.dict(os.environ, {"ARPENT_VAULT_ROOT": str(vault.root)}):
                with vault.exclusive_lock("mutations"):
                    thread = threading.Thread(target=append)
                    thread.start()
                    self.assertTrue(started.wait(1))
                    time.sleep(0.05)
                    self.assertFalse(finished.is_set())
                thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertTrue((vault.root / usage.USAGE_RELPATH).is_file())

    def test_usage_reader_streams_and_retains_a_bounded_recent_window(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            log = vault.root / usage.USAGE_RELPATH
            records = [
                {"timestamp": f"2030-01-0{day}T00:00:00Z", "command": f"cmd-{day}", "exit_code": 0}
                for day in range(1, 4)
            ]
            log.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
            result = usage.read_usage(vault, max_events=2)
            self.assertEqual([event["command"] for event in result["events"]], ["cmd-2", "cmd-3"])
            self.assertEqual(result["dropped_events"], 1)
            self.assertEqual(result["v1_count"], 3)
            with self.assertRaisesRegex(ValueError, "between 1"):
                usage.read_usage(vault, max_events=usage.MAX_USAGE_EVENTS + 1)

            oversized = json.dumps({
                "timestamp": "2030-01-04T00:00:00Z",
                "command": "x" * 256,
                "exit_code": 0,
            })
            valid = json.dumps({
                "timestamp": "2030-01-05T00:00:00Z",
                "command": "valid",
                "exit_code": 0,
            })
            log.write_text(f"{oversized}\n{valid}\n", encoding="utf-8")
            with mock.patch.object(usage, "MAX_USAGE_LINE_BYTES", 128):
                bounded = usage.read_usage(vault, max_events=2)
            self.assertEqual([event["command"] for event in bounded["events"]], ["valid"])
            self.assertEqual(bounded["malformed_lines"], 1)

            log.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )
            with mock.patch.object(usage, "MAX_USAGE_RETAINED_BYTES", 150):
                byte_bounded = usage.read_usage(vault, max_events=3)
            self.assertLess(len(byte_bounded["events"]), 3)
            self.assertGreater(byte_bounded["dropped_events"], 0)

    def test_triage_hashes_large_sources_with_bounded_preview_and_item_limit(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            payload = b"abcdefghij" * 20
            source = vault.root / "00_inbox/large.txt"
            source.write_bytes(payload)
            with mock.patch.object(views, "MAX_TRIAGE_TEXT_BYTES", 16):
                item = next(row for row in views.triage_items(vault) if row["path"].endswith("large.txt"))
            self.assertEqual(item["sha256"], hashlib.sha256(payload).hexdigest())
            self.assertIn("preview truncated", item["preview"])

            (vault.root / "00_inbox/second.txt").write_text("second", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "safety limit"):
                views.triage_items(vault, max_items=1)


if __name__ == "__main__":
    unittest.main()

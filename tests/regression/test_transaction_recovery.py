from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import backup
from scripts import frontmatter
from scripts import notes
from scripts import projects
from scripts import session
from scripts import todo
from tests.regression._support import initialized


class CoordinatedTransactionRecoveryTests(unittest.TestCase):
    def test_interrupted_note_move_is_rolled_back_before_next_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            plan = notes.plan_note_new(
                vault, title="Before interruption", ntype="note", body="original",
            )
            original, _, metadata = notes.apply_note_new(vault, plan)
            source_text = original.read_text(encoding="utf-8")
            changed = dict(metadata)
            changed["title"] = "after_interruption"
            changed["modified"] = frontmatter.now_note_timestamp()

            with mock.patch.object(
                notes, "_commit_note_transaction", side_effect=KeyboardInterrupt,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    notes.write_routed_note(
                        vault, original, changed, "changed", expected_source=source_text,
                    )

            moved = vault.root / "00_inbox/after_interruption.md"
            self.assertTrue(moved.is_file())
            self.assertTrue((vault.root / notes.TRANSACTION_RELPATH).is_file())

            trigger = notes.plan_note_new(
                vault, title="Recovery trigger", ntype="note", body="trigger",
            )
            notes.apply_note_new(vault, trigger)

            self.assertTrue(original.is_file())
            self.assertFalse(moved.exists())
            self.assertFalse((vault.root / notes.TRANSACTION_RELPATH).exists())
            restored, body = frontmatter.read_note(original)
            self.assertEqual(metadata["id"], restored["id"])
            self.assertEqual("original", body)

    def test_partial_session_is_restored_before_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            projects.create_project(vault, "Recovery project")
            context = vault.root / "01_projects/recovery-project/_context.md"
            before = context.read_bytes()
            real_write = vault.atomic_write_text

            def interrupt_after_context(relpath, content):
                result = real_write(relpath, content)
                if relpath.endswith("/_context.md"):
                    raise KeyboardInterrupt
                return result

            with mock.patch.object(
                vault, "atomic_write_text", side_effect=interrupt_after_context,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    session.end_session(
                        vault, project="recovery-project", summary="partial update",
                    )

            self.assertIn("partial update", context.read_text(encoding="utf-8"))
            self.assertTrue((vault.root / session.SESSION_JOURNAL_REL).is_file())

            session.end_session(
                vault, project="recovery-project", summary="recovered update",
            )
            text = context.read_text(encoding="utf-8")
            self.assertNotEqual(before, context.read_bytes())
            self.assertNotIn("partial update", text)
            self.assertIn("recovered update", text)
            self.assertFalse((vault.root / session.SESSION_JOURNAL_REL).exists())

    def test_todo_recovery_keeps_a_detectably_committed_database_update(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            created = todo.add_todo(vault, "Before commit boundary")

            with mock.patch.object(
                todo, "_commit_transaction", side_effect=KeyboardInterrupt,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    todo.edit_todo(
                        vault, created["id"], content="After commit boundary",
                    )

            self.assertTrue((vault.root / todo.TRANSACTION_RELPATH).is_file())
            recovered = todo.show_todo(vault, created["id"])
            self.assertEqual("After commit boundary", recovered["content"])
            self.assertIn("after_commit_boundary.md", recovered["path"])
            self.assertFalse((vault.root / todo.TRANSACTION_RELPATH).exists())

    def test_failed_backup_removes_unpublished_staging(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            destination = Path(temporary) / "snapshots"
            with mock.patch.object(
                backup, "_copy_regular_file", side_effect=OSError("injected copy failure"),
            ):
                with self.assertRaises(OSError):
                    backup.create_backup(vault, destination)

            self.assertTrue(destination.is_dir())
            self.assertEqual([], list(destination.iterdir()))


if __name__ == "__main__":
    unittest.main()

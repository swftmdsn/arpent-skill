from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import file_transaction
from scripts.vault import Vault


JOURNAL = "06_indexes/logs/regression-transaction.json"


class GenericFileTransactionRegressionTests(unittest.TestCase):
    def test_rollback_restores_existing_and_removes_created_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Vault(Path(temporary))
            vault.atomic_write_text("notes/existing.md", "before\n")
            snapshots = file_transaction.snapshot_files(
                vault,
                ["notes/existing.md", "notes/created.md"],
                expected_contents={
                    "notes/existing.md": "after\n",
                    "notes/created.md": "created\n",
                },
            )
            journal = file_transaction.prepare(vault, JOURNAL, snapshots)
            vault.atomic_write_text("notes/existing.md", "after\n")
            vault.atomic_write_text("notes/created.md", "created\n")

            file_transaction.rollback(vault, JOURNAL, journal)

            self.assertEqual((vault.root / "notes/existing.md").read_text(), "before\n")
            self.assertFalse((vault.root / "notes/created.md").exists())
            self.assertFalse((vault.root / JOURNAL).exists())

    def test_recovery_rolls_back_prepared_but_keeps_committed_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Vault(Path(temporary))
            vault.atomic_write_text("notes/item.md", "before\n")
            snapshots = file_transaction.snapshot_files(
                vault,
                ["notes/item.md"],
                expected_contents={"notes/item.md": "after\n"},
            )
            file_transaction.prepare(vault, JOURNAL, snapshots)
            vault.atomic_write_text("notes/item.md", "after\n")
            recovered = file_transaction.recover(vault, JOURNAL)
            self.assertEqual(recovered["phase"], "prepared")
            self.assertEqual((vault.root / "notes/item.md").read_text(), "before\n")

            journal = file_transaction.prepare(vault, JOURNAL, snapshots)
            vault.atomic_write_text("notes/item.md", "after\n")
            journal["phase"] = "committed"
            vault.atomic_write_text(JOURNAL, json.dumps(journal) + "\n")
            file_transaction.recover(vault, JOURNAL)
            self.assertEqual((vault.root / "notes/item.md").read_text(), "after\n")
            self.assertFalse((vault.root / JOURNAL).exists())

    def test_recovery_refuses_unowned_content_and_keeps_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Vault(Path(temporary))
            snapshots = file_transaction.snapshot_files(
                vault,
                ["notes/item.md"],
                expected_contents={"notes/item.md": "owned\n"},
            )
            file_transaction.prepare(vault, JOURNAL, snapshots)
            vault.atomic_write_text("notes/item.md", "external\n")

            with self.assertRaisesRegex(ValueError, "unowned file"):
                file_transaction.recover(vault, JOURNAL)

            self.assertEqual((vault.root / "notes/item.md").read_text(), "external\n")
            self.assertTrue((vault.root / JOURNAL).is_file())

    def test_invalid_or_unsafe_journal_is_not_applied(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Vault(Path(temporary))
            invalid = {
                "format": "arpent-file-transaction",
                "version": 1,
                "phase": "prepared",
                "files": [{
                    "path": "../outside.txt",
                    "existed": False,
                    "content": None,
                    "original_sha256": None,
                    "expected_sha256": None,
                }],
            }
            vault.atomic_write_text(JOURNAL, json.dumps(invalid) + "\n")

            with self.assertRaisesRegex(ValueError, "relative|cannot contain"):
                file_transaction.recover(vault, JOURNAL)

            self.assertTrue((vault.root / JOURNAL).is_file())
            self.assertFalse((vault.root.parent / "outside.txt").exists())


if __name__ == "__main__":
    unittest.main()

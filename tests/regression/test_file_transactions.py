from __future__ import annotations

import base64
import errno
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import file_transaction
from scripts.vault import Vault


JOURNAL = "06_indexes/logs/regression-transaction.json"


class GenericFileTransactionRegressionTests(unittest.TestCase):
    def test_v2_interrupted_recovery_preserves_exact_crlf_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Vault(Path(temporary))
            original = b"first\r\nsecond\r\n"
            target = vault.safe_output_path("notes/windows.md")
            target.write_bytes(original)
            snapshots = file_transaction.snapshot_files(
                vault,
                ["notes/windows.md"],
                expected_contents={"notes/windows.md": "changed\n"},
            )

            journal = file_transaction.prepare(vault, JOURNAL, snapshots)
            self.assertEqual(journal["version"], 2)
            self.assertEqual(
                base64.b64decode(journal["files"][0]["content_base64"]),
                original,
            )
            self.assertEqual(
                journal["files"][0]["original_sha256"],
                hashlib.sha256(original).hexdigest(),
            )
            vault.atomic_write_text("notes/windows.md", "changed\n")

            file_transaction.recover(vault, JOURNAL)

            self.assertEqual(target.read_bytes(), original)
            self.assertFalse((vault.root / JOURNAL).exists())

    def test_persisted_v1_journal_remains_recoverable(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Vault(Path(temporary))
            before = "before\n"
            after = "after\n"
            vault.atomic_write_text("notes/item.md", after)
            journal = {
                "format": "arpent-file-transaction",
                "version": 1,
                "phase": "prepared",
                "files": [{
                    "path": "notes/item.md",
                    "existed": True,
                    "content": before,
                    "original_sha256": hashlib.sha256(before.encode("utf-8")).hexdigest(),
                    "expected_sha256": hashlib.sha256(after.encode("utf-8")).hexdigest(),
                }],
            }
            vault.atomic_write_text(JOURNAL, json.dumps(journal) + "\n")

            recovered = file_transaction.recover(vault, JOURNAL)

            self.assertEqual(recovered["version"], 1)
            self.assertEqual((vault.root / "notes/item.md").read_bytes(), before.encode("utf-8"))
            self.assertFalse((vault.root / JOURNAL).exists())

    def test_v1_ownership_accepts_universal_newlines_but_v2_does_not(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Vault(Path(temporary))
            before = "before\n"
            after = "after\n"
            journal = {
                "format": file_transaction.FORMAT,
                "version": 1,
                "phase": "prepared",
                "files": [{
                    "path": "notes/item.md",
                    "existed": True,
                    "content": before,
                    "original_sha256": hashlib.sha256(before.encode()).hexdigest(),
                    "expected_sha256": hashlib.sha256(after.encode()).hexdigest(),
                }],
            }
            vault.atomic_write_text(JOURNAL, json.dumps(journal) + "\n")
            target = vault.safe_output_path("notes/item.md")
            target.write_bytes(b"after\r\n")

            file_transaction.recover(vault, JOURNAL)
            self.assertEqual(target.read_bytes(), b"before\n")

            target.write_bytes(b"before\n")
            snapshots = file_transaction.snapshot_files(
                vault,
                ["notes/item.md"],
                expected_contents={"notes/item.md": after},
            )
            file_transaction.prepare(vault, JOURNAL, snapshots)
            target.write_bytes(b"after\r\n")
            with self.assertRaisesRegex(ValueError, "unowned file"):
                file_transaction.recover(vault, JOURNAL)
            self.assertEqual(target.read_bytes(), b"after\r\n")

    def test_move_rollback_recreates_source_without_hardlinks_before_removing_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Vault(Path(temporary))
            source = vault.safe_output_path("notes/source.md")
            source.write_bytes(b"original\r\n")
            snapshots = file_transaction.snapshot_files(
                vault,
                ["notes/source.md", "notes/destination.md"],
                expected_contents={
                    "notes/source.md": "changed\n",
                    "notes/destination.md": "changed\n",
                },
            )
            file_transaction.prepare(vault, JOURNAL, snapshots)
            source.unlink()
            destination = vault.safe_output_path("notes/destination.md")
            destination.write_bytes(b"changed\n")

            unsupported = OSError(errno.ENOTSUP, "hardlinks unsupported")
            with mock.patch.object(file_transaction.os, "link", side_effect=unsupported):
                file_transaction.recover(vault, JOURNAL)

            self.assertEqual(source.read_bytes(), b"original\r\n")
            self.assertFalse(destination.exists())

    def test_failed_source_recreation_leaves_transaction_destination_intact(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = Vault(Path(temporary))
            source = vault.safe_output_path("notes/source.md")
            source.write_bytes(b"original\n")
            snapshots = file_transaction.snapshot_files(
                vault,
                ["notes/source.md", "notes/destination.md"],
                expected_contents={
                    "notes/source.md": "moved\n",
                    "notes/destination.md": "moved\n",
                },
            )
            file_transaction.prepare(vault, JOURNAL, snapshots)
            source.unlink()
            destination = vault.safe_output_path("notes/destination.md")
            destination.write_bytes(b"moved\n")

            unsupported = OSError(errno.ENOTSUP, "hardlinks unsupported")
            with mock.patch.object(file_transaction.os, "link", side_effect=unsupported), mock.patch.object(file_transaction, "_copy_no_replace", side_effect=OSError("copy failed")):
                with self.assertRaisesRegex(OSError, "copy failed"):
                    file_transaction.recover(vault, JOURNAL)

            self.assertFalse(source.exists())
            self.assertEqual(destination.read_bytes(), b"moved\n")
            self.assertTrue((vault.root / JOURNAL).is_file())

    def test_directory_move_fails_closed_without_atomic_no_replace_primitive(self):
        class NoRenamePrimitives:
            pass

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            with mock.patch.object(file_transaction.ctypes, "CDLL", return_value=NoRenamePrimitives()), mock.patch.object(file_transaction.os, "rename") as rename:
                with self.assertRaises(OSError) as raised:
                    file_transaction.move_no_replace(source, destination)

            self.assertEqual(raised.exception.errno, errno.ENOTSUP)
            rename.assert_not_called()
            self.assertTrue(source.is_dir())
            self.assertFalse(os.path.lexists(destination))

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

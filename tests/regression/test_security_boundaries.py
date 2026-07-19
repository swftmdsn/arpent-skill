from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import backup, index, notes, session, views
from tests.regression._support import initialized


class SecurityBoundaryRegressionTests(unittest.TestCase):
    def test_relative_absolute_and_ingest_escape_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            vault = initialized(parent)
            outside = parent / "outside.txt"
            outside.write_text("private\n", encoding="utf-8")

            for candidate in ("../escape.txt", str(outside.resolve())):
                with self.subTest(candidate=candidate), self.assertRaisesRegex(
                    ValueError, "relative|inside the vault|confined"
                ):
                    vault.safe_output_path(candidate)
            with self.assertRaisesRegex(ValueError, "confined under 00_inbox"):
                notes.plan_ingest(vault, str(outside), title="Escape")
            with self.assertRaisesRegex(ValueError, "single vault folder"):
                session.end_session(
                    vault, project="../outside", summary="Must not escape."
                )
            self.assertEqual(outside.read_text(encoding="utf-8"), "private\n")

    def test_symlinked_output_parent_is_never_followed(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            vault = initialized(parent)
            outside = parent / "outside"
            outside.mkdir()
            linked = vault.root / "00_inbox/linked"
            try:
                linked.symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "symlink"):
                vault.atomic_write_text("00_inbox/linked/escape.md", "blocked")

            self.assertEqual(list(outside.iterdir()), [])

    def test_note_filename_collision_preserves_the_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            first = notes.plan_note_new(
                vault, title="Same semantic name", ntype="note", body="first body"
            )
            path, _, metadata = notes.apply_note_new(vault, first)
            original = path.read_bytes()
            second = notes.plan_note_new(
                vault, title="Same semantic name", ntype="note", body="second body"
            )

            with self.assertRaisesRegex(ValueError, "already exists"):
                notes.apply_note_new(vault, second)

            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(notes.find_note(vault, metadata["id"])[2], "first body")

    def test_symlinked_inbox_is_rejected_without_reading_the_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            vault = initialized(parent)
            outside = parent / "outside-inbox"
            outside.mkdir()
            secret = outside / "secret.txt"
            secret.write_text("must not be inventoried", encoding="utf-8")
            shutil.rmtree(vault.root / "00_inbox")
            try:
                (vault.root / "00_inbox").symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "symlinked 00_inbox"):
                views.triage_items(vault)
            self.assertEqual("must not be inventoried", secret.read_text(encoding="utf-8"))

    def test_search_falls_back_when_the_generated_fts_database_is_corrupt(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = initialized(Path(temporary))
            plan = notes.plan_note_new(
                vault, title="Fallback source", ntype="note", body="livefallbacktoken",
            )
            _, _, metadata = notes.apply_note_new(vault, plan)
            index.build_index(vault)
            database = vault.root / "06_indexes/databases/search.db"
            database.write_bytes(b"not a sqlite database")

            hits = views.search(vault, "livefallbacktoken")

            self.assertEqual([metadata["id"]], [hit["id"] for hit in hits])
            self.assertTrue(all(hit["backend"] == "text-fallback" for hit in hits))

    def test_backup_manifest_traversal_is_rejected_before_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            vault = initialized(parent)
            result = backup.create_backup(vault, parent / "snapshots")
            snapshot = Path(result["snapshot_path"])
            manifest_path = snapshot / backup.MANIFEST_NAME
            checksum_path = snapshot / backup.MANIFEST_CHECKSUM_NAME
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["entries"].append({
                "path": "../escape",
                "type": "file",
                "mode": 0o600,
                "mtime_ns": 0,
                "size": 0,
                "sha256": hashlib.sha256(b"").hexdigest(),
            })
            encoded = (
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            manifest_path.write_bytes(encoded)
            checksum_path.write_text(
                "%s  %s\n" % (hashlib.sha256(encoded).hexdigest(), backup.MANIFEST_NAME),
                encoding="ascii",
            )
            target = parent / "must-not-exist"

            with self.assertRaisesRegex(ValueError, "Unsafe backup path"):
                backup.restore_backup(snapshot, target)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()

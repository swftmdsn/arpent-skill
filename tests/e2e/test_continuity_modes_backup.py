from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.e2e._support import initialize, json_result, require_success, run_cli


class ContinuityBackupAndModeE2ETests(unittest.TestCase):
    def test_context_session_backup_verify_and_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = initialize(parent)
            require_success(run_cli(root, "project", "create", "Restore Loop"))
            note = json_result(run_cli(
                root,
                "note", "new", "Restore source",
                "--project", "restore-loop",
                "--body", "Restore token: amber-planet.",
                "--json",
            ))
            require_success(run_cli(root, "index"))
            pending = json_result(run_cli(
                root, "context", "pending", "--path", note["path"], "--json",
            ))
            source = next(row for row in pending if row["path"] == note["path"])
            require_success(run_cli(
                root,
                "context", "set", note["path"],
                "--source-hash", source["source_hash"],
                "--summary", "The amber-planet source survives a logical restore.",
            ))
            require_success(run_cli(
                root,
                "session", "end", "--project", "restore-loop",
                "--summary", "Prepared a verified restore.",
                "--next-step", "Open the restored context.",
            ))

            destination = parent / "external-backups"
            require_success(run_cli(root, "backup", "--destination", str(destination)))
            snapshots = sorted(path for path in destination.iterdir() if path.is_dir())
            self.assertEqual(len(snapshots), 1)
            require_success(run_cli(root, "backup", "verify", str(snapshots[0])))

            restored = parent / "restored"
            require_success(run_cli(
                root,
                "backup", "restore", str(snapshots[0]),
                "--to", str(restored), "--yes",
            ))
            self.assertTrue((restored / note["path"]).is_file())
            self.assertIn(
                "Prepared a verified restore.",
                (restored / "01_projects/restore-loop/_context.md").read_text(encoding="utf-8"),
            )
            context_data = json.loads(
                (restored / "06_indexes/context_index.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                context_data["entries"][note["path"]]["l1"]["summary"],
                "The amber-planet source survives a logical restore.",
            )
            self.assertFalse((restored / "06_indexes/databases/search.db").exists())
            rebuilt = require_success(run_cli(restored, "index"))
            self.assertIn("Indexed", rebuilt.stdout)

    def test_minimal_blocks_domain_commands_and_roundtrip_preserves_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = initialize(Path(temporary), minimal=True)
            manual = root / "00_inbox/manual.txt"
            manual.write_text("preserve this exact content\n", encoding="utf-8")
            skill_before = (root / "06_indexes/global_skills/arpent.skill.md").read_bytes()

            for command in (
                ("status",),
                ("note", "new", "blocked"),
                ("todo", "list"),
                ("session", "end", "--summary", "blocked", "--memory-log"),
            ):
                with self.subTest(command=command):
                    blocked = run_cli(root, *command)
                    self.assertNotEqual(blocked.returncode, 0)
                    self.assertIn("not available in minimal mode", blocked.stderr)
            self.assertFalse((root / "00_inbox/blocked.md").exists())
            self.assertFalse((root / "06_indexes/logs/usage.log").exists())

            promoted = json_result(run_cli(root, "mode", "full", "--json"))
            self.assertTrue(promoted["changed"])
            marker = json.loads((root / ".arpent").read_text(encoding="utf-8"))
            self.assertEqual(marker["mode"], "full")
            self.assertTrue((root / ".git").is_dir())
            self.assertEqual(manual.read_text(encoding="utf-8"), "preserve this exact content\n")
            require_success(run_cli(root, "status"))

            demoted = json_result(run_cli(root, "mode", "minimal", "--json"))
            self.assertTrue(demoted["changed"])
            marker = json.loads((root / ".arpent").read_text(encoding="utf-8"))
            self.assertEqual(marker["mode"], "minimal")
            self.assertFalse(marker["auto_full"])
            self.assertEqual(manual.read_text(encoding="utf-8"), "preserve this exact content\n")
            self.assertEqual(
                (root / "06_indexes/global_skills/arpent.skill.md").read_bytes(),
                skill_before,
            )


if __name__ == "__main__":
    unittest.main()

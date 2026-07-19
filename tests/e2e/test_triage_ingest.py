from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts import frontmatter
from tests.e2e._support import initialize, json_result, require_success, run_cli


class TriageAndIngestE2ETests(unittest.TestCase):
    def test_text_malformed_and_binary_inventory_and_lossless_ingestion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = initialize(Path(temporary))
            raw_content = "\n\nFirst line\r\n\r\nSecond line\n"
            malformed_content = "---\ntitle: broken\nNo closing fence\n"
            binary_content = b"%PDF\x00\xfforiginal-bytes"
            raw = root / "00_inbox/raw.txt"
            malformed = root / "00_inbox/broken.md"
            binary = root / "00_inbox/report.pdf"
            raw.write_bytes(raw_content.encode("utf-8"))
            with malformed.open("w", encoding="utf-8", newline="") as stream:
                stream.write(malformed_content)
            binary.write_bytes(binary_content)

            inventory = json_result(run_cli(root, "triage", "--json"))
            by_path = {item["path"]: item for item in inventory}
            self.assertEqual(by_path["00_inbox/raw.txt"]["kind"], "text")
            self.assertEqual(by_path["00_inbox/broken.md"]["kind"], "malformed")
            self.assertEqual(by_path["00_inbox/report.pdf"]["kind"], "binary")
            for path, source in (
                ("00_inbox/raw.txt", raw),
                ("00_inbox/broken.md", malformed),
                ("00_inbox/report.pdf", binary),
            ):
                self.assertEqual(by_path[path]["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())

            for source_rel, title, expected, expected_kind in (
                ("00_inbox/raw.txt", "Raw imported", raw_content, "text"),
                ("00_inbox/broken.md", "Broken imported", malformed_content, "malformed"),
            ):
                preview = json_result(run_cli(
                    root, "note", "ingest", source_rel,
                    "--title", title, "--dry-run", "--json",
                ))
                self.assertEqual(preview["kind"], expected_kind)
                applied = json_result(run_cli(
                    root, "note", "ingest", source_rel,
                    "--title", title,
                    "--source-hash", preview["source_sha256"],
                    "--json",
                ))
                self.assertFalse((root / source_rel).exists())
                with (root / applied["destination_path"]).open(
                    "r", encoding="utf-8", newline=""
                ) as stream:
                    _, body = frontmatter.parse_note_text(stream.read())
                self.assertEqual(body, expected)

            require_success(run_cli(root, "project", "create", "Ingest Home"))
            binary_preview = json_result(run_cli(
                root,
                "note", "ingest", "00_inbox/report.pdf",
                "--title", "Report reference",
                "--project", "ingest-home",
                "--attachment", "--dry-run", "--json",
            ))
            binary_applied = json_result(run_cli(
                root,
                "note", "ingest", "00_inbox/report.pdf",
                "--title", "Report reference",
                "--project", "ingest-home",
                "--attachment",
                "--source-hash", binary_preview["source_sha256"],
                "--json",
            ))
            attachment = root / "01_projects/ingest-home/attachments/report.pdf"
            self.assertEqual(attachment.read_bytes(), binary_content)
            self.assertFalse(binary.exists())
            metadata, body = frontmatter.read_note(root / binary_applied["destination_path"])
            self.assertEqual(metadata["type"], "reference")
            self.assertEqual(metadata["link"], "01_projects/ingest-home/attachments/report.pdf")
            self.assertIn(metadata["link"], body)

            remaining = json_result(run_cli(root, "triage", "--json"))
            remaining_by_path = {item["path"]: item for item in remaining}
            self.assertEqual(set(remaining_by_path), {
                "00_inbox/raw_imported.md",
                "00_inbox/broken_imported.md",
            })
            self.assertTrue(all(item["kind"] == "note" for item in remaining))
            self.assertTrue(all(item["actions"] == ["edit", "leave"] for item in remaining))


if __name__ == "__main__":
    unittest.main()

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import frontmatter
from scripts import init_structure
from scripts import projects
from scripts.vault import init_vault


class InitStructureTests(unittest.TestCase):
    def test_json_creates_each_kind_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "structure.json"
            source.write_text(json.dumps({
                "areas": ["Personal Life"],
                "resources": ["Design References"],
                "projects": [{
                    "name": "Website Refresh",
                    "area": "Personal Life",
                    "effort_cadence": "slowburn",
                    "effort_level": "medium",
                }],
            }), encoding="utf-8")

            structure = init_structure.load_structure(source)
            vault = init_vault(root / "vault", minimal=True)
            first = init_structure.apply_structure(vault, structure)

            self.assertEqual(first["areas"]["created"], ["personal_life"])
            self.assertEqual(first["resources"]["created"], ["design-references"])
            self.assertEqual(first["projects"]["created"], ["website-refresh"])
            project = vault.root / "01_projects" / "website-refresh"
            for child in ("notes", "drafts", "attachments"):
                self.assertTrue((project / child).is_dir())
            metadata, _ = frontmatter.read_note(project / "_context.md")
            self.assertEqual(metadata["area"], "personal_life")
            self.assertEqual(metadata["effort_cadence"], "slowburn")
            self.assertEqual(metadata["effort_level"], "medium")

            second = init_structure.apply_structure(vault, structure)
            self.assertEqual(second["areas"]["existing"], ["personal_life"])
            self.assertEqual(second["resources"]["existing"], ["design-references"])
            self.assertEqual(second["projects"]["existing"], ["website-refresh"])

    def test_markdown_accepts_any_subset(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "structure.md"
            source.write_text(
                "# Initial Resources\n\n## Resources\n- Books\n- Design References\n",
                encoding="utf-8",
            )

            structure = init_structure.load_structure(source)

            self.assertEqual(structure["areas"], [])
            self.assertEqual(
                [item["slug"] for item in structure["resources"]],
                ["books", "design-references"],
            )
            self.assertEqual(structure["projects"], [])

    def test_unknown_json_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "structure.json"
            source.write_text('{"folders": ["misc"]}', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Unknown init structure key"):
                init_structure.load_structure(source)

    def test_structured_area_name_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "structure.json"
            source.write_text(json.dumps({
                "areas": ["area__perso__health__active"],
                "projects": [{
                    "name": "Fitness plan",
                    "area": "area__perso__health__active",
                }],
            }), encoding="utf-8")

            structure = init_structure.load_structure(source)

            self.assertEqual(structure["areas"][0]["slug"], "area__perso__health__active")
            self.assertEqual(structure["projects"][0]["area"], "area__perso__health__active")

    def test_noncanonical_existing_project_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "01_projects" / "website-refresh"
            project.mkdir(parents=True)
            structure = init_structure._validate_structure({"projects": ["Website refresh"]})

            with self.assertRaisesRegex(ValueError, "is not canonical"):
                init_structure.preflight_structure(root, structure, minimal=True)

    def test_incomplete_existing_project_context_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "01_projects" / "website-refresh"
            for child in ("notes", "drafts", "attachments"):
                (project / child).mkdir(parents=True)
            (project / "_context.md").write_text(
                "---\nproject: website-refresh\n---\n",
                encoding="utf-8",
            )
            structure = init_structure._validate_structure({"projects": ["Website refresh"]})

            with self.assertRaisesRegex(ValueError, "incomplete context frontmatter"):
                init_structure.preflight_structure(root, structure, minimal=True)

    def test_equivalent_structured_area_reference_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=True)
            vault.safe_ensure_directory("02_areas/area__perso__health__active")
            projects.create_project(vault, "Fitness plan", area="health")
            structure = init_structure._validate_structure({
                "projects": [{
                    "name": "Fitness plan",
                    "area": "area__perso__health__active",
                }],
            })

            result = init_structure.apply_structure(vault, structure)

            self.assertEqual(result["projects"]["existing"], ["fitness-plan"])

    def test_cli_rejects_missing_area_before_creating_vault(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "structure.json"
            target = root / "vault"
            source.write_text(json.dumps({
                "projects": [{"name": "Website refresh", "area": "missing"}],
            }), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable, "-m", "scripts.cli", "init", str(target),
                    "--minimal", "--structure", str(source),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("which is not configured or present", result.stderr)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()

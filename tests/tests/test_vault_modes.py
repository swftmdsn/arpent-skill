import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path

from scripts import cli, frontmatter, notes
from scripts import vault as vault_mod
from scripts.vault import MARKER_VERSION, Vault, init_vault


ROOT = Path(__file__).resolve().parents[2]
SKILLS = {
    "arpent.skill.md",
    "todo.skill.md",
    "context_summary.skill.md",
    "reader.skill.md",
    "review.skill.md",
    "z_backup.skill.md",
    "_template_tool.skill.md",
}


def _env(root: Path):
    env = os.environ.copy()
    env["ARPENT_VAULT_ROOT"] = str(root)
    env["PYTHONPATH"] = str(ROOT)
    return env


def _cli(root: Path, *args):
    return subprocess.run(
        [sys.executable, "-m", "scripts.cli", *args],
        cwd=root,
        env=_env(root),
        capture_output=True,
        text=True,
        check=False,
    )


class VaultModeTests(unittest.TestCase):
    def test_ready_template_requests_one_automatic_full_promotion(self):
        marker = json.loads((ROOT / "architecture_template/.arpent").read_text(encoding="utf-8"))
        self.assertEqual(marker, {
            "version": MARKER_VERSION,
            "name": "arpent",
            "mode": "minimal",
            "auto_full": True,
        })

    def test_ready_template_can_promote_to_full(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            shutil.copytree(ROOT / "architecture_template", root)

            result = _cli(root, "mode", "full", "--json")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(Vault(root).marker_data()["mode"], "full")
            self.assertTrue((root / ".git").is_dir())

    def test_ready_template_promotes_before_first_domain_command(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            shutil.copytree(ROOT / "architecture_template", root)

            result = _cli(root, "status")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(Vault(root).marker_data(), {
                "version": MARKER_VERSION,
                "name": "arpent",
                "mode": "full",
                "auto_full": False,
            })
            self.assertTrue((root / ".git").is_dir())
            inventory = json.loads((root / "06_indexes/index.json").read_text(encoding="utf-8"))
            sidecar = json.loads((root / "06_indexes/sidecar.json").read_text(encoding="utf-8"))
            self.assertNotIn("01_projects/_template_project/_context.md", sidecar)
            marker_entry = next(item for item in inventory["files"] if item["path"] == ".arpent")
            self.assertEqual(
                marker_entry["sha256"],
                hashlib.sha256((root / ".arpent").read_bytes()).hexdigest(),
            )

    def test_automatic_promotion_obeys_confirmation_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            shutil.copytree(ROOT / "architecture_template", root)
            operations = root / "06_indexes/cli/operations.yaml"
            operations.write_text(
                operations.read_text(encoding="utf-8").replace(
                    "policy: explicit-intent", "policy: always", 1,
                ),
                encoding="utf-8",
            )

            result = _cli(root, "status")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("arpent mode full --yes", result.stderr)
            self.assertEqual(Vault(root).marker_data()["mode"], "minimal")
            self.assertTrue(Vault(root).marker_data()["auto_full"])
            self.assertFalse((root / ".git").exists())

    def test_failed_promotion_restores_exact_minimal_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            shutil.copytree(ROOT / "architecture_template", root)
            original = (root / ".arpent").read_bytes()

            with mock.patch.object(cli.index_mod, "build_index", side_effect=ValueError("boom")):
                with self.assertRaisesRegex(ValueError, "boom"):
                    cli._promote_to_full(Vault(root))

            self.assertEqual((root / ".arpent").read_bytes(), original)
            self.assertEqual(Vault(root).marker_data()["mode"], "minimal")

    def test_failed_promotion_preserves_crlf_marker_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            shutil.copytree(ROOT / "architecture_template", root)
            marker = root / ".arpent"
            original = marker.read_bytes().replace(b"\n", b"\r\n")
            marker.write_bytes(original)

            with mock.patch.object(cli.index_mod, "build_index", side_effect=ValueError("boom")):
                with self.assertRaisesRegex(ValueError, "boom"):
                    cli._promote_to_full(Vault(root))

            self.assertEqual(marker.read_bytes(), original)

    def test_stale_automatic_promotion_cannot_override_explicit_minimal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "vault"
            shutil.copytree(ROOT / "architecture_template", root)
            vault = Vault(root)
            vault_mod.set_vault_mode(vault, "minimal")

            with self.assertRaisesRegex(ValueError, "disabled by an explicit minimal choice"):
                cli._promote_to_full(vault, automatic=True)

            self.assertEqual(vault.marker_data()["mode"], "minimal")
            self.assertFalse(vault.marker_data()["auto_full"])

    def test_shared_mode_lock_cannot_silently_upgrade(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault")

            with vault.shared_lock("mode"):
                with self.assertRaisesRegex(RuntimeError, "Cannot upgrade shared"):
                    with vault.exclusive_lock("mode"):
                        self.fail("shared mode lock was silently upgraded")

    def test_internal_cron_command_does_not_deadlock_on_mode_guard(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault")
            cron_path = vault.root / "06_indexes/cron.json"
            config = json.loads(cron_path.read_text(encoding="utf-8"))
            job = config["jobs"][0]
            job.update({
                "enabled": True,
                "schedule": "* * * * *",
                "command": "arpent status",
                "timeout_seconds": 5,
                "trust": "local-code",
                "last_started": None,
                "last_run": None,
            })
            cron_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

            result = _cli(
                vault.root, "cron", "run", "--tick", "--allow-local-code", "--yes",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("exit 124", result.stdout)

    def test_cron_rejects_recursive_vault_control_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault")
            cron_path = vault.root / "06_indexes/cron.json"
            config = json.loads(cron_path.read_text(encoding="utf-8"))
            config["jobs"][0].update({
                "enabled": True,
                "schedule": "* * * * *",
                "command": "arpent cron run --tick",
                "trust": "local-code",
            })
            cron_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

            result = _cli(
                vault.root, "cron", "run", "--tick", "--allow-local-code", "--yes",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("cannot recursively run cron", result.stderr)

            config["jobs"][0]["command"] = shlex.join([
                sys.executable, "-m", "scripts.cli", "mode", "minimal",
            ])
            cron_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            alternate = _cli(
                vault.root, "cron", "run", "--tick", "--allow-local-code", "--yes",
            )
            self.assertNotEqual(alternate.returncode, 0)
            self.assertIn("or change vault mode", alternate.stderr)

            config["jobs"][0]["command"] = shlex.join([
                sys.executable, "-u", "-m", "scripts.cli", "mode", "minimal",
            ])
            cron_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            with_options = _cli(
                vault.root, "cron", "run", "--tick", "--allow-local-code", "--yes",
            )
            self.assertNotEqual(with_options.returncode, 0)
            self.assertIn("or change vault mode", with_options.stderr)

    def test_mode_switch_waits_for_external_cron_job(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault")
            cron_path = vault.root / "06_indexes/cron.json"
            config = json.loads(cron_path.read_text(encoding="utf-8"))
            code = (
                "import pathlib,time;"
                "pathlib.Path('started.flag').write_text('1');"
                "time.sleep(0.5);"
                "pathlib.Path('finished.flag').write_text('1')"
            )
            config["jobs"][0].update({
                "enabled": True,
                "schedule": "* * * * *",
                "command": shlex.join([sys.executable, "-c", code]),
                "timeout_seconds": 5,
                "trust": "local-code",
                "last_started": None,
                "last_run": None,
            })
            cron_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            cron_process = subprocess.Popen(
                [
                    sys.executable, "-m", "scripts.cli", "cron", "run", "--tick",
                    "--allow-local-code", "--yes",
                ],
                cwd=vault.root,
                env=_env(vault.root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            deadline = time.monotonic() + 3
            while not (vault.root / "started.flag").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue((vault.root / "started.flag").exists())

            mode_process = subprocess.Popen(
                [sys.executable, "-m", "scripts.cli", "mode", "minimal", "--json"],
                cwd=vault.root,
                env=_env(vault.root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            with self.assertRaises(subprocess.TimeoutExpired):
                mode_process.wait(timeout=0.1)
            cron_stdout, cron_stderr = cron_process.communicate(timeout=10)
            mode_stdout, mode_stderr = mode_process.communicate(timeout=10)

            self.assertEqual(cron_process.returncode, 0, cron_stderr or cron_stdout)
            self.assertEqual(mode_process.returncode, 0, mode_stderr or mode_stdout)
            self.assertTrue((vault.root / "finished.flag").exists())
            self.assertEqual(Vault(vault.root).marker_data()["mode"], "minimal")

    def test_minimal_keeps_all_skills_and_does_not_initialize_git(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=True)

            self.assertEqual(vault.marker_data(), {
                "version": MARKER_VERSION,
                "name": "arpent",
                "mode": "minimal",
                "auto_full": False,
            })
            self.assertFalse((vault.root / ".git").exists())
            self.assertEqual(
                {path.name for path in (vault.root / "06_indexes/global_skills").glob("*.md")},
                SKILLS,
            )

    def test_minimal_blocks_cli_domain_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=True)

            status = _cli(vault.root, "status")
            capture = _cli(vault.root, "note", "new", "blocked")

            self.assertNotEqual(status.returncode, 0)
            self.assertIn("not available in minimal mode", status.stderr)
            self.assertNotEqual(capture.returncode, 0)
            self.assertFalse((vault.root / "00_inbox/blocked.md").exists())
            self.assertFalse((vault.root / "06_indexes/logs/usage.log").exists())

    def test_mode_roundtrip_preserves_skills_and_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=True)
            note = vault.root / "00_inbox/manual.txt"
            note.write_text("preserve me\n", encoding="utf-8")
            structured = vault.root / "00_inbox/minimal_capture.md"
            metadata = notes.build_frontmatter(
                vault, title="Minimal capture", ntype="note", source="manual",
            )
            structured.write_text(
                frontmatter.compose_note(metadata, "Created directly in minimal mode."),
                encoding="utf-8",
            )
            skill_hashes = {
                path.name: path.read_bytes()
                for path in (vault.root / "06_indexes/global_skills").glob("*.md")
            }

            to_full = _cli(vault.root, "mode", "full", "--json")
            self.assertEqual(to_full.returncode, 0, to_full.stderr)
            self.assertEqual(Vault(vault.root).marker_data()["mode"], "full")
            self.assertTrue((vault.root / ".git").is_dir())
            status = _cli(vault.root, "status")
            self.assertEqual(status.returncode, 0)
            self.assertIn("Notes: 1", status.stdout)

            to_minimal = _cli(vault.root, "mode", "minimal", "--json")
            self.assertEqual(to_minimal.returncode, 0, to_minimal.stderr)
            marker = Vault(vault.root).marker_data()
            self.assertEqual(marker["mode"], "minimal")
            self.assertFalse(marker["auto_full"])
            blocked = _cli(vault.root, "status")
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("not available in minimal mode", blocked.stderr)
            self.assertEqual(note.read_text(encoding="utf-8"), "preserve me\n")
            self.assertEqual(
                frontmatter.read_note(structured)[1], "Created directly in minimal mode."
            )
            self.assertEqual(
                {
                    path.name: path.read_bytes()
                    for path in (vault.root / "06_indexes/global_skills").glob("*.md")
                },
                skill_hashes,
            )

    def test_old_marker_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".arpent").write_text(
                json.dumps({"version": 1, "name": "arpent", "mode": "minimal"}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "current Arpent format"):
                Vault(root).marker_data()

    def test_generated_and_starter_frontmatter_policies_match(self):
        generated = frontmatter.parse_frontmatter_block(vault_mod.FRONTMATTER_POLICY_STUB)
        starter = frontmatter.parse_frontmatter_block(
            (ROOT / "architecture_template/06_indexes/schemas/frontmatter_policy.yaml").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(generated, starter)
        self.assertEqual(list(generated["fields"]), frontmatter.KEY_ORDER)
        self.assertEqual(generated["enums"]["source"], [
            "manual", "generated", "imported", "captured", "conversation", "derived",
        ])
        self.assertEqual(generated["enums"]["author"], ["user", "agent", "imported"])
        self.assertIn("howto", generated["enums"]["type"])
        self.assertEqual(generated["defaults"], {
            "type": "note",
            "status": "inbox",
            "source": "manual",
            "author": "user",
            "tags": [],
            "pinned": False,
            "related": [],
            "relations": [],
            "observations": [],
            "extracted_to": [],
        })

    def test_initialized_minimal_vault_has_dormant_project_and_routing_templates(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=True)

            self.assertNotIn("_template_project", vault.project_slugs())
            self.assertEqual(
                (vault.root / "01_projects/_template_project/_context.md").read_text(
                    encoding="utf-8"
                ),
                vault_mod.PROJECT_CONTEXT_TEMPLATE_STUB,
            )
            self.assertEqual(
                (vault.root / "06_indexes/docs/architecture/routing.md").read_text(
                    encoding="utf-8"
                ),
                vault_mod.ROUTING_DOC_STUB,
            )
            self.assertEqual(
                (vault.root / "02_areas/_context.template.md").read_text(encoding="utf-8"),
                vault_mod.AREA_CONTEXT_TEMPLATE_STUB,
            )
            self.assertEqual(
                (vault.root / "03_resources/templates/howto.template.md").read_text(
                    encoding="utf-8"
                ),
                vault_mod.HOWTO_TEMPLATE_STUB,
            )

    def test_zero_install_starter_contains_direct_capture_and_project_contracts(self):
        skill = (
            ROOT / "architecture_template/06_indexes/global_skills/arpent.skill.md"
        ).read_text(encoding="utf-8")
        readme = (ROOT / "architecture_template/README.md").read_text(encoding="utf-8")

        self.assertIn("06_indexes/schemas/frontmatter_policy.yaml", skill)
        self.assertIn("routing contract", skill)
        self.assertIn("<type>-<UTC YYYYMMDD>-<a..z,aa..>", skill)
        self.assertIn("In minimal, create a project directly", readme)
        self.assertIn("_template_project/_context.md", readme)

    def test_product_docs_do_not_use_degraded_mode_name(self):
        paths = [ROOT / "README.md", ROOT / "SKILL.md"]
        paths.extend((ROOT / "references").rglob("*.md"))
        paths.append(ROOT / "development/MANIFEST.md")

        violations = [
            path.relative_to(ROOT).as_posix()
            for path in paths
            if "degraded" in path.as_posix().lower()
            or "degraded" in path.read_text(encoding="utf-8").lower()
        ]
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import venv
import zipfile
from pathlib import Path, PurePosixPath


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DATA = {"scripts/COMPASS.md", "scripts/operations.yaml", "scripts/todo_schema.sql"}
BUNDLE_FILES = {
    path.relative_to(REPOSITORY_ROOT).as_posix()
    for path in [
        REPOSITORY_ROOT / "SKILL.md",
        *sorted((REPOSITORY_ROOT / "references").rglob("*")),
    ]
    if path.is_file() and not path.is_symlink() and path.name != ".DS_Store"
}
SDIST_FILES = PACKAGE_DATA | {
    "LICENSE", "README.md", "pyproject.toml", "scripts/__init__.py", "scripts/cli.py",
} | BUNDLE_FILES


class DistributionReleaseTests(unittest.TestCase):
    def _run(self, arguments, *, cwd, environment, timeout=120):
        result = subprocess.run(
            arguments,
            cwd=str(cwd),
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return result

    def _build_wheel(self, source, wheel_dir, environment):
        self._run(
            [
                sys.executable, "-m", "pip", "wheel", ".",
                "--wheel-dir", str(wheel_dir), "--no-deps", "--no-build-isolation",
                "--no-index", "--disable-pip-version-check",
            ],
            cwd=source,
            environment=environment,
        )
        wheels = list(wheel_dir.glob("arpent-*.whl"))
        self.assertEqual(1, len(wheels))
        return wheels[0]

    def _assert_wheel(self, wheel):
        with zipfile.ZipFile(wheel) as archive:
            names = set(archive.namelist())
            self.assertTrue(PACKAGE_DATA.issubset(names))
            for path in BUNDLE_FILES:
                suffix = ".data/data/share/arpent/skill/" + path
                self.assertEqual(1, sum(name.endswith(suffix) for name in names), path)
            entry_points_name = next(name for name in names if name.endswith(".dist-info/entry_points.txt"))
            metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
            entry_points = archive.read(entry_points_name).decode("utf-8")
            metadata = archive.read(metadata_name).decode("utf-8")
        self.assertIn("arpent = scripts.cli:main", entry_points)
        self.assertIn("arp = scripts.cli:main", entry_points)
        requirements = [line for line in metadata.splitlines() if line.startswith("Requires-Dist:")]
        self.assertTrue(all('extra == "dev"' in line for line in requirements), requirements)

    def _entrypoint(self, target, name):
        candidates = (
            target / "bin" / name,
            target / "bin" / (name + ".exe"),
            target / "Scripts" / (name + ".exe"),
            target / "Scripts" / (name + "-script.py"),
        )
        matches = [path for path in candidates if path.is_file()]
        self.assertEqual(1, len(matches), "entrypoint %s not found under %s" % (name, target))
        return matches[0]

    def _venv_python(self, environment):
        candidates = (
            environment / "bin" / "python",
            environment / "Scripts" / "python.exe",
        )
        matches = [path for path in candidates if path.is_file()]
        self.assertEqual(1, len(matches), "venv Python not found under %s" % environment)
        return matches[0]

    def test_sdist_and_wheel_install_entrypoints_and_data_without_network(self):
        try:
            import setuptools  # noqa: F401
        except ImportError:
            self.fail("install the optional dev dependencies to run distribution validation")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = os.environ.copy()
            environment.update({
                "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                "PIP_NO_INDEX": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
            })
            source = root / "source"
            source.mkdir()
            shutil.copy2(REPOSITORY_ROOT / "pyproject.toml", source)
            shutil.copy2(REPOSITORY_ROOT / "README.md", source)
            shutil.copy2(REPOSITORY_ROOT / "LICENSE", source)
            shutil.copy2(REPOSITORY_ROOT / "SKILL.md", source)
            shutil.copytree(REPOSITORY_ROOT / "references", source / "references")
            shutil.copytree(
                REPOSITORY_ROOT / "scripts",
                source / "scripts",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "*.egg-info"),
            )
            wheel_dir = root / "wheelhouse"
            wheel_dir.mkdir()
            source_wheel = self._build_wheel(source, wheel_dir, environment)
            self._assert_wheel(source_wheel)

            sdist_dir = root / "sdist"
            sdist_dir.mkdir()
            self._run(
                [
                    sys.executable,
                    "-c",
                    "import setuptools.build_meta as backend, sys; backend.build_sdist(sys.argv[1])",
                    str(sdist_dir),
                ],
                cwd=source,
                environment=environment,
            )
            sdists = list(sdist_dir.glob("arpent-*.tar.gz"))
            self.assertEqual(1, len(sdists))

            extracted = root / "extracted"
            extracted.mkdir()
            with tarfile.open(sdists[0], "r:gz") as archive:
                members = archive.getmembers()
                for member in members:
                    path = PurePosixPath(member.name)
                    self.assertFalse(path.is_absolute())
                    self.assertNotIn("..", path.parts)
                roots = {PurePosixPath(member.name).parts[0] for member in members}
                self.assertEqual(1, len(roots))
                prefix = next(iter(roots)) + "/"
                names = {member.name for member in members}
                self.assertTrue({prefix + path for path in SDIST_FILES}.issubset(names))
                archive.extractall(extracted)

            rebuilt_dir = root / "rebuilt-wheelhouse"
            rebuilt_dir.mkdir()
            rebuilt_wheel = self._build_wheel(extracted / prefix.rstrip("/"), rebuilt_dir, environment)
            self._assert_wheel(rebuilt_wheel)

            isolated = root / "isolated-venv"
            venv.EnvBuilder(with_pip=True, system_site_packages=False).create(isolated)
            isolated_python = self._venv_python(isolated)
            self._run(
                [
                    str(isolated_python), "-m", "pip", "install", str(rebuilt_wheel),
                    "--no-deps", "--no-index", "--disable-pip-version-check",
                ],
                cwd=root,
                environment=environment,
            )
            installed_environment = environment.copy()
            installed_environment.pop("PYTHONPATH", None)
            installed_environment.pop("PYTHONHOME", None)
            home = root / "isolated-home"
            home.mkdir()
            installed_environment.update({"HOME": str(home), "USERPROFILE": str(home)})
            configuration = (isolated / "pyvenv.cfg").read_text(encoding="utf-8").lower()
            self.assertIn("include-system-site-packages = false", configuration)
            probe = self._run(
                [
                    str(isolated_python), "-c",
                    "import json, scripts, site, sys; "
                    "print(json.dumps({'prefix': sys.prefix, 'base_prefix': sys.base_prefix, "
                    "'package': scripts.__file__, 'user_site': site.ENABLE_USER_SITE}))",
                ],
                cwd=root,
                environment=installed_environment,
            )
            isolation = json.loads(probe.stdout)
            self.assertNotEqual(isolation["prefix"], isolation["base_prefix"])
            self.assertFalse(isolation["user_site"])
            self.assertNotIn(str(REPOSITORY_ROOT), isolation["package"])
            for name in ("arpent", "arp"):
                entrypoint = self._entrypoint(isolated, name)
                command = [str(entrypoint), "--version"]
                result = self._run(command, cwd=root, environment=installed_environment, timeout=30)
                self.assertEqual("arpent 0.1.0", result.stdout.strip())

            workspace = root / "installed-package-workspace"
            workspace.mkdir()
            vault = workspace / "vault"
            arpent = self._entrypoint(isolated, "arpent")
            arp = self._entrypoint(isolated, "arp")
            skill_destination = workspace / "host-selected" / "skills" / "arpent"
            installed_skill = json.loads(self._run(
                [str(arpent), "skill", "install", "--to", str(skill_destination), "--json"],
                cwd=workspace,
                environment=installed_environment,
                timeout=60,
            ).stdout)
            self.assertEqual(
                (installed_skill["format"], installed_skill["version"]),
                ("arpent-skill-install-result", 1),
            )
            self.assertEqual(installed_skill["destination"], str(skill_destination))
            expected_bundle = {
                path: hashlib.sha256((source / path).read_bytes()).hexdigest()
                for path in BUNDLE_FILES
            }
            actual_paths = {
                path.relative_to(skill_destination).as_posix()
                for path in skill_destination.rglob("*")
                if path.is_file() and not path.is_symlink()
            }
            self.assertEqual(actual_paths, BUNDLE_FILES)
            self.assertFalse(any(path.is_symlink() for path in skill_destination.rglob("*")))
            self.assertEqual(
                {
                    path: hashlib.sha256((skill_destination / path).read_bytes()).hexdigest()
                    for path in actual_paths
                },
                expected_bundle,
            )
            self.assertEqual(
                {entry["path"]: entry["sha256"] for entry in installed_skill["files"]},
                expected_bundle,
            )
            essential_links = set(re.findall(
                r"references/[A-Za-z0-9_./-]+\.md",
                (skill_destination / "SKILL.md").read_text(encoding="utf-8"),
            ))
            self.assertTrue(essential_links)
            self.assertTrue(essential_links.issubset(actual_paths))

            stale = skill_destination / "stale-from-previous-install.txt"
            stale.write_text("remove on explicit replacement", encoding="utf-8")
            replaced_skill = json.loads(self._run(
                [
                    str(arpent), "skill", "install", "--to", str(skill_destination),
                    "--replace", "--json",
                ],
                cwd=workspace,
                environment=installed_environment,
                timeout=60,
            ).stdout)
            self.assertEqual(replaced_skill["destination"], str(skill_destination))
            self.assertFalse(stale.exists())
            self.assertEqual(
                {entry["path"]: entry["sha256"] for entry in replaced_skill["files"]},
                expected_bundle,
            )

            self._run(
                [str(arpent), "init", str(vault)],
                cwd=workspace,
                environment=installed_environment,
                timeout=60,
            )
            added = self._run(
                [str(arp), "todo", "add", "wheel package data check", "--json"],
                cwd=vault,
                environment=installed_environment,
                timeout=60,
            )
            todo_result = json.loads(added.stdout)
            self.assertEqual(("arpent-todo-add-result", 1), (
                todo_result["format"], todo_result["version"],
            ))
            self.assertTrue((vault / todo_result["path"]).is_file())
            self.assertTrue((vault / "06_indexes/databases/todo.db").is_file())
            self.assertEqual(
                (source / "scripts/COMPASS.md").read_text(encoding="utf-8"),
                (vault / "COMPASS.md").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                (source / "scripts/operations.yaml").read_text(encoding="utf-8"),
                (vault / "06_indexes/cli/operations.yaml").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                (source / "scripts/todo_schema.sql").read_text(encoding="utf-8"),
                (vault / "06_indexes/schemas/todo_schema.sql").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()

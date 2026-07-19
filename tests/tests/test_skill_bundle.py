import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import skill_bundle


ROOT = Path(__file__).resolve().parents[2]


def _hashes(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (root / "SKILL.md", *sorted((root / "references").rglob("*")))
        if path.is_file() and not path.is_symlink() and path.name != ".DS_Store"
    }


class SkillBundleTests(unittest.TestCase):
    def test_install_publishes_the_complete_verified_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "host" / "skills" / "arpent"

            result = skill_bundle.install_skill_bundle(destination)

            expected = _hashes(ROOT)
            self.assertEqual(expected, _hashes(destination))
            self.assertEqual(result["destination"], str(destination))
            self.assertEqual(result["file_count"], len(expected))
            self.assertEqual(
                {entry["path"]: entry["sha256"] for entry in result["files"]},
                expected,
            )
            self.assertFalse(any(path.is_symlink() for path in destination.rglob("*")))

    def test_install_refuses_existing_traversal_and_symlinked_destinations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            existing = root / "existing"
            existing.mkdir()
            with self.assertRaisesRegex(ValueError, "must not already exist"):
                skill_bundle.install_skill_bundle(existing)

            with self.assertRaisesRegex(ValueError, "must not contain"):
                skill_bundle.install_skill_bundle(root / "nested" / ".." / "escape")

            real = root / "real"
            real.mkdir()
            linked = root / "linked"
            try:
                linked.symlink_to(real, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            with self.assertRaisesRegex(ValueError, "symlinked skill destination"):
                skill_bundle.install_skill_bundle(linked / "arpent")
            self.assertFalse((real / "arpent").exists())

    def test_replace_removes_stale_content_but_still_refuses_unsafe_targets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "arpent"
            destination.mkdir()
            (destination / "stale.txt").write_text("old bundle", encoding="utf-8")

            skill_bundle.install_skill_bundle(destination, replace=True)

            self.assertEqual(_hashes(destination), _hashes(ROOT))
            self.assertFalse((destination / "stale.txt").exists())

            regular_file = root / "regular-file"
            regular_file.write_text("not a directory", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "replacement requires a directory"):
                skill_bundle.install_skill_bundle(regular_file, replace=True)

            real = root / "real"
            real.mkdir()
            linked = root / "linked"
            try:
                linked.symlink_to(real, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            with self.assertRaisesRegex(ValueError, "symlinked skill destination"):
                skill_bundle.install_skill_bundle(linked, replace=True)

    def test_replace_restores_the_original_directory_if_publication_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "arpent"
            destination.mkdir()
            marker = destination / "original.txt"
            marker.write_text("preserve me", encoding="utf-8")
            publish = skill_bundle._publish_no_replace
            calls = 0

            def fail_new_publication(source, target):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated publication failure")
                return publish(source, target)

            with mock.patch.object(
                skill_bundle, "_publish_no_replace", side_effect=fail_new_publication,
            ):
                with self.assertRaisesRegex(OSError, "simulated publication failure"):
                    skill_bundle.install_skill_bundle(destination, replace=True)

            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve me")
            self.assertEqual(list(destination.parent.glob(".arpent.*")), [])


if __name__ == "__main__":
    unittest.main()

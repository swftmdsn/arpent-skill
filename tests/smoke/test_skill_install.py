import hashlib
import unittest

from tests.support import CliTestCase, REPOSITORY_ROOT, load_json_text, snapshot_tree


def bundle_files(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [root / "SKILL.md", *sorted((root / "references").rglob("*"))]
        if path.is_file() and not path.is_symlink() and path.name != ".DS_Store"
    }


class SkillInstallSmokeTests(CliTestCase):
    def test_installs_the_complete_checkout_bundle_at_the_exact_destination(self):
        destination = self.isolated.path("host selected") / "skills" / "arpent exact"
        result = load_json_text(self.assertCliSuccess(self.cli(
            "skill", "install", "--to", destination, "--json",
        )).stdout)

        self.assertEqual(
            (result["format"], result["version"]),
            ("arpent-skill-install-result", 1),
        )
        self.assertEqual(result["destination"], str(destination))
        expected = bundle_files(REPOSITORY_ROOT)
        actual = bundle_files(destination)
        self.assertEqual(actual, expected)
        self.assertEqual(
            {entry["path"]: entry["sha256"] for entry in result["files"]},
            expected,
        )
        snapshot = snapshot_tree(destination)
        self.assertEqual(snapshot.symlinks, ())

        human_destination = self.isolated.path("another exact destination")
        human = self.assertCliSuccess(self.cli(
            "skill", "install", "--to", human_destination,
        ))
        self.assertIn(f"Installed Arpent skill bundle at {human_destination}", human.stdout)

    def test_refuses_unsafe_existing_and_symlinked_destinations(self):
        existing = self.isolated.path("existing")
        existing.mkdir()
        collision = self.assertCliFailure(self.cli("skill", "install", "--to", existing))
        self.assertIn("must not already exist", collision.output)

        traversal = self.assertCliFailure(self.cli(
            "skill", "install", "--to", "../outside",
        ))
        self.assertIn("must not contain '..'", traversal.output)
        self.assertFalse(self.isolated.path("outside").exists())

        real_parent = self.isolated.path("real parent")
        real_parent.mkdir()
        linked_parent = self.isolated.path("linked parent")
        try:
            linked_parent.symlink_to(real_parent, target_is_directory=True)
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        through_link = self.assertCliFailure(self.cli(
            "skill", "install", "--to", linked_parent / "arpent",
        ))
        self.assertIn("symlinked skill destination parent", through_link.output)
        self.assertFalse((real_parent / "arpent").exists())

        target_link = self.isolated.path("target link")
        target_link.symlink_to(real_parent, target_is_directory=True)
        linked_target = self.assertCliFailure(self.cli(
            "skill", "install", "--to", target_link,
        ))
        self.assertIn("symlinked skill destination", linked_target.output)

    def test_replace_explicitly_updates_an_existing_directory(self):
        destination = self.isolated.path("existing skill")
        destination.mkdir()
        (destination / "stale.txt").write_text("old bundle", encoding="utf-8")

        result = load_json_text(self.assertCliSuccess(self.cli(
            "skill", "install", "--to", destination, "--replace", "--json",
        )).stdout)

        self.assertEqual(bundle_files(destination), bundle_files(REPOSITORY_ROOT))
        self.assertFalse((destination / "stale.txt").exists())
        self.assertEqual(result["destination"], str(destination))

        regular_file = self.isolated.path("regular file")
        regular_file.write_text("not a directory", encoding="utf-8")
        refused = self.assertCliFailure(self.cli(
            "skill", "install", "--to", regular_file, "--replace",
        ))
        self.assertIn("replacement requires a directory", refused.output)


if __name__ == "__main__":
    unittest.main()

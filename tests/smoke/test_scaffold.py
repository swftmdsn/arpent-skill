import shutil
import unittest

from tests.support import CliTestCase, snapshot_tree


ESSENTIAL_DIRECTORIES = {
    "00_inbox/",
    "00_inbox/fleeting/",
    "00_inbox/unsure/",
    "01_projects/",
    "02_areas/",
    "02_areas/area__perso__todo__active/",
    "03_resources/",
    "03_resources/how-tos/",
    "03_resources/agent_infrastructure/",
    "04_archives/",
    "05_tools/",
    "06_indexes/",
    "06_indexes/cli/",
    "06_indexes/databases/",
    "06_indexes/global_skills/",
    "06_indexes/schemas/",
}

ESSENTIAL_FILES = {
    ".agent",
    ".arpent",
    ".gitignore",
    "COMPASS.md",
    "me.md",
    "06_indexes/cli/operations.yaml",
    "06_indexes/cron.json",
    "06_indexes/global_skills/arpent.skill.md",
    "06_indexes/global_skills/todo.skill.md",
    "06_indexes/schemas/frontmatter_policy.yaml",
    "06_indexes/schemas/todo_schema.sql",
    "06_indexes/tools.yaml",
    "03_resources/templates/howto.template.md",
}


class ScaffoldSmokeTests(CliTestCase):
    def assertScaffoldEssentials(self, vault):
        snapshot = snapshot_tree(vault, exclude=(".git",))
        self.assertTrue(ESSENTIAL_DIRECTORIES.issubset(set(snapshot.directories)))
        self.assertTrue(ESSENTIAL_FILES.issubset(set(snapshot.files)))
        self.assertEqual(snapshot.symlinks, ())

    def test_minimal_scaffold_is_complete_but_cli_inactive(self):
        vault = self.initVault(minimal=True, name="minimal vault with spaces")
        self.assertScaffoldEssentials(vault)
        self.assertFalse((vault / ".git").exists())
        marker = self.assertJsonFile(vault, ".arpent", {
            "version": 2,
            "name": "arpent",
            "mode": "minimal",
            "auto_full": False,
        })
        self.assertEqual(set(marker), {"version", "name", "mode", "auto_full"})

        shown = self.assertCliSuccess(self.cli("mode", "show", "--json", cwd=vault))
        self.assertIn('"mode": "minimal"', shown.stdout)
        blocked = self.assertCliFailure(self.cli("status", cwd=vault))
        self.assertIn("not available in minimal mode", blocked.output)

    @unittest.skipUnless(shutil.which("git"), "full scaffold requires git")
    def test_full_scaffold_initializes_git_without_a_default_project(self):
        vault = self.initVault(name="full vault with spaces")
        self.assertScaffoldEssentials(vault)
        self.assertTrue((vault / ".git").is_dir())
        self.assertJsonFile(vault, ".arpent", {"version": 2, "mode": "full"})
        self.assertEqual(
            sorted(path.name for path in (vault / "01_projects").iterdir()),
            ["_template_project"],
        )

        status = self.assertCliSuccess(self.cli("status", cwd=vault))
        self.assertIn("Vault:", status.stdout)
        self.assertIn(str(vault), status.stdout)

import json
import tempfile
import unittest
from pathlib import Path

from scripts import notes
from scripts import todo
from scripts import vault as vault_mod
from scripts.vault import init_vault


ROOT = Path(__file__).resolve().parents[2]


class TokenBudgetTests(unittest.TestCase):
    def test_hot_path_static_context_stays_bounded(self):
        skill = (ROOT / "SKILL.md").read_bytes()
        agent = (ROOT / "architecture_template/.agent").read_bytes()
        operations = (ROOT / "scripts/operations.yaml").read_bytes()

        self.assertLessEqual(len(skill), 8 * 1024)
        self.assertLessEqual(len(skill) + len(agent) + len(operations), 16 * 1024)

    def test_filesystem_note_bundle_stays_bounded(self):
        paths = [
            "SKILL.md",
            "architecture_template/.agent",
            "references/workflows/capture-note.md",
            "references/contracts/frontmatter.md",
            "references/contracts/routing.md",
            "references/contracts/provenance-and-body.md",
            "references/modes/minimal.md",
        ]
        total = sum(len((ROOT / path).read_bytes()) for path in paths)
        self.assertLessEqual(total, 24 * 1024)

    def test_local_minimal_hot_path_stays_bounded(self):
        paths = [
            "architecture_template/.agent",
            "architecture_template/COMPASS.md",
            "architecture_template/06_indexes/global_skills/arpent.skill.md",
            "architecture_template/06_indexes/cli/operations.yaml",
        ]
        total = sum(len((ROOT / path).read_bytes()) for path in paths)
        self.assertLessEqual(total, 16 * 1024)

    def test_representative_creation_plans_stay_compact(self):
        with tempfile.TemporaryDirectory() as temporary:
            note_vault = init_vault(Path(temporary) / "full-note", minimal=False)
            note_plan = notes.public_note_new_plan(notes.plan_note_new(
                note_vault,
                title="Compact plan",
                ntype="note",
                body="One short body.",
            ))
            self.assertLessEqual(len(json.dumps(note_plan).encode("utf-8")), 4 * 1024)

            full_vault = init_vault(Path(temporary) / "full", minimal=False)
            todo_plan = todo.plan_todo_add(full_vault, "Prepare compact review")
            self.assertLessEqual(len(json.dumps(todo_plan).encode("utf-8")), 4 * 1024)

    def test_runtime_and_template_copies_are_identical(self):
        self.assertEqual(
            (ROOT / "scripts/COMPASS.md").read_text(encoding="utf-8"),
            (ROOT / "architecture_template/COMPASS.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            (ROOT / "scripts/operations.yaml").read_text(encoding="utf-8"),
            (ROOT / "architecture_template/06_indexes/cli/operations.yaml").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            vault_mod.AGENT_STUB,
            (ROOT / "architecture_template/.agent").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            vault_mod.ARPENT_SKILL_STUB,
            (ROOT / "architecture_template/06_indexes/global_skills/arpent.skill.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            vault_mod.ARPENT_STUB,
            (ROOT / "architecture_template/06_indexes/docs/ARPENT.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            vault_mod.CONTEXT_SUMMARY_SKILL_STUB,
            (ROOT / "architecture_template/06_indexes/global_skills/context_summary.skill.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            vault_mod.READER_SKILL_STUB,
            (ROOT / "architecture_template/06_indexes/global_skills/reader.skill.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            vault_mod.REVIEW_SKILL_STUB,
            (ROOT / "architecture_template/06_indexes/global_skills/review.skill.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            vault_mod.BACKUP_SKILL_STUB,
            (ROOT / "architecture_template/06_indexes/global_skills/z_backup.skill.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            vault_mod.MENTAL_MODEL_STUB,
            (ROOT / "architecture_template/06_indexes/docs/mental-model.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            vault_mod.TOOLS_STUB,
            (ROOT / "architecture_template/06_indexes/tools.yaml").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            vault_mod.AGENT_WIKI_README_STUB,
            (ROOT / "architecture_template/03_resources/agent_wiki/_README.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            vault_mod.INDEXING_CONTEXT_DOC_STUB,
            (ROOT / "architecture_template/06_indexes/docs/architecture/indexing-and-context.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            vault_mod.ROUTING_DOC_STUB,
            (ROOT / "architecture_template/06_indexes/docs/architecture/routing.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            vault_mod.PROJECT_CONTEXT_TEMPLATE_STUB,
            (ROOT / "architecture_template/01_projects/_template_project/_context.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            vault_mod.AREA_CONTEXT_TEMPLATE_STUB,
            (ROOT / "architecture_template/02_areas/_context.template.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            vault_mod.HOWTO_TEMPLATE_STUB,
            (ROOT / "architecture_template/03_resources/templates/howto.template.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            vault_mod.GITIGNORE_STUB,
            (ROOT / "architecture_template/.gitignore").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()

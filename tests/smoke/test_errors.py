from tests.support import CliTestCase


class ErrorSmokeTests(CliTestCase):
    def test_commands_report_a_clean_missing_vault_error(self):
        commands = [
            ("mode", "show"),
            ("status",),
            ("index",),
            ("context", "pending"),
            ("triage",),
            ("efforts",),
            ("search", "needle"),
            ("backup",),
            ("health",),
            ("usage", "report"),
            ("archive", "note-20000101-a"),
            ("project", "create", "Missing Vault"),
            ("note", "new", "Missing Vault", "--dry-run"),
            ("session", "end", "--summary", "Missing vault"),
            ("tools", "list"),
            ("cron", "run", "--tick", "--dry-run"),
            ("sweep", "status"),
            ("todo", "list"),
            ("import", "apply", "missing-plan.json", "--dry-run"),
        ]
        for command in commands:
            with self.subTest(command=command):
                result = self.assertCliFailure(self.cli(*command))
                self.assertIn("Not inside an Arpent vault", result.output)

    def test_argparse_and_domain_errors_are_clean(self):
        parser_errors = [
            (),
            ("unknown-command",),
            ("todo",),
            ("todo", "defer", "todo-20000101-a"),
            ("triage", "--limit", "0"),
        ]
        for command in parser_errors:
            with self.subTest(command=command):
                result = self.assertCliFailure(self.cli(*command), code=2)
                self.assertIn("usage:", result.stderr)

        confidence = self.assertCliFailure(
            self.cli("import", "review", "missing.json", "--minimum-confidence", "1.1")
        )
        self.assertIn("between 0 and 1", confidence.output)

        vault = self.initVault()
        pagination = self.assertCliFailure(self.cli("triage", "--limit", "1", cwd=vault))
        self.assertIn("require --json-page", pagination.output)
        timestamp = self.assertCliFailure(
            self.cli(
                "todo", "add", "Invalid date", "--due", "2026-07-20T12:30:00Z",
                "--dry-run", cwd=vault,
            )
        )
        self.assertIn("dd-MM-YYYY-HH-mm", timestamp.output)

    def test_uninstalled_tool_stubs_fail_cleanly(self):
        for tool in ("fleeting", "reader", "calendar", "sport", "journal", "crm"):
            with self.subTest(tool=tool):
                result = self.assertCliFailure(self.cli(tool, "ignored", "arguments"))
                self.assertIn("Phase 2+ sub-tool", result.output)
                self.assertIn(tool, result.output)

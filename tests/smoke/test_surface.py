from __future__ import annotations

import argparse
import inspect
from pathlib import Path

from scripts import __version__ as package_version
from scripts import cli, operations
from tests.support import CliTestCase, REPOSITORY_ROOT


EXPECTED_CLI_HANDLERS = {
    ("init",): "cmd_init",
    ("mode", "show"): "cmd_mode_show",
    ("mode", "full"): "cmd_mode_set",
    ("mode", "minimal"): "cmd_mode_set",
    ("import", "scan"): "cmd_import_scan",
    ("import", "suggest"): "cmd_import_suggest",
    ("import", "review"): "cmd_import_review",
    ("import", "validate"): "cmd_import_validate",
    ("import", "summary"): "cmd_import_summary",
    ("import", "apply"): "cmd_import_apply",
    ("import", "status"): "cmd_import_status",
    ("status",): "cmd_status",
    ("index",): "cmd_index",
    ("triage",): "cmd_triage",
    ("efforts",): "cmd_efforts",
    ("backup",): "cmd_backup",
    ("backup", "verify"): "cmd_backup_verify",
    ("backup", "restore"): "cmd_backup_restore",
    ("health",): "cmd_health",
    ("usage", "report"): "cmd_usage_report",
    ("search",): "cmd_search",
    ("context", "pending"): "cmd_context_pending",
    ("context", "set"): "cmd_context_set",
    ("context", "show"): "cmd_context_show",
    ("archive",): "cmd_archive",
    ("project", "create"): "cmd_project_create",
    ("note", "new"): "cmd_note_new",
    ("note", "route"): "cmd_note_route",
    ("note", "read"): "cmd_note_read",
    ("note", "find"): "cmd_note_find",
    ("note", "status"): "cmd_note_status",
    ("note", "edit"): "cmd_note_edit",
    ("note", "ingest"): "cmd_note_ingest",
    ("note", "extract"): "cmd_note_extract",
    ("note", "dissolve"): "cmd_note_dissolve",
    ("session", "end"): "cmd_session_end",
    ("tools", "list"): "cmd_tools_list",
    ("tools", "show"): "cmd_tools_show",
    ("cron", "run"): "cmd_cron_run",
    ("sweep", "ephemeral"): "cmd_sweep_ephemeral",
    ("sweep", "status"): "cmd_sweep_status",
    ("todo", "add"): "cmd_todo_add",
    ("todo", "list"): "cmd_todo_list",
    ("todo", "show"): "cmd_todo_show",
    ("todo", "edit"): "cmd_todo_edit",
    ("todo", "done"): "cmd_todo_done",
    ("todo", "defer"): "cmd_todo_defer",
    ("todo", "block"): "cmd_todo_block",
    ("todo", "archive"): "cmd_todo_archive",
    ("fleeting",): "cmd_tool_stub",
    ("reader",): "cmd_tool_stub",
    ("calendar",): "cmd_tool_stub",
    ("sport",): "cmd_tool_stub",
    ("journal",): "cmd_tool_stub",
    ("crm",): "cmd_tool_stub",
}

EXPECTED_OPERATION_HANDLERS = {
    "init": "cmd_init",
    "mode_show": "cmd_mode_show",
    "mode_full": "cmd_mode_set",
    "mode_minimal": "cmd_mode_set",
    "import_scan": "cmd_import_scan",
    "import_suggest": "cmd_import_suggest",
    "import_review": "cmd_import_review",
    "import_validate": "cmd_import_validate",
    "import_summary": "cmd_import_summary",
    "import_apply": "cmd_import_apply",
    "import_status": "cmd_import_status",
    "status": "cmd_status",
    "index": "cmd_index",
    "context_pending": "cmd_context_pending",
    "context_set": "cmd_context_set",
    "context_show": "cmd_context_show",
    "triage": "cmd_triage",
    "efforts": "cmd_efforts",
    "search": "cmd_search",
    "backup": "cmd_backup_verify",
    "backup_create": "cmd_backup",
    "backup_restore": "cmd_backup_restore",
    "archive": "cmd_archive",
    "health": "cmd_health",
    "usage_report": "cmd_usage_report",
    "note_new": "cmd_note_new",
    "note_route": "cmd_note_route",
    "note_read": "cmd_note_read",
    "note_find": "cmd_note_find",
    "note_status": "cmd_note_status",
    "note_edit": "cmd_note_edit",
    "note_ingest": "cmd_note_ingest",
    "note_extract": "cmd_note_extract",
    "note_dissolve": "cmd_note_dissolve",
    "project_create": "cmd_project_create",
    "session_end": "cmd_session_end",
    "tools_list": "cmd_tools_list",
    "tools_show": "cmd_tools_show",
    "cron_run": "cmd_cron_run",
    "sweep_ephemeral": "cmd_sweep_ephemeral",
    "sweep_status": "cmd_sweep_status",
    "todo_add": "cmd_todo_add",
    "todo_list": "cmd_todo_list",
    "todo_show": "cmd_todo_show",
    "todo_edit": "cmd_todo_edit",
    "todo_done": "cmd_todo_done",
    "todo_defer": "cmd_todo_defer",
    "todo_block": "cmd_todo_block",
    "todo_archive": "cmd_todo_archive",
}


def _parser_handlers(parser, prefix=()):
    handlers = {}
    if "func" in parser._defaults:
        handlers[prefix] = parser._defaults["func"].__name__
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        for name, child in action.choices.items():
            handlers.update(_parser_handlers(child, (*prefix, name)))
    return handlers


def _project_metadata(path: Path):
    section = None
    project = {}
    scripts = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        value = value.split("#", 1)[0].strip().strip('"')
        if section == "project":
            project[key] = value
        elif section == "project.scripts":
            scripts[key] = value
    return project, scripts


class CliSurfaceSmokeTests(CliTestCase):
    def test_module_version_help_and_declared_aliases(self):
        project, scripts = _project_metadata(REPOSITORY_ROOT / "pyproject.toml")
        self.assertEqual(package_version, cli.__version__)
        self.assertEqual(project["version"], cli.__version__)
        self.assertEqual(project["name"], "arpent")
        self.assertEqual(scripts.get("arpent"), "scripts.cli:main")
        self.assertEqual(scripts.get("arp"), scripts.get("arpent"))

        version = self.assertCliSuccess(self.cli("--version"))
        self.assertEqual(version.stdout.strip(), "arpent {}".format(cli.__version__))
        help_result = self.assertCliSuccess(self.cli("--help"))
        self.assertIn("usage: arpent", help_result.stdout)
        for command in sorted({path[0] for path in EXPECTED_CLI_HANDLERS}):
            self.assertIn(command, help_result.stdout)

    def test_every_parser_path_has_the_expected_handler(self):
        parser = cli.build_parser()
        self.assertEqual(_parser_handlers(parser), EXPECTED_CLI_HANDLERS)
        declared = {
            name
            for name, value in inspect.getmembers(cli, inspect.isfunction)
            if name.startswith("cmd_")
        }
        self.assertEqual(declared, set(EXPECTED_CLI_HANDLERS.values()))

    def test_operation_registry_maps_to_live_handlers(self):
        registry = operations.default_operations()
        self.assertEqual(registry["version"], operations.OPERATIONS_VERSION)
        self.assertEqual(set(registry["operations"]), set(EXPECTED_OPERATION_HANDLERS))
        for operation, handler in EXPECTED_OPERATION_HANDLERS.items():
            with self.subTest(operation=operation):
                self.assertTrue(callable(getattr(cli, handler)))
                entry = registry["operations"][operation]
                self.assertIsInstance(entry.get("phase"), int)
                self.assertTrue(entry.get("summary"))

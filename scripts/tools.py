"""Read-only access to the vault and built-in tools registry."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from . import frontmatter as fmlib
from . import routing


BUILTIN_TOOLS = {
    "todo": {
        "category": "daily-flow",
        "ephemeral": True,
        "skill": "06_indexes/global_skills/todo.skill.md",
        "writes_to": ["02_areas/area__perso__todo__active"],
        "database": "06_indexes/databases/todo.db",
        "status": "installed",
        "lifecycle": [{
            "from": "done",
            "after_days": 30,
            "action": "archive-with-trace",
        }],
    },
}
TOOLS_VERSION = "0.2.0"
TOOL_FIELDS = {
    "category", "ephemeral", "skill", "writes_to", "database", "status", "lifecycle",
}
LIFECYCLE_ACTIONS = {"archive", "archive-with-trace", "delete-after-review"}
PROTECTED_STATUSES = {"active", "stable", "ongoing"}
ARCHIVE_SOURCE_STATUSES = {"done", "stale"}
MAX_AFTER_DAYS = 999_999_999


def load_tools(vault) -> dict:
    relpath = "06_indexes/tools.yaml"
    raw_path = vault.root / relpath
    if not raw_path.exists() and not raw_path.is_symlink():
        tools = dict(BUILTIN_TOOLS)
        _validate_tools(vault, tools)
        return tools
    path = vault.safe_source_path(relpath)
    data = fmlib.parse_frontmatter_block(path.read_text(encoding="utf-8"))
    if set(data) != {"version", "tools"}:
        raise ValueError("tools.yaml must contain exactly 'version' and 'tools'.")
    if data.get("version") != TOOLS_VERSION:
        raise ValueError(f"tools.yaml version must be '{TOOLS_VERSION}'.")
    tools = data.get("tools")
    if not isinstance(tools, dict):
        raise ValueError("tools.yaml 'tools' must be a mapping.")
    _validate_tools(vault, tools)
    return tools


def list_tools(vault, *, category=None, status=None) -> list[dict]:
    rows = []
    for name, cfg in sorted(load_tools(vault).items()):
        cfg = cfg if isinstance(cfg, dict) else {}
        if category and cfg.get("category") != category:
            continue
        if status and cfg.get("status") != status:
            continue
        rows.append({
            "name": name,
            "category": cfg.get("category") or "-",
            "status": cfg.get("status") or "-",
            "ephemeral": cfg.get("ephemeral"),
            "skill": cfg.get("skill") or "-",
        })
    return rows


def show_tool(vault, name: str) -> dict | None:
    cfg = load_tools(vault).get(name)
    return cfg if isinstance(cfg, dict) else None


def _validate_tools(vault, tools: dict) -> None:
    for name, config in tools.items():
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError("Tool names must contain only letters, digits, '_' or '-'.")
        if not isinstance(config, dict):
            raise ValueError(f"Tool '{name}' configuration must be a mapping.")
        missing = TOOL_FIELDS - set(config)
        unknown = set(config) - TOOL_FIELDS
        if missing or unknown:
            details = []
            if missing:
                details.append(f"missing {', '.join(sorted(missing))}")
            if unknown:
                details.append(f"unknown {', '.join(sorted(unknown))}")
            raise ValueError(f"Tool '{name}' has invalid fields: {'; '.join(details)}.")
        if not isinstance(config["category"], str) or not config["category"].strip():
            raise ValueError(f"Tool '{name}' category must be a non-empty string.")
        if type(config["ephemeral"]) is not bool:
            raise ValueError(f"Tool '{name}' ephemeral must be a boolean.")
        if config["status"] not in {"planned", "installed"}:
            raise ValueError(f"Tool '{name}' status must be 'planned' or 'installed'.")

        writes_to = config["writes_to"]
        if not isinstance(writes_to, list) or any(
            not _safe_registry_path(vault, value) for value in writes_to
        ):
            raise ValueError(f"Tool '{name}' writes_to must be a list of safe relative paths.")
        if len(writes_to) != len(set(writes_to)):
            raise ValueError(f"Tool '{name}' writes_to paths must be unique.")
        database = config["database"]
        if database is not None and not _safe_registry_path(vault, database):
            raise ValueError(f"Tool '{name}' database must be null or a safe relative path.")
        if database is not None and not database.startswith("06_indexes/databases/"):
            raise ValueError(f"Tool '{name}' database must live under 06_indexes/databases/.")

        lifecycle = config["lifecycle"]
        if not isinstance(lifecycle, list):
            raise ValueError(f"Tool '{name}' lifecycle must be a list.")
        for rule in lifecycle:
            _validate_lifecycle_rule(name, rule, database=database)

        skill = config.get("skill")
        skill_path = PurePosixPath(skill) if isinstance(skill, str) else None
        if (
            skill_path is None
            or skill_path.is_absolute()
            or ".." in skill_path.parts
            or skill_path.parts[:2] != ("06_indexes", "global_skills")
            or not skill.endswith(".skill.md")
            or not _safe_registry_path(vault, skill)
        ):
            raise ValueError(
                f"Tool '{name}' skill must live under 06_indexes/global_skills/; "
                "05_tools is runtime-only."
            )
        if config.get("status") == "installed":
            try:
                vault.safe_source_path(skill_path.as_posix())
            except ValueError as exc:
                raise ValueError(
                    f"Installed tool '{name}' skill must be an existing regular file "
                    "inside 06_indexes/global_skills/."
                ) from exc


def _safe_registry_path(vault, value) -> bool:
    if not isinstance(value, str) or not value or value != value.strip() or "\\" in value:
        return False
    normalized = value.rstrip("/")
    path = PurePosixPath(normalized)
    if (
        not path.parts
        or path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != normalized
    ):
        return False
    try:
        vault._safe_relative_path(normalized)
    except ValueError:
        return False
    return True


def _validate_lifecycle_rule(tool_name: str, rule, *, database=None) -> None:
    if not isinstance(rule, dict):
        raise ValueError(f"Tool '{tool_name}' lifecycle rules must be mappings.")
    allowed = {"from", "after_days", "to", "action"}
    if set(rule) - allowed or not {"from", "after_days"} <= set(rule):
        raise ValueError(f"Tool '{tool_name}' lifecycle rule has invalid fields.")
    if rule["from"] not in routing.STATUSES:
        raise ValueError(f"Tool '{tool_name}' lifecycle 'from' status is invalid.")
    if rule["from"] == "archived":
        raise ValueError(f"Tool '{tool_name}' cannot reactivate archived content.")
    if rule["from"] in PROTECTED_STATUSES:
        raise ValueError(
            f"Tool '{tool_name}' cannot sweep protected status '{rule['from']}'."
        )
    after_days = rule["after_days"]
    if (
        isinstance(after_days, bool)
        or not isinstance(after_days, int)
        or not 0 <= after_days <= MAX_AFTER_DAYS
    ):
        raise ValueError(
            f"Tool '{tool_name}' lifecycle after_days must be an integer from 0 to "
            f"{MAX_AFTER_DAYS}."
        )
    target = rule.get("to")
    action = rule.get("action")
    if (target is None) == (action is None):
        raise ValueError(f"Tool '{tool_name}' lifecycle rule needs exactly one of 'to' or 'action'.")
    if target is not None and target != "stale":
        raise ValueError(f"Tool '{tool_name}' lifecycle target must be 'stale'.")
    if target is not None and database is not None:
        raise ValueError(
            f"Tool '{tool_name}' cannot use lifecycle 'to' transitions because its "
            "Markdown and database states must change together."
        )
    if action is not None and action not in LIFECYCLE_ACTIONS:
        raise ValueError(f"Tool '{tool_name}' lifecycle action is invalid.")
    if action is not None and rule["from"] not in ARCHIVE_SOURCE_STATUSES:
        raise ValueError(f"Tool '{tool_name}' may archive only done or stale content.")

"""Read-only access to the vault and built-in tools registry."""

from __future__ import annotations

from pathlib import PurePosixPath

from . import frontmatter as fmlib


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


def load_tools(vault) -> dict:
    path = vault.root / "06_indexes" / "tools.yaml"
    if not path.exists():
        tools = dict(BUILTIN_TOOLS)
        _validate_skill_locations(vault, tools)
        return tools
    data = fmlib.parse_frontmatter_block(path.read_text(encoding="utf-8"))
    tools = data.get("tools") or {}
    tools = dict(tools) if isinstance(tools, dict) else {}
    _validate_skill_locations(vault, tools)
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


def _validate_skill_locations(vault, tools: dict) -> None:
    for name, config in tools.items():
        if not isinstance(config, dict):
            continue
        skill = config.get("skill")
        skill_path = PurePosixPath(skill) if isinstance(skill, str) else None
        if (
            skill_path is None
            or skill_path.is_absolute()
            or ".." in skill_path.parts
            or skill_path.parts[:2] != ("06_indexes", "global_skills")
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

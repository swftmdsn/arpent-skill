"""End-of-session protocol helpers."""

from __future__ import annotations

import json
from pathlib import Path

from . import file_transaction
from . import frontmatter as fmlib
from . import notes
from . import routing

SESSION_JOURNAL_REL = "06_indexes/logs/session-transaction.json"


def end_session(vault, *, project=None, area=None, summary, decisions=None,
                  next_steps=None, observations=None, traits=None,
                  memory_log=False) -> dict:
    """Apply explicitly selected session-end context, log, and queue writes."""
    decisions = decisions or []
    next_steps = next_steps or []
    observations = observations or []
    traits = traits or []
    if not project and not area and not memory_log and not observations and not traits:
        raise ValueError(
            "session end needs --project or --area; use --memory-log only when the "
            "optional cross-project log is explicitly wanted"
        )
    with vault.exclusive_lock("mutations"):
        _recover_session_transaction(vault)
        now = fmlib.now_note_timestamp()
        operational_now = fmlib.now_iso()
        folder = _target_folder(vault, project=project, area=area) if project or area else None
        prepared = []
        context_path = None
        if folder is not None:
            context_path, context_rel, context_content = _prepare_context(
                vault, folder, now, summary=summary,
                decisions=decisions, next_steps=next_steps,
                project=project, area=area,
            )
            prepared.append((context_rel, context_content))
        memory_path = None
        if memory_log:
            memory_path, memory_rel, memory_content = _prepare_memory_entry(
                vault, now, project=project, area=area, summary=summary,
                decisions=decisions, next_steps=next_steps,
            )
            prepared.append((memory_rel, memory_content))
        pending = _prepare_memory_writes(
            vault, operational_now, observations=observations, traits=traits,
        )
        queued = pending[2]
        if pending[0] is not None:
            prepared.append((pending[0], pending[1]))
        journal = file_transaction.prepare(
            vault,
            SESSION_JOURNAL_REL,
            [
                _snapshot(vault, relpath, expected_content=content)
                for relpath, content in prepared
            ],
        )

        try:
            for relpath, content in prepared:
                vault.atomic_write_text(relpath, content)
            file_transaction.commit(vault, SESSION_JOURNAL_REL, journal)
        except Exception:
            file_transaction.rollback(vault, SESSION_JOURNAL_REL, journal)
            raise

        return {
            "context_path": context_path,
            "memory_path": memory_path,
            "queued_writes": queued,
        }


def _snapshot(vault, relpath: str, *, expected_content: str) -> dict:
    return file_transaction.snapshot_file(
        vault, relpath, expected_content=expected_content,
    )


def _recover_session_transaction(vault) -> None:
    vault.refuse_foreign_transactions(SESSION_JOURNAL_REL)
    try:
        file_transaction.recover(vault, SESSION_JOURNAL_REL)
    except (OSError, ValueError, json.JSONDecodeError, AttributeError) as exc:
        raise ValueError(f"Cannot recover interrupted session transaction: {exc}") from exc


def _restore_snapshots(vault, snapshots: list[dict]) -> None:
    file_transaction.restore_files(vault, snapshots)


def _remove_session_journal(vault) -> None:
    file_transaction.remove_journal(vault, SESSION_JOURNAL_REL)


def _target_folder(vault, *, project=None, area=None) -> Path:
    if project:
        _validate_slug(project, "project")
        if area:
            folder_name = routing.resolve_area_folder(area, vault.area_slugs())
            if folder_name is None:
                raise ValueError(f"area '{area}' does not exist under 02_areas/")
        try:
            return vault.safe_directory_path(f"01_projects/{project}")
        except ValueError as exc:
            raise ValueError(
                f"project '{project}' does not exist under 01_projects/"
            ) from exc

    area_slugs = vault.area_slugs()
    folder_name = routing.resolve_area_folder(area, area_slugs)
    if folder_name is None:
        raise ValueError(f"area '{area}' does not exist under 02_areas/")
    return vault.safe_directory_path(f"02_areas/{folder_name}")


def _validate_slug(value: str, label: str) -> None:
    candidate = Path(value)
    if candidate.is_absolute() or len(candidate.parts) != 1 or value in (".", ".."):
        raise ValueError(f"{label} must be a single vault folder name")


def _prepare_context(vault, folder: Path, now: str, *, summary, decisions,
                     next_steps, project=None, area=None) -> tuple[Path, str, str]:
    relpath = (folder / "_context.md").relative_to(vault.root).as_posix()
    path = vault.safe_output_path(relpath)
    if path.exists():
        fm, body = fmlib.read_note(vault.safe_source_path(relpath))
        if not fm:
            fm = _context_frontmatter(vault, folder, project=project, area=area)
        else:
            if not fm.get("id"):
                fm["id"] = routing.new_id("note", vault.existing_ids())
            notes.normalize_frontmatter_fields(fm)
            fm["type"] = "note"
            fm["project"] = project
            fm["area"] = area
            fm["resource"] = None
            fm["status"] = "active" if project else "ongoing"
            fm["source"] = fm.get("source") or "generated"
            fm["author"] = fm.get("author") or "agent"
            fm["tags"] = list(dict.fromkeys([*(fm.get("tags") or []), "context"]))
        fm["modified"] = now
    else:
        fm = _context_frontmatter(vault, folder, project=project, area=area)
        body = _new_context_body()

    notes.validate_frontmatter_values(fm)
    body = body.rstrip() + "\n\n" + _session_block(now, summary, decisions, next_steps)
    return path, relpath, fmlib.compose_note(fm, body)


def _context_frontmatter(vault, folder: Path, *, project=None, area=None) -> dict:
    ts = fmlib.now_note_timestamp()
    note_id = routing.new_id("note", vault.existing_ids())
    return {
        "title": routing.slugify(f"{folder.name}_context"),
        "id": note_id,
        "created": ts,
        "modified": ts,
        "description": f"Living operational context for {folder.name}.",
        "type": "note",
        "project": project,
        "area": area,
        "resource": None,
        "status": "active" if project else "ongoing",
        "effort_cadence": None,
        "effort_level": None,
        "tags": ["context"],
        "chosen_location": "Maintained at the project or area root so agents read it before acting.",
        "source": "generated",
        "link": None,
        "author": "agent",
        "depth": None,
        "appreciated": None,
        "importance": None,
        "pinned": False,
        "expires_at": None,
        "related": [],
        "relations": [],
        "parent": None,
        "observations": [],
        "extracted_to": [],
    }


def _new_context_body() -> str:
    return (
        "## Vision\n\n"
        "## Current state\n\n"
        "## Key resources\n\n"
        "## Next steps\n"
    )


def _prepare_memory_entry(vault, now: str, *, project=None, area=None, summary,
                          decisions, next_steps) -> tuple[Path, str, str]:
    relpath = "06_indexes/memory/MEMORY.md"
    path = vault.safe_output_path(relpath)
    if path.exists():
        text = vault.safe_source_path(relpath).read_text(encoding="utf-8")
    else:
        text = "# MEMORY - working log\n\nNewest first. Disposable operational continuity.\n"

    target = project or area or "general"
    entry = _session_block(now, summary, decisions, next_steps, heading=f"Session - {target}")
    lines = text.rstrip().splitlines()
    insert_at = len(lines)
    for i, line in enumerate(lines[1:], start=1):
        if line.startswith("## "):
            insert_at = i
            break
    new_lines = lines[:insert_at] + ["", entry.rstrip(), ""] + lines[insert_at:]
    return path, relpath, "\n".join(new_lines).rstrip() + "\n"


def _session_block(now: str, summary: str, decisions: list[str], next_steps: list[str],
                   heading: str = "Session update") -> str:
    lines = [f"## {heading} ({now})", "", f"- Summary: {summary}"]
    if decisions:
        lines.append("- Decisions:")
        lines.extend(f"  - {item}" for item in decisions)
    if next_steps:
        lines.append("- Next steps:")
        lines.extend(f"  - {item}" for item in next_steps)
    return "\n".join(lines)


def _prepare_memory_writes(vault, now: str, *, observations, traits) -> tuple[str | None, str | None, int]:
    entries = []
    for item in observations:
        entries.append((now, "observation", {"content": item}))
    for item in traits:
        entries.append((now, "profile", {"content": item}))
    if not entries:
        return None, None, 0

    relpath = "06_indexes/pending_db_writes.yaml"
    path = vault.safe_output_path(relpath)
    if path.exists():
        text = vault.safe_source_path(relpath).read_text(encoding="utf-8")
    else:
        text = "version: 0.1.0\npending: []\n"
    if "pending: []" in text:
        text = text.replace("pending: []", "pending:")
    elif "pending:" not in text:
        text = text.rstrip() + "\npending:\n"

    blocks = []
    for timestamp, role, payload in entries:
        blocks.extend([
            f"  - timestamp: {_yaml_string(timestamp)}",
            f"    role: {role}",
            "    payload:",
        ])
        for key, value in payload.items():
            blocks.append(f"      {key}: {_yaml_string(value)}")
    content = text.rstrip() + "\n" + "\n".join(blocks) + "\n"
    return relpath, content, len(entries)


def _yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)

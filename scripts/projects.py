"""Explicit project creation helpers."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from . import frontmatter as fmlib
from . import notes
from . import routing


RESERVED_PROJECT_SLUGS = {
    "aux",
    "clock$",
    "con",
    "nul",
    "prn",
    "template-project",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


def normalize_project_slug(name: str) -> str:
    """Normalize a human project name to a safe lowercase ASCII kebab slug."""
    normalized = unicodedata.normalize("NFKD", name or "")
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")
    if (
        not slug
        or slug in {".", ".."}
        or slug in RESERVED_PROJECT_SLUGS
        or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug)
    ):
        raise ValueError(f"project name {name!r} does not produce a safe, non-reserved slug")
    return slug


def create_project(vault, name: str, *, area=None, effort_cadence=None,
                   effort_level=None) -> dict:
    """Create one project structure without merging into existing state."""
    slug = normalize_project_slug(name)
    if effort_cadence is not None and effort_cadence not in notes.EFFORT_CADENCES:
        raise ValueError(f"unknown effort cadence '{effort_cadence}'")
    if effort_level is not None and effort_level not in notes.EFFORT_LEVELS:
        raise ValueError(f"unknown effort level '{effort_level}'")

    with vault.exclusive_lock("mutations"):
        vault.refuse_foreign_transactions()
        if area is not None:
            _resolve_area(vault, area)

        projects_path = vault.safe_directory_path("01_projects")
        project_rel = f"01_projects/{slug}"
        project_path = projects_path / slug
        if project_path.exists() or project_path.is_symlink():
            raise ValueError(f"project '{slug}' already exists under 01_projects/")

        created: list[Path] = []
        try:
            project_path.mkdir()
            created.append(project_path)
            vault.fsync_directory(project_path.parent)
            for child_name in ("notes", "drafts", "attachments"):
                child = project_path / child_name
                child.mkdir()
                created.append(child)

            now = fmlib.now_note_timestamp()
            frontmatter = {
                "title": routing.slugify(f"{slug}_context"),
                "id": routing.new_id("note", vault.existing_ids()),
                "created": now,
                "modified": now,
                "description": f"Living operational context for {slug}.",
                "type": "note",
                "project": slug,
                "area": area,
                "resource": None,
                "status": "active",
                "effort_cadence": effort_cadence,
                "effort_level": effort_level,
                "tags": ["context"],
                "chosen_location": "Maintained at the project root so agents read it before acting.",
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
            notes.validate_frontmatter_values(frontmatter)
            context_rel = f"{project_rel}/_context.md"
            context_path = vault.atomic_create_text(
                context_rel, fmlib.compose_note(frontmatter, _context_body()),
            )
            created.append(context_path)
        except Exception:
            for path in reversed(created):
                try:
                    if path.is_file() and not path.is_symlink():
                        path.unlink()
                    elif path.is_dir() and not path.is_symlink():
                        path.rmdir()
                except OSError:
                    pass
            raise

        return {
            "name": name,
            "slug": slug,
            "project_path": project_path,
            "context_path": context_path,
        }


def _resolve_area(vault, area: str) -> str:
    match = routing.resolve_area_folder(area, vault.area_slugs())
    if match is None:
        raise ValueError(f"area '{area}' does not exist under 02_areas/")
    return match


def _context_body() -> str:
    return (
        "## Vision\n\n"
        "## Current state\n\n"
        "## Resume here\n\n"
        "## Deliverables / definition of done\n\n"
        "## Key resources\n\n"
        "## Next steps\n\n"
        "## Working rhythm and time budget\n\n"
        "## Session history\n"
    )

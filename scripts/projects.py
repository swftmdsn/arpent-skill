"""Explicit project creation helpers."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from . import file_transaction
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
    """Create or recover one canonical project without merging user content."""
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
        project_path = projects_path / slug
        if project_path.exists() or project_path.is_symlink():
            if _project_matches(
                project_path,
                slug,
                area=area,
                effort_cadence=effort_cadence,
                effort_level=effort_level,
            ):
                return _project_result(name, slug, project_path, created=False)
            raise ValueError(f"project '{slug}' already exists under 01_projects/")

        staging_rel = f"01_projects/.{slug}.arpent-project-staging"
        staging = projects_path / f".{slug}.arpent-project-staging"
        if staging.is_symlink() or (staging.exists() and not staging.is_dir()):
            raise ValueError(f"unsafe interrupted project staging for '{slug}'")
        if not staging.exists():
            staging.mkdir()
            vault.fsync_directory(projects_path)
        _validate_staging(staging, slug)

        staged_context = staging / "_context.md"
        if staged_context.exists() or staged_context.is_symlink():
            if not _context_matches(
                staged_context,
                slug,
                area=area,
                effort_cadence=effort_cadence,
                effort_level=effort_level,
            ):
                raise ValueError(f"unsafe interrupted project staging for '{slug}'")
        else:
            now = fmlib.now_note_timestamp()
            frontmatter = _context_frontmatter(
                slug,
                routing.new_id("note", vault.existing_ids()),
                now,
                area=area,
                effort_cadence=effort_cadence,
                effort_level=effort_level,
            )
            notes.validate_frontmatter_values(frontmatter)
            vault.atomic_create_text(
                f"{staging_rel}/_context.md",
                fmlib.compose_note(frontmatter, _context_body()),
            )

        _assert_staging_id_unique(vault, staged_context)
        for child_name in ("notes", "drafts", "attachments"):
            child = staging / child_name
            if child.is_symlink() or (child.exists() and not child.is_dir()):
                raise ValueError(f"unsafe interrupted project staging for '{slug}'")
            child.mkdir(exist_ok=True)
            vault.fsync_directory(child)

        vault.fsync_directory(staging)
        try:
            file_transaction.move_no_replace(staging, project_path)
        except FileExistsError as exc:
            raise ValueError(f"project '{slug}' already exists under 01_projects/") from exc
        vault.fsync_directory(projects_path)
        return _project_result(name, slug, project_path, created=True)


def _validate_staging(staging: Path, slug: str) -> None:
    allowed = {"notes", "drafts", "attachments", "_context.md"}
    if any(child.name not in allowed for child in staging.iterdir()):
        raise ValueError(f"unsafe interrupted project staging for '{slug}'")


def _assert_staging_id_unique(vault, staged_context: Path) -> None:
    metadata, _ = fmlib.read_note(staged_context)
    note_id = metadata["id"]
    matches = [
        path
        for path, frontmatter, _ in vault.iter_notes(skip_invalid=True)
        if frontmatter.get("id") == note_id
    ]
    if matches != [staged_context]:
        raise ValueError(f"duplicate staged project context id '{note_id}'")


def _project_matches(project_path: Path, slug: str, *, area, effort_cadence,
                     effort_level) -> bool:
    if project_path.is_symlink() or not project_path.is_dir():
        return False
    if any(
        (project_path / child).is_symlink() or not (project_path / child).is_dir()
        for child in ("notes", "drafts", "attachments")
    ):
        return False
    return _context_matches(
        project_path / "_context.md",
        slug,
        area=area,
        effort_cadence=effort_cadence,
        effort_level=effort_level,
    )


def _context_matches(path: Path, slug: str, *, area, effort_cadence,
                     effort_level) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    try:
        metadata, body = fmlib.read_note(path)
        notes.validate_frontmatter_values(metadata)
    except (OSError, UnicodeDecodeError, ValueError):
        return False
    note_id = metadata.get("id")
    timestamp = metadata.get("created")
    if (
        not isinstance(note_id, str)
        or re.fullmatch(r"note-\d{8}-[a-z]+", note_id) is None
        or not isinstance(timestamp, str)
        or metadata.get("modified") != timestamp
    ):
        return False
    expected = _context_frontmatter(
        slug,
        note_id,
        timestamp,
        area=area,
        effort_cadence=effort_cadence,
        effort_level=effort_level,
    )
    return metadata == expected and body == _context_body()


def _context_frontmatter(slug: str, note_id: str, timestamp: str, *, area,
                         effort_cadence, effort_level) -> dict:
    return {
        "title": routing.slugify(f"{slug}_context"),
        "id": note_id,
        "created": timestamp,
        "modified": timestamp,
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


def _project_result(name: str, slug: str, project_path: Path, *, created: bool) -> dict:
    return {
        "name": name,
        "slug": slug,
        "project_path": project_path,
        "context_path": project_path / "_context.md",
        "created": created,
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

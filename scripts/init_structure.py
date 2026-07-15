"""Declarative Area, Resource, and project creation during vault init."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from . import frontmatter
from . import notes
from . import projects
from . import routing
from .vault import MINIMAL_SCAFFOLD, SCAFFOLD


SECTIONS = ("areas", "resources", "projects")
PROJECT_KEYS = {"name", "area", "effort_cadence", "effort_level"}
WINDOWS_RESERVED_NAMES = {
    "aux", "clock$", "con", "nul", "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


def load_structure(path: Path) -> dict:
    """Read and validate an init structure from JSON or Markdown."""
    source = Path(path).expanduser()
    if not source.is_file():
        raise ValueError(f"Init structure is not a regular file: {source}")
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"Cannot read init structure '{source}': {exc}") from exc

    suffix = source.suffix.lower()
    if suffix == ".json":
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON init structure '{source}': {exc}") from exc
    elif suffix == ".md":
        raw = _parse_markdown(text)
    else:
        raise ValueError("Init structure must use a .json or .md extension.")
    return validate_structure(raw)


def apply_structure(vault, structure: dict) -> dict:
    """Create missing configured folders and canonical projects."""
    results = {
        "areas": {"created": [], "existing": []},
        "resources": {"created": [], "existing": []},
        "projects": {"created": [], "existing": []},
    }
    with vault.exclusive_lock("mutations"):
        vault.refuse_foreign_transactions()
        preflight_structure(
            vault.root,
            structure,
            minimal=vault.marker_data()["mode"] == "minimal",
        )
        for section, bucket in (("areas", "02_areas"), ("resources", "03_resources")):
            for item in structure[section]:
                relpath = f"{bucket}/{item['slug']}"
                destination = vault.root / relpath
                if destination.is_dir() and not destination.is_symlink():
                    results[section]["existing"].append(item["slug"])
                    continue
                vault.safe_ensure_directory(relpath)
                results[section]["created"].append(item["slug"])

        for item in structure["projects"]:
            destination = vault.root / "01_projects" / item["slug"]
            if _existing_project_matches(destination, item, area_slugs=vault.area_slugs()):
                results["projects"]["existing"].append(item["slug"])
                continue
            created = projects.create_project(
                vault,
                item["name"],
                area=item["area"],
                effort_cadence=item["effort_cadence"],
                effort_level=item["effort_level"],
            )
            results["projects"]["created"].append(created["slug"])
    return results


def preflight_structure(root: Path, structure: dict, *, minimal: bool) -> None:
    """Validate destinations and Area references without changing the target."""
    root = Path(root)
    scaffold = MINIMAL_SCAFFOLD if minimal else SCAFFOLD
    available_areas = {
        Path(relpath).name
        for relpath in scaffold
        if Path(relpath).parent.as_posix() == "02_areas"
    }
    areas_path = root / "02_areas"
    if areas_path.is_dir() and not areas_path.is_symlink():
        available_areas.update(
            path.name for path in areas_path.iterdir()
            if path.is_dir() and not path.is_symlink()
        )
    available_areas.update(item["slug"] for item in structure["areas"])

    for project in structure["projects"]:
        area = project["area"]
        if area is not None and routing.resolve_area_folder(area, available_areas) is None:
            raise ValueError(
                f"project '{project['slug']}' references area '{area}', which is not configured or present"
            )

    for section, bucket in (("areas", "02_areas"), ("resources", "03_resources")):
        for item in structure[section]:
            destination = root / bucket / item["slug"]
            if destination.exists() or destination.is_symlink():
                if destination.is_symlink() or not destination.is_dir():
                    raise ValueError(
                        f"configured {section[:-1]} destination is not a safe directory: {destination}"
                    )

    for item in structure["projects"]:
        _existing_project_matches(
            root / "01_projects" / item["slug"],
            item,
            area_slugs=available_areas,
        )


def _parse_markdown(text: str) -> dict:
    result = {section: [] for section in SECTIONS}
    current = None
    found_section = False
    headings = {section: section for section in SECTIONS}
    headings.update({section[:-1]: section for section in SECTIONS})
    for line_number, line in enumerate(text.splitlines(), start=1):
        heading = re.fullmatch(r"\s*#{1,6}\s+([^#]+?)\s*#*\s*", line)
        if heading:
            current = headings.get(heading.group(1).strip().lower())
            found_section = found_section or current is not None
            continue
        if current is None or not line.strip():
            continue
        item = re.fullmatch(r"\s*[-*+]\s+(.+?)\s*", line)
        if item is None:
            raise ValueError(
                f"Invalid Markdown init structure at line {line_number}: "
                f"entries below Areas, Resources, or Projects must be list items"
            )
        result[current].append(item.group(1))
    if not found_section:
        raise ValueError("Markdown init structure needs an Areas, Resources, or Projects heading.")
    return result


def validate_structure(raw) -> dict:
    """Normalize and validate declarative Areas, Resources, and projects."""
    if not isinstance(raw, dict):
        raise ValueError("Init structure must be an object with areas, resources, and/or projects.")
    unknown = set(raw) - set(SECTIONS)
    if unknown:
        raise ValueError(f"Unknown init structure key(s): {', '.join(sorted(unknown))}")

    result = {section: [] for section in SECTIONS}
    for section in ("areas", "resources"):
        values = raw.get(section, [])
        if not isinstance(values, list):
            raise ValueError(f"'{section}' must be a list of names.")
        for value in values:
            if not isinstance(value, str):
                raise ValueError(f"Every '{section}' entry must be a string.")
            slug = (
                _area_reference(value)
                if section == "areas"
                else _folder_slug(value, "-", "resource")
            )
            result[section].append({"name": value, "slug": slug})

    values = raw.get("projects", [])
    if not isinstance(values, list):
        raise ValueError("'projects' must be a list of names or project objects.")
    for value in values:
        if isinstance(value, str):
            value = {"name": value}
        if not isinstance(value, dict):
            raise ValueError("Every 'projects' entry must be a string or object.")
        unknown = set(value) - PROJECT_KEYS
        if unknown:
            raise ValueError(f"Unknown project key(s): {', '.join(sorted(unknown))}")
        name = value.get("name")
        if not isinstance(name, str):
            raise ValueError("Every project object needs a string 'name'.")
        area = value.get("area")
        if area is not None:
            if not isinstance(area, str):
                raise ValueError("Project 'area' must be a string or null.")
            area = _area_reference(area)
        effort_cadence = value.get("effort_cadence")
        effort_level = value.get("effort_level")
        if effort_cadence is not None and effort_cadence not in notes.EFFORT_CADENCES:
            raise ValueError(f"Unknown project effort_cadence '{effort_cadence}'.")
        if effort_level is not None and effort_level not in notes.EFFORT_LEVELS:
            raise ValueError(f"Unknown project effort_level '{effort_level}'.")
        result["projects"].append({
            "name": name,
            "slug": projects.normalize_project_slug(name),
            "area": area,
            "effort_cadence": effort_cadence,
            "effort_level": effort_level,
        })

    for section in SECTIONS:
        slugs = [item["slug"] for item in result[section]]
        duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
        if duplicates:
            raise ValueError(
                f"Duplicate normalized {section} slug(s): {', '.join(duplicates)}"
            )
    return result


# Kept as an internal alias for callers built before the validator became public.
_validate_structure = validate_structure


def _folder_slug(name: str, separator: str, label: str) -> str:
    normalized = unicodedata.normalize("NFKD", name or "")
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", separator, ascii_name).strip(separator)
    if not slug or slug in WINDOWS_RESERVED_NAMES:
        raise ValueError(f"{label} name {name!r} does not produce a safe, non-reserved slug")
    return slug


def _area_reference(name: str) -> str:
    if re.fullmatch(r"area__[a-z0-9]+(?:__[a-z0-9]+)+", name):
        return name
    return _folder_slug(name, "_", "area")


def _existing_project_matches(destination: Path, item: dict, *, area_slugs=()) -> bool:
    if not destination.exists() and not destination.is_symlink():
        return False
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError(f"configured project destination is not a safe directory: {destination}")
    missing = [
        child for child in ("notes", "drafts", "attachments")
        if not (destination / child).is_dir() or (destination / child).is_symlink()
    ]
    context = destination / "_context.md"
    if context.is_symlink() or not context.is_file():
        missing.append("_context.md")
    if missing:
        raise ValueError(
            f"project '{item['slug']}' already exists but is not canonical; "
            f"missing or unsafe: {', '.join(missing)}"
        )
    try:
        metadata, _ = frontmatter.read_note(context)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(
            f"project '{item['slug']}' has an unreadable _context.md: {exc}"
        ) from exc
    missing_fields = [key for key in frontmatter.KEY_ORDER if key not in metadata]
    if missing_fields:
        raise ValueError(
            f"project '{item['slug']}' has incomplete context frontmatter; missing: "
            f"{', '.join(missing_fields)}"
        )
    try:
        notes.validate_frontmatter_values(metadata)
    except ValueError as exc:
        raise ValueError(
            f"project '{item['slug']}' has invalid context frontmatter: {exc}"
        ) from exc
    expected = {
        "project": item["slug"],
        "effort_cadence": item["effort_cadence"],
        "effort_level": item["effort_level"],
    }
    conflicts = [key for key, value in expected.items() if metadata.get(key) != value]
    if not _areas_match(metadata.get("area"), item["area"], area_slugs):
        conflicts.append("area")
    if conflicts:
        raise ValueError(
            f"project '{item['slug']}' already exists with conflicting context field(s): "
            f"{', '.join(conflicts)}"
        )
    return True


def _areas_match(existing, configured, area_slugs) -> bool:
    if existing == configured:
        return True
    if existing is None or configured is None:
        return False
    return (
        routing.resolve_area_folder(existing, area_slugs)
        == routing.resolve_area_folder(configured, area_slugs)
    )

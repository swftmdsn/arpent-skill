"""
routing.py - deterministic routing.

`route()` is a pure function: given a frontmatter dict and the set of existing
folder slugs, it returns where the note belongs. It never guesses - ambiguity is
surfaced as a route into 00_inbox/unsure/ with a written reason.
"""

from __future__ import annotations

import itertools
import re
import string
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone

from . import operations as operations_mod
from . import frontmatter as fmlib

# --------------------------------------------------------------------------- #
# Contract (from operations.yaml)
# --------------------------------------------------------------------------- #

_DEFAULT_ROUTING = operations_mod.routing_contract()

TYPES = list(_DEFAULT_ROUTING.get("types") or [])
STATUSES = list(_DEFAULT_ROUTING.get("statuses") or [])
SOURCES = list(_DEFAULT_ROUTING.get("sources") or [])
AUTHORS = list(_DEFAULT_ROUTING.get("authors") or [])
TYPE_SUBFOLDER = dict(_DEFAULT_ROUTING.get("type_subfolders") or {})
DEFAULT_STATUS = dict(_DEFAULT_ROUTING.get("default_status") or {})


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii").lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "untitled"


def _letters():
    """a, b, ..., z, aa, ab, ... - for disambiguating same-type/same-day ids."""
    length = 1
    while True:
        yield from map("".join, itertools.product(string.ascii_lowercase, repeat=length))
        length += 1


def new_id(note_type: str, existing_ids, when: datetime | None = None) -> str:
    """Generate `<type>-<YYYYMMDD>-<letter>`, picking the next free letter."""
    when = when or datetime.now(timezone.utc)
    stamp = when.strftime("%Y%m%d")
    prefix = f"{note_type}-{stamp}-"
    taken = {i[len(prefix):] for i in existing_ids if i and i.startswith(prefix)}
    for letter in _letters():
        if letter not in taken:
            return prefix + letter
    raise RuntimeError("ran out of id letters for one type/day (unlikely)")


# --------------------------------------------------------------------------- #
# Routing result
# --------------------------------------------------------------------------- #

@dataclass
class Route:
    bucket_relpath: str          # path relative to vault root, e.g. "01_projects/foo/meetings"
    filename: str                # e.g. "reunion_lancement.md"
    reason: str | None = None    # set when routed to 00_inbox/unsure/
    append: bool = False         # True for fleeting (append-only day file)
    entry_time: str | None = None  # applied HH:MM for an append-only entry

    @property
    def relpath(self) -> str:
        return f"{self.bucket_relpath}/{self.filename}"


# --------------------------------------------------------------------------- #
# Slug resolution
# --------------------------------------------------------------------------- #

def resolve_area_folder(slug: str, area_slugs) -> str | None:
    """
    Areas may be named either directly (`sport`) or in the structured form
    (`area__perso__sport__active`). Resolve the slug to an existing folder name.
    """
    area_slugs = set(area_slugs)
    if slug in area_slugs:
        return slug
    matches = []
    for folder in sorted(area_slugs):
        # Structured form: area__<namespace>__<slug>__<status>
        parts = folder.split("__")
        if len(parts) >= 3 and parts[0] == "area" and parts[-2] == slug:
            matches.append(folder)
    if len(matches) > 1:
        raise ValueError(f"area '{slug}' is ambiguous: {', '.join(matches)}")
    return matches[0] if matches else None


# --------------------------------------------------------------------------- #
# The pure function
# --------------------------------------------------------------------------- #

def route(
    fm: dict,
    *,
    project_slugs=(),
    area_slugs=(),
    resource_slugs=(),
    operations_path=None,
) -> Route:
    """
    Map a (complete) frontmatter to a destination. Pure: depends only on `fm`
    and the provided sets of existing folder slugs. Routing rules come from
    operations.yaml.
    """
    contract = operations_mod.routing_contract(operations_path) if operations_path else _DEFAULT_ROUTING
    type_subfolders = contract.get("type_subfolders") or {}
    type_overrides = contract.get("type_overrides") or {}
    status_type_overrides = contract.get("status_type_overrides") or {}
    zero_field_routes = contract.get("zero_field_routes") or {}

    filename = f"{slugify(fm.get('title') or 'untitled')}.md"
    ntype = fm.get("type")
    project = fm.get("project")
    area = fm.get("area")
    resource = fm.get("resource")

    # Archived linear notes leave the active PARA structure even when their
    # former contextual area no longer exists.
    for rule in status_type_overrides.values():
        if ntype == rule.get("type") and fm.get("status") == rule.get("status"):
            return Route(rule.get("bucket"), filename)

    # Validate the universal PARA contract before applying other type-specific homes.
    if project and resource:
        reason = (
            f"Reason: project '{project}' and resource '{resource}' are both set.\n"
            "A note must be project-local or a global resource, never both.\n"
            "Link reusable global resources to projects with wikilinks instead."
        )
        return Route("00_inbox/unsure", filename, reason=reason)

    area_folder = None
    if area:
        try:
            area_folder = resolve_area_folder(area, area_slugs)
        except ValueError as exc:
            return Route("00_inbox/unsure", filename, reason=f"Reason: {exc}.")
        if area_folder is None:
            return Route("00_inbox/unsure", filename, reason=_missing("area", area, "02_areas"))

    # --- Type overrides that ignore the project/area/resource contract ---
    override = type_overrides.get(ntype)
    if isinstance(override, dict):
        if override.get("filename") == "date":
            created = fm.get("created")
            if created:
                day = fmlib.parse_note_timestamp(created).strftime("%d-%m-%Y")
            else:
                day = datetime.now(timezone.utc).strftime("%d-%m-%Y")
            return Route(override.get("bucket"), f"{day}.md", append=bool(override.get("append")))
        return Route(override.get("bucket"), filename, append=bool(override.get("append")))

    # --- draft not linked to a project, authored by agent ---
    if ntype == "draft" and not project and fm.get("author") == "agent":
        return Route("03_resources/agent_wiki/drafts", filename)

    # --- zero routing fields ---
    if not project and not area and not resource:
        if fm.get("source") == "captured":
            return Route(zero_field_routes.get("captured", "00_inbox/captures"), filename)
        return Route(zero_field_routes.get("default", "00_inbox"), filename)

    # --- destination precedence: project > resource > area ---
    if project:
        if project not in project_slugs:
            return Route("00_inbox/unsure", filename, reason=_missing("project", project, "01_projects"))
        base = f"01_projects/{project}"
        sub = "drafts" if ntype == "draft" else type_subfolders.get(ntype, "notes")
        return Route(f"{base}/{sub}" if sub else base, filename)

    if resource:
        if resource not in resource_slugs:
            return Route("00_inbox/unsure", filename, reason=_missing("resource", resource, "03_resources"))
        return Route(f"03_resources/{resource}", filename)

    if area_folder:
        base = f"02_areas/{area_folder}"
        sub = type_subfolders.get(ntype)
        return Route(f"{base}/{sub}" if sub else base, filename)

    raise AssertionError("routing destination was not resolved")


def _missing(field: str, slug: str, bucket: str) -> str:
    return (
        f"Reason: {field} '{slug}' does not exist as a folder under {bucket}/.\n"
        "Create the folder first, or correct the slug, then re-route."
    )

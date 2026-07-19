"""
views.py - read-only computed views over an Arpent vault.

These functions intentionally avoid maintaining their own state. The markdown
vault remains the source of truth; indexes and views are rebuildable.
"""

from __future__ import annotations

import codecs
import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import frontmatter as fmlib
from . import index as index_mod
from .vault import is_index_excluded


CADENCE_ORDER = {"heavylift": 0, "slowburn": 1}
LEVEL_ORDER = {"high": 0, "medium": 1, "low": 2}
MAX_TRIAGE_ITEMS = 10_000
MAX_TRIAGE_TEXT_BYTES = 256 * 1024


def status(vault) -> dict:
    """Return note counts used by ``arpent status``."""
    notes = list(vault.iter_notes())
    by_bucket, by_status = {}, {}
    inbox = 0

    for path, fm, _ in notes:
        rel = path.relative_to(vault.root).as_posix()
        bucket = rel.split("/", 1)[0]
        by_bucket[bucket] = by_bucket.get(bucket, 0) + 1
        stat = fm.get("status")
        by_status[stat] = by_status.get(stat, 0) + 1
        if bucket == "00_inbox":
            inbox += 1

    return {
        "total": len(notes),
        "inbox": inbox,
        "by_bucket": by_bucket,
        "by_status": by_status,
    }


def triage_items(vault, *, now=None, max_items=MAX_TRIAGE_ITEMS) -> list[dict]:
    """Return a safe, independent inventory of inbox items needing disposition."""
    inbox = vault.root / "00_inbox"
    if inbox.is_symlink():
        raise ValueError("Refusing to triage a symlinked 00_inbox directory.")
    if not inbox.exists():
        return []

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    items = []
    paths = []
    for current, dir_names, file_names in os.walk(inbox, followlinks=False):
        current_path = Path(current)
        kept_dirs = []
        for name in sorted(dir_names):
            child = current_path / name
            rel = child.relative_to(vault.root).as_posix()
            if (
                rel.startswith("00_inbox/fleeting/")
                or rel == "00_inbox/fleeting"
                or is_index_excluded(rel, directory=True)
            ):
                continue
            if child.is_symlink():
                paths.append(child)
            else:
                kept_dirs.append(name)
        dir_names[:] = kept_dirs
        paths.extend(current_path / name for name in sorted(file_names))
        if len(paths) > max_items:
            raise ValueError(
                f"Inbox triage exceeds the safety limit of {max_items} items; "
                "reduce or partition 00_inbox before retrying."
            )

    for path in sorted(paths):
        rel = path.relative_to(vault.root).as_posix()
        if rel.startswith("00_inbox/fleeting/"):
            continue
        if path.name in {".gitkeep"} or path.name.endswith("_reason.txt"):
            continue
        if rel == "00_inbox/unsure/README.md":
            continue

        items.append(_triage_item(vault, path, rel, now))
    return items


def efforts(vault) -> list[dict]:
    """Return active actionables grouped by explicit effort profile."""
    rows = []
    for base_rel, kind in (("01_projects", "project"), ("02_areas", "area")):
        raw_base = vault.root / base_rel
        if not raw_base.exists() and not raw_base.is_symlink():
            continue
        base = vault.safe_directory_path(base_rel)
        for candidate in sorted(base.iterdir()):
            if candidate.is_symlink() or not candidate.is_dir() or candidate.name.startswith("_"):
                continue
            folder = vault.safe_directory_path(candidate.relative_to(vault.root).as_posix())
            context = _context_frontmatter(vault, folder)
            if context.get("status") == "active":
                rows.append(_effort_row(
                    context,
                    kind=kind,
                    label=_display_slug(folder.name, kind),
                    path=(folder / "_context.md").relative_to(vault.root).as_posix(),
                ))

    for path, fm, _ in vault.iter_notes(skip_invalid=True):
        rel = path.relative_to(vault.root).as_posix()
        if (
            path.name == "_context.md"
            or fm.get("status") != "active"
            or fm.get("type") == "template"
            or rel.startswith("03_resources/templates/")
        ):
            continue
        rows.append(_effort_row(
            fm,
            kind=fm.get("type") or "note",
            label=fm.get("title") or path.stem,
            path=rel,
        ))

    return sorted(rows, key=_effort_sort_key)


def health(vault, *, now=None) -> dict:
    """Compute live density and lifecycle signals without relying on indexes."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Health calculation time must include a timezone.")
    now = now.astimezone(timezone.utc)
    metrics = {
        "input": 0,
        "output": 0,
        "integrations": 0,
        "maps": 0,
        "stale": 0,
        "maturing_over_90_days": 0,
    }

    for _, fm, _ in vault.iter_notes():
        source = fm.get("source")
        if source in {"captured", "imported"}:
            metrics["input"] += 1
        if source in {"manual", "derived"}:
            metrics["output"] += 1
        if fm.get("type") == "integration":
            metrics["integrations"] += 1
        if fm.get("type") == "map":
            metrics["maps"] += 1
        if fm.get("status") == "stale":
            metrics["stale"] += 1
        if fm.get("status") == "maturing":
            changed = _parse_datetime(fm.get("modified") or fm.get("created"))
            if changed is not None and now - changed > timedelta(days=90):
                metrics["maturing_over_90_days"] += 1

    metrics["ratio"] = metrics["output"] / metrics["input"] if metrics["input"] else None
    metrics["unresolved_unsure"] = _count_unsure(vault)
    iso_year, iso_week, _ = now.isocalendar()
    metrics["period"] = f"{iso_year}-W{iso_week:02d}"
    metrics["warning"] = metrics["ratio"] is not None and metrics["ratio"] < 0.5
    return metrics


def search(vault, query: str) -> list[dict]:
    """Phase 1 keyword search over the generated FTS index, with text fallback."""
    q = (query or "").casefold().strip()
    if not q:
        return []

    fts_hits = index_mod.search_fts(vault, query)
    if fts_hits is not None:
        return fts_hits

    hits = []
    for path, fm, body in vault.iter_notes():
        haystack = "\n".join([
            str(fm.get("id") or ""),
            str(fm.get("title") or ""),
            str(fm.get("description") or ""),
            " ".join(str(t) for t in fm.get("tags") or []),
            body or "",
        ]).casefold()
        if q in haystack:
            hits.append({
                "id": fm.get("id"),
                "title": fm.get("title") or "(untitled)",
                "path": path.relative_to(vault.root).as_posix(),
                "snippet": "",
                "backend": "text-fallback",
            })
    return sorted(hits, key=lambda item: (item["path"], item.get("id") or ""))


def _triage_item(vault, path: Path, rel: str, now: datetime) -> dict:
    extension = path.suffix.lstrip(".").lower() or "file"
    base = {
        "path": rel,
        "kind": "malformed",
        "id": None,
        "title": None,
        "type": extension,
        "preview": "(unreadable)",
        "reason": None,
        "created_at": None,
        "age_seconds": 0,
        "age_basis": "filesystem-mtime",
        "sha256": None,
        "actions": ["leave"],
    }
    try:
        stat_result = path.lstat()
        modified = datetime.fromtimestamp(stat_result.st_mtime, timezone.utc)
        base["age_seconds"] = max(0, int((now - modified).total_seconds()))
    except OSError as exc:
        base["reason"] = f"Cannot inspect inbox item: {exc}"
        return base

    if path.is_symlink():
        base["preview"] = "Symlink not followed"
        base["reason"] = "Symlinks are not actionable inbox sources."
        return base

    try:
        source = vault.safe_source_path(rel)
        digest, raw, truncated, valid_utf8 = _read_triage_source(source)
    except (OSError, ValueError) as exc:
        base["reason"] = f"Cannot read inbox item: {exc}"
        return base

    base["sha256"] = digest
    if not valid_utf8:
        base.update({
            "kind": "binary",
            "preview": f"Binary or non-UTF-8 file: {path.name}",
            "actions": ["ingest", "leave"],
        })
        return _with_unsure_reason(vault, path, rel, base)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        if truncated:
            text = raw.decode("utf-8", errors="ignore")
        else:
            base.update({
                "kind": "binary",
                "preview": f"Binary or non-UTF-8 file: {path.name}",
                "actions": ["ingest", "leave"],
            })
            return _with_unsure_reason(vault, path, rel, base)
    if _looks_binary(text):
        base.update({
            "kind": "binary",
            "preview": f"Binary file: {path.name}",
            "actions": ["ingest", "leave"],
        })
        return _with_unsure_reason(vault, path, rel, base)

    try:
        fm, body = fmlib.parse_note_text(text)
    except ValueError as exc:
        base.update({
            "kind": "malformed",
            "preview": _preview(text) + (" (preview truncated)" if truncated else ""),
            "reason": f"Malformed frontmatter: {exc}",
            "actions": ["ingest", "leave"],
        })
        return _with_unsure_reason(vault, path, rel, base)

    if fm:
        base.update({
            "kind": "note",
            "id": fm.get("id"),
            "title": fm.get("title"),
            "type": fm.get("type") or extension,
            "preview": _preview(body) + (" (preview truncated)" if truncated else ""),
            "actions": ["edit", "leave"] if fm.get("id") else ["ingest", "leave"],
        })
        created = _parse_datetime(fm.get("created"))
        if created is not None:
            base["created_at"] = fm.get("created")
            base["age_seconds"] = max(0, int((now - created).total_seconds()))
            base["age_basis"] = "frontmatter-created"
    else:
        base.update({
            "kind": "text",
            "preview": _preview(text) + (" (preview truncated)" if truncated else ""),
            "actions": ["ingest", "leave"],
        })
    return _with_unsure_reason(vault, path, rel, base)


def _with_unsure_reason(vault, path: Path, rel: str, item: dict) -> dict:
    if not rel.startswith("00_inbox/unsure/"):
        return item
    reason_path = path.parent / f"{path.name}_reason.txt"
    reason_rel = reason_path.relative_to(vault.root).as_posix()
    if reason_path.is_symlink() or not reason_path.exists():
        return item
    try:
        reason = vault.safe_source_path(reason_rel).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError, ValueError):
        return item
    if reason:
        item["reason"] = reason
    return item


def _looks_binary(text: str) -> bool:
    sample = text[:4096]
    if "\x00" in sample:
        return True
    controls = sum(ord(character) < 32 and character not in "\n\r\t\f\b" for character in sample)
    return bool(sample) and controls / len(sample) > 0.05


def _preview(body: str) -> str:
    for line in (body or "").splitlines():
        line = line.strip()
        if line:
            return line[:120]
    return "(empty)"


def _read_triage_source(path: Path) -> tuple[str, bytes, bool, bool]:
    """Hash a source completely while retaining only a bounded UTF-8 preview."""
    digest = hashlib.sha256()
    decoder = codecs.getincrementaldecoder("utf-8")()
    captured = bytearray()
    total = 0
    valid_utf8 = True
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            total += len(chunk)
            if len(captured) < MAX_TRIAGE_TEXT_BYTES:
                captured.extend(chunk[:MAX_TRIAGE_TEXT_BYTES - len(captured)])
            if valid_utf8:
                try:
                    decoder.decode(chunk, final=False)
                except UnicodeDecodeError:
                    valid_utf8 = False
    if valid_utf8:
        try:
            decoder.decode(b"", final=True)
        except UnicodeDecodeError:
            valid_utf8 = False
    return digest.hexdigest(), bytes(captured), total > len(captured), valid_utf8


def _context_frontmatter(vault, folder) -> dict:
    context = folder / "_context.md"
    if context.is_symlink() or not context.exists():
        return {}
    rel = context.relative_to(vault.root).as_posix()
    fm, _ = fmlib.read_note(vault.safe_source_path(rel))
    return fm


def _display_slug(folder_name: str, kind: str) -> str:
    if kind == "area":
        parts = folder_name.split("__")
        if len(parts) >= 3 and parts[0] == "area":
            return parts[-2]
    return folder_name


def _effort_row(fm: dict, *, kind: str, label: str, path: str) -> dict:
    cadence = fm.get("effort_cadence")
    level = fm.get("effort_level")
    classified = cadence in CADENCE_ORDER and level in LEVEL_ORDER
    return {
        "kind": kind,
        "label": label,
        "path": path,
        "project": fm.get("project"),
        "area": fm.get("area"),
        "resource": fm.get("resource"),
        "effort_cadence": cadence,
        "effort_level": level,
        "group": f"{cadence}:{level}" if classified else "unclassified",
    }


def _effort_sort_key(row: dict) -> tuple:
    cadence = row.get("effort_cadence")
    level = row.get("effort_level")
    if row["group"] == "unclassified":
        return 2, 9, row["kind"], row["label"]
    return CADENCE_ORDER[cadence], LEVEL_ORDER[level], row["kind"], row["label"]


def _parse_datetime(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = fmlib.parse_note_timestamp(value)
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc)


def _count_unsure(vault) -> int:
    unsure = vault.root / "00_inbox" / "unsure"
    if not unsure.exists() or unsure.is_symlink():
        return 0
    count = 0
    for current, dirs, files in os.walk(unsure, followlinks=False):
        current_path = Path(current)
        dirs[:] = [name for name in dirs if not (current_path / name).is_symlink()]
        for name in files:
            path = current_path / name
            if path.is_symlink() or name in {".gitkeep", "README.md"} or name.endswith("_reason.txt"):
                continue
            count += 1
    return count

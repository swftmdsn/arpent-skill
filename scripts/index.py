"""
index.py - inventory the vault and build its generated indexes.

These are rebuildable derivatives of the markdown source of truth. They are
never authoritative; deleting them and re-running `index` reconstructs them.
"""

from __future__ import annotations

import codecs
import hashlib
import json
import mimetypes
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import context as context_mod
from . import frontmatter as fmlib
from .vault import INDEX_EXCLUDED_DIR_NAMES, Vault, is_index_excluded, raise_walk_error

SIDECAR_FIELDS = [
    "id", "title", "type", "status", "project", "area", "resource",
    "effort_cadence", "effort_level", "tags", "source", "author", "created", "modified",
    "related", "relations", "parent", "pinned",
]

EXCLUDED_FILE_NAMES = {".DS_Store", "Thumbs.db"}
GENERATED_INDEX_PATHS = {
    "06_indexes/context_index.json",
    "06_indexes/index.json",
    "06_indexes/sidecar.json",
}


def build_index(vault: Vault) -> dict:
    with vault.exclusive_lock("index"):
        with vault.exclusive_lock("mutations"):
            return _build_index(vault)


def _build_index(vault: Vault) -> dict:
    vault.refuse_foreign_transactions()
    source_signature = _search_source_signature(vault)
    for relpath in (
        "06_indexes/index.json",
        "06_indexes/sidecar.json",
        "06_indexes/context_index.json",
        "06_indexes/databases/search.db",
    ):
        vault.safe_output_path(relpath)

    folders, files, notes = build_inventory(vault)
    if _search_source_signature(vault) != source_signature:
        raise ValueError("Vault sources changed during indexing; retry the index operation.")

    sidecar = {
        rel: {k: fm.get(k) for k in SIDECAR_FIELDS}
        for rel, fm, _ in notes
    }

    by_type, by_status, by_bucket = {}, {}, {}
    for rel, fm, _ in notes:
        by_type[fm.get("type")] = by_type.get(fm.get("type"), 0) + 1
        by_status[fm.get("status")] = by_status.get(fm.get("status"), 0) + 1
        bucket = rel.split("/", 1)[0]
        by_bucket[bucket] = by_bucket.get(bucket, 0) + 1

    search_available = build_search_db(
        vault, notes, source_signature=source_signature,
    )
    index = {
        "version": 2,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note_count": len(notes),
        "file_count": len(files),
        "folder_count": len(folders),
        "by_type": by_type,
        "by_status": by_status,
        "by_bucket": by_bucket,
        "paths": sorted(rel for rel, _, _ in notes),
        "folders": folders,
        "files": files,
        "search_backend": "fts5" if search_available else "text-fallback",
    }

    context_mod.refresh_context_index(vault, folders=folders, files=files)
    vault.atomic_write_text("06_indexes/index.json", json.dumps(index, indent=2) + "\n")
    vault.atomic_write_text("06_indexes/sidecar.json", json.dumps(sidecar, indent=2) + "\n")
    return index


def build_inventory(vault: Vault, *, start_rel=".") -> tuple[list[dict], list[dict], list[tuple]]:
    """Inventory user-owned folders and files without following symlinks."""
    start = vault.safe_directory_path(start_rel)
    folder_paths = set()
    files = []
    notes = []

    for current, dir_names, file_names in os.walk(
        start,
        followlinks=False,
        onerror=raise_walk_error,
    ):
        current_path = Path(current)
        current_rel = _relative(vault, current_path)
        folder_paths.add(current_rel)

        kept_dirs = []
        for name in sorted(dir_names):
            child = current_path / name
            child_rel = _relative(vault, child)
            if child.is_symlink():
                files.append(_symlink_entry(vault, child))
            elif not _excluded_directory(child_rel, name):
                kept_dirs.append(name)
        dir_names[:] = kept_dirs

        for name in sorted(file_names):
            path = current_path / name
            rel = _relative(vault, path)
            if name in EXCLUDED_FILE_NAMES or rel in GENERATED_INDEX_PATHS:
                continue
            if path.is_symlink():
                files.append(_symlink_entry(vault, path))
                continue
            entry, note = _file_entry(vault, path)
            files.append(entry)
            if note:
                notes.append((rel, note[0], note[1]))

    folders = _folder_entries(vault, folder_paths, files)
    return folders, sorted(files, key=lambda item: item["path"]), sorted(notes)


def _file_entry(vault: Vault, path: Path) -> tuple[dict, tuple | None]:
    rel = _relative(vault, path)
    try:
        path = vault.safe_source_path(rel)
        for _ in range(2):
            before = path.stat()
            sha256, is_text, text = _inspect_file(
                path,
                capture_full=path.suffix.lower() == ".md",
            )
            after = path.stat()
            if _stat_signature(before) == _stat_signature(after):
                stat = after
                break
        else:
            raise ValueError(f"Source changed repeatedly while indexing: {rel}")
        readable = True
    except OSError:
        stat = path.lstat()
        sha256 = None
        is_text = False
        text = None
        readable = False

    note = None
    if is_text and path.suffix.lower() == ".md" and not _note_infrastructure_path(rel):
        fm, body = fmlib.parse_note_text(text or "")
        if fm.get("id"):
            note = (fm, body)
    kind = "note" if note else "text" if is_text else "file"
    fm, body = note if note else ({}, None)
    context_hash = _note_context_hash(fm, body) if note else sha256 or _stat_hash(stat)
    mime_type, _ = mimetypes.guess_type(path.name)
    entry = {
        "path": rel,
        "parent": _parent_rel(rel),
        "name": path.name,
        "extension": path.suffix.lower() or None,
        "kind": kind,
        "mime_type": mime_type,
        "size": stat.st_size,
        "modified": _timestamp(stat.st_mtime),
        "sha256": sha256,
        "context_hash": context_hash,
        "readable": readable,
        "note_id": fm.get("id"),
        "title": fm.get("title"),
        "description": fm.get("description"),
        "preview": _body_preview(body) if note else _text_preview(text) if is_text else None,
    }
    return entry, note


def _symlink_entry(vault: Vault, path: Path) -> dict:
    rel = _relative(vault, path)
    try:
        target = os.readlink(path)
    except OSError:
        target = None
    target_bytes = os.fsencode(target or "")
    target_display = target_bytes.decode("utf-8", errors="backslashreplace")
    digest = hashlib.sha256(target_bytes).hexdigest()
    return {
        "path": rel,
        "parent": _parent_rel(rel),
        "name": path.name,
        "extension": path.suffix.lower() or None,
        "kind": "symlink",
        "mime_type": None,
        "size": len(target_bytes),
        "modified": None,
        "sha256": digest,
        "context_hash": digest,
        "readable": False,
        "note_id": None,
        "title": None,
        "description": None,
        "preview": None,
        "target": target_display,
    }


def _folder_entries(vault: Vault, paths: set[str], files: list[dict]) -> list[dict]:
    data = {
        rel: {
            "path": rel,
            "parent": None if rel == "." else _parent_rel(rel),
            "name": vault.root.name if rel == "." else _path_name(rel),
            "kind": "folder",
            "children": [],
            "direct_file_count": 0,
            "direct_folder_count": 0,
        }
        for rel in paths
    }

    for rel, entry in data.items():
        if rel != "." and entry["parent"] in data:
            data[entry["parent"]]["children"].append(rel)
            data[entry["parent"]]["direct_folder_count"] += 1
    for file_entry in files:
        parent = file_entry["parent"]
        if parent in data:
            data[parent]["children"].append(file_entry["path"])
            data[parent]["direct_file_count"] += 1

    files_by_path = {item["path"]: item for item in files}
    for rel in sorted(data, key=_path_depth, reverse=True):
        entry = data[rel]
        child_folders = [data[p] for p in entry["children"] if p in data]
        direct_files = [files_by_path[p] for p in entry["children"] if p in files_by_path]
        entry["children"].sort()
        entry["recursive_file_count"] = entry["direct_file_count"] + sum(
            child["recursive_file_count"] for child in child_folders
        )
        entry["recursive_folder_count"] = entry["direct_folder_count"] + sum(
            child["recursive_folder_count"] for child in child_folders
        )
        material = [
            f"path\0{rel}",
            *(f"file\0{item['name']}\0{item['context_hash']}" for item in direct_files),
            *(f"folder\0{child['name']}\0{child['context_hash']}" for child in child_folders),
        ]
        entry["context_hash"] = hashlib.sha256("\n".join(sorted(material)).encode("utf-8")).hexdigest()
    return [data[path] for path in sorted(data)]


def _path_name(rel: str) -> str:
    return rel.rsplit("/", 1)[-1]


def _path_depth(rel: str) -> int:
    return 0 if rel == "." else rel.count("/") + 1


def _excluded_directory(rel: str, name: str) -> bool:
    return name in INDEX_EXCLUDED_DIR_NAMES or is_index_excluded(rel, directory=True)


def _relative(vault: Vault, path: Path) -> str:
    rel = path.relative_to(vault.root).as_posix()
    return rel or "."


def _parent_rel(rel: str) -> str:
    if "/" not in rel:
        return "."
    return rel.rsplit("/", 1)[0]


def current_context_hash(vault: Vault, relpath: str, kind: str) -> str:
    """Compute the current semantic hash without relying on the cached index."""
    if kind == "folder":
        folders, _, _ = build_inventory(vault, start_rel=relpath)
        match = next((entry for entry in folders if entry["path"] == relpath), None)
        if match is None:
            raise ValueError(f"Indexed folder no longer exists: {relpath}")
        return match["context_hash"]

    path = vault.safe_source_path(relpath)
    entry, _ = _file_entry(vault, path)
    if entry["kind"] != kind:
        raise ValueError(f"Indexed source kind changed for '{relpath}'. Run `arpent index`.")
    return entry["context_hash"]


def _inspect_file(path: Path, *, capture_full=False) -> tuple[str, bool, str | None]:
    digest = hashlib.sha256()
    decoder = codecs.getincrementaldecoder("utf-8")()
    is_text = True
    captured = []
    captured_length = 0
    capture_limit = None if capture_full else 64 * 1024
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            if is_text:
                if b"\x00" in chunk:
                    is_text = False
                else:
                    try:
                        decoded = decoder.decode(chunk, final=False)
                        if capture_limit is None or captured_length < capture_limit:
                            remaining = None if capture_limit is None else capture_limit - captured_length
                            piece = decoded if remaining is None else decoded[:remaining]
                            captured.append(piece)
                            captured_length += len(piece)
                    except UnicodeDecodeError:
                        is_text = False
                        captured = []
    if is_text:
        try:
            decoded = decoder.decode(b"", final=True)
            if capture_limit is None or captured_length < capture_limit:
                remaining = None if capture_limit is None else capture_limit - captured_length
                captured.append(decoded if remaining is None else decoded[:remaining])
        except UnicodeDecodeError:
            is_text = False
            captured = []
    return digest.hexdigest(), is_text, "".join(captured) if is_text else None


def _note_context_hash(fm: dict, body: str | None) -> str:
    stable_frontmatter = {
        key: value
        for key, value in fm.items()
        if key not in {"created", "modified"}
    }
    content = {
        "frontmatter": stable_frontmatter,
        "body": body or "",
    }
    encoded = json.dumps(content, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _stat_hash(stat) -> str:
    return hashlib.sha256(f"{stat.st_size}:{stat.st_mtime_ns}".encode("ascii")).hexdigest()


def _stat_signature(stat) -> tuple:
    return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino


def _text_preview(text: str | None) -> str | None:
    for line in (text or "").splitlines()[:80]:
        stripped = line.strip()
        if stripped and stripped != "---" and not stripped.startswith("#"):
            return stripped[:160]
    return None


def _note_infrastructure_path(relpath: str) -> bool:
    return relpath.startswith(("06_indexes/docs/", "06_indexes/global_skills/"))


def _body_preview(body: str | None) -> str | None:
    for line in (body or "").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped[:160]
    return None


def _timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_search_db(vault: Vault, notes=None, *, source_signature=None) -> bool:
    """Rebuild the Phase 1 FTS5 database from markdown notes."""
    if notes is None:
        source_signature = source_signature or _search_source_signature(vault)
        notes = [
            (path.relative_to(vault.root).as_posix(), fm, body)
            for path, fm, body in vault.iter_notes()
        ]
    source_signature = source_signature or _search_source_signature(vault)

    db_path = vault.safe_output_path("06_indexes/databases/search.db")
    fd, temporary_name = tempfile.mkstemp(
        dir=db_path.parent,
        prefix=".search.",
        suffix=".db.tmp",
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        con = sqlite3.connect(temporary)
    except sqlite3.Error:
        temporary.unlink(missing_ok=True)
        return False
    try:
        con.execute("DROP TABLE IF EXISTS notes_fts")
        con.execute(
            """
            CREATE VIRTUAL TABLE notes_fts USING fts5(
                id UNINDEXED,
                path UNINDEXED,
                title,
                description,
                tags,
                body,
                type UNINDEXED,
                status UNINDEXED,
                source UNINDEXED,
                author UNINDEXED
            )
            """
        )
        con.execute("CREATE TABLE search_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        rows = []
        for rel, fm, body in notes:
            rows.append((
                fm.get("id"),
                rel,
                fm.get("title") or "",
                fm.get("description") or "",
                " ".join(str(t) for t in fm.get("tags") or []),
                body or "",
                fm.get("type") or "",
                fm.get("status") or "",
                fm.get("source") or "",
                fm.get("author") or "",
            ))
        con.executemany(
            """
            INSERT INTO notes_fts(
                id, path, title, description, tags, body, type, status, source, author
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        con.execute(
            "INSERT INTO search_meta(key, value) VALUES ('source_signature', ?)",
            (source_signature,),
        )
        con.commit()
    except sqlite3.Error:
        con.close()
        temporary.unlink(missing_ok=True)
        return False
    finally:
        try:
            con.close()
        except sqlite3.Error:
            pass
    try:
        current_signature = _search_source_signature(vault)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    if current_signature != source_signature:
        temporary.unlink(missing_ok=True)
        raise ValueError("Vault sources changed while building search.db; retry indexing.")
    os.replace(temporary, db_path)
    return True


def search_fts(vault: Vault, query: str) -> list[dict] | None:
    """Search the generated FTS database. Return None when it is unavailable."""
    q = (query or "").strip()
    if not q:
        return []

    try:
        db_path = vault.safe_source_path("06_indexes/databases/search.db")
    except (OSError, ValueError):
        return None

    try:
        con = sqlite3.connect(db_path)
    except sqlite3.Error:
        return None
    con.row_factory = sqlite3.Row
    try:
        try:
            stored_signature = con.execute(
                "SELECT value FROM search_meta WHERE key = 'source_signature'"
            ).fetchone()
            if stored_signature is None or stored_signature["value"] != _search_source_signature(vault):
                return None
            rows = con.execute(
                """
                SELECT id, title, path, snippet(notes_fts, 5, '', '', '...', 12) AS snippet
                FROM notes_fts
                WHERE notes_fts MATCH ?
                ORDER BY rank
                LIMIT 50
                """,
                (_fts_query(q),),
            ).fetchall()
        except sqlite3.Error:
            return None
        return [
            {
                "id": row["id"],
                "title": row["title"] or "(untitled)",
                "path": row["path"],
                "snippet": row["snippet"] or "",
            }
            for row in rows
        ]
    finally:
        con.close()


def _search_source_signature(vault: Vault) -> str:
    """Hash paths and stat data for every Markdown file eligible to become a note."""
    digest = hashlib.sha256()
    for current, dir_names, file_names in os.walk(
        vault.root,
        followlinks=False,
        onerror=raise_walk_error,
    ):
        current_path = Path(current)
        kept_dirs = []
        for name in sorted(dir_names):
            child = current_path / name
            rel = _relative(vault, child)
            if not child.is_symlink() and not is_index_excluded(rel, directory=True):
                kept_dirs.append(name)
        dir_names[:] = kept_dirs
        for name in sorted(file_names):
            if not name.lower().endswith(".md"):
                continue
            path = current_path / name
            rel = _relative(vault, path)
            if _note_infrastructure_path(rel):
                continue
            source = vault.safe_source_path(rel)
            stat = source.stat()
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            digest.update(str(stat.st_size).encode("ascii"))
            digest.update(b":")
            digest.update(str(stat.st_mtime_ns).encode("ascii"))
            digest.update(b":")
            digest.update(str(stat.st_ctime_ns).encode("ascii"))
            digest.update(b"\0")
    return digest.hexdigest()


def _fts_query(query: str) -> str:
    terms = [term.strip('"') for term in query.split() if term.strip('"')]
    return " ".join(f'"{term}"' for term in terms) if terms else '""'

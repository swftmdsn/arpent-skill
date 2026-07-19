"""Build and maintain the optional L0/L1/L2 context cache."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import PurePosixPath

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None
    import msvcrt
else:  # pragma: no cover - not used on Windows
    msvcrt = None


CONTEXT_REL_PATH = "06_indexes/context_index.json"


def refresh_context_index(
    vault, *, folders: list[dict], files: list[dict], generation: str | None = None,
) -> dict:
    """Refresh deterministic levels and retain AI summaries with matching hashes."""
    with vault.exclusive_lock("mutations"), _context_lock(vault):
        result = prepare_context_index(
            vault, folders=folders, files=files, generation=generation,
        )
        _write_context_index(vault, result)
        return result


def prepare_context_index(
    vault, *, folders: list[dict], files: list[dict], generation: str | None = None,
) -> dict:
    """Build a context generation in memory for coordinated index publication."""
    old = load_context_index(vault, required=False, validate_generation=False)
    old_entries = old.get("entries") or {}
    reusable = _summaries_by_hash(old_entries)
    entries = {}

    for item in [*folders, *files]:
        path = item["path"]
        source_hash = item["context_hash"]
        eligible = item["kind"] in {"folder", "note", "text"}
        previous = old_entries.get(path, {}).get("l1") or {}

        if previous.get("source_hash") != source_hash:
            previous = reusable.get((item["kind"], source_hash), previous)
        if not eligible:
            previous = {}

        summary = previous.get("summary")
        summary_hash = previous.get("source_hash")
        if not eligible:
            status = "unsupported"
        elif summary and summary_hash == source_hash:
            status = "fresh"
        elif summary:
            status = "stale"
        else:
            status = "missing"

        entries[path] = {
            "kind": item["kind"],
            "source_hash": source_hash,
            "l0": _l0(item),
            "l1": {
                "status": status,
                "summary": summary,
                "source_hash": summary_hash,
                "updated_at": previous.get("updated_at"),
                "provider": previous.get("provider"),
            },
            "l2": _l2(item),
        }

    result = {
        "version": 1,
        "generated": _now_iso(),
        "levels": {
            "L0": "Deterministic one-line orientation, safe to load broadly.",
            "L1": "Optional AI summary, valid only for its recorded source_hash.",
            "L2": "Source pointer or folder children, loaded only on demand.",
        },
        "entries": dict(sorted(entries.items())),
    }
    if generation is not None:
        result["generation"] = generation
    return result


def load_context_index(
    vault, *, required: bool = True, validate_generation: bool = True,
) -> dict:
    raw_path = vault.root / CONTEXT_REL_PATH
    if not raw_path.exists() and not raw_path.is_symlink():
        if required:
            raise ValueError("No context index. Run `arpent index` first.")
        return {}
    try:
        path = vault.safe_source_path(CONTEXT_REL_PATH)
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read {CONTEXT_REL_PATH}: {exc}") from exc
    if (
        not isinstance(data, dict)
        or data.get("version") != 1
        or not isinstance(data.get("entries"), dict)
    ):
        raise ValueError(
            f"Invalid structure in {CONTEXT_REL_PATH}; the existing file was preserved."
        )
    generation = data.get("generation")
    if validate_generation and generation is not None:
        index_relpath = "06_indexes/index.json"
        raw_index = vault.root / index_relpath
        if not raw_index.exists() and not raw_index.is_symlink():
            raise ValueError("Context index publication is incomplete; run `arpent index` again.")
        try:
            index_data = json.loads(
                vault.safe_source_path(index_relpath).read_text(encoding="utf-8")
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot validate context index generation: {exc}") from exc
        if not isinstance(index_data, dict) or index_data.get("generation") != generation:
            raise ValueError("Context index generation is incomplete; run `arpent index` again.")
    return data


def pending_summaries(vault, *, kind=None, prefix=None) -> list[dict]:
    data = load_context_index(vault)
    normalized_prefix = normalize_path(prefix) if prefix else None
    rows = []
    for path, entry in sorted((data.get("entries") or {}).items()):
        if kind and entry.get("kind") != kind:
            continue
        if normalized_prefix and not _under_prefix(path, normalized_prefix):
            continue
        l1 = entry.get("l1") or {}
        if l1.get("status") not in {"missing", "stale"}:
            continue
        rows.append({
            "path": path,
            "kind": entry.get("kind"),
            "status": l1.get("status"),
            "source_hash": entry.get("source_hash"),
            "l0": entry.get("l0"),
        })
    return rows


def set_summary(
    vault,
    path: str,
    summary: str,
    *,
    expected_hash: str,
    provider="agent",
    force=False,
) -> dict:
    normalized = normalize_path(path)
    text = (summary or "").strip()
    if not text:
        raise ValueError("Summary cannot be empty.")

    with vault.exclusive_lock("mutations"), _context_lock(vault):
        vault.refuse_foreign_transactions()
        data = load_context_index(vault)
        entries = data.get("entries") or {}
        entry = entries.get(normalized)
        if entry is None:
            raise ValueError(f"No indexed path '{normalized}'. Run `arpent index` after creating it.")
        if entry.get("source_hash") != expected_hash:
            raise ValueError(
                f"Source hash changed for '{normalized}'; discard this summary and regenerate it."
            )
        from . import index as index_mod

        live_hash = index_mod.current_context_hash(vault, normalized, entry.get("kind"))
        if live_hash != expected_hash:
            raise ValueError(
                f"Source content changed for '{normalized}' since it was loaded; "
                "run `arpent index` and regenerate the summary."
            )
        if (entry.get("l1") or {}).get("status") == "unsupported":
            raise ValueError(f"L1 summaries are not supported for '{normalized}'.")
        if (entry.get("l1") or {}).get("status") == "fresh" and not force:
            raise ValueError(
                f"L1 summary for '{normalized}' is already fresh; content has not changed."
            )

        entry["l1"] = {
            "status": "fresh",
            "summary": text,
            "source_hash": entry["source_hash"],
            "updated_at": _now_iso(),
            "provider": provider or "agent",
        }
        data["summaries_updated"] = _now_iso()
        _write_context_index(vault, data)
        return entry


def get_entry(vault, path: str) -> dict:
    data = load_context_index(vault)
    normalized = normalize_path(path)
    entry = (data.get("entries") or {}).get(normalized)
    if entry is None:
        raise ValueError(f"No indexed path '{normalized}'.")
    return entry


def normalize_path(path: str | None) -> str:
    value = "." if path is None or path == "" else path
    if os.name == "nt":  # pragma: no cover - Windows only
        value = value.replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    value = value or "."
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("Path must be relative to the vault and cannot contain '..'.")
    return candidate.as_posix()


def _l0(item: dict) -> str:
    if item["kind"] == "folder":
        label = "Vault root" if item["path"] == "." else item["name"]
        return (
            f"{label} - {item['recursive_file_count']} files, "
            f"{item['recursive_folder_count']} subfolders"
        )
    if item["kind"] == "note":
        title = item.get("title") or item["name"]
        detail = item.get("description") or item.get("preview")
        return f"{title} - {detail}" if detail else title
    if item["kind"] == "text":
        preview = item.get("preview")
        return f"{item['name']} - {preview}" if preview else item["name"]
    if item["kind"] == "symlink":
        return f"{item['name']} - symbolic link to {item.get('target') or '?'}"
    return f"{item['name']} - binary or unreadable file, {item['size']} bytes"


def _l2(item: dict) -> dict:
    if item["kind"] == "folder":
        return {
            "type": "children",
            "path": item["path"],
            "children": item["children"],
        }
    return {
        "type": "source",
        "path": item["path"],
        "size": item["size"],
        "sha256": item.get("sha256"),
    }


def _summaries_by_hash(entries: dict) -> dict:
    reusable = {}
    for entry in entries.values():
        if not isinstance(entry, dict):
            continue
        l1 = entry.get("l1") or {}
        if l1.get("summary") and l1.get("source_hash"):
            reusable[(entry.get("kind"), l1["source_hash"])] = l1
    return reusable


def _under_prefix(path: str, prefix: str) -> bool:
    return prefix == "." or path == prefix or path.startswith(prefix + "/")


def _write_context_index(vault, data: dict) -> None:
    vault.atomic_write_text(
        CONTEXT_REL_PATH,
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
    )


@contextmanager
def _context_lock(vault):
    path = vault.safe_output_path("06_indexes/logs/context_index.lock")
    with path.open("a+", encoding="utf-8") as stream:
        if fcntl is not None:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        elif msvcrt is not None:  # pragma: no cover - Windows only
            stream.seek(0)
            if stream.read(1) == "":
                stream.write("\0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            elif msvcrt is not None:  # pragma: no cover - Windows only
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

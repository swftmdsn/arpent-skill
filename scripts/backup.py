"""Consistent, verifiable, and restorable logical vault snapshots."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from .vault import MUTATION_TRANSACTION_PATHS, Vault


BACKUP_FORMAT = "arpent-backup"
BACKUP_VERSION = 1
MANIFEST_NAME = "manifest.json"
MANIFEST_CHECKSUM_NAME = "manifest.sha256"
PAYLOAD_NAME = "payload"
DEFAULT_BACKUP_RELPATH = "06_indexes/backup"

_EXCLUDED_DIRECTORY_NAMES = {".git", ".venv", "__pycache__", "node_modules"}
_REBUILDABLE_PATHS = {
    "06_indexes/index.json",
    "06_indexes/sidecar.json",
    "06_indexes/databases/search.db",
}
_VOLATILE_FILE_NAMES = {".DS_Store", "Thumbs.db"}
_SQLITE_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


def create_backup(vault: Vault, destination: str | Path | None = None) -> dict:
    """Create and atomically publish a complete logical vault snapshot."""
    with vault.exclusive_lock("mutations"):
        vault.refuse_foreign_transactions()
        destination_root = _prepare_destination(vault, destination)
        source_entries, exclusions = _scan_tree(vault.root, apply_exclusions=True)

        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S_%f")
        snapshot_name = f"{stamp}-{uuid.uuid4().hex[:8]}"
        final = destination_root / snapshot_name
        staging = destination_root / f".partial-{snapshot_name}"
        if final.exists() or final.is_symlink() or staging.exists() or staging.is_symlink():
            raise ValueError(f"Backup destination collision: {final}")

        staging.mkdir(mode=0o700)
        payload = staging / PAYLOAD_NAME
        payload.mkdir(mode=0o700)
        try:
            manifest_entries = _copy_source_entries(vault, source_entries, payload)
            _assert_source_unchanged(
                vault.root,
                source_entries,
                exclusions,
                manifest_entries,
                staging,
            )
            manifest = _build_manifest(manifest_entries, exclusions)
            _write_manifest(staging, manifest)
            _fsync_tree(staging)
            verify_backup(staging)
            os.rename(staging, final)
            _fsync_directory(destination_root)
        except BaseException:
            if staging.exists() and not staging.is_symlink():
                shutil.rmtree(staging, ignore_errors=True)
            raise

    result = dict(manifest)
    result["snapshot_path"] = str(final)
    return result


def verify_backup(snapshot_path: str | Path) -> dict:
    """Verify manifest integrity, exact payload contents, and SQLite health."""
    snapshot = _existing_directory(snapshot_path, label="Backup snapshot")
    manifest_path = _regular_child(snapshot, MANIFEST_NAME)
    checksum_path = _regular_child(snapshot, MANIFEST_CHECKSUM_NAME)
    payload = _existing_directory(snapshot / PAYLOAD_NAME, label="Backup payload")

    manifest_bytes = manifest_path.read_bytes()
    expected_checksum = _read_manifest_checksum(checksum_path)
    actual_checksum = hashlib.sha256(manifest_bytes).hexdigest()
    if actual_checksum != expected_checksum:
        raise ValueError("Backup manifest checksum mismatch.")
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid backup manifest: {exc}") from exc

    _validate_manifest(manifest)
    _verify_payload(payload, manifest)
    result = dict(manifest)
    result["snapshot_path"] = str(snapshot)
    return result


def restore_backup(snapshot_path: str | Path, target_path: str | Path) -> dict:
    """Restore a verified snapshot into a new directory and publish atomically."""
    verified = verify_backup(snapshot_path)
    snapshot = Path(verified["snapshot_path"])
    payload = snapshot / PAYLOAD_NAME

    supplied_target = Path(target_path).expanduser()
    if supplied_target.exists() or supplied_target.is_symlink():
        raise ValueError(f"Restore target must not already exist: {supplied_target}")
    target = supplied_target.resolve(strict=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.parent.is_symlink():
        raise ValueError(f"Refusing to restore through a symlinked parent: {target.parent}")

    staging = target.parent / f".{target.name}.restore-{uuid.uuid4().hex[:8]}"
    if staging.exists() or staging.is_symlink():
        raise ValueError(f"Restore staging collision: {staging}")
    staging.mkdir(mode=0o700)
    try:
        _restore_entries(payload, staging, verified["entries"])
        _verify_payload(staging, verified)
        _fsync_tree(staging)
        if target.exists() or target.is_symlink():
            raise ValueError(f"Restore target appeared during restore: {target}")
        os.rename(staging, target)
        _fsync_directory(target.parent)
    except BaseException:
        if staging.exists() and not staging.is_symlink():
            shutil.rmtree(staging, ignore_errors=True)
        raise

    result = dict(verified)
    result["restored_path"] = str(target)
    return result


def _prepare_destination(vault: Vault, destination: str | Path | None) -> Path:
    default = vault.root / DEFAULT_BACKUP_RELPATH
    if destination is None:
        return vault.safe_ensure_directory(DEFAULT_BACKUP_RELPATH)

    supplied = Path(destination).expanduser()
    if supplied.is_symlink():
        raise ValueError(f"Refusing a symlinked backup destination: {supplied}")
    resolved = supplied.resolve(strict=False)
    try:
        relative = resolved.relative_to(vault.root)
    except ValueError:
        relative = None
    if relative is not None and resolved != default:
        raise ValueError(
            "A destination inside the vault must be exactly 06_indexes/backup; "
            "use an external directory otherwise."
        )
    if resolved == default:
        return vault.safe_ensure_directory(DEFAULT_BACKUP_RELPATH)
    resolved.mkdir(parents=True, exist_ok=True)
    if not resolved.is_dir():
        raise ValueError(f"Backup destination is not a directory: {resolved}")
    return resolved


def _scan_tree(root: Path, *, apply_exclusions: bool) -> tuple[list[dict], list[dict]]:
    entries: list[dict] = []
    exclusions: list[dict] = []

    def walk(directory: Path, prefix: PurePosixPath | None = None) -> None:
        try:
            children = sorted(os.scandir(directory), key=lambda child: child.name)
        except OSError as exc:
            raise ValueError(f"Cannot inventory backup source '{directory}': {exc}") from exc
        for child in children:
            rel = PurePosixPath(child.name) if prefix is None else prefix / child.name
            relpath = rel.as_posix()
            _validate_relpath(relpath)
            reason = _exclusion_reason(relpath) if apply_exclusions else None
            if reason:
                exclusions.append({"path": relpath, "reason": reason})
                continue
            try:
                metadata = child.stat(follow_symlinks=False)
                if child.is_symlink():
                    entries.append({
                        "path": relpath,
                        "type": "symlink",
                        "target": os.readlink(child.path),
                    })
                elif child.is_dir(follow_symlinks=False):
                    entries.append({
                        "path": relpath,
                        "type": "directory",
                        "mode": stat.S_IMODE(metadata.st_mode),
                        "mtime_ns": metadata.st_mtime_ns,
                    })
                    walk(Path(child.path), rel)
                elif child.is_file(follow_symlinks=False):
                    path = Path(child.path)
                    entry_type = "sqlite" if _looks_like_sqlite(path) else "file"
                    entries.append({
                        "path": relpath,
                        "type": entry_type,
                        "mode": stat.S_IMODE(metadata.st_mode),
                        "mtime_ns": metadata.st_mtime_ns,
                        "source_size": metadata.st_size,
                    })
                else:
                    raise ValueError(f"Unsupported filesystem entry in vault: {relpath}")
            except OSError as exc:
                raise ValueError(f"Cannot inspect backup source '{relpath}': {exc}") from exc

    walk(root)
    return entries, exclusions


def _exclusion_reason(relpath: str) -> str | None:
    path = PurePosixPath(relpath)
    if relpath == DEFAULT_BACKUP_RELPATH or relpath.startswith(DEFAULT_BACKUP_RELPATH + "/"):
        return "backup recursion"
    if any(part in _EXCLUDED_DIRECTORY_NAMES for part in path.parts):
        return "rebuildable dependency or VCS metadata"
    if relpath in _REBUILDABLE_PATHS:
        return "rebuildable index"
    if relpath in MUTATION_TRANSACTION_PATHS:
        return "interrupted transaction journal"
    if relpath.startswith("06_indexes/logs/") and path.name.endswith(".lock"):
        return "runtime lock"
    if path.name in _VOLATILE_FILE_NAMES or path.name.endswith((".swp", "~")):
        return "volatile editor or operating-system state"
    if relpath == ".obsidian/workspace.json":
        return "volatile application workspace"
    if path.name.endswith(_SQLITE_SIDECAR_SUFFIXES):
        return "SQLite sidecar captured through the SQLite backup API"
    return None


def _copy_source_entries(vault: Vault, source_entries: list[dict], payload: Path) -> list[dict]:
    directories = [entry for entry in source_entries if entry["type"] == "directory"]
    for entry in sorted(directories, key=lambda item: (_path_depth(item["path"]), item["path"])):
        destination = _path_from_rel(payload, entry["path"])
        destination.mkdir(mode=0o700)

    manifest_entries: list[dict] = []
    for entry in source_entries:
        manifest_entry = {
            key: entry[key]
            for key in ("path", "type", "mode", "mtime_ns", "target")
            if key in entry
        }
        destination = _path_from_rel(payload, entry["path"])
        if entry["type"] == "directory":
            manifest_entries.append(manifest_entry)
            continue
        if entry["type"] == "symlink":
            destination.symlink_to(entry["target"])
            manifest_entries.append(manifest_entry)
            continue

        source = vault.safe_source_path(entry["path"])
        if entry["type"] == "sqlite":
            _copy_sqlite(source, destination)
            manifest_entry["quick_check"] = "ok"
        else:
            _copy_regular_file(source, destination)
        _apply_file_metadata(destination, entry)
        manifest_entry["size"] = destination.stat().st_size
        manifest_entry["sha256"] = _sha256_file(destination)
        manifest_entries.append(manifest_entry)

    for entry in sorted(directories, key=lambda item: _path_depth(item["path"]), reverse=True):
        _apply_directory_metadata(_path_from_rel(payload, entry["path"]), entry)
    return sorted(manifest_entries, key=lambda entry: entry["path"])


def _assert_source_unchanged(
    root: Path,
    original_entries: list[dict],
    original_exclusions: list[dict],
    manifest_entries: list[dict],
    staging: Path,
) -> None:
    current_entries, current_exclusions = _scan_tree(root, apply_exclusions=True)
    if original_exclusions != current_exclusions:
        raise ValueError("Vault exclusions changed while the backup was being created.")
    original_by_path = {entry["path"]: entry for entry in original_entries}
    current_by_path = {entry["path"]: entry for entry in current_entries}
    if original_by_path.keys() != current_by_path.keys():
        raise ValueError("Vault contents changed while the backup was being created.")

    manifest_by_path = {entry["path"]: entry for entry in manifest_entries}
    recheck_dir = staging / ".sqlite-recheck"
    for relpath, original in original_by_path.items():
        current = current_by_path[relpath]
        for key in ("type", "mode", "mtime_ns", "source_size", "target"):
            if original.get(key) != current.get(key):
                raise ValueError(f"Vault entry changed during backup: {relpath}")
        if original["type"] == "file":
            if _sha256_file(_safe_regular_path(root, relpath)) != manifest_by_path[relpath]["sha256"]:
                raise ValueError(f"Vault file changed during backup: {relpath}")
        elif original["type"] == "sqlite":
            recheck_dir.mkdir(mode=0o700, exist_ok=True)
            recheck = recheck_dir / f"{uuid.uuid4().hex}.db"
            try:
                _copy_sqlite(_safe_regular_path(root, relpath), recheck)
                if _sha256_file(recheck) != manifest_by_path[relpath]["sha256"]:
                    raise ValueError(f"Vault database changed during backup: {relpath}")
            finally:
                recheck.unlink(missing_ok=True)
    if recheck_dir.exists():
        recheck_dir.rmdir()


def _build_manifest(entries: list[dict], exclusions: list[dict]) -> dict:
    file_entries = [entry for entry in entries if entry["type"] in {"file", "sqlite"}]
    return {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "hash_algorithm": "sha256",
        "entries": entries,
        "excluded": exclusions,
        "totals": {
            "directories": sum(entry["type"] == "directory" for entry in entries),
            "files": len(file_entries),
            "sqlite_databases": sum(entry["type"] == "sqlite" for entry in entries),
            "symlinks": sum(entry["type"] == "symlink" for entry in entries),
            "bytes": sum(entry["size"] for entry in file_entries),
        },
    }


def _write_manifest(snapshot: Path, manifest: dict) -> None:
    encoded = (json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    checksum = hashlib.sha256(encoded).hexdigest()
    _write_bytes(snapshot / MANIFEST_NAME, encoded, mode=0o600)
    _write_bytes(
        snapshot / MANIFEST_CHECKSUM_NAME,
        f"{checksum}  {MANIFEST_NAME}\n".encode("ascii"),
        mode=0o600,
    )


def _validate_manifest(manifest: object) -> None:
    if not isinstance(manifest, dict):
        raise ValueError("Backup manifest must be a JSON object.")
    if manifest.get("format") != BACKUP_FORMAT or manifest.get("version") != BACKUP_VERSION:
        raise ValueError("Unsupported backup format or version.")
    if manifest.get("hash_algorithm") != "sha256":
        raise ValueError("Unsupported backup hash algorithm.")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Backup manifest entries must be a list.")
    paths: list[str] = []
    symlink_paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Every backup manifest entry must be an object.")
        relpath = entry.get("path")
        if not isinstance(relpath, str):
            raise ValueError("Every backup manifest entry requires a string path.")
        _validate_relpath(relpath)
        entry_type = entry.get("type")
        if entry_type not in {"directory", "file", "sqlite", "symlink"}:
            raise ValueError(f"Unsupported backup entry type for '{relpath}'.")
        if entry_type == "symlink":
            if not isinstance(entry.get("target"), str):
                raise ValueError(f"Backup symlink '{relpath}' requires a target.")
            symlink_paths.add(relpath)
        elif entry_type == "directory":
            _validate_integer_field(entry, "mode", relpath)
            _validate_integer_field(entry, "mtime_ns", relpath)
        else:
            _validate_integer_field(entry, "mode", relpath)
            _validate_integer_field(entry, "mtime_ns", relpath)
            _validate_integer_field(entry, "size", relpath)
            digest = entry.get("sha256")
            if not isinstance(digest, str) or len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise ValueError(f"Backup entry '{relpath}' has an invalid SHA-256 digest.")
        paths.append(relpath)
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ValueError("Backup manifest paths must be unique and sorted.")
    for relpath in paths:
        parts = PurePosixPath(relpath).parts
        for index in range(1, len(parts)):
            if PurePosixPath(*parts[:index]).as_posix() in symlink_paths:
                raise ValueError(f"Backup path traverses a symlink entry: {relpath}")


def _verify_payload(payload: Path, manifest: dict) -> None:
    actual_entries, _ = _scan_tree(payload, apply_exclusions=False)
    actual_by_path = {entry["path"]: entry for entry in actual_entries}
    expected_by_path = {entry["path"]: entry for entry in manifest["entries"]}
    if actual_by_path.keys() != expected_by_path.keys():
        missing = sorted(expected_by_path.keys() - actual_by_path.keys())
        extra = sorted(actual_by_path.keys() - expected_by_path.keys())
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if extra:
            details.append("unexpected: " + ", ".join(extra))
        raise ValueError("Backup payload does not match its manifest (" + "; ".join(details) + ").")

    for relpath, expected in expected_by_path.items():
        actual = actual_by_path[relpath]
        if actual["type"] != expected["type"]:
            raise ValueError(f"Backup entry type mismatch: {relpath}")
        path = _path_from_rel(payload, relpath)
        if expected["type"] == "symlink":
            if actual["target"] != expected["target"]:
                raise ValueError(f"Backup symlink target mismatch: {relpath}")
        elif expected["type"] in {"file", "sqlite"}:
            if path.stat().st_size != expected["size"]:
                raise ValueError(f"Backup file size mismatch: {relpath}")
            if _sha256_file(path) != expected["sha256"]:
                raise ValueError(f"Backup file checksum mismatch: {relpath}")
            if expected["type"] == "sqlite":
                _check_sqlite(path)


def _restore_entries(payload: Path, target: Path, entries: list[dict]) -> None:
    directories = [entry for entry in entries if entry["type"] == "directory"]
    for entry in sorted(directories, key=lambda item: (_path_depth(item["path"]), item["path"])):
        _path_from_rel(target, entry["path"]).mkdir(mode=0o700)

    for entry in entries:
        if entry["type"] in {"directory", "symlink"}:
            continue
        source = _safe_regular_path(payload, entry["path"])
        destination = _path_from_rel(target, entry["path"])
        _copy_regular_file(source, destination)
        if destination.stat().st_size != entry["size"] or _sha256_file(destination) != entry["sha256"]:
            raise ValueError(f"Restored file failed verification: {entry['path']}")
        _apply_file_metadata(destination, entry)

    for entry in entries:
        if entry["type"] == "symlink":
            _path_from_rel(target, entry["path"]).symlink_to(entry["target"])

    for entry in sorted(directories, key=lambda item: _path_depth(item["path"]), reverse=True):
        _apply_directory_metadata(_path_from_rel(target, entry["path"]), entry)


def _copy_regular_file(source: Path, destination: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(source, flags)
    try:
        with os.fdopen(descriptor, "rb") as input_stream, destination.open("xb") as output_stream:
            descriptor = -1
            shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)
            output_stream.flush()
            os.fsync(output_stream.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _copy_sqlite(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"Refusing to replace SQLite backup destination: {destination}")
    source_uri = source.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as source_connection:
        with sqlite3.connect(destination) as destination_connection:
            source_connection.backup(destination_connection)
            destination_connection.commit()
    _check_sqlite(destination)
    with destination.open("rb") as stream:
        os.fsync(stream.fileno())


def _check_sqlite(path: Path) -> None:
    uri = path.resolve().as_uri() + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            rows = [row[0] for row in connection.execute("PRAGMA quick_check")]
    except sqlite3.Error as exc:
        raise ValueError(f"SQLite verification failed for '{path}': {exc}") from exc
    if rows != ["ok"]:
        raise ValueError(f"SQLite verification failed for '{path}': {'; '.join(rows)}")


def _looks_like_sqlite(path: Path) -> bool:
    try:
        with path.open("rb") as stream:
            return stream.read(16) == b"SQLite format 3\x00"
    except OSError as exc:
        raise ValueError(f"Cannot inspect possible SQLite file '{path}': {exc}") from exc


def _safe_regular_path(root: Path, relpath: str) -> Path:
    path = root
    parts = PurePosixPath(relpath).parts
    for index, part in enumerate(parts):
        path = path / part
        if path.is_symlink():
            raise ValueError(f"Refusing to follow symlink in backup path: {relpath}")
        if index < len(parts) - 1 and not path.is_dir():
            raise ValueError(f"Backup path parent is not a directory: {relpath}")
    if not path.is_file():
        raise ValueError(f"Backup path is not a regular file: {relpath}")
    return path


def _path_from_rel(root: Path, relpath: str) -> Path:
    _validate_relpath(relpath)
    return root.joinpath(*PurePosixPath(relpath).parts)


def _validate_relpath(relpath: str) -> None:
    path = PurePosixPath(relpath)
    if (
        not relpath
        or path.is_absolute()
        or relpath != path.as_posix()
        or "\\" in relpath
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"Unsafe backup path: {relpath!r}")


def _validate_integer_field(entry: dict, field: str, relpath: str) -> None:
    value = entry.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"Backup entry '{relpath}' has an invalid {field} value.")


def _apply_file_metadata(path: Path, entry: dict) -> None:
    os.chmod(path, entry["mode"] & 0o777)
    os.utime(path, ns=(entry["mtime_ns"], entry["mtime_ns"]))


def _apply_directory_metadata(path: Path, entry: dict) -> None:
    os.chmod(path, entry["mode"] & 0o777)
    os.utime(path, ns=(entry["mtime_ns"], entry["mtime_ns"]))


def _write_bytes(path: Path, content: bytes, *, mode: int) -> None:
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(path, mode)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return digest.hexdigest()


def _read_manifest_checksum(path: Path) -> str:
    try:
        line = path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"Cannot read backup manifest checksum: {exc}") from exc
    parts = line.split()
    if (
        len(parts) != 2
        or parts[1] != MANIFEST_NAME
        or len(parts[0]) != 64
        or any(character not in "0123456789abcdef" for character in parts[0])
    ):
        raise ValueError("Invalid backup manifest checksum file.")
    return parts[0]


def _existing_directory(path: str | Path, *, label: str) -> Path:
    supplied = Path(path).expanduser()
    if supplied.is_symlink():
        raise ValueError(f"{label} must not be a symlink: {supplied}")
    resolved = supplied.resolve(strict=False)
    if not resolved.is_dir():
        raise ValueError(f"{label} is not a directory: {resolved}")
    return resolved


def _regular_child(parent: Path, name: str) -> Path:
    child = parent / name
    if child.is_symlink() or not child.is_file():
        raise ValueError(f"Backup snapshot is missing regular file: {name}")
    return child


def _path_depth(relpath: str) -> int:
    return len(PurePosixPath(relpath).parts)


def _fsync_tree(root: Path) -> None:
    directories = [root]
    for current, dir_names, _ in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in dir_names:
            path = current_path / name
            if not path.is_symlink():
                directories.append(path)
    for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        _fsync_directory(directory)


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        pass

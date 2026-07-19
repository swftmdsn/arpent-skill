"""Durable transactions for coordinated UTF-8 text-file mutations."""

from __future__ import annotations

import base64
import binascii
import ctypes
import errno
import hashlib
import json
import os
import tempfile


FORMAT = "arpent-file-transaction"
VERSION = 2
SUPPORTED_VERSIONS = {1, VERSION}
PHASES = {"prepared", "committed"}
_UNSUPPORTED_LINK_ERRNOS = {
    errno.EACCES,
    errno.EPERM,
    errno.EXDEV,
    getattr(errno, "ENOSYS", -1),
    getattr(errno, "ENOTSUP", -1),
    getattr(errno, "EOPNOTSUPP", -1),
}
_UNSUPPORTED_RENAME_ERRNOS = {
    errno.EINVAL,
    getattr(errno, "ENOSYS", -1),
    getattr(errno, "ENOTSUP", -1),
    getattr(errno, "EOPNOTSUPP", -1),
}


def snapshot_file(vault, relpath: str, *, expected_content=None) -> dict:
    """Capture a text file and the hashes allowed to be restored over it."""
    if expected_content is not None and not isinstance(expected_content, str):
        raise ValueError("expected file content must be text")
    expected_hash = _sha256_bytes(expected_content.encode("utf-8")) if expected_content is not None else None
    path = vault.safe_output_path(relpath)
    if not path.exists():
        return {
            "path": relpath,
            "existed": False,
            "content_base64": None,
            "original_sha256": None,
            "expected_sha256": expected_hash,
        }

    content = vault.safe_source_path(relpath).read_bytes()
    content.decode("utf-8")
    return {
        "path": relpath,
        "existed": True,
        "content_base64": base64.b64encode(content).decode("ascii"),
        "original_sha256": _sha256_bytes(content),
        "expected_sha256": expected_hash,
    }


def snapshot_files(vault, relpaths, *, expected_contents=None) -> list[dict]:
    expected_contents = expected_contents or {}
    return [
        snapshot_file(
            vault,
            relpath,
            expected_content=expected_contents.get(relpath),
        )
        for relpath in dict.fromkeys(relpaths)
    ]


def prepare(vault, journal_relpath: str, snapshots: list[dict], *, metadata=None) -> dict:
    """Durably write a versioned prepared journal."""
    metadata = metadata or {}
    if not isinstance(metadata, dict):
        raise ValueError("file transaction metadata must be a mapping")
    reserved = {"format", "version", "phase", "files"}
    if reserved.intersection(metadata):
        raise ValueError("file transaction metadata uses a reserved field")
    if vault.safe_output_path(journal_relpath).exists():
        raise ValueError("a previous file transaction must be recovered before continuing")

    journal = {
        "format": FORMAT,
        "version": VERSION,
        "phase": "prepared",
        "files": snapshots,
        **metadata,
    }
    _validate_journal(journal)
    vault.atomic_write_text(journal_relpath, json.dumps(journal) + "\n")
    return journal


def commit(vault, journal_relpath: str, journal: dict) -> None:
    """Mark a transaction committed, then durably remove its journal."""
    _validate_journal(journal)
    journal["format"] = FORMAT
    journal["phase"] = "committed"
    vault.atomic_write_text(journal_relpath, json.dumps(journal) + "\n")
    remove_journal(vault, journal_relpath)


def rollback(vault, journal_relpath: str, journal: dict, *, after_restore=None) -> None:
    """Restore every snapshot and remove the journal after optional compensation."""
    _validate_journal(journal)
    restore_files(vault, journal["files"], version=journal["version"])
    if after_restore is not None:
        after_restore(journal)
    remove_journal(vault, journal_relpath)


def recover(vault, journal_relpath: str, *, prepared_is_committed=None,
            after_restore=None):
    """Recover a prepared or committed current-format journal."""
    path = vault.safe_output_path(journal_relpath)
    if not path.exists():
        return None

    journal = read_journal(vault, journal_relpath)
    keep_changes = journal["phase"] == "committed"
    if not keep_changes and prepared_is_committed is not None:
        keep_changes = bool(prepared_is_committed(journal))
    if not keep_changes:
        restore_files(vault, journal["files"], version=journal["version"])
        if after_restore is not None:
            after_restore(journal)
    remove_journal(vault, journal_relpath)
    return journal


def read_journal(vault, journal_relpath: str) -> dict:
    journal = json.loads(
        vault.safe_source_path(journal_relpath).read_text(encoding="utf-8")
    )
    _validate_journal(journal)
    return journal


def restore_files(vault, snapshots: list[dict], *, version=None) -> None:
    """Restore snapshots only over content owned by their SHA-256 hashes."""
    if version is None:
        version = 2 if any("content_base64" in snapshot for snapshot in snapshots) else 1
    if version not in SUPPORTED_VERSIONS:
        raise ValueError("unsupported file transaction journal format or version")
    validated = [_validate_snapshot(snapshot, version) for snapshot in snapshots]
    for snapshot in validated:
        _assert_owned_current(vault, snapshot, version)

    # Recreate original files before removing paths created by the transaction.
    # A failed restore therefore keeps at least one side of an interrupted move.
    ordered = [
        *reversed([snapshot for snapshot in validated if snapshot["existed"]]),
        *reversed([snapshot for snapshot in validated if not snapshot["existed"]]),
    ]
    for snapshot in ordered:
        relpath = snapshot["path"]
        path = vault.safe_output_path(relpath)
        if snapshot["existed"]:
            content = _snapshot_content(snapshot, version)
            if path.exists():
                _assert_owned_current(vault, snapshot, version)
                _atomic_write_bytes(vault, relpath, content)
            else:
                try:
                    _atomic_create_bytes(vault, relpath, content)
                except FileExistsError as exc:
                    raise ValueError(
                        f"Transaction recovery refused to overwrite or remove unowned file '{relpath}'."
                    ) from exc
        elif path.exists():
            _assert_owned_current(vault, snapshot, version)
            path.unlink()
            vault.fsync_directory(path.parent)


def move_no_replace(source, destination) -> None:
    """Atomically rename without replacing a destination on supported platforms."""
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)
    libc = ctypes.CDLL(None, use_errno=True)

    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is not None:
        renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        renameat2.restype = ctypes.c_int
        if renameat2(-100, source_bytes, -100, destination_bytes, 1) == 0:
            return
        error = ctypes.get_errno()
        if error not in _UNSUPPORTED_RENAME_ERRNOS:
            raise OSError(error, os.strerror(error), os.fspath(destination))

    renamex_np = getattr(libc, "renamex_np", None)
    if renamex_np is not None:
        renamex_np.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        renamex_np.restype = ctypes.c_int
        if renamex_np(source_bytes, destination_bytes, 0x00000004) == 0:
            return
        error = ctypes.get_errno()
        if error not in _UNSUPPORTED_RENAME_ERRNOS:
            raise OSError(error, os.strerror(error), os.fspath(destination))

    raise OSError(
        errno.ENOTSUP,
        "atomic no-replace rename is not supported on this platform",
        os.fspath(destination),
    )


def remove_journal(vault, journal_relpath: str) -> None:
    """Remove a journal and fsync its directory entry."""
    path = vault.safe_output_path(journal_relpath)
    path.unlink(missing_ok=True)
    vault.fsync_directory(path.parent)


def _validate_journal(journal) -> None:
    if not isinstance(journal, dict):
        raise ValueError("invalid file transaction journal")
    if (
        journal.get("format") != FORMAT
        or type(journal.get("version")) is not int
        or journal["version"] not in SUPPORTED_VERSIONS
    ):
        raise ValueError("unsupported file transaction journal format or version")
    if journal.get("phase") not in PHASES:
        raise ValueError("invalid file transaction phase")
    if not isinstance(journal.get("files"), list):
        raise ValueError("invalid file transaction snapshots")
    for snapshot in journal["files"]:
        _validate_snapshot(snapshot, journal["version"])


def _validate_snapshot(snapshot, version: int) -> dict:
    if not isinstance(snapshot, dict):
        raise ValueError("invalid snapshot in file transaction journal")
    relpath = snapshot.get("path")
    if not isinstance(relpath, str) or not relpath:
        raise ValueError("invalid path in file transaction journal")
    existed = snapshot.get("existed")
    if not isinstance(existed, bool):
        raise ValueError("invalid existence flag in file transaction journal")
    original_hash = snapshot.get("original_sha256")
    expected_hash = snapshot.get("expected_sha256")
    if version == 1:
        content = snapshot.get("content")
        if existed:
            if not isinstance(content, str) or original_hash != _sha256_text(content):
                raise ValueError("invalid original content in file transaction journal")
        elif content is not None or original_hash is not None:
            raise ValueError("invalid absent file snapshot in file transaction journal")
    else:
        content = snapshot.get("content_base64")
        if existed:
            decoded = _decode_snapshot_content(content)
            if original_hash != _sha256_bytes(decoded):
                raise ValueError("invalid original content in file transaction journal")
        elif content is not None or original_hash is not None:
            raise ValueError("invalid absent file snapshot in file transaction journal")
    if expected_hash is not None and not _is_sha256(expected_hash):
        raise ValueError("invalid expected hash in file transaction journal")
    return snapshot


def _assert_owned_current(vault, snapshot: dict, version: int) -> None:
    relpath = snapshot["path"]
    path = vault.safe_output_path(relpath)
    if not path.exists():
        return
    content = vault.safe_source_path(relpath).read_bytes()
    actual_hashes = {_sha256_bytes(content)}
    if version == 1:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            universal_text = text.replace("\r\n", "\n").replace("\r", "\n")
            actual_hashes.add(_sha256_text(universal_text))
    allowed_hashes = {
        value
        for value in (
            snapshot.get("original_sha256"),
            snapshot.get("expected_sha256"),
        )
        if value is not None
    }
    if actual_hashes.isdisjoint(allowed_hashes):
        raise ValueError(
            f"Transaction recovery refused to overwrite or remove unowned file '{relpath}'."
        )


def _snapshot_content(snapshot: dict, version: int) -> bytes:
    if version == 1:
        return snapshot["content"].encode("utf-8")
    return _decode_snapshot_content(snapshot["content_base64"])


def _decode_snapshot_content(content) -> bytes:
    if not isinstance(content, str):
        raise ValueError("invalid original content in file transaction journal")
    try:
        decoded = base64.b64decode(content, validate=True)
        decoded.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise ValueError("invalid original content in file transaction journal") from exc
    if base64.b64encode(decoded).decode("ascii") != content:
        raise ValueError("invalid original content in file transaction journal")
    return decoded


def _atomic_write_bytes(vault, relpath: str, content: bytes) -> None:
    target = vault.safe_output_path(relpath)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    temporary = os.fsdecode(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        vault.fsync_directory(target.parent)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _atomic_create_bytes(vault, relpath: str, content: bytes) -> None:
    target = vault.safe_output_path(relpath)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    temporary = os.fsdecode(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, target)
        except OSError as exc:
            if exc.errno not in _UNSUPPORTED_LINK_ERRNOS:
                raise
            _copy_no_replace(temporary, target)
        vault.fsync_directory(target.parent)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _copy_no_replace(source, target) -> None:
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with open(source, "rb") as input_stream, os.fdopen(descriptor, "wb") as output_stream:
            descriptor = None
            for chunk in iter(lambda: input_stream.read(1024 * 1024), b""):
                output_stream.write(chunk)
            output_stream.flush()
            os.fsync(output_stream.fileno())
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        try:
            os.unlink(target)
        except FileNotFoundError:
            pass
        raise


def _sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _is_sha256(value) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)

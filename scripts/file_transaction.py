"""Durable transactions for coordinated UTF-8 text-file mutations."""

from __future__ import annotations

import hashlib
import json


FORMAT = "arpent-file-transaction"
VERSION = 1
PHASES = {"prepared", "committed"}


def snapshot_file(vault, relpath: str, *, expected_content=None) -> dict:
    """Capture a text file and the hashes allowed to be restored over it."""
    if expected_content is not None and not isinstance(expected_content, str):
        raise ValueError("expected file content must be text")
    expected_hash = _sha256(expected_content) if expected_content is not None else None
    path = vault.safe_output_path(relpath)
    if not path.exists():
        return {
            "path": relpath,
            "existed": False,
            "content": None,
            "original_sha256": None,
            "expected_sha256": expected_hash,
        }

    content = vault.safe_source_path(relpath).read_text(encoding="utf-8")
    return {
        "path": relpath,
        "existed": True,
        "content": content,
        "original_sha256": _sha256(content),
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
    journal["version"] = VERSION
    journal["phase"] = "committed"
    vault.atomic_write_text(journal_relpath, json.dumps(journal) + "\n")
    remove_journal(vault, journal_relpath)


def rollback(vault, journal_relpath: str, journal: dict, *, after_restore=None) -> None:
    """Restore every snapshot and remove the journal after optional compensation."""
    _validate_journal(journal)
    restore_files(vault, journal["files"])
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
        restore_files(vault, journal["files"])
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


def restore_files(vault, snapshots: list[dict]) -> None:
    """Restore snapshots only over content owned by their SHA-256 hashes."""
    validated = [_validate_snapshot(snapshot) for snapshot in snapshots]
    for snapshot in validated:
        relpath = snapshot["path"]
        path = vault.safe_output_path(relpath)
        if not path.exists():
            continue
        actual_hash = hashlib.sha256(
            vault.safe_source_path(relpath).read_bytes()
        ).hexdigest()
        allowed_hashes = {
            value
            for value in (
                snapshot.get("original_sha256"),
                snapshot.get("expected_sha256"),
            )
            if value is not None
        }
        if actual_hash not in allowed_hashes:
            raise ValueError(
                f"Transaction recovery refused to overwrite or remove unowned file '{relpath}'."
            )

    for snapshot in reversed(validated):
        relpath = snapshot["path"]
        path = vault.safe_output_path(relpath)
        if snapshot["existed"]:
            vault.atomic_write_text(relpath, snapshot["content"])
        elif path.exists():
            path.unlink()
            vault.fsync_directory(path.parent)


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
        or journal["version"] != VERSION
    ):
        raise ValueError("unsupported file transaction journal format or version")
    if journal.get("phase") not in PHASES:
        raise ValueError("invalid file transaction phase")
    if not isinstance(journal.get("files"), list):
        raise ValueError("invalid file transaction snapshots")
    for snapshot in journal["files"]:
        _validate_snapshot(snapshot)


def _validate_snapshot(snapshot) -> dict:
    if not isinstance(snapshot, dict):
        raise ValueError("invalid snapshot in file transaction journal")
    relpath = snapshot.get("path")
    if not isinstance(relpath, str) or not relpath:
        raise ValueError("invalid path in file transaction journal")
    existed = snapshot.get("existed")
    if not isinstance(existed, bool):
        raise ValueError("invalid existence flag in file transaction journal")
    content = snapshot.get("content")
    original_hash = snapshot.get("original_sha256")
    expected_hash = snapshot.get("expected_sha256")
    if existed:
        if not isinstance(content, str) or original_hash != _sha256(content):
            raise ValueError("invalid original content in file transaction journal")
    elif content is not None or original_hash is not None:
        raise ValueError("invalid absent file snapshot in file transaction journal")
    if expected_hash is not None and not _is_sha256(expected_hash):
        raise ValueError("invalid expected hash in file transaction journal")
    return snapshot


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _is_sha256(value) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)

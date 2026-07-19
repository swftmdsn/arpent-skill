"""Locate and safely install the host-neutral Arpent agent skill bundle."""

from __future__ import annotations

import errno
import hashlib
import os
import shutil
import stat
import uuid
from importlib import metadata
from pathlib import Path, PurePosixPath

from . import file_transaction


BUNDLE_DATA_SUFFIX = ("share", "arpent", "skill", "SKILL.md")
RESULT_FORMAT = "arpent-skill-install-result"
RESULT_VERSION = 1


def install_skill_bundle(destination: str | Path, *, replace=False) -> dict:
    """Install the complete packaged skill at one exact destination."""
    bundle_root = _bundle_root()
    files = _bundle_files(bundle_root)
    target = _safe_destination(destination)
    original_target_stat = _initial_target_stat(target, replace=replace)

    created_parents = []
    staging = None
    replaced_backup = None
    try:
        created_parents = _safe_create_parents(target.parent)
        _validate_parent_chain(target)
        if original_target_stat is None:
            _refuse_existing_target(target)
        else:
            _require_unchanged_replaceable_target(target, original_target_stat)

        staging = target.parent / f".{target.name}.arpent-skill-{uuid.uuid4().hex[:12]}"
        if _lstat(staging) is not None:
            raise ValueError(f"Skill installation staging collision: {staging}")
        staging.mkdir(mode=0o700)
        _write_bundle(staging, files)

        _validate_parent_chain(target)
        if original_target_stat is None:
            _refuse_existing_target(target, appeared=True)
        else:
            _require_unchanged_replaceable_target(target, original_target_stat)
            replaced_backup = target.parent / f".{target.name}.arpent-replaced-{uuid.uuid4().hex[:12]}"
            if _lstat(replaced_backup) is not None:
                raise ValueError(f"Skill replacement backup collision: {replaced_backup}")
            _publish_no_replace(target, replaced_backup)
        _publish_no_replace(staging, target)
        staging = None
        _fsync_directory(target.parent)
        if replaced_backup is not None:
            _remove_replaced_target(replaced_backup)
            replaced_backup = None
            _fsync_directory(target.parent)
    except BaseException:
        if staging is not None:
            _remove_staging(staging)
        if replaced_backup is not None and _lstat(target) is None:
            try:
                _publish_no_replace(replaced_backup, target)
            except OSError as restore_error:
                raise ValueError(
                    "Skill replacement failed; the original bundle remains at "
                    f"{replaced_backup}: {restore_error}"
                ) from restore_error
            replaced_backup = None
            _fsync_directory(target.parent)
        _remove_empty_parents(created_parents)
        raise

    public_files = [
        {key: entry[key] for key in ("path", "bytes", "sha256")}
        for entry in files
    ]
    return {
        "format": RESULT_FORMAT,
        "version": RESULT_VERSION,
        "destination": str(target),
        "file_count": len(public_files),
        "total_bytes": sum(entry["bytes"] for entry in public_files),
        "hash_algorithm": "sha256",
        "files": public_files,
    }


def _bundle_root() -> Path:
    checkout = Path(__file__).resolve().parent.parent
    if _looks_like_bundle(checkout):
        return checkout

    try:
        distribution = metadata.distribution("arpent")
    except metadata.PackageNotFoundError as exc:
        raise ValueError("Cannot locate the packaged Arpent skill bundle.") from exc
    for entry in distribution.files or ():
        parts = PurePosixPath(str(entry).replace("\\", "/")).parts
        if tuple(parts[-len(BUNDLE_DATA_SUFFIX):]) != BUNDLE_DATA_SUFFIX:
            continue
        candidate = Path(distribution.locate_file(entry)).parent
        if _looks_like_bundle(candidate):
            return candidate
    raise ValueError("The installed Arpent distribution is missing its skill bundle data.")


def _looks_like_bundle(root: Path) -> bool:
    skill = root / "SKILL.md"
    references = root / "references"
    return (
        skill.is_file()
        and not skill.is_symlink()
        and references.is_dir()
        and not references.is_symlink()
    )


def _bundle_files(root: Path) -> list[dict]:
    paths = [root / "SKILL.md"]
    references = root / "references"

    def walk(directory: Path) -> None:
        for entry in sorted(os.scandir(directory), key=lambda item: item.name):
            if entry.name == ".DS_Store":
                continue
            entry_stat = entry.stat(follow_symlinks=False)
            path = Path(entry.path)
            if stat.S_ISLNK(entry_stat.st_mode):
                raise ValueError(f"The Arpent skill bundle contains a symlink: {path}")
            if stat.S_ISDIR(entry_stat.st_mode):
                walk(path)
            elif stat.S_ISREG(entry_stat.st_mode):
                paths.append(path)
            else:
                raise ValueError(f"The Arpent skill bundle contains an unsafe entry: {path}")

    walk(references)
    result = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        _validate_bundle_path(relative)
        content = _read_regular_file(path)
        result.append({
            "path": relative,
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "content": content,
        })
    result.sort(key=lambda entry: entry["path"])
    if not result or result[0]["path"] != "SKILL.md":
        raise ValueError("The Arpent skill bundle is missing SKILL.md.")
    return result


def _safe_destination(value: str | Path) -> Path:
    raw = os.fspath(value)
    if not raw or "\x00" in raw or raw in {".", ".."}:
        raise ValueError("Skill destination is unsafe; provide an exact new directory path.")
    try:
        supplied = Path(raw).expanduser()
    except RuntimeError as exc:
        raise ValueError(f"Skill destination cannot be expanded: {raw}") from exc
    if ".." in supplied.parts:
        raise ValueError("Skill destination must not contain '..'.")
    target = supplied if supplied.is_absolute() else Path.cwd() / supplied
    if target == Path(target.anchor):
        raise ValueError("Skill destination cannot be a filesystem root.")
    return target


def _safe_create_parents(parent: Path) -> list[Path]:
    created = []
    for current in _path_components(parent):
        current_stat = _lstat(current)
        if current_stat is None:
            try:
                current.mkdir(mode=0o755)
            except FileExistsError:
                pass
            else:
                created.append(current)
            current_stat = _lstat(current)
        _require_regular_directory(current, current_stat)
    return created


def _validate_parent_chain(target: Path) -> None:
    for parent in _path_components(target.parent):
        _require_regular_directory(parent, _lstat(parent))


def _path_components(path: Path):
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        yield current


def _require_regular_directory(path: Path, path_stat) -> None:
    if path_stat is None:
        raise ValueError(f"Skill destination parent disappeared: {path}")
    if stat.S_ISLNK(path_stat.st_mode):
        # macOS exposes trusted system prefixes such as /var through root-owned links.
        if os.access(path.parent, os.W_OK) or not path.is_dir():
            raise ValueError(f"Refusing a symlinked skill destination parent: {path}")
        return
    if not stat.S_ISDIR(path_stat.st_mode):
        raise ValueError(f"Skill destination parent is not a directory: {path}")


def _refuse_existing_target(target: Path, *, appeared=False) -> None:
    target_stat = _lstat(target)
    if target_stat is None:
        return
    if stat.S_ISLNK(target_stat.st_mode):
        raise ValueError(f"Refusing a symlinked skill destination: {target}")
    if appeared:
        raise ValueError(f"Skill destination appeared during installation: {target}")
    raise ValueError(f"Skill destination must not already exist: {target}")


def _initial_target_stat(target: Path, *, replace: bool):
    target_stat = _lstat(target)
    if target_stat is None:
        return None
    if stat.S_ISLNK(target_stat.st_mode):
        raise ValueError(f"Refusing a symlinked skill destination: {target}")
    if not replace:
        raise ValueError(f"Skill destination must not already exist: {target}")
    if not stat.S_ISDIR(target_stat.st_mode):
        raise ValueError(f"Skill destination replacement requires a directory: {target}")
    return target_stat


def _require_unchanged_replaceable_target(target: Path, original_stat) -> None:
    current_stat = _lstat(target)
    if current_stat is None:
        raise ValueError(f"Skill destination disappeared during replacement: {target}")
    if stat.S_ISLNK(current_stat.st_mode):
        raise ValueError(f"Refusing a symlinked skill destination: {target}")
    if not stat.S_ISDIR(current_stat.st_mode):
        raise ValueError(f"Skill destination replacement requires a directory: {target}")
    if (current_stat.st_dev, current_stat.st_ino) != (original_stat.st_dev, original_stat.st_ino):
        raise ValueError(f"Skill destination changed during replacement: {target}")


def _write_bundle(staging: Path, files: list[dict]) -> None:
    directories = {PurePosixPath(entry["path"]).parent for entry in files}
    for relative in sorted(directories, key=lambda path: (len(path.parts), path.as_posix())):
        if relative == PurePosixPath("."):
            continue
        destination = staging.joinpath(*relative.parts)
        destination.mkdir(mode=0o755)
    for entry in files:
        destination = staging.joinpath(*PurePosixPath(entry["path"]).parts)
        with destination.open("xb") as stream:
            stream.write(entry["content"])
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(destination, 0o644)
        if hashlib.sha256(destination.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Installed skill file failed verification: {entry['path']}")
    os.chmod(staging, 0o755)


def _publish_no_replace(source: Path, destination: Path) -> None:
    try:
        if os.name == "nt":
            os.rename(source, destination)
        else:
            file_transaction.move_no_replace(source, destination)
    except OSError as exc:
        if exc.errno in {errno.EEXIST, errno.ENOTEMPTY} or _lstat(destination) is not None:
            raise ValueError(f"Skill destination appeared during installation: {destination}") from exc
        raise


def _read_regular_file(path: Path) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        path_stat = os.fstat(descriptor)
        if not stat.S_ISREG(path_stat.st_mode):
            raise ValueError(f"The Arpent skill bundle entry is not a regular file: {path}")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            return stream.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _validate_bundle_path(relative: str) -> None:
    path = PurePosixPath(relative)
    if (
        not relative
        or path.is_absolute()
        or relative != path.as_posix()
        or any(part in {"", ".", ".."} for part in path.parts)
        or (relative != "SKILL.md" and path.parts[0] != "references")
    ):
        raise ValueError(f"Unsafe Arpent skill bundle path: {relative!r}")


def _lstat(path: Path):
    try:
        return path.lstat()
    except FileNotFoundError:
        return None


def _remove_staging(path: Path) -> None:
    path_stat = _lstat(path)
    if path_stat is None:
        return
    if stat.S_ISLNK(path_stat.st_mode):
        path.unlink()
    elif stat.S_ISDIR(path_stat.st_mode):
        shutil.rmtree(path, ignore_errors=True)


def _remove_replaced_target(path: Path) -> None:
    path_stat = _lstat(path)
    if path_stat is None:
        return
    if not stat.S_ISDIR(path_stat.st_mode) or stat.S_ISLNK(path_stat.st_mode):
        raise ValueError(f"Refusing to remove an unsafe skill replacement backup: {path}")
    shutil.rmtree(path)


def _remove_empty_parents(paths: list[Path]) -> None:
    for path in reversed(paths):
        try:
            path.rmdir()
        except OSError:
            break


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        pass

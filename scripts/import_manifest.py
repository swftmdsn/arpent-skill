"""Read-only filesystem scanning and reviewable import manifests."""

from __future__ import annotations

import codecs
import hashlib
import json
import os
import re
import stat
import tempfile
import uuid
from collections import Counter
from pathlib import Path

from . import frontmatter
from . import init_structure


FORMAT = "arpent-import-plan"
VERSION = 1
ROLES = ("project", "area", "resource", "group", "inbox", "ignore")
FINAL_ROLES = {"project", "area", "resource", "inbox", "ignore"}
EXCLUDED_DIRECTORY_NAMES = {".git", ".venv", "__pycache__", "node_modules"}
EXCLUDED_FILE_NAMES = {".DS_Store", "Thumbs.db"}
PROJECT_CONTAINERS = {"projects", "project", "clients", "missions"}
AREA_CONTAINERS = {"areas", "area", "responsibilities", "responsabilites"}
RESOURCE_CONTAINERS = {
    "resources", "resource", "knowledge", "references", "reference",
    "library", "bibliotheque",
}
PROJECT_WORDS = {
    "project", "projet", "client", "launch", "lancement", "migration",
    "redesign", "refonte", "move", "demenagement",
}
AREA_WORDS = {
    "health", "sante", "finance", "finances", "family", "famille", "home",
    "maison", "career", "carriere", "admin", "sport",
}
RESOURCE_WORDS = {
    "books", "livres", "articles", "docs", "documentation", "research",
    "recherche", "templates", "modeles", "archive", "archives", "wiki",
}
PROJECT_FILE_SIGNALS = {
    "roadmap", "milestones", "deliverables", "brief", "todo", "tasks",
    "planning", "plan", "livrables",
}


def scan_source(source: Path, output: Path, *, overwrite: bool = False) -> dict:
    """Inventory one external tree without following symlinks or mutating it."""
    supplied = Path(source).expanduser()
    if supplied.is_symlink():
        raise ValueError(f"Refusing a symlinked import root: {supplied}")
    root = supplied.resolve()
    if _is_link_like(supplied) or not root.is_dir():
        raise ValueError(f"Import source is not a directory: {root}")
    supplied_output = Path(output).expanduser()
    if supplied_output.is_symlink():
        raise ValueError(f"Refusing a symlinked import output: {supplied_output}")
    plan_path = supplied_output.parent.resolve() / supplied_output.name
    if not plan_path.parent.is_dir():
        raise ValueError(f"Import plan parent does not exist: {plan_path.parent}")
    import_id = uuid.uuid4().hex[:16]
    inventory_path = plan_path.with_name(
        f"{plan_path.stem}.{import_id}.inventory.jsonl"
    )
    if _is_within(plan_path, root) or _is_within(inventory_path, root):
        raise ValueError("Import plan and inventory must be stored outside the source tree.")
    for path in (plan_path, inventory_path):
        if (path.exists() or path.is_symlink()) and not overwrite:
            raise ValueError(f"Refusing to replace existing import output: {path}")
        if path.is_symlink():
            raise ValueError(f"Refusing a symlinked import output: {path}")

    folder_stats: dict[str, dict] = {".": _empty_folder_stats()}
    skipped = Counter()
    count = 0
    total_bytes = 0
    temporary = _temporary_path(inventory_path)
    excluded_outputs = {plan_path, inventory_path, temporary}
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            for current, directory_names, file_names in os.walk(
                root, followlinks=False, onerror=_raise_walk_error,
            ):
                current_path = Path(current)
                folder_rel = _relative(root, current_path)
                stats = folder_stats.setdefault(folder_rel, _empty_folder_stats())
                kept_directories = []
                for name in sorted(directory_names):
                    child = current_path / name
                    if _is_link_like(child):
                        skipped["symlink"] += 1
                    elif name in EXCLUDED_DIRECTORY_NAMES:
                        skipped["excluded_directory"] += 1
                    else:
                        kept_directories.append(name)
                        child_rel = _relative(root, child)
                        folder_stats.setdefault(child_rel, _empty_folder_stats())
                directory_names[:] = kept_directories
                stats["child_directories"] = len(kept_directories)

                for name in sorted(file_names):
                    path = current_path / name
                    if path in excluded_outputs:
                        continue
                    if _is_link_like(path):
                        skipped["symlink"] += 1
                        continue
                    if name in EXCLUDED_FILE_NAMES:
                        skipped["excluded_file"] += 1
                        continue
                    if not path.is_file():
                        skipped["special"] += 1
                        continue
                    record = _scan_file(root, path)
                    stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
                    count += 1
                    total_bytes += record["size"]
                    stats["direct_files"] += 1
                    stats["descendant_files"] += 1
                    stats["descendant_bytes"] += record["size"]
                    stats[f"{record['kind']}_files"] += 1
                    if len(stats["sample_files"]) < 12:
                        stats["sample_files"].append(name)
                    for ancestor in _ancestor_folders(folder_rel):
                        ancestor_stats = folder_stats.setdefault(ancestor, _empty_folder_stats())
                        ancestor_stats["descendant_files"] += 1
                        ancestor_stats["descendant_bytes"] += record["size"]
                        ancestor_stats[f"{record['kind']}_files"] += 1
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, inventory_path)
    finally:
        temporary.unlink(missing_ok=True)

    folders = []
    for relpath in sorted((path for path in folder_stats if path != "."), key=_path_sort_key):
        stats = folder_stats[relpath]
        suggestion = classify_folder(relpath, stats)
        folders.append({
            "path": relpath,
            "parent": _parent_relpath(relpath),
            "depth": len(Path(relpath).parts),
            "stats": stats,
            "suggestion": suggestion,
            "decision": None,
        })

    plan = {
        "format": FORMAT,
        "version": VERSION,
        "import_id": import_id,
        "created_at": frontmatter.now_iso(),
        "source": {"root": str(root), "mode": "copy"},
        "inventory": {
            "path": inventory_path.name,
            "sha256": _hash_file(inventory_path),
            "files": count,
            "bytes": total_bytes,
            "skipped": dict(sorted(skipped.items())),
        },
        "defaults": {"root_files": "inbox", "conflict": "reject"},
        "folders": folders,
        "review": {"completed": not folders, "completed_at": None},
    }
    save_plan(plan_path, plan, overwrite=overwrite)
    return plan


def load_plan(path: Path) -> tuple[Path, dict]:
    supplied = Path(path).expanduser()
    if supplied.is_symlink():
        raise ValueError(f"Import plan is not a regular file: {supplied}")
    plan_path = supplied.parent.resolve() / supplied.name
    if not plan_path.is_file():
        raise ValueError(f"Import plan is not a regular file: {plan_path}")
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read import plan '{plan_path}': {exc}") from exc
    _validate_plan_shape(plan)
    return plan_path, plan


def save_plan(path: Path, plan: dict, *, overwrite: bool = True) -> None:
    _validate_plan_shape(plan)
    destination = Path(path)
    if destination.is_symlink():
        raise ValueError(f"Refusing a symlinked import plan: {destination}")
    if destination.exists() and not overwrite:
        raise ValueError(f"Refusing to replace existing import plan: {destination}")
    content = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    temporary = _temporary_path(destination)
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def refresh_suggestions(plan: dict) -> int:
    changed = 0
    for folder in plan["folders"]:
        suggestion = classify_folder(folder["path"], folder["stats"])
        if suggestion != folder.get("suggestion"):
            folder["suggestion"] = suggestion
            changed += 1
    return changed


def review_plan(plan: dict, *, accept_suggestions: bool = False,
                minimum_confidence: float = 0.0, input_fn=input,
                output_fn=print, assume_yes: bool = False) -> dict:
    """Review uncovered folder roots, interactively or by accepting suggestions."""
    by_path = {folder["path"]: folder for folder in plan["folders"]}
    accepted = 0
    unresolved = []
    for folder in sorted(plan["folders"], key=lambda item: _path_sort_key(item["path"])):
        inherited = resolve_folder_decision(folder["parent"], by_path)
        if inherited is not None and inherited["role"] != "group":
            continue
        decision = folder.get("decision")
        if decision is not None:
            continue
        suggestion = folder["suggestion"]
        if accept_suggestions:
            if suggestion["confidence"] < minimum_confidence:
                unresolved.append(folder["path"])
                continue
            folder["decision"] = _decision_for(
                suggestion["role"], Path(folder["path"]).name,
            )
            accepted += 1
            continue

        output_fn("")
        output_fn(f"Folder: {folder['path']}")
        stats = folder["stats"]
        output_fn(
            f"Files: {stats['descendant_files']} ({stats['text_files']} text, "
            f"{stats['binary_files']} binary)"
        )
        output_fn(
            f"Suggestion: {suggestion['role']} "
            f"({round(suggestion['confidence'] * 100)}%) - {'; '.join(suggestion['reasons'])}"
        )
        role = _prompt_role(input_fn, suggestion["role"])
        if role is None:
            unresolved.append(folder["path"])
            continue
        name = Path(folder["path"]).name
        if role in {"project", "area", "resource"}:
            entered = input_fn(f"Destination name [{name}]: ").strip()
            name = entered or name
        decision = _decision_for(role, name)
        if role == "project":
            area = input_fn("Contextual Area slug (optional): ").strip()
            decision["area"] = area or None
        folder["decision"] = decision
        accepted += 1

    unresolved = unresolved_folders(plan)
    complete = not unresolved
    if complete and not assume_yes and not accept_suggestions:
        answer = input_fn("Mark this review complete? [y/N]: ").strip().lower()
        complete = answer in {"y", "yes", "o", "oui"}
    plan["review"] = {
        "completed": complete,
        "completed_at": frontmatter.now_iso() if complete else None,
    }
    return {"accepted": accepted, "unresolved": unresolved, "completed": complete}


def validate_plan(plan_path: Path, plan: dict, *, vault=None,
                  verify_sources: bool = False) -> dict:
    """Validate plan decisions, inventory integrity, and optionally every source hash."""
    errors = []
    warnings = []
    inventory_path = inventory_path_for(plan_path, plan)
    if not inventory_path.is_file() or inventory_path.is_symlink():
        errors.append(f"inventory is not a regular file: {inventory_path}")
        record_count = 0
    elif _hash_file(inventory_path) != plan["inventory"]["sha256"]:
        errors.append("inventory SHA-256 does not match the plan")
        record_count = 0
    else:
        try:
            known_folders = {folder["path"] for folder in plan["folders"]}
            record_count = 0
            record_paths = set()
            duplicate_paths = set()
            unknown_folders = set()
            for record in iter_inventory(plan_path, plan):
                record_count += 1
                if record["path"] in record_paths:
                    duplicate_paths.add(record["path"])
                record_paths.add(record["path"])
                if record["folder"] != "." and record["folder"] not in known_folders:
                    unknown_folders.add(record["folder"])
            if duplicate_paths:
                errors.append(
                    "inventory contains duplicate paths: "
                    + ", ".join(sorted(duplicate_paths)[:20])
                )
            if unknown_folders:
                errors.append(
                    "inventory references unknown folders: "
                    + ", ".join(sorted(unknown_folders)[:20])
                )
        except ValueError as exc:
            errors.append(str(exc))
            record_count = 0

    unresolved = unresolved_folders(plan)
    if unresolved:
        errors.append(f"unresolved folder decisions: {', '.join(unresolved[:20])}")
    if not plan["review"].get("completed"):
        errors.append("review is not marked complete")
    if record_count != plan["inventory"]["files"]:
        errors.append(
            f"inventory count mismatch: expected {plan['inventory']['files']}, found {record_count}"
        )

    try:
        structure = structure_from_plan(plan)
        normalized = init_structure.validate_structure(structure)
        if vault is not None:
            init_structure.preflight_structure(vault.root, normalized)
    except (OSError, ValueError) as exc:
        errors.append(f"invalid declared destinations: {exc}")

    changed_sources = []
    root = None
    try:
        root = source_root(plan)
        if _is_within(plan_path, root) or _is_within(inventory_path, root):
            errors.append("plan and inventory must remain outside the source tree")
    except ValueError as exc:
        errors.append(str(exc))
    if verify_sources and record_count and root is not None:
        for record in iter_inventory(plan_path, plan):
            try:
                source = safe_source_file(root, record["path"])
                if _hash_file(source) != record["sha256"]:
                    changed_sources.append(record["path"])
            except (OSError, ValueError):
                changed_sources.append(record["path"])
        if changed_sources:
            errors.append(
                f"source files missing or changed: {', '.join(changed_sources[:20])}"
            )

    if not record_count and plan["inventory"]["files"] == 0:
        warnings.append("source inventory is empty")
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "files": record_count,
        "decision_sha256": decision_hash(plan),
    }


def summarize_plan(plan_path: Path, plan: dict) -> dict:
    by_path = {folder["path"]: folder for folder in plan["folders"]}
    roles = Counter()
    kinds = Counter()
    covered_files = 0
    for record in iter_inventory(plan_path, plan):
        decision = resolve_folder_decision(record["folder"], by_path)
        role = decision["role"] if decision is not None else plan["defaults"]["root_files"]
        roles[role] += 1
        kinds[record["kind"]] += 1
        if decision is not None or record["folder"] == ".":
            covered_files += 1
    return {
        "import_id": plan["import_id"],
        "source_root": plan["source"]["root"],
        "files": plan["inventory"]["files"],
        "bytes": plan["inventory"]["bytes"],
        "by_role": dict(sorted(roles.items())),
        "by_kind": dict(sorted(kinds.items())),
        "unresolved_folders": unresolved_folders(plan),
        "review_completed": bool(plan["review"].get("completed")),
        "decision_sha256": decision_hash(plan),
    }


def structure_from_plan(plan: dict) -> dict:
    areas = []
    resources = []
    projects = []
    seen = {"area": set(), "resource": set(), "project": set()}
    for folder in plan["folders"]:
        decision = folder.get("decision")
        if decision is None:
            continue
        if decision["role"] == "area":
            if decision["name"] not in seen["area"]:
                areas.append(decision["name"])
                seen["area"].add(decision["name"])
        elif decision["role"] == "resource":
            if decision["name"] not in seen["resource"]:
                resources.append(decision["name"])
                seen["resource"].add(decision["name"])
        elif decision["role"] == "project":
            project = {"name": decision["name"]}
            if decision.get("area"):
                project["area"] = decision["area"]
            key = (project["name"], project.get("area"))
            if key not in seen["project"]:
                projects.append(project)
                seen["project"].add(key)
    return {"areas": areas, "resources": resources, "projects": projects}


def normalized_structure(plan: dict) -> dict:
    return init_structure.validate_structure(structure_from_plan(plan))


def resolve_folder_decision(folder_path: str, by_path: dict[str, dict]):
    current = folder_path
    while current != ".":
        folder = by_path.get(current)
        if folder is not None and folder.get("decision") is not None:
            decision = folder["decision"]
            if decision["role"] != "group":
                return decision
        current = _parent_relpath(current)
    return None


def unresolved_folders(plan: dict) -> list[str]:
    by_path = {folder["path"]: folder for folder in plan["folders"]}
    unresolved = []
    for folder in sorted(plan["folders"], key=lambda item: _path_sort_key(item["path"])):
        inherited = resolve_folder_decision(folder["parent"], by_path)
        if inherited is not None:
            continue
        decision = folder.get("decision")
        if decision is None:
            unresolved.append(folder["path"])
    return unresolved


def iter_inventory(plan_path: Path, plan: dict):
    path = inventory_path_for(plan_path, plan)
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid inventory JSON at line {line_number}: {exc}") from exc
                _validate_inventory_record(record, line_number)
                yield record
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"cannot read import inventory: {exc}") from exc


def inventory_path_for(plan_path: Path, plan: dict) -> Path:
    name = plan["inventory"]["path"]
    candidate = Path(name)
    if candidate.is_absolute() or len(candidate.parts) != 1 or name in {".", ".."}:
        raise ValueError("inventory path must be a filename beside the plan")
    return Path(plan_path).parent / candidate


def source_root(plan: dict) -> Path:
    root = Path(plan["source"]["root"])
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"import source root is unavailable: {root}")
    return root.resolve()


def safe_source_file(root: Path, relpath: str) -> Path:
    relative = Path(relpath)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError(f"unsafe import source path: {relpath}")
    current = Path(root)
    for part in relative.parts:
        current = current / part
        if _is_link_like(current):
            raise ValueError(f"refusing symlinked import source: {relpath}")
    if not current.is_file():
        raise ValueError(f"import source is not a regular file: {relpath}")
    return current


def decision_hash(plan: dict) -> str:
    payload = {
        "format": plan["format"],
        "version": plan["version"],
        "import_id": plan["import_id"],
        "source": plan["source"],
        "inventory_sha256": plan["inventory"]["sha256"],
        "defaults": plan["defaults"],
        "decisions": [
            {"path": folder["path"], "decision": folder.get("decision")}
            for folder in plan["folders"]
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def classify_folder(relpath: str, stats: dict) -> dict:
    name = Path(relpath).name.lower()
    parent = Path(relpath).parent.name.lower()
    words = {word for word in re.split(r"[^a-z0-9]+", _ascii(name)) if word}
    sample_stems = {
        Path(filename).stem.lower()
        for filename in stats.get("sample_files", [])
    }
    if name in PROJECT_CONTAINERS | AREA_CONTAINERS | RESOURCE_CONTAINERS:
        return _suggestion("group", 0.98, "recognized organizational container")
    if parent in PROJECT_CONTAINERS:
        return _suggestion("project", 0.92, "child of a project container")
    if parent in AREA_CONTAINERS:
        return _suggestion("area", 0.92, "child of an Area container")
    if parent in RESOURCE_CONTAINERS:
        return _suggestion("resource", 0.92, "child of a Resource container")
    if words & PROJECT_WORDS or sample_stems & PROJECT_FILE_SIGNALS:
        return _suggestion("project", 0.82, "project-oriented name or working files")
    if words & AREA_WORDS:
        return _suggestion("area", 0.78, "ongoing-responsibility name")
    if words & RESOURCE_WORDS:
        return _suggestion("resource", 0.84, "reference-oriented name")
    files = stats.get("descendant_files", 0)
    binaries = stats.get("binary_files", 0)
    if files and binaries / files >= 0.6:
        return _suggestion("resource", 0.7, "mostly binary/reference material")
    if stats.get("child_directories", 0):
        return _suggestion("group", 0.55, "contains subfolders with no strong semantic signal")
    return _suggestion("resource", 0.42, "leaf folder with no strong project or Area signal")


def _scan_file(root: Path, path: Path) -> dict:
    digest = hashlib.sha256()
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    binary = False
    controls = 0
    characters = 0
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            if binary:
                continue
            try:
                text = decoder.decode(chunk, final=False)
            except UnicodeDecodeError:
                binary = True
                continue
            if "\x00" in text:
                binary = True
                continue
            controls += sum(
                ord(character) < 32 and character not in "\n\r\t\f\b"
                for character in text
            )
            characters += len(text)
    if not binary:
        try:
            tail = decoder.decode(b"", final=True)
        except UnicodeDecodeError:
            binary = True
        else:
            controls += sum(
                ord(character) < 32 and character not in "\n\r\t\f\b"
                for character in tail
            )
            characters += len(tail)
            binary = bool(characters) and controls / characters > 0.05
    stat = path.stat()
    relpath = path.relative_to(root).as_posix()
    return {
        "path": relpath,
        "folder": _parent_relpath(relpath),
        "name": path.name,
        "extension": path.suffix.lower(),
        "kind": "binary" if binary else "text",
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": digest.hexdigest(),
    }


def _validate_plan_shape(plan: dict) -> None:
    if not isinstance(plan, dict) or plan.get("format") != FORMAT or plan.get("version") != VERSION:
        raise ValueError("Unsupported or invalid Arpent import plan.")
    required = {"import_id", "created_at", "source", "inventory", "defaults", "folders", "review"}
    missing = required - set(plan)
    if missing:
        raise ValueError(f"Import plan is missing: {', '.join(sorted(missing))}")
    if not re.fullmatch(r"[a-f0-9]{16}", str(plan["import_id"])):
        raise ValueError("Import plan has an invalid import_id.")
    if not isinstance(plan["source"], dict) or set(plan["source"]) != {"root", "mode"}:
        raise ValueError("Import plan source must be an object with root and mode.")
    if plan["source"].get("mode") != "copy" or not isinstance(plan["source"].get("root"), str):
        raise ValueError("Import plan source must use copy mode and a root path.")
    inventory = plan["inventory"]
    if (
        not isinstance(inventory, dict)
        or type(inventory.get("files")) is not int
        or inventory["files"] < 0
        or type(inventory.get("bytes")) is not int
        or inventory["bytes"] < 0
        or not isinstance(inventory.get("path"), str)
        or not re.fullmatch(r"[a-f0-9]{64}", str(inventory.get("sha256")))
        or not isinstance(inventory.get("skipped"), dict)
    ):
        raise ValueError("Import plan has invalid inventory metadata.")
    if (
        not isinstance(plan["defaults"], dict)
        or set(plan["defaults"]) != {"root_files", "conflict"}
        or plan["defaults"].get("root_files") not in {"inbox", "ignore"}
        or plan["defaults"].get("conflict") != "reject"
    ):
        raise ValueError("Import plan has invalid defaults.")
    if (
        not isinstance(plan["review"], dict)
        or set(plan["review"]) != {"completed", "completed_at"}
        or type(plan["review"].get("completed")) is not bool
        or (
            plan["review"].get("completed_at") is not None
            and not isinstance(plan["review"].get("completed_at"), str)
        )
    ):
        raise ValueError("Import plan has invalid review metadata.")
    if not isinstance(plan["folders"], list):
        raise ValueError("Import plan folders must be a list.")
    seen = set()
    for folder in plan["folders"]:
        if not isinstance(folder, dict) or not isinstance(folder.get("path"), str):
            raise ValueError("Import plan has an invalid folder entry.")
        folder_path = Path(folder["path"])
        if folder_path.is_absolute() or not folder_path.parts or ".." in folder_path.parts:
            raise ValueError(f"Import plan has an unsafe folder path: {folder['path']}")
        if folder.get("parent") != _parent_relpath(folder["path"]):
            raise ValueError(f"Import folder has an invalid parent: {folder['path']}")
        if type(folder.get("depth")) is not int or folder["depth"] != len(folder_path.parts):
            raise ValueError(f"Import folder has an invalid depth: {folder['path']}")
        _validate_folder_stats(folder.get("stats"), folder["path"])
        suggestion = folder.get("suggestion")
        if (
            not isinstance(suggestion, dict)
            or set(suggestion) != {"role", "confidence", "reasons"}
            or suggestion.get("role") not in ROLES
            or type(suggestion.get("confidence")) not in {int, float}
            or isinstance(suggestion.get("confidence"), bool)
            or not 0 <= suggestion["confidence"] <= 1
            or not isinstance(suggestion.get("reasons"), list)
            or not all(isinstance(reason, str) for reason in suggestion["reasons"])
        ):
            raise ValueError(f"Import folder has an invalid suggestion: {folder['path']}")
        if folder["path"] in seen:
            raise ValueError(f"Duplicate import folder: {folder['path']}")
        seen.add(folder["path"])
        decision = folder.get("decision")
        if decision is not None:
            _validate_decision(decision)


def _validate_decision(decision: dict) -> None:
    if not isinstance(decision, dict) or decision.get("role") not in ROLES:
        raise ValueError("Import folder decision has an invalid role.")
    role = decision["role"]
    if role in {"project", "area", "resource"}:
        if not isinstance(decision.get("name"), str) or not decision["name"].strip():
            raise ValueError(f"Import {role} decision needs a destination name.")
    elif set(decision) != {"role"}:
        raise ValueError(f"Import {role} decision cannot contain destination metadata.")
    if role == "project" and set(decision) - {"role", "name", "area"}:
        raise ValueError("Import project decision has unsupported metadata.")
    if role in {"area", "resource"} and set(decision) != {"role", "name"}:
        raise ValueError(f"Import {role} decision has unsupported metadata.")


def _validate_inventory_record(record, line_number: int) -> None:
    required = {"path", "folder", "name", "extension", "kind", "size", "mtime_ns", "sha256"}
    if not isinstance(record, dict) or set(record) != required:
        raise ValueError(f"invalid inventory record at line {line_number}")
    for key in ("path", "folder", "name", "extension", "kind", "sha256"):
        if not isinstance(record[key], str):
            raise ValueError(f"invalid inventory {key} at line {line_number}")
    path = Path(record["path"])
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError(f"unsafe inventory path at line {line_number}")
    if record["kind"] not in {"text", "binary"}:
        raise ValueError(f"invalid inventory kind at line {line_number}")
    if record["folder"] != _parent_relpath(record["path"]):
        raise ValueError(f"invalid inventory folder at line {line_number}")
    if record["name"] != path.name or record["extension"] != path.suffix.lower():
        raise ValueError(f"invalid inventory filename metadata at line {line_number}")
    if type(record["size"]) is not int or record["size"] < 0:
        raise ValueError(f"invalid inventory size at line {line_number}")
    if type(record["mtime_ns"]) is not int or record["mtime_ns"] < 0:
        raise ValueError(f"invalid inventory timestamp at line {line_number}")
    if not re.fullmatch(r"[a-f0-9]{64}", str(record["sha256"])):
        raise ValueError(f"invalid inventory hash at line {line_number}")


def _decision_for(role: str, name: str) -> dict:
    if role not in ROLES:
        raise ValueError(f"Unknown import role: {role}")
    if role in {"project", "area", "resource"}:
        return {"role": role, "name": name}
    return {"role": role}


def _prompt_role(input_fn, default: str):
    aliases = {
        "p": "project", "project": "project",
        "a": "area", "area": "area",
        "r": "resource", "resource": "resource",
        "g": "group", "group": "group",
        "i": "inbox", "inbox": "inbox",
        "x": "ignore", "ignore": "ignore",
        "s": None, "skip": None,
    }
    prompt = "Role [p]roject/[a]rea/[r]esource/[g]roup/[i]nbox/[x]ignore/[s]kip "
    while True:
        raw = input_fn(f"{prompt}[{default}]: ").strip().lower()
        if not raw:
            return default
        if raw in aliases:
            return aliases[raw]
        print("Unknown role. Choose p, a, r, g, i, x, or s.")


def _suggestion(role: str, confidence: float, reason: str) -> dict:
    return {"role": role, "confidence": confidence, "reasons": [reason]}


def _empty_folder_stats() -> dict:
    return {
        "direct_files": 0,
        "descendant_files": 0,
        "descendant_bytes": 0,
        "text_files": 0,
        "binary_files": 0,
        "child_directories": 0,
        "sample_files": [],
    }


def _ancestor_folders(folder_rel: str):
    current = _parent_relpath(folder_rel)
    while current != ".":
        yield current
        current = _parent_relpath(current)
    if folder_rel != ".":
        yield "."


def _parent_relpath(relpath: str) -> str:
    parent = Path(relpath).parent.as_posix()
    return parent if parent not in {"", "."} else "."


def _relative(root: Path, path: Path) -> str:
    rel = path.relative_to(root).as_posix()
    return rel or "."


def _path_sort_key(path: str):
    return len(Path(path).parts), path


def _ascii(value: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _temporary_path(destination: Path) -> Path:
    descriptor, name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    os.close(descriptor)
    return Path(name)


def _validate_folder_stats(stats, path: str) -> None:
    expected = {
        "direct_files", "descendant_files", "descendant_bytes", "text_files",
        "binary_files", "child_directories", "sample_files",
    }
    if not isinstance(stats, dict) or set(stats) != expected:
        raise ValueError(f"Import folder has invalid stats: {path}")
    for key in expected - {"sample_files"}:
        if type(stats[key]) is not int or stats[key] < 0:
            raise ValueError(f"Import folder has invalid {key}: {path}")
    if not isinstance(stats["sample_files"], list) or not all(
        isinstance(name, str) for name in stats["sample_files"]
    ):
        raise ValueError(f"Import folder has invalid sample files: {path}")


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _is_link_like(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def _raise_walk_error(error: OSError) -> None:
    raise error

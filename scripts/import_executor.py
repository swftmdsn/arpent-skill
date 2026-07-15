"""Preview and resumably apply reviewed external import plans."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from collections import Counter
from pathlib import Path

from . import frontmatter as fmlib
from . import import_manifest
from . import init_structure
from . import notes
from . import operations as operations_mod
from . import routing


STATE_ROOT = "06_indexes/imports"


def apply_import(vault, plan_path: Path, plan: dict, *, dry_run: bool = False,
                 stop_on_error: bool = False, include_previews: bool = False,
                 expected_execution_hash=None) -> dict:
    """Apply a reviewed plan one source at a time, preserving external sources."""
    validation = import_manifest.validate_plan(plan_path, plan, vault=vault)
    if not validation["valid"]:
        raise ValueError("Import plan is invalid: " + "; ".join(validation["errors"]))
    decision_sha256 = validation["decision_sha256"]
    plan_hash, routing_sha256 = _execution_hash(vault, decision_sha256)
    if expected_execution_hash is not None and expected_execution_hash != plan_hash:
        raise ValueError("Import execution no longer matches --plan-hash; review a fresh dry run.")
    by_path = {folder["path"]: folder for folder in plan["folders"]}
    normalized = import_manifest.normalized_structure(plan)
    slug_maps = _slug_maps(plan, normalized)
    state_rel = f"{STATE_ROOT}/{plan['import_id']}/state.jsonl"
    report_rel = f"{STATE_ROOT}/{plan['import_id']}/report.json"
    root = import_manifest.source_root(plan)
    if _paths_overlap(root, vault.root):
        raise ValueError("Import source and target vault must not contain one another.")
    lock_name = f"import-{plan['import_id']}"
    if dry_run:
        structure_result = _preview_structure(vault, normalized)
        prior = _read_state(vault, state_rel)
        _validate_state_hash(prior, plan_hash)
        report = _process_items(
            vault, plan_path, plan, plan_hash, by_path, slug_maps, root,
            state_rel=state_rel, prior=prior, dry_run=True,
            stop_on_error=stop_on_error, include_previews=include_previews,
        )
        report["decision_sha256"] = decision_sha256
        report["routing_sha256"] = routing_sha256
        report["structure"] = structure_result
        report["counts"]["structure_planned"] = _structure_count(
            structure_result, "planned",
        )
        return report

    with vault.exclusive_lock(lock_name):
        _repair_state_tail(vault, state_rel)
        prior = _read_state(vault, state_rel)
        _validate_state_hash(prior, plan_hash)
        with vault.exclusive_lock("mutations"):
            notes.recover_ingest_transaction(vault)
            structure_result = init_structure.apply_structure(vault, normalized)
            report = _process_items(
                vault, plan_path, plan, plan_hash, by_path, slug_maps, root,
                state_rel=state_rel, prior=prior, dry_run=False,
                stop_on_error=stop_on_error, include_previews=False,
                existing_ids=vault.existing_ids(),
            )
            report["decision_sha256"] = decision_sha256
            report["routing_sha256"] = routing_sha256
            report["structure"] = structure_result
            report["counts"]["structure_created"] = _structure_count(
                structure_result, "created",
            )
            vault.atomic_write_text(
                report_rel,
                json.dumps(report, indent=2, sort_keys=True) + "\n",
            )
            return report


def _process_items(vault, plan_path, plan, plan_hash, by_path, slug_maps, root, *,
                   state_rel, prior, dry_run, stop_on_error, include_previews,
                   existing_ids=None):
    counts = Counter()
    failures = []
    previews = []
    planned_outputs = {}
    for record in import_manifest.iter_inventory(plan_path, plan):
        previous = prior.get(record["path"])
        if previous and previous.get("status") == "ignored":
            counts["already_complete"] += 1
            continue
        decision_path, decision = _mapping_for(record["folder"], by_path)
        role = decision["role"] if decision is not None else plan["defaults"]["root_files"]
        if role == "ignore":
            counts["ignored"] += 1
            if not dry_run:
                _append_state(vault, state_rel, {
                    "path": record["path"],
                    "source_sha256": record["sha256"],
                    "plan_sha256": plan_hash,
                    "status": "ignored",
                    "timestamp": fmlib.now_iso(),
                })
            continue
        try:
            item = _planned_item(vault, plan, record, decision_path, decision, slug_maps)
            stale_previous = False
            duplicate = []
            for output in (item["destination_path"], item.get("attachment_path")):
                if output and output in planned_outputs:
                    duplicate.append(f"{output} (also from {planned_outputs[output]})")
                elif output:
                    planned_outputs[output] = record["path"]
            if duplicate:
                item["collision"] = True
                item["collision_reason"] = "duplicate planned output: " + ", ".join(duplicate)
            if previous and previous.get("status") == "applied":
                if _state_output_complete(vault, previous):
                    counts["already_complete"] += 1
                    continue
                counts["stale_state"] += 1
                stale_previous = True
            if dry_run:
                counts["planned"] += 1
                if item["collision"]:
                    counts["collisions"] += 1
                if include_previews:
                    previews.append(item)
                continue
            result = None if stale_previous else _completed_result(vault, plan, record, item)
            if result is None and item["collision"]:
                if stale_previous:
                    raise ValueError(
                        "Recorded import output changed; inspect it and resolve the collision before retrying."
                    )
                raise ValueError(item.get("collision_reason") or "Import destination already exists.")
            if result is None:
                result = _apply_item(
                    vault, root, plan, record, item, existing_ids=existing_ids,
                )
        except (OSError, UnicodeDecodeError, RuntimeError, ValueError) as exc:
            counts["failed"] += 1
            failures.append({"path": record["path"], "error": str(exc)})
            if not dry_run:
                _append_state(vault, state_rel, {
                    "path": record["path"],
                    "source_sha256": record["sha256"],
                    "plan_sha256": plan_hash,
                    "status": "failed",
                    "error": str(exc),
                    "timestamp": fmlib.now_iso(),
                })
                try:
                    notes.recover_ingest_transaction(vault)
                    if existing_ids is not None:
                        existing_ids.clear()
                        existing_ids.update(vault.existing_ids())
                except (OSError, RuntimeError, ValueError) as recovery_exc:
                    failures.append({
                        "path": record["path"],
                        "error": f"import recovery failed: {recovery_exc}",
                    })
                    break
            if stop_on_error:
                break
            continue
        counts["applied"] += 1
        destination_sha256 = _hash_file(vault.safe_source_path(result["destination_path"]))
        retained_source = (
            result.get("source_path")
            if record["kind"] == "binary" and result.get("attachment_path") is None
            else None
        )
        _append_state(vault, state_rel, {
            "path": record["path"],
            "source_sha256": record["sha256"],
            "plan_sha256": plan_hash,
            "status": "applied",
            "destination_path": result["destination_path"],
            "destination_sha256": destination_sha256,
            "attachment_path": result.get("attachment_path"),
            "retained_source_path": retained_source,
            "timestamp": fmlib.now_iso(),
        })

    return {
        "format": "arpent-import-report",
        "version": 1,
        "import_id": plan["import_id"],
        "plan_sha256": plan_hash,
        "dry_run": dry_run,
        "counts": dict(sorted(counts.items())),
        "failures": failures,
        "previews": previews,
        "completed_at": fmlib.now_iso(),
    }


def import_status(vault, plan: dict) -> dict:
    state_rel = f"{STATE_ROOT}/{plan['import_id']}/state.jsonl"
    latest = _read_state(vault, state_rel)
    execution_sha256, _ = _execution_hash(vault, import_manifest.decision_hash(plan))
    _validate_state_hash(latest, execution_sha256)
    counts = Counter()
    for event in latest.values():
        if event["status"] == "applied" and not _state_output_complete(vault, event):
            counts["missing_or_changed"] += 1
        else:
            counts[event["status"]] += 1
    complete = counts["applied"] + counts["ignored"]
    return {
        "import_id": plan["import_id"],
        "total": plan["inventory"]["files"],
        "complete": complete,
        "remaining": max(0, plan["inventory"]["files"] - complete),
        "by_status": dict(sorted(counts.items())),
        "execution_sha256": execution_sha256,
    }


def _planned_item(vault, plan: dict, record: dict, decision_path, decision,
                  slug_maps: dict) -> dict:
    role = decision["role"] if decision is not None else "inbox"
    mapping_key = (role, decision.get("name")) if decision is not None else None
    slug = slug_maps.get(mapping_key)
    project = slug if role == "project" else None
    area = slug if role == "area" else None
    resource = slug if role == "resource" else None
    if role == "project" and decision.get("area"):
        area = _normalized_project_area(slug, slug_maps)
    title = _item_title(record, decision_path, role)
    note_type = "reference" if record["kind"] == "binary" else "note"
    proposed_projects = {
        value for (kind, _), value in slug_maps.items() if kind == "project"
    }
    proposed_areas = {
        value for (kind, _), value in slug_maps.items() if kind == "area"
    }
    proposed_resources = {
        value for (kind, _), value in slug_maps.items() if kind == "resource"
    }
    operations_path = vault.operations_path()
    safe_operations_path = None
    if operations_path.exists() or operations_path.is_symlink():
        safe_operations_path = vault.safe_source_path(
            operations_path.relative_to(vault.root).as_posix()
        )
    route = routing.route(
        {
            "title": title,
            "type": note_type,
            "status": "inbox",
            "project": project,
            "area": area,
            "resource": resource,
            "source": "imported",
            "author": "imported",
        },
        project_slugs=set(vault.project_slugs()) | proposed_projects,
        area_slugs=set(vault.area_slugs()) | proposed_areas,
        resource_slugs=set(vault.resource_slugs()) | proposed_resources,
        operations_path=safe_operations_path,
    )
    if project:
        home = f"01_projects/{project}"
    elif resource:
        home = f"03_resources/{resource}"
    elif area:
        folder = routing.resolve_area_folder(
            area, set(vault.area_slugs()) | proposed_areas,
        ) or area
        home = f"02_areas/{folder}"
    else:
        home = "00_inbox"
    destination = route.relpath
    attachment = None
    if record["kind"] == "binary" and role != "inbox":
        attachment = f"{home}/attachments/{routing.slugify(title)}{record['extension']}"
    collision = any(
        path is not None and ((vault.root / path).exists() or (vault.root / path).is_symlink())
        for path in (destination, attachment)
    )
    return {
        "source_path": record["path"],
        "kind": record["kind"],
        "role": role,
        "title": title,
        "type": note_type,
        "project": project,
        "area": area,
        "resource": resource,
        "destination_path": destination,
        "attachment_path": attachment,
        "collision": collision,
        "collision_reason": "Import destination already exists." if collision else None,
        "routing_reason": route.reason,
    }


def _apply_item(vault, root: Path, plan: dict, record: dict, item: dict, *,
                existing_ids=None) -> dict:
    source = import_manifest.safe_source_file(root, record["path"])
    if _hash_file(source) != record["sha256"]:
        raise ValueError("Source changed after scan; run a fresh scan.")
    stage_rel = _stage_relpath(plan["import_id"], record, item)
    _copy_to_stage(vault, source, stage_rel, record["sha256"])
    ingest_plan = notes.plan_ingest(
        vault,
        stage_rel,
        title=item["title"],
        ntype=item["type"],
        project=item["project"],
        area=item["area"],
        resource=item["resource"],
        source="imported",
        author="imported",
        link=(f"import:{plan['import_id']}:{record['path']}" if record["kind"] == "text" else None),
        chosen_location=(
            f"Imported from {record['path']} through reviewed import {plan['import_id']}."
        ),
        tags=["imported"],
        attachment=record["kind"] == "binary",
        source_hash=record["sha256"],
        allow_structured_source=True,
        existing_ids=existing_ids,
    )
    return notes.apply_ingest(vault, ingest_plan, existing_ids=existing_ids)


def _completed_result(vault, plan: dict, record: dict, item: dict):
    """Recognize an item committed before its import-state event was appended."""
    destination = vault.root / item["destination_path"]
    if destination.is_symlink() or not destination.is_file():
        return None
    try:
        metadata, _ = fmlib.read_note(vault.safe_source_path(item["destination_path"]))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    expected_reason = f"Imported from {record['path']} through reviewed import {plan['import_id']}."
    if metadata.get("chosen_location") != expected_reason:
        return None
    attachment = item.get("attachment_path")
    if attachment:
        attachment_path = vault.root / attachment
        if attachment_path.is_symlink() or not attachment_path.is_file():
            return None
        if _hash_file(attachment_path) != record["sha256"]:
            return None
    return {
        "source_path": _stage_relpath(plan["import_id"], record, item),
        "destination_path": item["destination_path"],
        "attachment_path": attachment,
    }


def _copy_to_stage(vault, source: Path, stage_rel: str, expected_hash: str) -> None:
    destination = vault.safe_output_path(stage_rel)
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise ValueError(f"Unsafe import staging destination: {stage_rel}")
        if _hash_file(destination) != expected_hash:
            raise ValueError(f"Import staging collision: {stage_rel}")
        return
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError as exc:
            raise ValueError(f"Import staging collision: {stage_rel}") from exc
        vault.fsync_directory(destination.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _stage_relpath(import_id: str, record: dict, item: dict) -> str:
    source_path = Path(record["path"])
    if record["kind"] == "binary" and item["role"] != "inbox":
        filename = f"{routing.slugify(item['title'])}{record['extension']}"
        source_path = source_path.with_name(filename)
    return (Path("00_inbox") / "captures" / f".arpent-import-{import_id}" / source_path).as_posix()


def _mapping_for(folder_path: str, by_path: dict[str, dict]):
    current = folder_path
    while current != ".":
        folder = by_path.get(current)
        if folder is not None and folder.get("decision") is not None:
            decision = folder["decision"]
            if decision["role"] != "group":
                return current, decision
        current = Path(current).parent.as_posix()
        if current in {"", "."}:
            current = "."
    return ".", None


def _item_title(record: dict, decision_path: str, role: str) -> str:
    source = Path(record["path"])
    if role == "inbox" or decision_path == ".":
        relative = source
    else:
        relative = source.relative_to(Path(decision_path))
    without_suffix = relative.with_suffix("")
    return " - ".join(without_suffix.parts)


def _slug_maps(plan: dict, normalized: dict) -> dict:
    raw = import_manifest.structure_from_plan(plan)
    result = {}
    for role, section in (("area", "areas"), ("resource", "resources")):
        for name, item in zip(raw[section], normalized[section]):
            result[(role, name)] = item["slug"]
    for value, item in zip(raw["projects"], normalized["projects"]):
        name = value["name"] if isinstance(value, dict) else value
        result[("project", name)] = item["slug"]
        result[("project_area", item["slug"])] = item["area"]
    return result


def _normalized_project_area(project_slug: str, slug_maps: dict):
    return slug_maps.get(("project_area", project_slug))


def _read_state(vault, relpath: str) -> dict:
    path = vault.root / relpath
    if not path.exists() and not path.is_symlink():
        return {}
    source = vault.safe_source_path(relpath)
    latest = {}
    try:
        with source.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    if not line.endswith("\n"):
                        break
                    raise
                _validate_state_event(event, line_number)
                latest[event["path"]] = event
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read import state: {exc}") from exc
    return latest


def _append_state(vault, relpath: str, event: dict) -> None:
    path = vault.safe_output_path(relpath)
    existed = path.exists()
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    if not existed:
        vault.fsync_directory(path.parent)


def _repair_state_tail(vault, relpath: str) -> None:
    path = vault.root / relpath
    if not path.exists() and not path.is_symlink():
        return
    source = vault.safe_source_path(relpath)
    with source.open("r+b") as stream:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        if size == 0:
            return
        stream.seek(-1, os.SEEK_END)
        if stream.read(1) == b"\n":
            return
        position = size
        truncate_at = 0
        while position > 0:
            chunk_size = min(8192, position)
            position -= chunk_size
            stream.seek(position)
            chunk = stream.read(chunk_size)
            newline = chunk.rfind(b"\n")
            if newline >= 0:
                truncate_at = position + newline + 1
                break
        stream.truncate(truncate_at)
        stream.flush()
        os.fsync(stream.fileno())
    vault.fsync_directory(source.parent)


def _validate_state_hash(events: dict, expected_hash: str) -> None:
    if any(event["plan_sha256"] != expected_hash for event in events.values()):
        raise ValueError(
            "Import decisions or routing changed after application started; create a new scan plan."
        )


def _validate_state_event(event, line_number: int) -> None:
    common = {"path", "source_sha256", "plan_sha256", "status", "timestamp"}
    if not isinstance(event, dict) or not common.issubset(event):
        raise ValueError(f"invalid import state event at line {line_number}")
    if not isinstance(event["path"], str):
        raise ValueError(f"invalid import state event at line {line_number}")
    source_path = Path(event["path"])
    if (
        source_path.is_absolute()
        or not source_path.parts
        or ".." in source_path.parts
        or not re.fullmatch(r"[a-f0-9]{64}", str(event["source_sha256"]))
        or not re.fullmatch(r"[a-f0-9]{64}", str(event["plan_sha256"]))
        or not isinstance(event["timestamp"], str)
    ):
        raise ValueError(f"invalid import state event at line {line_number}")
    status = event["status"]
    if status == "ignored":
        expected = common
    elif status == "failed":
        expected = common | {"error"}
        if not isinstance(event.get("error"), str):
            raise ValueError(f"invalid import state event at line {line_number}")
    elif status == "applied":
        expected = common | {
            "destination_path", "destination_sha256", "attachment_path",
            "retained_source_path",
        }
        if (
            not isinstance(event.get("destination_path"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", str(event.get("destination_sha256")))
            or (
            event.get("attachment_path") is not None
            and not isinstance(event.get("attachment_path"), str)
            )
            or (
                event.get("retained_source_path") is not None
                and not isinstance(event.get("retained_source_path"), str)
            )
        ):
            raise ValueError(f"invalid import state event at line {line_number}")
    else:
        raise ValueError(f"invalid import state event at line {line_number}")
    if set(event) != expected:
        raise ValueError(f"invalid import state event at line {line_number}")


def _execution_hash(vault, decision_sha256: str) -> tuple[str, str]:
    operations_path = vault.operations_path()
    safe_operations_path = None
    if operations_path.exists() or operations_path.is_symlink():
        safe_operations_path = vault.safe_source_path(
            operations_path.relative_to(vault.root).as_posix()
        )
    contract = operations_mod.routing_contract(safe_operations_path)
    encoded_contract = json.dumps(
        contract, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    routing_sha256 = hashlib.sha256(encoded_contract).hexdigest()
    encoded_execution = json.dumps(
        {
            "decision_sha256": decision_sha256,
            "routing_sha256": routing_sha256,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded_execution).hexdigest(), routing_sha256


def _state_output_complete(vault, event: dict) -> bool:
    try:
        destination = vault.safe_source_path(event["destination_path"])
        if _hash_file(destination) != event["destination_sha256"]:
            return False
        attachment = event.get("attachment_path")
        if attachment and _hash_file(vault.safe_source_path(attachment)) != event["source_sha256"]:
            return False
        retained = event.get("retained_source_path")
        if retained and _hash_file(vault.safe_source_path(retained)) != event["source_sha256"]:
            return False
    except (OSError, ValueError):
        return False
    return True


def _preview_structure(vault, normalized: dict) -> dict:
    result = {
        "areas": {"planned": [], "existing": []},
        "resources": {"planned": [], "existing": []},
        "projects": {"planned": [], "existing": []},
    }
    for section, bucket in (("areas", "02_areas"), ("resources", "03_resources")):
        for item in normalized[section]:
            destination = vault.root / bucket / item["slug"]
            key = "existing" if destination.is_dir() and not destination.is_symlink() else "planned"
            result[section][key].append(item["slug"])
    for item in normalized["projects"]:
        destination = vault.root / "01_projects" / item["slug"]
        key = "existing" if destination.is_dir() and not destination.is_symlink() else "planned"
        result["projects"][key].append(item["slug"])
    return result


def _structure_count(result: dict, key: str) -> int:
    return sum(len(section.get(key, [])) for section in result.values())


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _paths_overlap(first: Path, second: Path) -> bool:
    first = first.resolve()
    second = second.resolve()
    try:
        first.relative_to(second)
        return True
    except ValueError:
        pass
    try:
        second.relative_to(first)
        return True
    except ValueError:
        return False

"""
notes.py - operations on individual notes.
"""

from __future__ import annotations

import copy
import codecs
import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from . import file_transaction
from . import frontmatter as fmlib
from . import routing
from .vault import Vault

AGENT_SUBJECTIVE_FIELDS = ("appreciated", "importance")
ARCHIVE_FRONTMATTER_FIELDS = {"archived_at", "archived_from"}
EFFORT_CADENCES = ("heavylift", "slowburn")
EFFORT_LEVELS = ("low", "medium", "high")
EXTRACTABLE_TYPES = tuple(ntype for ntype in routing.TYPES if ntype != "fleeting")
TRANSACTION_RELPATH = "06_indexes/logs/note-transaction.json"
INGEST_TRANSACTION_RELPATH = "06_indexes/logs/note-ingest-transaction.json"


def _blank_frontmatter() -> dict:
    ts = fmlib.now_note_timestamp()
    return {
        "title": None, "id": None, "created": ts, "modified": ts,
        "description": None, "type": "note",
        "project": None, "area": None, "resource": None,
        "status": "inbox", "effort_cadence": None, "effort_level": None,
        "tags": [], "chosen_location": None,
        "source": "manual", "link": None, "author": "user",
        "depth": None, "appreciated": None, "importance": None, "pinned": False,
        "expires_at": None,
        "related": [], "relations": [], "parent": None,
        "observations": [], "extracted_to": [],
    }


def build_frontmatter(vault: Vault, *, title, ntype, status=None, project=None,
                      area=None, resource=None, tags=None, source="manual",
                       author="user", description=None, link=None,
                       chosen_location=None, relations=None,
                       effort_cadence=None, effort_level=None, depth=None,
                       existing_ids=None) -> dict:
    if ntype not in routing.TYPES:
        raise ValueError(f"unknown type '{ntype}'. Valid: {', '.join(routing.TYPES)}")
    if status and status not in routing.STATUSES:
        raise ValueError(f"unknown status '{status}'. Valid: {', '.join(routing.STATUSES)}")
    if source not in routing.SOURCES:
        raise ValueError(f"unknown source '{source}'. Valid: {', '.join(routing.SOURCES)}")
    if author not in routing.AUTHORS:
        raise ValueError(f"unknown author '{author}'. Valid: {', '.join(routing.AUTHORS)}")

    fm = _blank_frontmatter()
    fm["id"] = routing.new_id(
        ntype,
        vault.existing_ids() if existing_ids is None else existing_ids,
    )
    fm["title"] = routing.slugify(title)
    fm["description"] = _useful_description(fm["title"], description)
    fm["type"] = ntype
    fm["status"] = status or routing.DEFAULT_STATUS.get(ntype, "inbox")
    fm["effort_cadence"] = effort_cadence
    fm["effort_level"] = effort_level
    fm["project"] = project
    fm["area"] = area
    fm["resource"] = resource
    fm["tags"] = tags or []
    fm["source"] = source
    fm["author"] = author
    fm["link"] = link
    fm["chosen_location"] = chosen_location
    fm["relations"] = relations or []
    fm["depth"] = depth
    validate_frontmatter_values(fm)
    return fm


def frontmatter_warnings(fm: dict) -> list[str]:
    """Return non-fatal frontmatter coherence warnings."""
    source = fm.get("source")
    link = fm.get("link")
    warnings = []
    if source == "manual" and link:
        warnings.append("source manual should normally have link: null")
    elif source == "captured" and not _external_url(link):
        warnings.append("source captured requires an http(s) URL in link")
    elif source == "imported" and not link:
        warnings.append("source imported requires a URL or external identifier in link")
    elif source == "derived" and link:
        warnings.append("source derived should normally have link: null")
    return warnings


def _external_url(value) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def route_for(vault: Vault, fm: dict) -> routing.Route:
    operations_path = vault.operations_path()
    safe_operations_path = None
    if operations_path.exists() or operations_path.is_symlink():
        relpath = operations_path.relative_to(vault.root).as_posix()
        safe_operations_path = vault.safe_source_path(relpath)
    return routing.route(
        fm,
        project_slugs=vault.project_slugs(),
        area_slugs=vault.area_slugs(),
        resource_slugs=vault.resource_slugs(),
        operations_path=safe_operations_path,
    )


def plan_note_new(vault: Vault, *, title, ntype, body="", status=None,
                  project=None, area=None, resource=None, tags=None,
                  source="manual", author="user", description=None, link=None,
                  chosen_location=None, relations=None, effort_cadence=None,
                  effort_level=None, depth=None, expected_plan_hash=None) -> dict:
    """Build the complete public plan used by note-new preview and apply."""
    fm = build_frontmatter(
        vault,
        title=title,
        ntype=ntype,
        status=status,
        project=project,
        area=area,
        resource=resource,
        tags=tags,
        source=source,
        author=author,
        description=description,
        link=link,
        chosen_location=chosen_location,
        relations=relations,
        effort_cadence=effort_cadence,
        effort_level=effort_level,
        depth=depth,
    )
    route = route_for(vault, fm)
    warnings = frontmatter_warnings(fm)
    if route.reason:
        warnings.append(route.reason)
    side_effects = [f"{'append' if route.append else 'create'}:{route.relpath}"]
    if route.reason:
        side_effects.append(f"create:{route.bucket_relpath}/{route.filename}_reason.txt")
    plan = {
        "format": "arpent-note-new-plan",
        "version": 1,
        "frontmatter": fm,
        "destination_path": route.relpath,
        "append": route.append,
        "reason": route.reason,
        "warnings": warnings,
        "side_effects": side_effects,
        "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "_body": body,
    }
    plan["plan_sha256"] = _note_new_plan_hash(plan)
    if expected_plan_hash is not None and expected_plan_hash != plan["plan_sha256"]:
        raise ValueError("Note creation plan no longer matches --plan-hash; review a fresh dry run.")
    return plan


def apply_note_new(vault: Vault, plan: dict) -> tuple[Path, routing.Route, dict]:
    """Apply a validated note-new plan through the normal transaction path."""
    fm = copy.deepcopy(plan["frontmatter"])
    expected_id = None if plan["append"] else fm["id"]
    destination, route = create_note(
        vault,
        fm,
        plan["_body"],
        expected_id=expected_id,
        expected_route={
            "destination_path": plan["destination_path"],
            "append": plan["append"],
            "reason": plan["reason"],
        },
    )
    return destination, route, fm


def public_note_new_plan(plan: dict) -> dict:
    if plan.get("append"):
        return {
            "format": "arpent-fleeting-plan",
            "version": 1,
            "destination_path": plan["destination_path"],
            "append": True,
            "warnings": plan["warnings"],
            "side_effects": plan["side_effects"],
            "body_sha256": plan["body_sha256"],
            "plan_sha256": plan["plan_sha256"],
        }
    public = {key: value for key, value in plan.items() if not key.startswith("_")}
    public["frontmatter"] = copy.deepcopy(public["frontmatter"])
    public["frontmatter"].pop("created", None)
    public["frontmatter"].pop("modified", None)
    public["apply_generated_fields"] = ["created", "modified"]
    return public


def _note_new_plan_hash(plan: dict) -> str:
    frontmatter = copy.deepcopy(plan["frontmatter"])
    for field in ("created", "modified"):
        frontmatter.pop(field, None)
    payload = {
        "frontmatter": frontmatter,
        "destination_path": plan["destination_path"],
        "append": plan["append"],
        "reason": plan["reason"],
        "body_sha256": plan["body_sha256"],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def create_note(vault: Vault, fm: dict, body: str = "", *, expected_id=None,
                expected_route=None) -> tuple[Path, routing.Route]:
    with vault.exclusive_lock("mutations"):
        _recover_note_transaction(vault)
        normalize_frontmatter_fields(fm)
        normalize_agent_subjective_fields(fm)
        existing_ids = vault.existing_ids()
        if expected_id is not None:
            if expected_id in existing_ids:
                raise ValueError("Note creation plan is stale; review a fresh dry run.")
            fm["id"] = expected_id
        else:
            fm["id"] = routing.new_id(fm["type"], existing_ids)
        r = route_for(vault, fm)
        actual_route = {
            "destination_path": r.relpath,
            "append": r.append,
            "reason": r.reason,
        }
        if expected_route is not None and actual_route != expected_route:
            raise ValueError("Note routing changed after planning; review a fresh dry run.")
        dest = vault.safe_output_path(r.relpath)
        relpaths = [r.relpath]
        reason_rel = None
        if r.reason:
            reason_rel = f"{r.bucket_relpath}/{r.filename}_reason.txt"
            relpaths.append(reason_rel)

        if not r.append and dest.exists():
            raise ValueError(
                f"a note named '{r.filename}' already exists in {r.bucket_relpath}; "
                "choose a semantic qualifier for the title"
            )
        if r.append:
            stamp = datetime.now(timezone.utc).strftime("%H:%M")
            r.entry_time = stamp
            if dest.exists():
                text = vault.safe_source_path(r.relpath).read_text(encoding="utf-8")
            else:
                text = f"# Fleeting - {dest.stem}\n"
            note_content = text.rstrip() + f"\n\n## {stamp}\n{body.strip()}\n"
        else:
            note_content = fmlib.compose_note(fm, body)
        expected_contents = {r.relpath: note_content}
        if r.reason:
            expected_contents[reason_rel] = r.reason + "\n"
        journal = _start_note_transaction(
            vault, relpaths, expected_contents=expected_contents,
        )
        try:
            if r.append:
                vault.atomic_write_text(r.relpath, note_content)
            else:
                vault.atomic_create_text(r.relpath, note_content)
            if r.reason:
                vault.atomic_create_text(reason_rel, r.reason + "\n")
        except Exception:
            _rollback_note_transaction(vault, journal)
            raise
        _commit_note_transaction(vault, journal)
        return dest, r


def write_routed_note(vault: Vault, original_path: Path, fm: dict, body: str, *,
                      expected_source: str | None = None,
                      expected_destination: str | None = None) -> tuple[Path, routing.Route]:
    """Write a note through the routing function, removing its previous path if moved."""
    with vault.exclusive_lock("mutations"):
        _recover_note_transaction(vault)
        source_rel = original_path.relative_to(vault.root).as_posix()
        source = vault.safe_source_path(source_rel)
        current_source = source.read_text(encoding="utf-8")
        if expected_source is not None and current_source != expected_source:
            raise ValueError("Note changed during update; retry with the current source.")

        normalize_frontmatter_fields(fm)
        normalize_agent_subjective_fields(fm)
        r = route_for(vault, fm)
        if expected_destination is not None and r.relpath != expected_destination:
            raise ValueError(
                "Routing changed after planning; build and confirm a fresh edit plan."
            )
        dest = vault.safe_output_path(r.relpath)
        moved = r.relpath != source_rel
        if moved and dest.exists():
            raise ValueError(
                f"a note named '{r.filename}' already exists in {r.bucket_relpath}; "
                "choose a semantic qualifier for the title"
            )

        relpaths = [source_rel]
        if moved:
            relpaths.append(r.relpath)
        reason_rel = None
        if r.reason:
            reason_rel = f"{r.bucket_relpath}/{r.filename}_reason.txt"
            reason_path = vault.safe_output_path(reason_rel)
            if moved and reason_path.exists():
                raise ValueError(f"Routing reason destination already exists: {reason_rel}")
            relpaths.append(reason_rel)
        if moved:
            relpaths.append(
                f"{Path(source_rel).parent.as_posix()}/{original_path.name}_reason.txt"
            )
        content = fmlib.compose_note(fm, body)
        expected_contents = {source_rel: content}
        if moved:
            expected_contents[r.relpath] = content
        if r.reason:
            expected_contents[reason_rel] = r.reason + "\n"
        journal = _start_note_transaction(
            vault, relpaths, expected_contents=expected_contents,
        )
        try:
            vault.atomic_write_text(source_rel, content)
            if moved:
                vault.atomic_move_no_replace(source_rel, r.relpath)
            if r.reason:
                if moved:
                    vault.atomic_create_text(reason_rel, r.reason + "\n")
                else:
                    vault.atomic_write_text(reason_rel, r.reason + "\n")
            if moved:
                stale_reason_rel = (
                    f"{Path(source_rel).parent.as_posix()}/{original_path.name}_reason.txt"
                )
                stale_reason = vault.safe_output_path(stale_reason_rel)
                if stale_reason.exists():
                    stale_reason.unlink()
                    vault.fsync_directory(stale_reason.parent)
        except Exception:
            _rollback_note_transaction(vault, journal)
            raise
        _commit_note_transaction(vault, journal)
        return dest, r


def plan_note_edit(vault: Vault, note_id: str, *, changes=None, clear_fields=(),
                   inbox=False, replacement_body=None, replace_body=False,
                   expected_plan_hash=None) -> dict:
    """Build the complete plan used by both note-edit preview and apply."""
    changes = dict(changes or {})
    if changes.get("project") is not None and changes.get("resource") is not None:
        raise ValueError("--project cannot be combined with --resource.")
    if inbox and any(changes.get(field) is not None for field in ("project", "area", "resource")):
        raise ValueError("--inbox cannot be combined with --project, --area, or --resource.")

    hit = find_note(vault, note_id)
    if not hit:
        raise ValueError(f"No note with id '{note_id}'.")
    path, current_fm, current_body = hit
    original = path.read_text(encoding="utf-8")
    before = copy.deepcopy(current_fm)
    after = copy.deepcopy(current_fm)

    if changes.get("type") == "fleeting":
        raise ValueError(
            "Use `arpent note new --type fleeting`; editing an existing note into "
            "a fleeting capture is unsupported."
        )
    if after.get("type") == "linear" and after.get("status") == "archived":
        raise ValueError("A dissolved linear note is an immutable archive record.")

    changed = False
    for key, value in changes.items():
        if value is not None:
            after[key] = routing.slugify(value) if key == "title" else value
            changed = True
    for field in clear_fields:
        value = [] if field == "tags" else None
        after[field] = value
        changed = True
    if inbox:
        for field in ("project", "area", "resource"):
            after[field] = None
        changed = True

    if (after.get("type") == "linear" and after.get("status") == "archived"):
        raise ValueError("Use `arpent note dissolve <id> --yes` to archive a linear note safely.")

    body_after = replacement_body if replace_body else current_body
    body_changed = body_after != current_body
    changed = changed or body_changed
    if changed:
        after["modified"] = fmlib.now_note_timestamp()
        normalize_frontmatter_fields(after)
        normalize_agent_subjective_fields(after)
        validate_frontmatter_values(after)

    route = route_for(vault, after)
    source_rel = path.relative_to(vault.root).as_posix()
    warnings = frontmatter_warnings(after)
    if route.reason:
        warnings.append(route.reason)
    plan = {
        "id": note_id,
        "source_path": source_rel,
        "destination_path": route.relpath,
        "frontmatter_before": before,
        "frontmatter_after": after,
        "body_changed": body_changed,
        "move": route.relpath != source_rel,
        "reason": route.reason,
        "warnings": warnings,
        "source_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
        "_changed": changed,
        "_body_after": body_after,
        "_source_content": original,
    }
    plan["plan_sha256"] = _note_edit_plan_hash(plan)
    if expected_plan_hash is not None and expected_plan_hash != plan["plan_sha256"]:
        raise ValueError("Note edit plan no longer matches --plan-hash; review a fresh dry run.")
    return plan


def apply_note_edit(vault: Vault, plan: dict) -> tuple[Path, routing.Route] | None:
    """Apply exactly one previously built note-edit plan."""
    if not plan.get("_changed"):
        return None
    source = vault.safe_source_path(plan["source_path"])
    current_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if current_hash != plan["source_sha256"]:
        raise ValueError("Note changed after planning; build a fresh edit plan.")
    return write_routed_note(
        vault,
        source,
        copy.deepcopy(plan["frontmatter_after"]),
        plan["_body_after"],
        expected_source=plan["_source_content"],
        expected_destination=plan["destination_path"],
    )


def public_note_edit_plan(plan: dict) -> dict:
    return {key: value for key, value in plan.items() if not key.startswith("_")}


def _note_edit_plan_hash(plan: dict) -> str:
    after = copy.deepcopy(plan["frontmatter_after"])
    after.pop("modified", None)
    payload = {
        "id": plan["id"],
        "source_path": plan["source_path"],
        "source_sha256": plan["source_sha256"],
        "destination_path": plan["destination_path"],
        "frontmatter_after": after,
        "body_sha256": hashlib.sha256(plan["_body_after"].encode("utf-8")).hexdigest(),
        "reason": plan["reason"],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def plan_ingest(vault: Vault, inbox_path: str, *, title: str, ntype=None,
                 project=None, area=None, resource=None, status=None, source="manual",
                 author="user", description=None, tags=None, depth=None,
                 effort_cadence=None, effort_level=None, link=None,
                 chosen_location=None, attachment=False, source_hash=None,
                 allow_structured_source=False, existing_ids=None) -> dict:
    """Plan lossless conversion of one raw inbox file into a structured note."""
    if project and resource:
        raise ValueError("--project cannot be combined with --resource.")
    source_rel = _normalize_inbox_source(vault, inbox_path)
    source_path = vault.safe_source_path(source_rel)
    actual_hash = _hash_path(source_path)
    if source_hash is not None and source_hash != actual_hash:
        raise ValueError("Inbox source hash does not match --source-hash; rebuild the plan.")

    warnings = []
    binary = file_is_binary(source_path)
    text = None
    if not binary:
        try:
            with source_path.open("r", encoding="utf-8", newline="") as stream:
                text = stream.read()
        except UnicodeDecodeError:
            binary = True
        else:
            if looks_binary_text(text):
                binary = True
                text = None
    malformed = False
    if ntype == "fleeting":
        raise ValueError("Fleeting captures cannot be created by note ingestion.")
    if binary:
        if not attachment:
            raise ValueError("Binary or non-UTF-8 ingestion requires --attachment.")
        if link is not None:
            raise ValueError("--link cannot override the generated binary attachment link.")
        body = ""
    else:
        if attachment:
            raise ValueError("--attachment is only valid for binary or non-UTF-8 sources.")
        try:
            existing_fm, _ = fmlib.parse_note_text(text)
        except ValueError as exc:
            malformed = True
            warnings.append(f"Malformed frontmatter becomes body text: {exc}")
        else:
            if existing_fm and existing_fm.get("id"):
                if not allow_structured_source:
                    raise ValueError("Inbox source already has valid frontmatter; use `arpent note edit`.")
                malformed = True
                warnings.append(
                    "Existing structured frontmatter is preserved verbatim as imported body text."
                )
            if existing_fm:
                if not existing_fm.get("id"):
                    malformed = True
                    warnings.append(
                        "Incomplete frontmatter without an ID becomes body text before complete metadata is added."
                    )
            if fmlib.OPENING_FENCE_RE.match(text) and not existing_fm:
                malformed = True
                warnings.append("Empty or incomplete frontmatter becomes body text.")
        body = text

    note_type = ntype or ("reference" if binary else "note")
    attachment_rel = None
    note_link = link
    attachment_dir_rel = None
    if binary:
        if any((project, area, resource)):
            attachment_dir_rel = _attachment_directory(vault, project, area, resource)
            attachment_rel = f"{attachment_dir_rel}/{source_path.name}"
            _check_output_path(vault, attachment_rel)
            note_link = attachment_rel
        else:
            note_link = source_rel
        body = f"Attachment: [{source_path.name}]({note_link})\n"

    fm = build_frontmatter(
        vault,
        title=title,
        ntype=note_type,
        status=status,
        project=project,
        area=area,
        resource=resource,
        tags=tags,
        source=source,
        author=author,
        description=description,
        link=note_link,
        chosen_location=chosen_location,
        effort_cadence=effort_cadence,
        effort_level=effort_level,
        depth=depth,
        existing_ids=existing_ids,
    )
    route = route_for(vault, fm)
    destination_rel = route.relpath
    _check_output_path(vault, destination_rel)
    if destination_rel == source_rel:
        raise ValueError("Ingestion destination collides with the inbox source; choose another title or route.")
    if (vault.root / destination_rel).exists() or (vault.root / destination_rel).is_symlink():
        raise ValueError(f"Ingestion note destination already exists: {destination_rel}")
    if attachment_rel and ((vault.root / attachment_rel).exists() or (vault.root / attachment_rel).is_symlink()):
        raise ValueError(f"Attachment destination already exists: {attachment_rel}")

    reason_rel = None
    if route.reason:
        reason_rel = f"{route.bucket_relpath}/{route.filename}_reason.txt"
        _check_output_path(vault, reason_rel)
        if (vault.root / reason_rel).exists() or (vault.root / reason_rel).is_symlink():
            raise ValueError(f"Routing reason destination already exists: {reason_rel}")
        warnings.append(route.reason)

    triaged = not destination_rel.startswith("00_inbox/")
    retain_source = bool(binary and attachment_rel is None)
    if not triaged and route.reason is None:
        warnings.append("No final home selected; result remains in inbox (captured but not triaged).")

    source_reason_rel = _source_reason_rel(vault, source_path, source_rel)
    if source_reason_rel:
        try:
            old_reason = vault.safe_source_path(source_reason_rel).read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError, ValueError):
            old_reason = None
        if old_reason:
            warnings.append(f"Previous unsure reason: {old_reason}")

    note_content = (
        fmlib.compose_note(fm, body)
        if binary
        else fmlib.compose_note_verbatim(fm, body)
    )
    return {
        "id": fm["id"],
        "kind": "binary" if binary else ("malformed" if malformed else "text"),
        "source_path": source_rel,
        "destination_path": destination_rel,
        "attachment_path": attachment_rel,
        "frontmatter": fm,
        "triaged": triaged,
        "warnings": warnings,
        "reason": route.reason,
        "source_sha256": actual_hash,
        "_source_text": text,
        "_source_reason_path": source_reason_rel,
        "_reason_path": reason_rel,
        "_note_content": note_content,
        "_attachment_directory": attachment_dir_rel,
        "_retain_source": retain_source,
    }


def apply_ingest(vault: Vault, plan: dict, *, existing_ids=None) -> dict:
    """Apply one ingest plan under a durable, recoverable transaction."""
    with vault.exclusive_lock("mutations"):
        _recover_ingest_transaction(vault)
        source = vault.safe_source_path(plan["source_path"])
        if _hash_path(source) != plan["source_sha256"]:
            raise ValueError("Inbox source changed after planning; build a fresh ingest plan.")
        ids = vault.existing_ids() if existing_ids is None else existing_ids
        if plan["id"] in ids:
            raise ValueError("Ingestion note ID is no longer unique; build a fresh ingest plan.")

        for relpath, label in (
            (plan["destination_path"], "Ingestion note destination"),
            (plan.get("attachment_path"), "Attachment destination"),
            (plan.get("_reason_path"), "Routing reason destination"),
        ):
            if not relpath:
                continue
            _check_output_path(vault, relpath)
            path = vault.root / relpath
            if path.exists() or path.is_symlink():
                raise ValueError(f"{label} already exists: {relpath}")

        source_reason_rel = plan.get("_source_reason_path")
        if source_reason_rel:
            vault.safe_source_path(source_reason_rel).read_text(encoding="utf-8")

        binary = plan["kind"] == "binary"
        retain_source = bool(plan.get("_retain_source"))
        relpaths = [plan["destination_path"]]
        expected = {plan["destination_path"]: plan["_note_content"]}
        if not binary:
            relpaths.insert(0, plan["source_path"])
        if source_reason_rel and not retain_source:
            relpaths.append(source_reason_rel)
        if plan.get("_reason_path"):
            relpaths.append(plan["_reason_path"])
            expected[plan["_reason_path"]] = plan["reason"] + "\n"
        snapshots = file_transaction.snapshot_files(vault, relpaths, expected_contents=expected)
        attachment_dir = plan.get("_attachment_directory")
        attachment_dir_existed = bool(attachment_dir and (vault.root / attachment_dir).is_dir())
        journal = file_transaction.prepare(
            vault,
            INGEST_TRANSACTION_RELPATH,
            snapshots,
            metadata={
                "operation": "note_ingest",
                "source_path": plan["source_path"],
                "source_sha256": plan["source_sha256"],
                "attachment_path": plan.get("attachment_path"),
                "attachment_directory": attachment_dir,
                "attachment_directory_created": bool(attachment_dir and not attachment_dir_existed),
                "source_reason_path": source_reason_rel,
                "source_retained": retain_source,
            },
        )
        try:
            if attachment_dir and not attachment_dir_existed:
                vault.safe_ensure_directory(attachment_dir)
            if binary and not retain_source:
                vault.atomic_move_no_replace(plan["source_path"], plan["attachment_path"])
            vault.atomic_create_text(plan["destination_path"], plan["_note_content"])
            if plan.get("_reason_path"):
                vault.atomic_create_text(plan["_reason_path"], plan["reason"] + "\n")
            if not binary:
                source.unlink()
                vault.fsync_directory(source.parent)
            if source_reason_rel and not retain_source:
                reason_path = vault.safe_source_path(source_reason_rel)
                reason_path.unlink()
                vault.fsync_directory(reason_path.parent)
        except Exception:
            file_transaction.rollback(
                vault,
                INGEST_TRANSACTION_RELPATH,
                journal,
                after_restore=lambda current: _restore_ingest_attachment(vault, current),
            )
            raise
        file_transaction.commit(vault, INGEST_TRANSACTION_RELPATH, journal)
        if existing_ids is not None:
            existing_ids.add(plan["id"])
        return public_ingest_plan(plan)


def recover_ingest_transaction(vault: Vault) -> None:
    with vault.exclusive_lock("mutations"):
        _recover_ingest_transaction(vault)


def public_ingest_plan(plan: dict) -> dict:
    return {key: value for key, value in plan.items() if not key.startswith("_")}


def _normalize_inbox_source(vault: Vault, supplied: str) -> str:
    path = Path(supplied)
    if path.is_absolute():
        try:
            path = path.relative_to(vault.root)
        except ValueError as exc:
            raise ValueError("Ingestion source must be confined under 00_inbox/.") from exc
    if not path.parts or path.parts[0] != "00_inbox" or ".." in path.parts:
        raise ValueError("Ingestion source must be a vault-relative path under 00_inbox/.")
    rel = path.as_posix()
    if rel == "00_inbox" or rel.startswith("00_inbox/fleeting/"):
        raise ValueError("Fleeting captures are not ingestible inbox sources.")
    if path.name == ".gitkeep" or path.name.endswith("_reason.txt"):
        raise ValueError("Inbox sidecars and placeholders cannot be ingested.")
    if rel == "00_inbox/unsure/README.md":
        raise ValueError("The unsure README is not an ingestible inbox source.")
    return rel


def _attachment_directory(vault: Vault, project, area, resource) -> str:
    if project:
        vault.safe_directory_path(f"01_projects/{project}")
        return f"01_projects/{project}/attachments"
    if resource:
        vault.safe_directory_path(f"03_resources/{resource}")
        return f"03_resources/{resource}/attachments"
    try:
        area_folder = routing.resolve_area_folder(area, vault.area_slugs())
    except ValueError:
        raise
    if area_folder is None:
        raise ValueError(f"area '{area}' does not exist under 02_areas/")
    vault.safe_directory_path(f"02_areas/{area_folder}")
    return f"02_areas/{area_folder}/attachments"


def _check_output_path(vault: Vault, relpath: str) -> Path:
    candidate = Path(relpath)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("Vault output path must be relative and cannot contain '..'.")
    current = vault.root
    for part in candidate.parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Refusing generated output through symlink: {relpath}")
        if current.exists() and not current.is_dir():
            raise ValueError(f"Vault output parent is not a directory: {relpath}")
    target = vault.root / candidate
    if target.is_symlink():
        raise ValueError(f"Refusing to replace generated-output symlink: {relpath}")
    return target


def _source_reason_rel(vault: Vault, source: Path, source_rel: str) -> str | None:
    if not source_rel.startswith("00_inbox/unsure/"):
        return None
    reason = source.parent / f"{source.name}_reason.txt"
    if not reason.exists() or reason.is_symlink() or not reason.is_file():
        return None
    return reason.relative_to(vault.root).as_posix()


def file_is_binary(path: Path) -> bool:
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    controls = 0
    characters = 0
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            try:
                text = decoder.decode(chunk, final=False)
            except UnicodeDecodeError:
                return True
            if "\x00" in text:
                return True
            controls += sum(
                ord(character) < 32 and character not in "\n\r\t\f\b"
                for character in text
            )
            characters += len(text)
    try:
        tail = decoder.decode(b"", final=True)
    except UnicodeDecodeError:
        return True
    controls += sum(
        ord(character) < 32 and character not in "\n\r\t\f\b"
        for character in tail
    )
    characters += len(tail)
    return bool(characters) and controls / characters > 0.05


def looks_binary_text(text: str) -> bool:
    if "\x00" in text:
        return True
    controls = sum(
        ord(character) < 32 and character not in "\n\r\t\f\b"
        for character in text
    )
    return bool(text) and controls / len(text) > 0.05


def _hash_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _recover_ingest_transaction(vault: Vault) -> None:
    vault.refuse_foreign_transactions(INGEST_TRANSACTION_RELPATH)
    try:
        file_transaction.recover(
            vault,
            INGEST_TRANSACTION_RELPATH,
            prepared_is_committed=lambda journal: _ingest_transaction_complete(vault, journal),
            after_restore=lambda journal: _restore_ingest_attachment(vault, journal),
        )
    except (OSError, ValueError, json.JSONDecodeError, AttributeError) as exc:
        raise ValueError(f"Cannot recover interrupted note ingestion: {exc}") from exc


def _ingest_transaction_complete(vault: Vault, journal: dict) -> bool:
    source_rel = journal.get("source_path")
    source_reason_rel = journal.get("source_reason_path")
    source_retained = bool(journal.get("source_retained"))
    absent = set() if source_retained else {source_rel, source_reason_rel}
    if source_retained and not _path_has_hash(vault, source_rel, journal["source_sha256"]):
        return False
    for snapshot in journal["files"]:
        relpath = snapshot["path"]
        path = vault.root / relpath
        if relpath in absent:
            if path.exists() or path.is_symlink():
                return False
            continue
        expected_hash = snapshot.get("expected_sha256")
        if expected_hash is None or not _path_has_hash(vault, relpath, expected_hash):
            return False
    attachment = journal.get("attachment_path")
    if attachment and not _path_has_hash(vault, attachment, journal["source_sha256"]):
        return False
    return True


def _restore_ingest_attachment(vault: Vault, journal: dict) -> None:
    attachment_rel = journal.get("attachment_path")
    source_rel = journal.get("source_path")
    expected_hash = journal.get("source_sha256")
    if not isinstance(source_rel, str):
        raise ValueError("Cannot recover ingestion: invalid source path metadata.")
    source_rel = _normalize_inbox_source(vault, source_rel)
    if attachment_rel is not None:
        if not isinstance(attachment_rel, str):
            raise ValueError("Cannot recover ingestion: invalid attachment path metadata.")
        _check_output_path(vault, attachment_rel)
    attachment_directory = journal.get("attachment_directory")
    if attachment_directory is not None:
        if not isinstance(attachment_directory, str):
            raise ValueError("Cannot recover ingestion: invalid attachment directory metadata.")
        _check_output_path(vault, attachment_directory)
    if attachment_rel:
        attachment = vault.root / attachment_rel
        source = vault.root / source_rel
        if attachment.exists() or attachment.is_symlink():
            if not _path_has_hash(vault, attachment_rel, expected_hash):
                raise ValueError("Cannot recover ingestion: attachment content changed.")
            if source.exists() or source.is_symlink():
                if not _path_has_hash(vault, source_rel, expected_hash):
                    raise ValueError("Cannot recover ingestion over a changed inbox source.")
                attachment.unlink()
                vault.fsync_directory(attachment.parent)
            else:
                vault.atomic_move_no_replace(attachment_rel, source_rel)
    if journal.get("attachment_directory_created"):
        if not attachment_directory:
            raise ValueError("Cannot recover ingestion: missing attachment directory metadata.")
        directory = vault.root / attachment_directory
        try:
            directory.rmdir()
            vault.fsync_directory(directory.parent)
        except FileNotFoundError:
            pass
        except OSError:
            if directory.exists() and not any(directory.iterdir()):
                raise


def _path_has_hash(vault: Vault, relpath: str, expected_hash: str) -> bool:
    try:
        source = vault.safe_source_path(relpath)
        return hashlib.sha256(source.read_bytes()).hexdigest() == expected_hash
    except (OSError, ValueError):
        return False


def find_note(vault: Vault, note_id: str):
    matches = [
        note for note in vault.iter_notes(skip_invalid=True)
        if note[1].get("id") == note_id
    ]
    if len(matches) > 1:
        raise ValueError(f"Duplicate note id '{note_id}' prevents a safe mutation.")
    return matches[0] if matches else None


def _find_unique_note(vault: Vault, note_id: str):
    matches = [note for note in vault.iter_notes() if note[1].get("id") == note_id]
    if len(matches) > 1:
        raise ValueError(f"Duplicate note id '{note_id}' prevents a safe lifecycle operation.")
    return matches[0] if matches else None


def _lifecycle_locked(operation):
    @wraps(operation)
    def wrapped(vault, linear_id, *args, **kwargs):
        with _note_lifecycle_lock(vault, linear_id):
            return operation(vault, linear_id, *args, **kwargs)
    return wrapped


def _notes_locked(operation):
    @wraps(operation)
    def wrapped(vault, *args, **kwargs):
        with vault.exclusive_lock("mutations"):
            _recover_note_transaction(vault)
            return operation(vault, *args, **kwargs)
    return wrapped


@_lifecycle_locked
@_notes_locked
def extract_note(vault: Vault, linear_id: str, *, child_type: str, title: str,
                 body: str = "", status=None, project=None, area=None,
                 resource=None, author="user", after=None) -> dict:
    """Create a typed child and record the bidirectional extraction link."""
    hit = _find_unique_note(vault, linear_id)
    if not hit:
        raise ValueError(f"No note with id '{linear_id}'.")
    source_path, source_fm, source_body = hit
    source_original = source_path.read_text(encoding="utf-8")
    if source_fm.get("type") != "linear":
        raise ValueError(f"Note '{linear_id}' is not a linear note.")
    if source_fm.get("status") == "archived":
        raise ValueError(f"Linear note '{linear_id}' is already archived.")
    if child_type == "fleeting":
        raise ValueError("fleeting captures cannot be extracted children because they have no per-note frontmatter")
    if child_type == "linear" and status == "archived":
        raise ValueError("An archived linear note can only be produced by confirmed dissolution.")

    child_fm = build_frontmatter(
        vault,
        title=title,
        ntype=child_type,
        status=status,
        project=project,
        area=area,
        resource=resource,
        source="derived",
        author=author,
    )
    child_fm["parent"] = linear_id
    child_route = route_for(vault, child_fm)
    if child_route.append:
        raise ValueError(f"type '{child_type}' cannot be represented as an extracted note")

    child_rel = child_route.relpath
    source_rel = source_path.relative_to(vault.root).as_posix()
    vault.safe_source_path(source_rel)
    link = f"[[{child_rel.removesuffix('.md')}]]"
    updated_body = _insert_extraction_link(source_body, link, after=after)
    extracted_to = source_fm.get("extracted_to") or []
    if not isinstance(extracted_to, list) or any(
        not isinstance(item, str) or not item for item in extracted_to
    ):
        raise ValueError(f"Linear note '{linear_id}' has an invalid extracted_to field.")
    if child_fm["id"] in extracted_to:
        raise ValueError(f"Linear note '{linear_id}' already records child '{child_fm['id']}'.")
    source_fm["extracted_to"] = [*extracted_to, child_fm["id"]]
    source_fm["modified"] = fmlib.now_note_timestamp()
    validate_frontmatter_values(source_fm)

    child_path = vault.safe_output_path(child_rel)
    if child_path.exists():
        raise ValueError(
            f"a note named '{child_route.filename}' already exists in {child_route.bucket_relpath}; "
            "choose a semantic qualifier for the title"
        )

    reason_rel = None
    relpaths = [source_rel, child_rel]
    if child_route.reason:
        reason_rel = f"{child_route.bucket_relpath}/{child_route.filename}_reason.txt"
        reason_path = vault.safe_output_path(reason_rel)
        if reason_path.exists():
            raise ValueError(f"Routing reason path already exists: {reason_rel}")
        relpaths.append(reason_rel)
    child_content = fmlib.compose_note(child_fm, body)
    source_content = fmlib.compose_note(source_fm, updated_body)
    expected_contents = {
        child_rel: child_content,
        source_rel: source_content,
    }
    if reason_rel:
        expected_contents[reason_rel] = child_route.reason + "\n"
    journal = _start_note_transaction(
        vault, relpaths, expected_contents=expected_contents,
    )
    try:
        if source_path.read_text(encoding="utf-8") != source_original:
            raise ValueError("Linear note changed during extraction; retry with the current source.")
        vault.atomic_create_text(child_rel, child_content)
        if child_route.reason:
            vault.atomic_create_text(reason_rel, child_route.reason + "\n")
        if source_path.read_text(encoding="utf-8") != source_original:
            raise ValueError("Linear note changed during extraction; retry with the current source.")
        vault.atomic_write_text(source_rel, source_content)
    except Exception:
        _rollback_note_transaction(vault, journal)
        raise
    _commit_note_transaction(vault, journal)

    return {
        "source_id": linear_id,
        "source_path": source_path,
        "child_id": child_fm["id"],
        "child_path": child_path,
        "route_reason": child_route.reason,
        "link": link,
    }


@_lifecycle_locked
@_notes_locked
def dissolve_note(vault: Vault, linear_id: str) -> dict:
    """Archive a fully linked linear note as its immutable dissolution record."""
    hit = _find_unique_note(vault, linear_id)
    if not hit:
        raise ValueError(f"No note with id '{linear_id}'.")
    source_path, source_fm, source_body = hit
    source_original = source_path.read_text(encoding="utf-8")
    if source_fm.get("type") != "linear":
        raise ValueError(f"Note '{linear_id}' is not a linear note.")
    if source_fm.get("status") not in ("maturing", "active"):
        raise ValueError(
            f"Linear note '{linear_id}' must be maturing or active before dissolution; "
            f"current status is '{source_fm.get('status')}'."
        )

    listed = source_fm.get("extracted_to") or []
    if not isinstance(listed, list) or any(not isinstance(item, str) or not item for item in listed):
        raise ValueError(f"Linear note '{linear_id}' has an invalid extracted_to field.")
    if len(listed) != len(set(listed)):
        raise ValueError(f"Linear note '{linear_id}' contains duplicate extracted_to IDs.")

    notes_by_id = {}
    discovered = []
    for path, fm, body in vault.iter_notes():
        note_id = fm.get("id")
        if note_id in notes_by_id:
            raise ValueError(f"Duplicate note id '{note_id}' prevents safe dissolution.")
        notes_by_id[note_id] = (path, fm, body)
        if fm.get("parent") == linear_id:
            discovered.append(note_id)

    for child_id in listed:
        child = notes_by_id.get(child_id)
        if not child:
            raise ValueError(f"Extracted child '{child_id}' does not exist.")
        if child[1].get("parent") != linear_id:
            raise ValueError(f"Extracted child '{child_id}' does not point back to '{linear_id}'.")

    child_ids = [*listed, *sorted(child_id for child_id in discovered if child_id not in listed)]
    if not child_ids:
        raise ValueError(f"Linear note '{linear_id}' has no extracted children to dissolve.")

    source_rel = source_path.relative_to(vault.root).as_posix()
    source_fm["status"] = "archived"
    source_fm["modified"] = fmlib.now_note_timestamp()
    source_fm["archived_at"] = source_fm["modified"]
    source_fm["archived_from"] = source_rel
    source_fm["extracted_to"] = child_ids
    validate_frontmatter_values(source_fm)
    route = route_for(vault, source_fm)
    if route.reason or route.bucket_relpath != "04_archives/linear_notes":
        raise ValueError("Dissolution did not resolve to 04_archives/linear_notes; source was not changed.")
    dest_rel = route.relpath
    dest = vault.safe_output_path(dest_rel)
    if dest.exists() and dest.resolve() != source_path.resolve():
        raise ValueError(
            f"a dissolved note named '{route.filename}' already exists in {route.bucket_relpath}; "
            "rename the source with a semantic qualifier before dissolving"
        )

    if source_path.read_text(encoding="utf-8") != source_original:
        raise ValueError("Linear note changed during dissolution; retry with the current source.")
    content = fmlib.compose_note(source_fm, source_body)
    journal = _start_note_transaction(
        vault,
        [source_rel, dest_rel],
        expected_contents={source_rel: content, dest_rel: content},
    )
    try:
        vault.atomic_write_text(source_rel, content)
        if dest_rel != source_rel:
            vault.atomic_move_no_replace(source_rel, dest_rel)
    except Exception:
        _rollback_note_transaction(vault, journal)
        raise
    _commit_note_transaction(vault, journal)
    return {
        "source_id": linear_id,
        "source_path": source_path,
        "archive_path": dest,
        "child_ids": child_ids,
    }


def set_status(vault: Vault, note_id: str, new_status: str):
    if new_status not in routing.STATUSES:
        raise ValueError(f"unknown status '{new_status}'. Valid: {', '.join(routing.STATUSES)}")
    hit = find_note(vault, note_id)
    if not hit:
        return None
    path, fm, body = hit
    original = path.read_text(encoding="utf-8")
    old = fm.get("status")
    if fm.get("type") == "linear":
        if old == "archived" and new_status != "archived":
            raise ValueError("A dissolved linear note is an immutable archive record.")
        if new_status == "archived" and old != "archived":
            raise ValueError("Use `arpent note dissolve <id> --yes` to archive a linear note safely.")
        if old == new_status == "archived":
            return old, new_status, path
    fm["status"] = new_status
    fm["modified"] = fmlib.now_note_timestamp()
    dest, _ = write_routed_note(vault, path, fm, body, expected_source=original)
    return old, new_status, dest


def archive_note(vault: Vault, note_id: str):
    """Move a note into 04_archives/<YYYY_qX>/ and set status archived."""
    with vault.exclusive_lock("mutations"):
        _recover_note_transaction(vault)
        hit = find_note(vault, note_id)
        if not hit:
            return None
        path, fm, body = hit
        if fm.get("type") == "linear":
            raise ValueError("Use `arpent note dissolve <id> --yes` to archive a linear note safely.")
        now = datetime.now(timezone.utc)
        quarter = f"{now.year}_q{(now.month - 1) // 3 + 1}"
        vault.safe_ensure_directory(f"04_archives/{quarter}")
        rel = path.relative_to(vault.root).as_posix()
        fm["status"] = "archived"
        fm["modified"] = fmlib.now_note_timestamp()
        fm["archived_at"] = fm["modified"]
        fm["archived_from"] = rel
        normalize_frontmatter_fields(fm)
        normalize_agent_subjective_fields(fm)
        dest_rel = f"04_archives/{quarter}/{routing.slugify(fm['title'])}.md"
        dest = vault.safe_output_path(dest_rel)
        if dest.exists():
            raise ValueError(
                f"an archived note named '{dest.name}' already exists in {quarter}; "
                "rename the note with a semantic qualifier before archiving"
            )
        content = fmlib.compose_note(fm, body)
        journal = _start_note_transaction(
            vault,
            [rel, dest_rel],
            expected_contents={rel: content, dest_rel: content},
        )
        try:
            vault.atomic_write_text(rel, content)
            vault.atomic_move_no_replace(rel, dest_rel)
        except Exception:
            _rollback_note_transaction(vault, journal)
            raise
        _commit_note_transaction(vault, journal)
        return path, dest


def validate_frontmatter_values(fm: dict) -> None:
    """Validate enum fields that can be edited after note creation."""
    _reject_unsupported_frontmatter_fields(fm)
    for field in ("created", "modified", "expires_at", "archived_at"):
        value = fm.get(field)
        if value is not None:
            try:
                fmlib.parse_note_timestamp(value)
            except ValueError as exc:
                raise ValueError(f"{field} must be a valid UTC timestamp") from exc
    if fm.get("type") not in routing.TYPES:
        raise ValueError(f"unknown type '{fm.get('type')}'. Valid: {', '.join(routing.TYPES)}")
    if fm.get("status") not in routing.STATUSES:
        raise ValueError(f"unknown status '{fm.get('status')}'. Valid: {', '.join(routing.STATUSES)}")
    if fm.get("source") not in routing.SOURCES:
        raise ValueError(f"unknown source '{fm.get('source')}'. Valid: {', '.join(routing.SOURCES)}")
    if fm.get("author") not in routing.AUTHORS:
        raise ValueError(f"unknown author '{fm.get('author')}'. Valid: {', '.join(routing.AUTHORS)}")
    cadence = fm.get("effort_cadence")
    if cadence is not None and cadence not in EFFORT_CADENCES:
        raise ValueError(f"unknown effort cadence '{cadence}'. Valid: {', '.join(EFFORT_CADENCES)}")
    level = fm.get("effort_level")
    if level is not None and level not in EFFORT_LEVELS:
        raise ValueError(f"unknown effort level '{level}'. Valid: {', '.join(EFFORT_LEVELS)}")
    depth = fm.get("depth")
    if depth is not None and (not isinstance(depth, int) or isinstance(depth, bool) or not 1 <= depth <= 5):
        raise ValueError("depth must be an integer from 1 to 5")
    validate_relations(fm.get("relations", []))


def validate_relations(relations) -> None:
    """Validate typed semantic graph relations."""
    if relations in (None, []):
        return
    if not isinstance(relations, list):
        raise ValueError("relations must be a list of mappings with type and target")
    for index, relation in enumerate(relations, start=1):
        if not isinstance(relation, dict):
            raise ValueError(f"relations[{index}] must be a mapping with type and target")
        relation_type = relation.get("type")
        if relation_type not in fmlib.RELATION_TYPES:
            valid = ", ".join(fmlib.RELATION_TYPES)
            raise ValueError(f"unknown relation type '{relation_type}'. Valid: {valid}")
        target = relation.get("target")
        if not isinstance(target, str) or not target.strip():
            raise ValueError(f"relations[{index}] target must be a non-empty note id")


def normalize_agent_subjective_fields(fm: dict) -> list[str]:
    """Agents cannot set user-subjective evaluation fields."""
    if fm.get("author") != "agent":
        return []
    changed = []
    for field in AGENT_SUBJECTIVE_FIELDS:
        if fm.get(field) is not None:
            fm[field] = None
            changed.append(field)
    return changed


def normalize_frontmatter_fields(fm: dict) -> None:
    """Apply canonical representations that are safe to infer."""
    _reject_unsupported_frontmatter_fields(fm)
    defaults = _blank_frontmatter()
    for key, value in defaults.items():
        fm.setdefault(key, value)
    fm["title"] = routing.slugify(fm.get("title") or "untitled")
    fm["description"] = _useful_description(fm["title"], fm.get("description"))


def _reject_unsupported_frontmatter_fields(fm: dict) -> None:
    supported = set(fmlib.KEY_ORDER) | ARCHIVE_FRONTMATTER_FIELDS
    unsupported = sorted(set(fm) - supported)
    if unsupported:
        raise ValueError(
            "unsupported frontmatter fields: " + ", ".join(unsupported)
        )


def _useful_description(title: str, description):
    if not description or not str(description).strip():
        return None
    description = str(description).strip()
    return None if routing.slugify(description) == title else description


def _insert_extraction_link(body: str, link: str, *, after=None) -> str:
    if link in body:
        raise ValueError(f"Source body already contains extraction link '{link}'.")
    if after is not None:
        index = body.find(after)
        if index < 0:
            raise ValueError("The --after passage was not found in the linear note body.")
        position = index + len(after)
        return body[:position] + f"\n\n{link}" + body[position:]
    return body.rstrip() + f"\n\n{link}\n"


def _start_note_transaction(vault: Vault, relpaths: list[str], *, expected_contents=None) -> dict:
    expected_contents = expected_contents or {}
    snapshots = [
        _snapshot_note_file(
            vault, relpath, expected_content=expected_contents.get(relpath),
        )
        for relpath in dict.fromkeys(relpaths)
    ]
    return file_transaction.prepare(vault, TRANSACTION_RELPATH, snapshots)


def _commit_note_transaction(vault: Vault, journal: dict) -> None:
    file_transaction.commit(vault, TRANSACTION_RELPATH, journal)


def _rollback_note_transaction(vault: Vault, journal: dict) -> None:
    file_transaction.rollback(vault, TRANSACTION_RELPATH, journal)


def _recover_note_transaction(vault: Vault) -> None:
    vault.refuse_foreign_transactions(TRANSACTION_RELPATH)
    try:
        file_transaction.recover(vault, TRANSACTION_RELPATH)
    except (OSError, ValueError, json.JSONDecodeError, AttributeError) as exc:
        raise ValueError(f"Cannot recover interrupted note transaction: {exc}") from exc


def _snapshot_note_file(vault: Vault, relpath: str, *, expected_content=None) -> dict:
    return file_transaction.snapshot_file(
        vault, relpath, expected_content=expected_content,
    )


def _restore_note_files(vault: Vault, snapshots: list[dict]) -> None:
    file_transaction.restore_files(vault, snapshots)


def _remove_note_transaction(vault: Vault) -> None:
    file_transaction.remove_journal(vault, TRANSACTION_RELPATH)


@contextmanager
def _note_lifecycle_lock(vault: Vault, linear_id: str):
    rel = f"06_indexes/logs/note-lifecycle-{routing.slugify(linear_id)}.lock"
    path = vault.safe_output_path(rel)
    descriptor = None
    for attempt in range(2):
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            break
        except FileExistsError as exc:
            if attempt == 0 and _remove_stale_lifecycle_lock(path):
                continue
            raise ValueError(f"Another lifecycle operation is running for '{linear_id}'.") from exc
    try:
        owner = json.dumps({"pid": os.getpid(), "note_id": linear_id}) + "\n"
        os.write(descriptor, owner.encode("utf-8"))
        os.close(descriptor)
        descriptor = None
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        path.unlink(missing_ok=True)


def _remove_stale_lifecycle_lock(path: Path) -> bool:
    try:
        owner = json.loads(path.read_text(encoding="utf-8"))
        pid = owner.get("pid")
    except (OSError, json.JSONDecodeError, AttributeError):
        return False
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return True
    except PermissionError:
        return False
    return False

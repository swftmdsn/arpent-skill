"""
cli.py - command-line interface (argparse), zero dependencies.

Implemented commands:
  init, skill, import, status, health, index, context, triage, efforts, search, backup, project, session, cron, tools
  note new | edit | ingest | read | find | status | route | extract | dissolve
  archive, sweep
  todo add | list | show | edit | done | defer | block | archive
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path

from . import backup as backup_mod
from . import context as context_mod
from . import cron as cron_mod
from . import frontmatter as fmlib
from . import index as index_mod
from . import import_executor as import_executor_mod
from . import import_manifest as import_manifest_mod
from . import init_structure as init_structure_mod
from . import notes as notes_mod
from . import operations as operations_mod
from . import projects as projects_mod
from . import routing
from . import session as session_mod
from . import skill_bundle as skill_bundle_mod
from . import sweep as sweep_mod
from . import todo as todo_mod
from . import tools as tools_mod
from . import usage as usage_mod
from . import views
from .vault import Vault, init_vault, prepare_full_mode, set_vault_mode

__version__ = "0.1.0"
CONFIRMATION_HELP = "confirm when required by the confirmation policy"
PLAN_HASH_HELP = "apply only if the current plan matches this exact plan_sha256"


def _positive_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _encode_cursor(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def _decode_cursor(token: str) -> dict:
    try:
        padded = token + "=" * (-len(token) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error) as exc:
        raise ValueError("Invalid pagination cursor.") from exc
    if not isinstance(value, dict):
        raise ValueError("Invalid pagination cursor.")
    return value


def _json_sha256(value) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _counts(items, key):
    result = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        result[value] = result.get(value, 0) + 1
    return dict(sorted(result.items()))


def _page_items(items, *, view, limit, cursor=None, all_items=False,
                query=None, summary=None, snapshot_items=None) -> dict:
    """Return a complete, snapshot-bound JSON page without silent truncation."""
    if all_items and cursor:
        raise ValueError("--all cannot be combined with --cursor.")
    query = query or {}
    snapshot_material = items if snapshot_items is None else snapshot_items
    if len(snapshot_material) != len(items):
        raise ValueError("Pagination snapshot material must match the item count.")
    snapshot_sha = _json_sha256(snapshot_material)
    query_sha = _json_sha256(query)
    start = 0
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded.get("view") != view or decoded.get("query_sha256") != query_sha:
            raise ValueError("Pagination cursor does not match this query.")
        if decoded.get("snapshot_sha256") != snapshot_sha:
            raise ValueError("Pagination cursor is stale; rerun the query from the first page.")
        start = decoded.get("offset")
        if type(start) is not int or start < 0 or start > len(items):
            raise ValueError("Invalid pagination cursor offset.")
    end = len(items) if all_items else min(len(items), start + limit)
    has_more = end < len(items)
    next_cursor = None
    if has_more:
        next_cursor = _encode_cursor({
            "view": view,
            "query_sha256": query_sha,
            "snapshot_sha256": snapshot_sha,
            "offset": end,
        })
    global_summary = {"total": len(items), **(summary or {})}
    return {
        "format": "arpent-page",
        "version": 1,
        "view": view,
        "query": query,
        "snapshot": {"sha256": snapshot_sha},
        "summary": global_summary,
        "page": {
            "first_ordinal": start + 1 if end > start else None,
            "last_ordinal": end if end > start else None,
            "returned": end - start,
            "limit": None if all_items else limit,
            "has_more": has_more,
            "next_cursor": next_cursor,
            "complete_result": start == 0 and not has_more,
        },
        "items": items[start:end],
    }


def _page_text(text: str, *, view, path, max_bytes, cursor=None, full=False,
               metadata=None) -> dict:
    """Return one UTF-8-safe, source-hash-bound text page."""
    if full and cursor:
        raise ValueError("--full cannot be combined with --cursor.")
    raw = text.encode("utf-8")
    content_sha = hashlib.sha256(raw).hexdigest()
    start = 0
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded.get("view") != view or decoded.get("path") != path:
            raise ValueError("Content cursor does not match this source.")
        if decoded.get("content_sha256") != content_sha:
            raise ValueError("Content cursor is stale; reload the source from the beginning.")
        start = decoded.get("offset")
        if type(start) is not int or start < 0 or start > len(raw):
            raise ValueError("Invalid content cursor offset.")
    end = len(raw) if full else min(len(raw), start + max_bytes)
    if not full and end < len(raw) and end > start:
        lower_bound = start + max(1, (end - start) // 2)
        paragraph = raw.rfind(b"\n\n", lower_bound, end)
        line = raw.rfind(b"\n", lower_bound, end)
        if paragraph >= lower_bound:
            end = paragraph + 2
        elif line >= lower_bound:
            end = line + 1
    while end > start:
        try:
            chunk = raw[start:end].decode("utf-8")
            break
        except UnicodeDecodeError:
            end -= 1
    else:
        end = min(len(raw), start + 1)
        while end <= len(raw):
            try:
                chunk = raw[start:end].decode("utf-8")
                break
            except UnicodeDecodeError:
                end += 1
        else:  # pragma: no cover - input was produced by encoding valid text
            raise ValueError("Cannot advance UTF-8 content pagination.")
    has_more = end < len(raw)
    next_cursor = None
    if has_more:
        next_cursor = _encode_cursor({
            "view": view,
            "path": path,
            "content_sha256": content_sha,
            "offset": end,
        })
    return {
        "format": "arpent-content-page",
        "version": 1,
        "view": view,
        "path": path,
        "source": {
            "content_sha256": content_sha,
            "total_bytes": len(raw),
            **(metadata or {}),
        },
        "page": {
            "start_byte": start,
            "end_byte_exclusive": end,
            "returned_bytes": end - start,
            "has_more": has_more,
            "next_cursor": next_cursor,
            "complete_result": start == 0 and not has_more,
            "starts_with_line_fragment": start > 0 and raw[start - 1:start] != b"\n",
            "ends_with_line_fragment": has_more and raw[end - 1:end] != b"\n",
        },
        "content": chunk,
    }


def _add_page_arguments(parser, *, default_limit):
    parser.add_argument("--json-page", action="store_true", help="emit a versioned bounded JSON page")
    parser.add_argument("--limit", type=_positive_int, default=default_limit)
    parser.add_argument("--cursor", default=None)
    parser.add_argument("--all", action="store_true", help="emit the complete filtered result")


def _validate_page_arguments(args, *, default_limit):
    if args.json_page:
        return
    if args.cursor or args.all or args.limit != default_limit:
        sys.exit("--limit, --cursor, and --all require --json-page.")


def _validate_content_page_arguments(args, *, default_bytes, default_limit=None):
    if args.json_page:
        return
    changed = args.cursor or args.full or args.max_bytes != default_bytes
    if default_limit is not None:
        changed = changed or args.limit != default_limit
    if changed:
        sys.exit("--max-bytes, --limit, --cursor, and --full require --json-page.")


def _need_vault() -> Vault:
    v = Vault.find()
    if v is None:
        sys.exit("Not inside an Arpent vault (no .arpent marker found). Run `arpent init`.")
    return v


def _confirmation_required(vault: Vault, operation: str, *, count=1) -> bool:
    operations_path = vault.operations_path()
    relpath = operations_path.relative_to(vault.root).as_posix()
    safe_path = vault.safe_source_path(relpath)
    return operations_mod.requires_confirmation(operation, count=count, path=safe_path)


def _require_confirmation_flag(args, vault: Vault, operation: str, *, count=1,
                               message=None) -> None:
    try:
        required = _confirmation_required(vault, operation, count=count)
    except ValueError as exc:
        sys.exit(str(exc))
    confirmed = getattr(args, "yes", False) or getattr(args, "backup_yes", False)
    if required and not confirmed:
        sys.exit(message or "Confirmation policy requires confirmation; re-run with --yes.")


def _promote_to_full(vault: Vault, *, automatic=False) -> bool:
    """Reconcile derivatives and enable full mode as one guarded transition."""
    with vault.exclusive_lock("mode"):
        with vault.exclusive_lock("mutations"):
            original_marker = vault.safe_source_path(".arpent").read_bytes().decode("utf-8")
            marker = vault.marker_data()
            if marker["mode"] == "full":
                return False
            if automatic and not marker["auto_full"]:
                raise ValueError("Automatic promotion was disabled by an explicit minimal choice.")
            vault.refuse_foreign_transactions()
            prepare_full_mode(vault)
            vault.atomic_write_text(".arpent", json.dumps({
                "version": marker["version"],
                "name": marker["name"],
                "mode": "full",
                "auto_full": False,
            }, sort_keys=True) + "\n")
            try:
                index_mod.build_index(vault)
            except BaseException:
                vault.atomic_write_text(".arpent", original_marker)
                raise
            return True


@contextmanager
def _vault_mode_guard(args):
    """Keep the checked mode stable until the current CLI command completes."""
    command = getattr(args, "command", None)
    if command == "skill":
        yield
        return
    if command == "init":
        root = Path(args.path).expanduser().resolve()
        candidate = Vault(root)
        try:
            candidate.marker_data()
        except (OSError, ValueError):
            yield
        else:
            with candidate.exclusive_lock("mode"):
                yield
        return
    vault = Vault.find()
    if vault is None:
        yield
        return
    if command == "mode":
        with vault.exclusive_lock("mode"):
            try:
                vault.marker_data()
            except (OSError, ValueError) as exc:
                sys.exit(f"Cannot read Arpent vault mode: {exc}")
            yield
        return
    while True:
        with vault.shared_lock("mode"):
            try:
                marker = vault.marker_data()
            except (OSError, ValueError) as exc:
                sys.exit(f"Cannot read Arpent vault mode: {exc}")
            if marker["mode"] == "full":
                yield
                return
            if not marker["auto_full"]:
                sys.exit(
                    f"`arpent {command}` is not available in minimal mode; it is mode-gated. "
                    "Use direct-file operations, or run `arpent mode full`."
                )
        try:
            if _confirmation_required(vault, "mode_full"):
                sys.exit(
                    "Automatic full-mode promotion requires confirmation under the "
                    "local policy; run `arpent mode full --yes`, then retry."
                )
            _promote_to_full(vault, automatic=True)
        except (OSError, ValueError) as exc:
            sys.exit(f"Cannot promote the vault to full mode: {exc}")


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #

def cmd_skill_install(args):
    result = skill_bundle_mod.install_skill_bundle(args.to, replace=args.replace)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"Installed Arpent skill bundle at {result['destination']} "
            f"({result['file_count']} files, {result['total_bytes']} bytes)"
        )


def cmd_init(args):
    structure = None
    if args.structure:
        try:
            structure = init_structure_mod.load_structure(Path(args.structure))
        except (OSError, ValueError) as e:
            sys.exit(str(e))
    supplied = Path(args.path).expanduser()
    if supplied.is_symlink():
        sys.exit(f"Refusing to initialize through a symlink: {supplied}")
    root = supplied.resolve()
    try:
        if structure is not None:
            init_structure_mod.preflight_structure(root, structure)
        v = init_vault(root, minimal=args.minimal)
        structure_result = (
            init_structure_mod.apply_structure(v, structure) if structure is not None else None
        )
    except (OSError, ValueError) as e:
        sys.exit(str(e))
    mode = "minimal" if args.minimal else "full"
    print(f"Initialized Arpent vault at {v.root} ({mode} mode)")
    print("Buckets created: 00_inbox 01_projects 02_areas 03_resources "
          "04_archives 05_tools 06_indexes (unresolved routing lives in 00_inbox/unsure)")
    if structure_result is not None:
        created = sum(len(values["created"]) for values in structure_result.values())
        existing = sum(len(values["existing"]) for values in structure_result.values())
        print(f"Configured structure: {created} created, {existing} already present")


def cmd_mode_show(args):
    v = _need_vault()
    marker = v.marker_data()
    usage_mod.set_result(args, subject_kind="vault", outcome="read", changed=False)
    if args.json:
        print(json.dumps(marker, indent=2, sort_keys=True))
    else:
        print(marker["mode"])


def cmd_mode_set(args):
    v = _need_vault()
    marker = v.marker_data()
    target = args.mode_cmd
    if marker["mode"] == target and not (target == "minimal" and marker["auto_full"]):
        changed = False
    else:
        _require_confirmation_flag(args, v, f"mode_{target}")
        try:
            if target == "full":
                changed = _promote_to_full(v)
            else:
                changed = set_vault_mode(v, target)
        except (OSError, ValueError) as exc:
            sys.exit(str(exc))
    usage_mod.set_result(
        args, subject_kind="vault", outcome="edited" if changed else "read", changed=changed,
    )
    result = {"version": 1, "mode": target, "changed": changed}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        state = "Changed to" if changed else "Already in"
        print(f"{state} {target} mode")


def cmd_import_scan(args):
    try:
        plan = import_manifest_mod.scan_source(
            Path(args.source), Path(args.output), overwrite=args.force,
        )
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
    result = {
        "plan": str(Path(args.output).expanduser().resolve()),
        "inventory": plan["inventory"]["path"],
        "import_id": plan["import_id"],
        "files": plan["inventory"]["files"],
        "bytes": plan["inventory"]["bytes"],
        "folders": len(plan["folders"]),
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"Scanned {result['files']} files across {result['folders']} folders")
        print(f"Plan: {result['plan']}")
        print("Next: arpent import review <plan>")


def cmd_import_suggest(args):
    try:
        path, plan = import_manifest_mod.load_plan(Path(args.plan))
        changed = import_manifest_mod.refresh_suggestions(plan)
        import_manifest_mod.save_plan(path, plan)
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
    result = {"plan": str(path), "suggestions_changed": changed}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"Updated folder suggestions: {changed} changed")


def cmd_import_review(args):
    if not 0 <= args.minimum_confidence <= 1:
        sys.exit("--minimum-confidence must be between 0 and 1.")
    if args.json and not args.accept_suggestions:
        sys.exit("Import review --json requires --accept-suggestions for JSON-only output.")
    if not args.accept_suggestions and not sys.stdin.isatty():
        sys.exit(
            "Interactive import review requires a terminal. Use --accept-suggestions "
            "or edit the plan JSON explicitly."
        )
    try:
        path, plan = import_manifest_mod.load_plan(Path(args.plan))
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
    try:
        result = import_manifest_mod.review_plan(
            plan,
            accept_suggestions=args.accept_suggestions,
            minimum_confidence=args.minimum_confidence,
            assume_yes=args.yes,
        )
    except (EOFError, OSError, ValueError) as exc:
        try:
            import_manifest_mod.save_plan(path, plan)
        except (OSError, ValueError):
            pass
        sys.exit(str(exc))
    try:
        import_manifest_mod.save_plan(path, plan)
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"Review: {result['accepted']} decisions added, "
            f"{len(result['unresolved'])} unresolved"
        )
        print("Review marked complete" if result["completed"] else "Review remains incomplete")


def cmd_import_validate(args):
    try:
        path, plan = import_manifest_mod.load_plan(Path(args.plan))
        vault = Vault.find()
        result = import_manifest_mod.validate_plan(
            path, plan, vault=vault, verify_sources=args.sources,
        )
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("Import plan is valid" if result["valid"] else "Import plan is invalid")
        for warning in result["warnings"]:
            print(f"Warning: {warning}")
        for error in result["errors"]:
            print(f"Error: {error}")
        print(f"Decision hash: {result['decision_sha256']}")
    if not result["valid"]:
        sys.exit(1)


def cmd_import_summary(args):
    try:
        path, plan = import_manifest_mod.load_plan(Path(args.plan))
        result = import_manifest_mod.summarize_plan(path, plan)
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_import_summary(result)


def cmd_import_apply(args):
    vault = _need_vault()
    _validate_page_arguments(args, default_limit=50)
    if args.json_page and not args.dry_run:
        sys.exit("Import --json-page is available for dry-run previews; use --json for apply results.")
    try:
        path, plan = import_manifest_mod.load_plan(Path(args.plan))
        summary = import_manifest_mod.summarize_plan(path, plan)
        confirmation_required = _confirmation_required(
            vault, "import_apply", count=max(1, summary.get("files", 1)),
        )
        if (args.json or args.json_page) and not args.dry_run and confirmation_required and not args.yes:
            sys.exit("Import apply --json requires --yes for JSON-only output.")
        if not args.dry_run and confirmation_required and not args.yes:
            if not sys.stdin.isatty():
                sys.exit("Import apply requires --yes when no interactive terminal is available.")
            _print_import_summary(summary)
            answer = input(
                "Apply this import in copy mode? External source files will remain unchanged. [y/N]: "
            ).strip().lower()
            if answer not in {"y", "yes", "o", "oui"}:
                print("Import cancelled")
                return
        report = import_executor_mod.apply_import(
            vault,
            path,
            plan,
            dry_run=args.dry_run,
            stop_on_error=args.stop_on_error,
            include_previews=args.json or args.json_page,
            expected_execution_hash=args.plan_hash,
        )
    except (EOFError, OSError, ValueError) as exc:
        sys.exit(str(exc))
    counts = report["counts"]
    usage_mod.set_result(
        args,
        subject_kind="import",
        outcome="dry_run" if args.dry_run else "imported",
        changed=(
            not args.dry_run
            and (
                counts.get("applied", 0) > 0
                or counts.get("structure_created", 0) > 0
            )
        ),
        count=counts.get("planned", 0) if args.dry_run else counts.get("applied", 0),
    )
    if args.json_page:
        try:
            page = _page_items(
                report.get("previews") or [],
                view="import-preview",
                limit=args.limit,
                cursor=args.cursor,
                all_items=args.all,
                query={"plan_sha256": report.get("plan_sha256")},
                summary={"counts": report.get("counts") or {}, "failures": len(report.get("failures") or [])},
            )
        except ValueError as exc:
            sys.exit(str(exc))
        page["report"] = {key: value for key, value in report.items() if key != "previews"}
        print(json.dumps(page, indent=2, ensure_ascii=False, sort_keys=True))
    elif args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        label = "Import preview" if args.dry_run else "Import result"
        rendered = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        print(f"{label}: {rendered or 'no items'}")
        for failure in report["failures"][:20]:
            print(f"Failed: {failure['path']}: {failure['error']}")
    if report["failures"]:
        sys.exit(1)


def cmd_import_status(args):
    vault = _need_vault()
    try:
        _, plan = import_manifest_mod.load_plan(Path(args.plan))
        result = import_executor_mod.import_status(vault, plan)
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"Import {result['import_id']}: {result['complete']}/{result['total']} complete, "
            f"{result['remaining']} remaining"
        )
        if result["by_status"]:
            print(", ".join(f"{key}={value}" for key, value in result["by_status"].items()))
    if result["by_status"].get("missing_or_changed", 0):
        sys.exit(1)


def _print_import_summary(summary):
    print(f"Import: {summary['import_id']}")
    print(f"Source: {summary['source_root']}")
    print(f"Files: {summary['files']} ({summary['bytes']} bytes)")
    roles = ", ".join(f"{key}={value}" for key, value in summary["by_role"].items())
    print(f"Planned roles: {roles or 'none'}")
    print(f"Unresolved folders: {len(summary['unresolved_folders'])}")
    print(f"Review complete: {'yes' if summary['review_completed'] else 'no'}")


def cmd_status(args):
    v = _need_vault()
    s = views.status(v)
    usage_mod.set_result(
        args, subject_kind="vault", outcome="read", changed=False, count=s["total"],
    )
    print(f"Vault: {v.root}")
    print(f"Notes: {s['total']}   Inbox awaiting triage: {s['inbox']}")
    if s["by_bucket"]:
        print("\nBy bucket:")
        for k in sorted(s["by_bucket"]):
            print(f"  {k:<16} {s['by_bucket'][k]}")
    if s["by_status"]:
        print("\nBy status:")
        for k in sorted(s["by_status"], key=lambda x: routing.STATUSES.index(x) if x in routing.STATUSES else 99):
            print(f"  {str(k):<12} {s['by_status'][k]}")


def cmd_index(args):
    v = _need_vault()
    _require_confirmation_flag(args, v, "index")
    try:
        idx = index_mod.build_index(v)
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
    usage_mod.set_result(
        args, subject_kind="index", outcome="indexed", changed=True,
        count=idx["note_count"],
    )
    print(
        f"Indexed {idx['note_count']} notes, {idx['file_count']} files, "
        f"{idx['folder_count']} folders → 06_indexes/index.json + sidecar.json + "
        f"context_index.json; search={idx['search_backend']}"
    )


def cmd_context_pending(args):
    v = _need_vault()
    _validate_page_arguments(args, default_limit=100)
    try:
        rows = context_mod.pending_summaries(v, kind=args.kind, prefix=args.path)
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
    if args.json_page:
        try:
            page = _page_items(
                rows,
                view="context-pending",
                limit=args.limit,
                cursor=args.cursor,
                all_items=args.all,
                query={"kind": args.kind, "path": args.path},
                summary={"by_kind": _counts(rows, "kind"), "by_status": _counts(rows, "status")},
            )
        except ValueError as exc:
            sys.exit(str(exc))
        print(json.dumps(page, indent=2, ensure_ascii=False, sort_keys=True))
        return
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    if not rows:
        print("No missing or stale L1 summaries.")
        return
    for row in rows:
        print(f"{row['status']:<7} {row['kind']:<6} {row['path']}")
        print(f"        {row['l0']}")


def cmd_context_set(args):
    v = _need_vault()
    _require_confirmation_flag(args, v, "context_set")
    summary = sys.stdin.read() if args.stdin else args.summary
    try:
        entry = context_mod.set_summary(
            v,
            args.path,
            summary,
            expected_hash=args.source_hash,
            provider=args.provider,
            force=args.force,
        )
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
    print(f"Stored fresh L1 summary for {context_mod.normalize_path(args.path)}")
    print(f"Source hash: {entry['source_hash']}")


def cmd_context_show(args):
    v = _need_vault()
    _validate_content_page_arguments(args, default_bytes=32 * 1024, default_limit=200)
    try:
        entry = context_mod.get_entry(v, args.path)
        normalized = context_mod.normalize_path(args.path)
    except ValueError as exc:
        sys.exit(str(exc))

    if args.level == "l0":
        print(entry["l0"])
        return
    if args.level == "l1":
        l1 = entry.get("l1") or {}
        if not l1.get("summary"):
            sys.exit(f"No L1 summary for '{normalized}' ({l1.get('status') or 'missing'}).")
        try:
            live_hash = index_mod.current_context_hash(v, normalized, entry.get("kind"))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            sys.exit(f"Cannot validate L1 summary for '{normalized}': {exc}")
        if live_hash != l1.get("source_hash"):
            sys.exit(
                f"L1 summary for '{normalized}' is stale; run `arpent index` "
                "and regenerate it."
            )
        if l1.get("status") != "fresh":
            print(f"Warning: L1 summary is {l1.get('status')}.", file=sys.stderr)
        print(l1["summary"])
        return

    l2 = entry.get("l2") or {}
    if entry.get("kind") == "folder":
        if args.json_page:
            children = l2.get("children") or []
            try:
                page = _page_items(
                    children,
                    view="context-l2-folder",
                    limit=args.limit,
                    cursor=args.cursor,
                    all_items=args.full,
                    query={"path": normalized},
                    summary={"source_hash": entry.get("source_hash")},
                )
            except ValueError as exc:
                sys.exit(str(exc))
            print(json.dumps(page, indent=2, ensure_ascii=False, sort_keys=True))
            return
        print(json.dumps(l2, indent=2, ensure_ascii=False))
        return
    if entry.get("kind") in {"note", "text"}:
        try:
            source = v.safe_source_path(normalized)
            text = source.read_text(encoding="utf-8")
            if args.json_page:
                live_semantic_hash = index_mod.current_context_hash(
                    v, normalized, entry.get("kind"),
                )
                page = _page_text(
                    text,
                    view="context-l2-source",
                    path=normalized,
                    max_bytes=args.max_bytes,
                    cursor=args.cursor,
                    full=args.full,
                    metadata={
                        "kind": entry.get("kind"),
                        "indexed_semantic_sha256": entry.get("source_hash"),
                        "live_semantic_sha256": live_semantic_hash,
                        "index_fresh": live_semantic_hash == entry.get("source_hash"),
                    },
                )
                print(json.dumps(page, indent=2, ensure_ascii=False, sort_keys=True))
            else:
                print(text, end="")
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            sys.exit(f"Cannot load L2 source '{normalized}': {exc}")
        return
    print(json.dumps(l2, indent=2, ensure_ascii=False))


def cmd_triage(args):
    v = _need_vault()
    _validate_page_arguments(args, default_limit=50)
    try:
        items = views.triage_items(v)
    except ValueError as exc:
        sys.exit(str(exc))
    usage_mod.set_result(
        args, subject_kind="triage", outcome="triaged", changed=False, count=len(items),
    )
    if args.json_page:
        try:
            page = _page_items(
                items,
                view="triage",
                limit=args.limit,
                cursor=args.cursor,
                all_items=args.all,
                summary={"by_kind": _counts(items, "kind"), "by_type": _counts(items, "type")},
                snapshot_items=[
                    {key: value for key, value in item.items() if key != "age_seconds"}
                    for item in items
                ],
            )
        except ValueError as exc:
            sys.exit(str(exc))
        print(json.dumps(page, indent=2, ensure_ascii=False, sort_keys=True))
        return
    if args.json:
        print(json.dumps(items, indent=2, ensure_ascii=False))
        return
    if not items:
        print("Inbox is clear. Nothing to triage.")
        return
    print(f"{len(items)} item(s) in inbox:\n")
    for it in items:
        print(f"  [{it['type']}] {it['id'] or Path(it['path']).name}")
        print(f"      {it['title'] or it['preview']}")
        print(f"      {it['path']}")
        if it.get("reason"):
            print("      " + it["reason"].replace("\n", "\n      "))
    print("\nStructured notes: arpent note edit <id> [routing flags]")
    print("Raw, malformed, or binary files: arpent note ingest <inbox-path> --title <title> [routing flags]")
    print("Items may also be left in place for later review.")


def cmd_efforts(args):
    v = _need_vault()
    _validate_page_arguments(args, default_limit=100)
    rows = views.efforts(v)
    if args.json_page:
        try:
            page = _page_items(
                rows,
                view="efforts",
                limit=args.limit,
                cursor=args.cursor,
                all_items=args.all,
                summary={"by_group": _counts(rows, "group"), "by_kind": _counts(rows, "kind")},
            )
        except ValueError as exc:
            sys.exit(str(exc))
        print(json.dumps(page, indent=2, ensure_ascii=False, sort_keys=True))
        return
    if not rows:
        print("No active actionables.")
        return
    current_group = None
    for r in rows:
        if r["group"] != current_group:
            if current_group is not None:
                print()
            current_group = r["group"]
            if current_group == "unclassified":
                print("UNCLASSIFIED")
            else:
                cadence, level = current_group.split(":", 1)
                print(f"{cadence.upper()} / {level.upper()}")
        print(f"  {r['kind']:<12} {r['label']:<28} {r['path']}")


def cmd_search(args):
    v = _need_vault()
    _validate_page_arguments(args, default_limit=50)
    hits = views.search(v, args.query)
    usage_mod.set_result(
        args, subject_kind="search", outcome="searched", changed=False, count=len(hits),
    )
    if args.json_page:
        try:
            page = _page_items(
                hits,
                view="search",
                limit=args.limit,
                cursor=args.cursor,
                all_items=args.all,
                query={"query": args.query},
                summary={"by_backend": _counts(hits, "backend")},
            )
        except ValueError as exc:
            sys.exit(str(exc))
        print(json.dumps(page, indent=2, ensure_ascii=False, sort_keys=True))
        return
    if not hits:
        print(f"No vault matches for '{args.query}'.")
        return
    print(f"{len(hits)} match(es) in the vault:\n")
    for h in hits[:50]:
        print(f"  {h['id']}  {h['title']}")
        print(f"      {h['path']}")
    if len(hits) > 50:
        print(f"\nShowing 50 of {len(hits)}. Use --json-page to continue or --json-page --all.")


def cmd_backup(args):
    v = _need_vault()
    _require_confirmation_flag(args, v, "backup_create")
    try:
        result = backup_mod.create_backup(v, destination=args.destination)
    except (OSError, ValueError, sqlite3.Error) as exc:
        sys.exit(str(exc))
    snapshot = Path(result["snapshot_path"])
    try:
        display = snapshot.relative_to(v.root).as_posix()
    except ValueError:
        display = str(snapshot)
    totals = result["totals"]
    print(
        f"Backed up {totals['files']} files and {totals['sqlite_databases']} "
        f"durable database(s) -> {display}/"
    )


def cmd_backup_verify(args):
    try:
        result = backup_mod.verify_backup(args.snapshot)
    except (OSError, ValueError, sqlite3.Error) as exc:
        sys.exit(str(exc))
    totals = result["totals"]
    print(
        f"Verified {totals['files']} files and {totals['sqlite_databases']} "
        f"durable database(s) in {result['snapshot_path']}"
    )


def cmd_backup_restore(args):
    try:
        verified = backup_mod.verify_backup(args.snapshot)
        source_vault = Vault(Path(verified["snapshot_path"]) / backup_mod.PAYLOAD_NAME)
        source_vault.marker_data()
        _require_confirmation_flag(args, source_vault, "backup_restore")
        result = backup_mod.restore_backup(args.snapshot, args.to)
    except (OSError, ValueError, sqlite3.Error) as exc:
        sys.exit(str(exc))
    print(f"Restored verified vault to {result['restored_path']}")
    print(f"Run: cd {result['restored_path']} && arpent index")


def cmd_note_new(args):
    v = _need_vault()
    # Keep ID planning and publication in one interprocess critical section.
    with v.exclusive_lock("mutations"):
        body = _read_body(args)
        if args.type == "fleeting" and not body:
            body = args.title
        try:
            plan = notes_mod.plan_note_new(
                v, title=args.title, ntype=args.type, body=body, status=args.status,
                project=args.project, area=args.area, resource=args.resource,
                tags=_split_tags(args.tags), source=args.source, author=args.author,
                description=args.description, link=args.link,
                chosen_location=args.chosen_location,
                effort_cadence=args.effort_cadence,
                effort_level=args.effort_level,
                expected_plan_hash=args.plan_hash,
            )
        except ValueError as e:
            sys.exit(str(e))
        public_plan = notes_mod.public_note_new_plan(plan)
        try:
            confirmation_required = _confirmation_required(v, "note_new")
        except ValueError as e:
            sys.exit(str(e))
        public_plan["confirmation_required"] = confirmation_required
        if args.dry_run or (confirmation_required and not args.plan_hash):
            if args.json:
                print(json.dumps(public_plan, indent=2, ensure_ascii=False, sort_keys=True))
            else:
                print(f"Planned note → {plan['destination_path']}")
                print(f"Plan hash: {plan['plan_sha256']}")
                for warning in plan["warnings"]:
                    print(f"Warning: {warning}")
                if confirmation_required and not args.dry_run:
                    print("Review the plan, then re-run with --plan-hash <plan_sha256>.")
            usage_mod.set_result(
                args, subject_kind="note", subject_type=plan["frontmatter"]["type"],
                status_after=plan["frontmatter"]["status"], outcome="dry_run",
                changed=False, count=1,
            )
            return
        for warning in plan["warnings"]:
            print(f"Warning: {warning}", file=sys.stderr)
        try:
            dest, r, fm = notes_mod.apply_note_new(v, plan)
        except ValueError as e:
            sys.exit(str(e))
        usage_mod.set_result(
            args, subject_kind="note", subject_type=fm["type"],
            status_after=fm["status"], outcome="captured", changed=True, count=1,
        )
        rel = dest.relative_to(v.root).as_posix()
        if args.json:
            if r.append:
                result = {
                    "format": "arpent-fleeting-result",
                    "version": 1,
                    "path": rel,
                    "append": True,
                    "captured_time": r.entry_time,
                    "warnings": plan["warnings"],
                    "plan_sha256": plan["plan_sha256"],
                }
            else:
                result = {
                    "format": "arpent-note-new-result",
                    "version": 1,
                    "id": fm["id"],
                    "path": rel,
                    "frontmatter": fm,
                    "warnings": plan["warnings"],
                    "plan_sha256": plan["plan_sha256"],
                }
            print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
            return
        if r.reason:
            print(f"⚠ Routed to unsure: {rel}")
            print("  " + r.reason.replace("\n", "\n  "))
        elif r.append:
            print(f"Captured fleeting → {rel}")
        else:
            print(f"Created {fm['id']} → {rel}")


def cmd_note_route(args):
    """Re-route an existing note by replacing its PARA routing fields."""
    _reject_todo_mutation(args.id)
    v = _need_vault()
    _require_confirmation_flag(args, v, "note_route")
    hit = notes_mod.find_note(v, args.id)
    if not hit:
        sys.exit(f"No note with id '{args.id}'.")
    path, fm, body = hit
    original = path.read_text(encoding="utf-8")
    if fm.get("type") == "linear" and fm.get("status") == "archived":
        sys.exit("A dissolved linear note is an immutable archive record.")
    fm["project"] = args.project
    fm["area"] = args.area
    fm["resource"] = args.resource
    fm["modified"] = fmlib.now_note_timestamp()
    try:
        dest, r = notes_mod.write_routed_note(
            v, path, fm, body, expected_source=original,
        )
    except ValueError as e:
        sys.exit(str(e))
    usage_mod.set_result(
        args, subject_kind="note", subject_type=fm.get("type"),
        status_before=fm.get("status"), status_after=fm.get("status"),
        outcome="routed", changed=True, count=1,
    )
    rel = dest.relative_to(v.root).as_posix()
    if r.reason:
        print(f"⚠ {args.id} → unsure: {rel}")
    else:
        print(f"Routed {args.id} → {rel}")


def cmd_note_read(args):
    v = _need_vault()
    _validate_content_page_arguments(args, default_bytes=32 * 1024)
    hit = notes_mod.find_note(v, args.id)
    if not hit:
        sys.exit(f"No note with id '{args.id}'.")
    path, fm, body = hit
    relpath = path.relative_to(v.root).as_posix()
    if args.json_page:
        try:
            page = _page_text(
                body,
                view="note-read",
                path=relpath,
                max_bytes=args.max_bytes,
                cursor=args.cursor,
                full=args.full,
                metadata={
                    "id": fm.get("id"),
                    "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    "frontmatter": fm,
                },
            )
        except ValueError as exc:
            sys.exit(str(exc))
        print(json.dumps(page, indent=2, ensure_ascii=False, sort_keys=True))
        return
    print(f"{fm.get('title')} [{fm.get('type')} / {fm.get('status')}]")
    print(f"{relpath}\n")
    print(body.strip() or "(empty body)")


def cmd_note_find(args):
    v = _need_vault()
    _validate_page_arguments(args, default_limit=50)
    hits = views.search(v, args.query)
    if args.json_page:
        try:
            page = _page_items(
                hits,
                view="note-find",
                limit=args.limit,
                cursor=args.cursor,
                all_items=args.all,
                query={"query": args.query},
                summary={"by_backend": _counts(hits, "backend")},
            )
        except ValueError as exc:
            sys.exit(str(exc))
        print(json.dumps(page, indent=2, ensure_ascii=False, sort_keys=True))
        return
    if not hits:
        print(f"No notes matching '{args.query}'.")
        return
    for h in hits[:50]:
        print(f"  {h['id']:<26} {h['title']}  ({h['path']})")
    if len(hits) > 50:
        print(f"Showing 50 of {len(hits)}. Use --json-page to continue or --json-page --all.")


def cmd_note_status(args):
    _reject_todo_mutation(args.id)
    v = _need_vault()
    _require_confirmation_flag(args, v, "note_status")
    try:
        res = notes_mod.set_status(v, args.id, args.status)
    except ValueError as e:
        sys.exit(str(e))
    if not res:
        sys.exit(f"No note with id '{args.id}'.")
    old, new, path = res
    fm, _ = fmlib.read_note(path)
    usage_mod.set_result(
        args, subject_kind="note", subject_type=fm.get("type"),
        status_before=old, status_after=new,
        outcome="status_changed" if old != new else "no_change",
        changed=old != new, count=1,
    )
    print(f"{args.id}: status {old} → {new}")


def cmd_note_edit(args):
    _reject_todo_mutation(args.id)
    if args.project is not None and args.resource is not None:
        sys.exit("--project cannot be combined with --resource.")
    if args.inbox and any(value is not None for value in (args.project, args.area, args.resource)):
        sys.exit("--inbox cannot be combined with --project, --area, or --resource.")
    v = _need_vault()
    changes = {}
    for attr, key in (
        ("title", "title"),
        ("description", "description"),
        ("type", "type"),
        ("status", "status"),
        ("effort_cadence", "effort_cadence"),
        ("effort_level", "effort_level"),
        ("source", "source"),
        ("author", "author"),
        ("link", "link"),
        ("chosen_location", "chosen_location"),
    ):
        value = getattr(args, attr)
        if value is not None:
            changes[key] = value
    clear_fields = []
    if args.clear_link:
        clear_fields.append("link")
    if args.clear_chosen_location:
        clear_fields.append("chosen_location")
    if args.clear_effort:
        clear_fields.extend(("effort_cadence", "effort_level"))
    if args.tags is not None:
        changes["tags"] = _split_tags(args.tags)
    if args.clear_tags:
        clear_fields.append("tags")
    if args.project is not None:
        changes["project"] = args.project
        clear_fields.append("resource")
    if args.resource is not None:
        changes["resource"] = args.resource
        clear_fields.append("project")
    if args.area is not None:
        changes["area"] = args.area
    for clear, field in (
        (args.clear_project, "project"),
        (args.clear_area, "area"),
        (args.clear_resource, "resource"),
    ):
        if clear:
            clear_fields.append(field)
    replace_body = args.body is not None or args.stdin
    try:
        plan = notes_mod.plan_note_edit(
            v,
            args.id,
            changes=changes,
            clear_fields=clear_fields,
            inbox=args.inbox,
            replacement_body=_read_body(args) if replace_body else None,
            replace_body=replace_body,
            expected_plan_hash=args.plan_hash,
        )
        confirmation_required = _confirmation_required(v, "note_edit")
        policy_preview = confirmation_required and not args.plan_hash and not args.dry_run
        if not args.dry_run and not policy_preview:
            result = notes_mod.apply_note_edit(v, plan)
        else:
            result = None
    except (OSError, ValueError) as e:
        sys.exit(str(e))
    before = plan["frontmatter_before"]
    after = plan["frontmatter_after"]
    if args.dry_run or policy_preview:
        effective, outcome, changed = before, "dry_run", False
    elif result is None:
        effective, outcome, changed = before, "no_change", False
    else:
        effective, outcome, changed = after, "edited", True
    usage_mod.set_result(
        args, subject_kind="note", subject_type=effective.get("type"),
        status_before=before.get("status"), status_after=effective.get("status"),
        outcome=outcome, changed=changed, count=1,
    )
    public_plan = notes_mod.public_note_edit_plan(plan)
    public_plan["confirmation_required"] = confirmation_required
    if args.json:
        print(json.dumps(public_plan, indent=2, ensure_ascii=False))
        return
    for warning in public_plan["warnings"]:
        print(f"Warning: {warning}", file=sys.stderr)
    if args.dry_run:
        print(f"Dry run: {public_plan['source_path']} → {public_plan['destination_path']}")
    elif policy_preview:
        print(f"Planned edit: {public_plan['source_path']} → {public_plan['destination_path']}")
        print(f"Plan hash: {public_plan['plan_sha256']}")
        print("Review the plan, then re-run with --plan-hash <plan_sha256>.")
    elif result is None:
        print("No changes requested.")
    elif result[1].reason:
        print(f"⚠ Edited {args.id} and routed to unsure: {public_plan['destination_path']}")
    else:
        print(f"Edited {args.id} → {public_plan['destination_path']}")


def cmd_note_ingest(args):
    if args.project is not None and args.resource is not None:
        sys.exit("--project cannot be combined with --resource.")
    v = _need_vault()
    try:
        confirmation_required = _confirmation_required(v, "note_ingest")
        policy_preview = confirmation_required and not args.yes and not args.dry_run
        if not args.dry_run and not policy_preview:
            notes_mod.recover_ingest_transaction(v)
        plan = notes_mod.plan_ingest(
            v,
            args.inbox_path,
            title=args.title,
            ntype=args.type,
            project=args.project,
            area=args.area,
            resource=args.resource,
            status=args.status,
            source=args.source,
            author=args.author,
            description=args.description,
            tags=_split_tags(args.tags),
            depth=args.depth,
            effort_cadence=args.effort_cadence,
            effort_level=args.effort_level,
            link=args.link,
            chosen_location=args.chosen_location,
            attachment=args.attachment,
            source_hash=args.source_hash,
        )
        if not args.dry_run and not policy_preview:
            notes_mod.apply_ingest(v, plan)
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
    fm = plan["frontmatter"]
    usage_mod.set_result(
        args, subject_kind="ingestion",
        subject_type=None if args.dry_run or policy_preview else fm.get("type"),
        status_after=None if args.dry_run or policy_preview else fm.get("status"),
        outcome="dry_run" if args.dry_run or policy_preview else "ingested",
        changed=not args.dry_run and not policy_preview, count=1, ingestion_kind=plan["kind"],
    )
    public_plan = notes_mod.public_ingest_plan(plan)
    public_plan["confirmation_required"] = confirmation_required
    if args.json:
        print(json.dumps(public_plan, indent=2, ensure_ascii=False))
        return
    for warning in public_plan["warnings"]:
        print(f"Warning: {warning}", file=sys.stderr)
    prefix = "Dry run" if args.dry_run else "Planned" if policy_preview else "Ingested"
    print(f"{prefix}: {public_plan['source_path']} → {public_plan['destination_path']}")
    if public_plan["attachment_path"]:
        print(f"Attachment: {public_plan['attachment_path']}")
    if not public_plan["triaged"]:
        print("Disposition: captured but not triaged; result remains in inbox.")
    if policy_preview:
        print("Review the plan, then re-run with --yes.")


def cmd_note_extract(args):
    if args.inbox and any((args.project, args.area, args.resource)):
        sys.exit("--inbox cannot be combined with --project, --area, or --resource.")
    v = _need_vault()
    _require_confirmation_flag(args, v, "note_extract")
    body = _read_body(args) if args.body is not None or args.stdin else args.title
    try:
        result = notes_mod.extract_note(
            v,
            args.linear_id,
            child_type=args.type,
            title=args.title,
            body=body,
            status=args.status,
            project=None if args.inbox else args.project,
            area=None if args.inbox else args.area,
            resource=None if args.inbox else args.resource,
            author=args.author,
            after=args.after,
        )
    except (OSError, ValueError) as e:
        sys.exit(str(e))
    child = notes_mod.find_note(v, result["child_id"])
    child_fm = child[1] if child else {}
    usage_mod.set_result(
        args, subject_kind="note", subject_type=child_fm.get("type"),
        status_after=child_fm.get("status"), outcome="extracted",
        changed=True, count=1,
    )
    child_rel = result["child_path"].relative_to(v.root).as_posix()
    source_rel = result["source_path"].relative_to(v.root).as_posix()
    if result["route_reason"]:
        print(f"Warning: child routed to unsure: {result['route_reason']}", file=sys.stderr)
    print(f"Extracted {result['child_id']} → {child_rel}")
    print(f"Updated {result['source_id']} → {source_rel} ({result['link']})")


def cmd_note_dissolve(args):
    v = _need_vault()
    try:
        confirmation_required = _confirmation_required(v, "note_dissolve")
    except ValueError as exc:
        sys.exit(str(exc))
    if confirmation_required and not args.yes:
        sys.exit("Dissolution is deliberate. Review the source and re-run with --yes to confirm.")
    before_hit = notes_mod.find_note(v, args.linear_id)
    try:
        result = notes_mod.dissolve_note(v, args.linear_id)
    except (OSError, ValueError) as e:
        sys.exit(str(e))
    fm, _ = fmlib.read_note(result["archive_path"])
    usage_mod.set_result(
        args, subject_kind="note", subject_type=fm.get("type"),
        status_before=before_hit[1].get("status") if before_hit else None,
        status_after=fm.get("status"), outcome="dissolved", changed=True, count=1,
    )
    archive_rel = result["archive_path"].relative_to(v.root).as_posix()
    print("CHANGE      ID                         PATH")
    print(f"dissolved   {result['source_id']:<26} {archive_rel}")
    for child_id in result["child_ids"]:
        print(f"preserved   {child_id:<26} parent={result['source_id']}")


def cmd_archive(args):
    _reject_todo_mutation(args.id)
    v = _need_vault()
    _require_confirmation_flag(args, v, "archive")
    before_hit = notes_mod.find_note(v, args.id)
    try:
        res = notes_mod.archive_note(v, args.id)
    except ValueError as e:
        sys.exit(str(e))
    if not res:
        sys.exit(f"No note with id '{args.id}'.")
    src, dest = res
    fm, _ = fmlib.read_note(dest)
    usage_mod.set_result(
        args, subject_kind="note", subject_type=fm.get("type"),
        status_before=before_hit[1].get("status") if before_hit else None,
        status_after=fm.get("status"), outcome="archived", changed=True, count=1,
    )
    print(f"Archived {args.id} → {dest.relative_to(v.root).as_posix()}")


def cmd_project_create(args):
    v = _need_vault()
    _require_confirmation_flag(args, v, "project_create")
    try:
        result = projects_mod.create_project(
            v,
            args.name,
            area=args.area,
            effort_cadence=args.effort_cadence,
            effort_level=args.effort_level,
        )
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
    usage_mod.set_result(
        args,
        subject_kind="project",
        outcome="created" if result["created"] else "no_change",
        changed=result["created"],
        count=1 if result["created"] else 0,
    )
    if result["name"] != result["slug"]:
        print(f"Name: {result['name']}")
    relpath = result["project_path"].relative_to(v.root).as_posix()
    if result["created"]:
        print(f"Created project '{result['slug']}' -> {relpath}/")
    else:
        print(f"Project '{result['slug']}' already exists -> {relpath}/")


def cmd_session_end(args):
    v = _need_vault()
    item_count = max(1, len(args.decision) + len(args.next_step))
    _require_confirmation_flag(args, v, "session_end", count=item_count)
    try:
        result = session_mod.end_session(
            v,
            project=args.project,
            area=args.area,
            summary=args.summary,
            decisions=args.decision,
            next_steps=args.next_step,
            memory_log=args.memory_log,
        )
    except ValueError as e:
        sys.exit(str(e))
    usage_mod.set_result(
        args, subject_kind="session", outcome="session_closed", changed=True, count=1,
    )
    if result["context_path"]:
        print(f"Updated context: {result['context_path'].relative_to(v.root).as_posix()}")
    if result["memory_path"]:
        print(f"Updated optional memory log: {result['memory_path'].relative_to(v.root).as_posix()}")


def cmd_tools_list(args):
    v = _need_vault()
    try:
        rows = tools_mod.list_tools(v, category=args.category, status=args.status)
    except ValueError as e:
        sys.exit(str(e))
    if not rows:
        print("No tools matched.")
        return
    for row in rows:
        ephemeral = "ephemeral" if row["ephemeral"] else "permanent"
        print(f"{row['name']:<16} {row['category']:<18} {row['status']:<10} {ephemeral:<10} {row['skill']}")


def cmd_tools_show(args):
    v = _need_vault()
    try:
        cfg = tools_mod.show_tool(v, args.name)
    except ValueError as e:
        sys.exit(str(e))
    if cfg is None:
        sys.exit(f"No tool named '{args.name}' in 06_indexes/tools.yaml.")
    print(json.dumps(cfg, indent=2, sort_keys=True))


def cmd_cron_run(args):
    if not args.tick:
        sys.exit("Use `arpent cron run --tick` to dispatch due cron jobs.")
    v = _need_vault()
    if not args.dry_run:
        _require_confirmation_flag(args, v, "cron_run")
    try:
        results = cron_mod.run_tick(
            v,
            dry_run=args.dry_run,
            allow_local_code=args.allow_local_code,
        )
    except (OSError, ValueError, json.JSONDecodeError) as e:
        sys.exit(str(e))
    if not results:
        print("No due cron jobs.")
        return
    for result in results:
        mode = "dry-run" if result["dry_run"] else f"exit {result['returncode']}"
        print(f"{result['id']}: {mode} - {result['command']}")
    failures = [result for result in results if not result["dry_run"] and result["returncode"] != 0]
    if failures:
        sys.exit(f"{len(failures)} cron job(s) failed.")


def cmd_sweep_ephemeral(args):
    v = _need_vault()
    if not args.dry_run:
        _require_confirmation_flag(args, v, "sweep_ephemeral")
    try:
        summary = sweep_mod.run_ephemeral(v, dry_run=args.dry_run)
    except (OSError, ValueError) as e:
        sys.exit(str(e))
    mode = "DRY RUN" if summary["dry_run"] else "APPLIED"
    print(f"Ephemeral sweep {mode} at {summary['run_at']} ({summary['result']})")
    print("TOOL              SCANNED  TRANSITIONS  ARCHIVED  TRACED  PROPOSED  SKIPPED  ERRORS")
    for name, counts in summary["tools"].items():
        print(
            f"{name:<17} {counts['scanned']:>7}  {counts['transitioned']:>7}  "
            f"{counts['archived']:>8}  {counts['traced']:>6}  {counts['proposed']:>8}  "
            f"{counts['skipped']:>7}  {counts['errors']:>6}"
        )
    if not summary["tools"]:
        print("No ephemeral tools with lifecycle rules are configured.")
    if summary["errors"]:
        sys.exit(f"Sweep completed with {summary['errors']} error(s); see 06_indexes/logs/sweep.log.")


def cmd_sweep_status(args):
    v = _need_vault()
    try:
        status = sweep_mod.latest_status(v)
    except (OSError, ValueError) as e:
        sys.exit(str(e))
    if status is None:
        print("No completed ephemeral sweep has been logged.")
        return
    if args.json:
        print(json.dumps(status, indent=2, sort_keys=True))
        return
    mode = ", dry run" if status.get("dry_run") else ""
    print(f"Last ephemeral sweep: {status['run_at']} ({status['result']}{mode})")
    print(
        f"Scanned {status['scanned']}; transitioned {status['transitioned']}; "
        f"archived {status['archived']}; traced {status['traced']}; "
        f"proposed {status['proposed']}; errors {status['errors']}"
    )


def cmd_health(args):
    v = _need_vault()
    metrics = views.health(v)
    usage_mod.set_result(args, subject_kind="vault", outcome="read", changed=False)
    if args.json:
        print(json.dumps(metrics, indent=2, sort_keys=True))
        return
    ratio = "n/a" if metrics["ratio"] is None else f"{metrics['ratio']:.2f}"
    print(f"Vault health - {metrics['period']}")
    print()
    print(f"Captures (input):       source in {{captured, imported}}  {metrics['input']:>6} notes")
    print(f"Reflections (output):   source in {{manual, derived}}     {metrics['output']:>6} notes")
    print(f"Integrations:           type: integration                {metrics['integrations']:>6} notes")
    print(f"Maps:                   type: map                        {metrics['maps']:>6} notes")
    print(f"Output/input ratio:                                      {ratio:>6}")
    print()
    print(f"Maturing > 90 days:                                     {metrics['maturing_over_90_days']:>6} notes")
    print(f"Stale:                                                   {metrics['stale']:>6} notes")
    print(f"Unresolved unsure:                                      {metrics['unresolved_unsure']:>6} items")
    if metrics["warning"]:
        print()
        print("Warning: captures substantially outpace reflections; consider reviewing captured material.")


def cmd_todo_add(args):
    v = _need_vault()
    try:
        plan = todo_mod.plan_todo_add(
            v,
            args.content,
            priority=args.priority,
            status=args.status,
            due_date=args.due_date,
            do_date=args.do_date,
            duration=args.duration,
            linked_project_id=args.linked_project_id,
            depends_on_id=args.depends_on_id,
            is_optional=args.is_optional,
            frequency=args.frequency,
            list_order=args.list_order,
            assignee_id=args.assignee_id,
            expected_plan_hash=args.plan_hash,
        )
    except (OSError, ValueError, sqlite3.Error) as exc:
        sys.exit(str(exc))
    try:
        confirmation_required = _confirmation_required(v, "todo_add")
    except ValueError as exc:
        sys.exit(str(exc))
    public_plan = todo_mod.public_todo_add_plan(plan)
    public_plan["confirmation_required"] = confirmation_required
    if args.dry_run or (confirmation_required and not args.plan_hash):
        if args.json:
            print(json.dumps(public_plan, indent=2, ensure_ascii=False, sort_keys=True))
        else:
            print(f"Planned todo → {plan['destination_path']}")
            print(f"Plan hash: {plan['plan_sha256']}")
            if confirmation_required and not args.dry_run:
                print("Review the plan, then re-run with --plan-hash <plan_sha256>.")
        usage_mod.set_result(
            args, subject_kind="todo", subject_type="checklist",
            status_after=plan["todo"]["status"], outcome="dry_run",
            changed=False, count=1,
        )
        return
    try:
        item = todo_mod.apply_todo_add(v, plan)
    except (OSError, ValueError, sqlite3.Error) as exc:
        sys.exit(str(exc))
    usage_mod.set_result(
        args, subject_kind="todo", subject_type="checklist",
        status_after=item["lifecycle_status"], outcome="added", changed=True, count=1,
    )
    if args.json:
        result = {
            "format": "arpent-todo-add-result",
            "version": 1,
            "id": item["id"],
            "path": item["path"],
            "todo": item,
            "plan_sha256": plan["plan_sha256"],
        }
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(f"Added {item['id']} → {item['path']}")


def cmd_todo_list(args):
    v = _need_vault()
    _validate_page_arguments(args, default_limit=50)
    try:
        rows = todo_mod.list_todos(
            v,
            status=args.status,
            include_archived=args.include_archived,
        )
    except (OSError, ValueError, sqlite3.Error) as exc:
        sys.exit(str(exc))
    if args.json_page:
        try:
            page = _page_items(
                rows,
                view="todo-list",
                limit=args.limit,
                cursor=args.cursor,
                all_items=args.all,
                query={"status": args.status, "include_archived": args.include_archived},
                summary={
                    "by_status": _counts(rows, "status"),
                    "by_lifecycle_status": _counts(rows, "lifecycle_status"),
                },
            )
        except ValueError as exc:
            sys.exit(str(exc))
        print(json.dumps(page, indent=2, ensure_ascii=False, sort_keys=True))
        return
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False, sort_keys=True))
        return
    if not rows:
        print("No todos matched.")
        return
    print(f"{'ID':<26} {'STATUS':<10} {'DO':<17} {'DUE':<17} {'PRIORITY':<14} CONTENT")
    for row in rows:
        status = row["lifecycle_status"] or row["status"]
        print(
            f"{row['id']:<26} {status:<10} {(row['do_date'] or '-'):<17} "
            f"{(row['due_date'] or '-'):<17} {(row['priority'] or '-'):<14} {row['content']}"
        )


def cmd_todo_show(args):
    v = _need_vault()
    try:
        item = todo_mod.show_todo(v, args.id)
    except (OSError, ValueError, sqlite3.Error) as exc:
        sys.exit(str(exc))
    if args.json:
        print(json.dumps(item, indent=2, ensure_ascii=False, sort_keys=True))
        return
    for key in (*todo_mod.SCHEMA_COLUMNS, "lifecycle_status", "path"):
        print(f"{key}: {item.get(key)}")


def cmd_todo_edit(args):
    changes = {}
    for argument, field in (
        ("content", "content"),
        ("priority", "priority"),
        ("status", "status"),
        ("due_date", "due_date"),
        ("do_date", "do_date"),
        ("duration", "duration"),
        ("linked_project_id", "linked_project_id"),
        ("depends_on_id", "depends_on_id"),
        ("frequency", "frequency"),
        ("list_order", "list_order"),
        ("assignee_id", "assignee_id"),
    ):
        value = getattr(args, argument)
        if value is not None:
            changes[field] = value
    for clear, field in (
        ("clear_priority", "priority"),
        ("clear_due", "due_date"),
        ("clear_do", "do_date"),
        ("clear_duration", "duration"),
        ("clear_project", "linked_project_id"),
        ("clear_dependency", "depends_on_id"),
        ("clear_frequency", "frequency"),
        ("clear_list_order", "list_order"),
        ("clear_assignee", "assignee_id"),
    ):
        if getattr(args, clear):
            changes[field] = None
    if args.is_optional is not None:
        changes["is_optional"] = args.is_optional

    v = _need_vault()
    _require_confirmation_flag(args, v, "todo_edit")
    try:
        item = todo_mod.edit_todo(v, args.id, **changes)
    except (OSError, ValueError, sqlite3.Error) as exc:
        sys.exit(str(exc))
    usage_mod.set_result(
        args, subject_kind="todo", subject_type="checklist",
        status_after=item["lifecycle_status"],
        outcome="edited" if item["changed"] else "no_change",
        changed=item["changed"], count=1,
    )
    if item["changed"]:
        print(f"Edited {item['id']} → {item['path']}")
    else:
        print("No todo values changed.")


def cmd_todo_done(args):
    v = _need_vault()
    _require_confirmation_flag(args, v, "todo_done")
    try:
        item = todo_mod.done_todo(v, args.id)
    except (OSError, ValueError, sqlite3.Error) as exc:
        sys.exit(str(exc))
    usage_mod.set_result(
        args, subject_kind="todo", subject_type="checklist", status_after="done",
        outcome="done", changed=item.get("changed", True), count=1,
    )
    print(f"{item['id']}: status → done ({item['path']})")


def cmd_todo_defer(args):
    v = _need_vault()
    _require_confirmation_flag(args, v, "todo_defer")
    try:
        item = todo_mod.defer_todo(v, args.id, args.to_date)
    except (OSError, ValueError, sqlite3.Error) as exc:
        sys.exit(str(exc))
    usage_mod.set_result(
        args, subject_kind="todo", subject_type="checklist",
        status_after=item["lifecycle_status"], outcome="deferred",
        changed=item.get("changed", True), count=1,
    )
    print(f"Deferred {item['id']} → {item['do_date']}")


def cmd_todo_block(args):
    v = _need_vault()
    _require_confirmation_flag(args, v, "todo_block")
    try:
        item = todo_mod.block_todo(v, args.id, args.dependency_id)
    except (OSError, ValueError, sqlite3.Error) as exc:
        sys.exit(str(exc))
    usage_mod.set_result(
        args, subject_kind="todo", subject_type="checklist", status_after="waiting",
        outcome="blocked", changed=item.get("changed", True), count=1,
    )
    print(f"Blocked {item['id']} on {item['depends_on_id']}")


def cmd_todo_archive(args):
    v = _need_vault()
    _require_confirmation_flag(args, v, "todo_archive")
    try:
        item = todo_mod.archive_todo(v, args.id)
    except (OSError, ValueError, sqlite3.Error) as exc:
        sys.exit(str(exc))
    usage_mod.set_result(
        args, subject_kind="todo", subject_type="checklist", status_before="done",
        status_after="archived", outcome="archived", changed=True, count=1,
    )
    print(f"Archived {item['id']} → {item['path']}")


def cmd_usage_report(args):
    v = _need_vault()
    try:
        report = usage_mod.usage_report(v, since=args.since)
    except ValueError as exc:
        sys.exit(str(exc))
    usage_mod.set_result(
        args, subject_kind="vault", outcome="read", changed=False,
        count=report["commands"]["total"],
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(usage_mod.format_report(report), end="")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _split_tags(raw):
    return [t.strip() for t in raw.split(",") if t.strip()] if raw else []


def _read_body(args):
    if getattr(args, "body", None):
        return args.body
    if getattr(args, "stdin", False):
        return sys.stdin.read()
    return ""


def _reject_todo_mutation(note_id):
    if todo_mod.is_todo_id(note_id):
        sys.exit(
            "Todo records are tool-owned. Use `arpent todo edit`, `done`, "
            "`block`, or `archive`."
        )


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="arpent",
        description="Arpent - a filesystem-native personal LifeOS.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Capture loop:
  arpent note new <title> ... --json
  Run status, triage, index, or search only when the current task needs them.

Composed continuity loop (no synthetic resume command):
  capture: arpent note new ... or arpent note ingest ...
  resume:  read me.md, then the target _context.md, then only needed notes/sources; never read MEMORY.md by default
  produce: continue useful work with the semantically correct note type and status
  close:   arpent session end --summary ... [--project ...] [--area ...]

Create a deliberate project destination with: arpent project create <name>""",
    )
    p.add_argument("--version", action="version", version=f"arpent {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser(
        "init",
        help="scaffold a full or minimal filesystem-native LifeOS vault",
        description=(
            "Scaffold a vault. Full mode initializes Git without creating a commit; "
            "minimal mode requires neither Git nor later CLI operation. "
            "Projects remain deliberate: create them afterward with `arpent project create`, "
            "or declare them explicitly with `--structure`."
        ),
    )
    sp.add_argument("path", nargs="?", default=".", help="vault directory (default: .)")
    sp.add_argument(
        "--minimal",
        action="store_true",
        help=(
            "seed the complete vault and skills for direct-file operation; "
            "the CLI remains inactive except for changing mode"
        ),
    )
    sp.add_argument(
        "--structure",
        metavar="FILE",
        help="create Areas, Resources, and/or projects declared in a .json or .md file",
    )
    sp.set_defaults(func=cmd_init)

    skill = sub.add_parser(
        "skill",
        help="install the host-neutral Arpent agent skill bundle",
    ).add_subparsers(dest="skill_cmd", required=True)
    sk = skill.add_parser(
        "install",
        help="copy the complete bundle to one exact directory",
    )
    sk.add_argument(
        "--to",
        required=True,
        help="exact destination directory; never host-inferred",
    )
    sk.add_argument(
        "--replace",
        action="store_true",
        help="explicitly replace an existing directory after validating the new bundle",
    )
    sk.add_argument("--json", action="store_true", help="emit a versioned install result")
    sk.set_defaults(func=cmd_skill_install)

    mode = sub.add_parser(
        "mode",
        help="show or change how this vault is operated",
    ).add_subparsers(dest="mode_cmd", required=True)
    m = mode.add_parser("show", help="show the active vault mode")
    m.add_argument("--json", action="store_true")
    m.set_defaults(func=cmd_mode_show)
    for mode_name in ("full", "minimal"):
        m = mode.add_parser(mode_name, help=f"switch this vault to {mode_name} mode")
        m.add_argument("--yes", action="store_true", help=CONFIRMATION_HELP)
        m.add_argument("--json", action="store_true")
        m.set_defaults(func=cmd_mode_set)

    import_commands = sub.add_parser(
        "import",
        help="scan, review, and resumably import an external filesystem tree",
        description=(
            "Build a read-only inventory and reviewable folder plan, then copy sources "
            "into canonical Arpent destinations without modifying the external tree."
        ),
    ).add_subparsers(dest="import_cmd", required=True)

    imp = import_commands.add_parser("scan", help="scan an external directory without changing it")
    imp.add_argument("source")
    imp.add_argument("--output", required=True, help="new plan.json path")
    imp.add_argument("--force", action="store_true", help="replace an existing plan and inventory")
    imp.add_argument("--json", action="store_true")
    imp.set_defaults(func=cmd_import_scan)

    imp = import_commands.add_parser("suggest", help="refresh deterministic folder suggestions")
    imp.add_argument("plan")
    imp.add_argument("--json", action="store_true")
    imp.set_defaults(func=cmd_import_suggest)

    imp = import_commands.add_parser("review", help="review folder roles interactively")
    imp.add_argument("plan")
    imp.add_argument(
        "--accept-suggestions",
        action="store_true",
        help="accept suggestions non-interactively instead of asking folder questions",
    )
    imp.add_argument(
        "--minimum-confidence",
        type=float,
        default=0.0,
        help="with --accept-suggestions, leave lower-confidence folders unresolved (0-1)",
    )
    imp.add_argument("--yes", action="store_true", help="confirm marking a complete interactive review")
    imp.add_argument("--json", action="store_true")
    imp.set_defaults(func=cmd_import_review)

    imp = import_commands.add_parser("validate", help="validate decisions and inventory integrity")
    imp.add_argument("plan")
    imp.add_argument("--sources", action="store_true", help="rehash every external source file")
    imp.add_argument("--json", action="store_true")
    imp.set_defaults(func=cmd_import_validate)

    imp = import_commands.add_parser("summary", help="summarize reviewed roles and unresolved folders")
    imp.add_argument("plan")
    imp.add_argument("--json", action="store_true")
    imp.set_defaults(func=cmd_import_summary)

    imp = import_commands.add_parser("apply", help="preview or apply a reviewed import plan")
    imp.add_argument("plan")
    imp.add_argument("--dry-run", action="store_true")
    imp.add_argument("--yes", action="store_true", help="provide policy confirmation without an interactive prompt")
    imp.add_argument("--plan-hash", default=None, help="apply only if decisions and routing match a reviewed dry run")
    imp.add_argument("--stop-on-error", action="store_true")
    imp.add_argument("--json", action="store_true")
    _add_page_arguments(imp, default_limit=50)
    imp.set_defaults(func=cmd_import_apply)

    imp = import_commands.add_parser("status", help="show resumable application progress")
    imp.add_argument("plan")
    imp.add_argument("--json", action="store_true")
    imp.set_defaults(func=cmd_import_status)

    sub.add_parser("status", help="show vault state").set_defaults(func=cmd_status)
    sp = sub.add_parser("index", help="inventory the vault and rebuild generated indexes")
    sp.add_argument("--yes", action="store_true", help=CONFIRMATION_HELP)
    sp.set_defaults(func=cmd_index)
    sp = sub.add_parser(
        "triage",
        help="inventory inbox items for an agent-mediated plan/apply pass",
        description=(
            "Inventory every non-fleeting inbox item without moving it. Use the result "
            "to propose one policy-governed plan, then apply structured edits or raw ingestion "
            "per item and re-run triage; report partial batches honestly."
        ),
    )
    sp.add_argument("--json", action="store_true", help="emit stable item details, hashes, ages, and available actions")
    _add_page_arguments(sp, default_limit=50)
    sp.set_defaults(func=cmd_triage)
    sp = sub.add_parser("efforts", help="active actionables by effort cadence and level")
    _add_page_arguments(sp, default_limit=100)
    sp.set_defaults(func=cmd_efforts)
    sp = sub.add_parser("backup", help="create, verify, or restore a complete logical vault snapshot")
    sp.add_argument(
        "--destination",
        default=None,
        help="snapshot parent directory (default: 06_indexes/backup/)",
    )
    sp.add_argument("--yes", dest="backup_yes", action="store_true", help=CONFIRMATION_HELP)
    sp.set_defaults(func=cmd_backup)
    backup = sp.add_subparsers(dest="backup_cmd")
    b = backup.add_parser("verify", help="verify a snapshot manifest, payload, and databases")
    b.add_argument("snapshot")
    b.set_defaults(func=cmd_backup_verify)
    b = backup.add_parser("restore", help="restore a verified snapshot into a new directory")
    b.add_argument("snapshot")
    b.add_argument("--to", required=True, help="new target directory; must not exist")
    b.add_argument("--yes", action="store_true", help=CONFIRMATION_HELP)
    b.set_defaults(func=cmd_backup_restore)
    sp = sub.add_parser("health", help="show live vault density and lifecycle metrics")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_health)

    usage = sub.add_parser("usage", help="local privacy-preserving usage reporting").add_subparsers(
        dest="usage_cmd", required=True,
    )
    u = usage.add_parser(
        "report",
        help="report v2 command events and current triage age",
        description=(
            "Report local privacy-allowlisted command metrics and current triage age. "
            "Documentary resume reads and resume quality are unavailable metrics and "
            "belong in usage-journal.md."
        ),
    )
    u.add_argument("--since", default=None, help="include events on or after this dd-MM-YYYY-HH-mm UTC timestamp")
    u.add_argument("--json", action="store_true")
    u.set_defaults(func=cmd_usage_report)

    sp = sub.add_parser("search", help="keyword search across the vault")
    sp.add_argument("query")
    _add_page_arguments(sp, default_limit=50)
    sp.set_defaults(func=cmd_search)

    context = sub.add_parser(
        "context",
        help="optional L0/L1/L2 context-summary module",
    ).add_subparsers(dest="context_cmd", required=True)
    c = context.add_parser("pending", help="list missing or stale optional L1 summaries")
    c.add_argument("--kind", choices=("folder", "note", "text"), default=None)
    c.add_argument("--path", default=None, help="limit results to a relative path")
    c.add_argument("--json", action="store_true")
    _add_page_arguments(c, default_limit=100)
    c.set_defaults(func=cmd_context_pending)

    c = context.add_parser("set", help="store an AI-generated L1 summary")
    c.add_argument("path", help="indexed path relative to the vault")
    summary_input = c.add_mutually_exclusive_group(required=True)
    summary_input.add_argument("--summary", default=None)
    summary_input.add_argument("--stdin", action="store_true")
    c.add_argument("--source-hash", required=True, help="hash returned by context pending")
    c.add_argument("--provider", default="agent", help="agent or provider identifier")
    c.add_argument("--force", action="store_true", help="replace an already-fresh L1 summary")
    c.add_argument("--yes", action="store_true", help=CONFIRMATION_HELP)
    c.set_defaults(func=cmd_context_set)

    c = context.add_parser("show", help="read one context level for an indexed path")
    c.add_argument("path", help="indexed path relative to the vault")
    c.add_argument("--level", choices=("l0", "l1", "l2"), default="l0")
    c.add_argument("--json-page", action="store_true", help="emit bounded structured L2 content")
    c.add_argument("--limit", type=_positive_int, default=200, help="folder-child page size")
    c.add_argument("--max-bytes", type=_positive_int, default=32 * 1024, help="UTF-8 source bytes per page")
    c.add_argument("--cursor", default=None)
    c.add_argument("--full", action="store_true", help="emit the complete L2 source or child list")
    c.set_defaults(func=cmd_context_show)

    sp = sub.add_parser("archive", help="archive a note by id (never deletes)")
    sp.add_argument("id")
    sp.add_argument("--yes", action="store_true", help=CONFIRMATION_HELP)
    sp.set_defaults(func=cmd_archive)

    project = sub.add_parser("project", help="deliberate project operations").add_subparsers(
        dest="project_cmd", required=True,
    )
    pr = project.add_parser(
        "create",
        help="create a project and its complete canonical context",
        description=(
            "Create 01_projects/<slug>/ with complete universal-frontmatter "
            "_context.md, notes/, drafts/, and "
            "attachments/. Human names normalize to lowercase ASCII kebab-case; "
            "existing destinations are never merged or overwritten."
        ),
    )
    pr.add_argument("name", help="human project name; normalized to an ASCII kebab-case slug")
    pr.add_argument("--area", default=None, help="existing unambiguous area slug")
    pr.add_argument("--effort-cadence", choices=notes_mod.EFFORT_CADENCES, default=None)
    pr.add_argument("--effort-level", choices=notes_mod.EFFORT_LEVELS, default=None)
    pr.add_argument("--yes", action="store_true", help=CONFIRMATION_HELP)
    pr.set_defaults(func=cmd_project_create)

    note = sub.add_parser("note", help="note operations").add_subparsers(dest="note_cmd", required=True)

    n = note.add_parser("new", help="create and route a note")
    n.add_argument("title")
    n.add_argument("--type", default="note", help=f"one of: {', '.join(routing.TYPES)}")
    n.add_argument("--status", default=None, help=f"one of: {', '.join(routing.STATUSES)}")
    n.add_argument("--effort-cadence", choices=notes_mod.EFFORT_CADENCES, default=None)
    n.add_argument("--effort-level", choices=notes_mod.EFFORT_LEVELS, default=None)
    n.add_argument("--project", default=None)
    n.add_argument("--area", default=None)
    n.add_argument("--resource", default=None)
    n.add_argument("--tags", default=None, help="comma-separated")
    n.add_argument("--source", default="manual", help=f"one of: {', '.join(routing.SOURCES)}")
    n.add_argument("--author", default="user", help=f"one of: {', '.join(routing.AUTHORS)}")
    n.add_argument("--description", default=None)
    n.add_argument("--link", default=None)
    n.add_argument("--chosen-location", dest="chosen_location", default=None)
    n.add_argument("--body", default=None)
    n.add_argument("--stdin", action="store_true", help="read body from stdin")
    n.add_argument("--dry-run", action="store_true", help="show the complete creation plan without mutation")
    n.add_argument("--plan-hash", default=None, help=PLAN_HASH_HELP)
    n.add_argument("--json", action="store_true", help="emit a versioned creation plan or result")
    n.set_defaults(func=cmd_note_new)

    n = note.add_parser("route", help="re-route an existing note")
    n.add_argument("id")
    n.add_argument("--project", default=None)
    n.add_argument("--area", default=None)
    n.add_argument("--resource", default=None)
    n.add_argument("--yes", action="store_true", help=CONFIRMATION_HELP)
    n.set_defaults(func=cmd_note_route)

    n = note.add_parser("read", help="print a note by id")
    n.add_argument("id")
    n.add_argument("--json-page", action="store_true", help="emit bounded structured body content")
    n.add_argument("--max-bytes", type=_positive_int, default=32 * 1024)
    n.add_argument("--cursor", default=None)
    n.add_argument("--full", action="store_true", help="emit the complete body in structured form")
    n.set_defaults(func=cmd_note_read)

    n = note.add_parser("find", help="find notes by keyword")
    n.add_argument("query")
    _add_page_arguments(n, default_limit=50)
    n.set_defaults(func=cmd_note_find)

    n = note.add_parser("status", help="change a note's status")
    n.add_argument("id")
    n.add_argument("status")
    n.add_argument("--yes", action="store_true", help=CONFIRMATION_HELP)
    n.set_defaults(func=cmd_note_status)

    n = note.add_parser(
        "edit",
        help="plan or apply a structured-note edit and routing change",
        description=(
            "Plan and apply from the same current note state. Use --dry-run to inspect "
            "complete before/after frontmatter, paths, body-change state, and warnings; "
            "add --json for machine-readable output."
        ),
    )
    n.add_argument("id")
    n.add_argument("--title", default=None)
    n.add_argument("--description", default=None)
    n.add_argument("--type", default=None, help=f"one of: {', '.join(routing.TYPES)}")
    n.add_argument("--status", default=None, help=f"one of: {', '.join(routing.STATUSES)}")
    n.add_argument("--effort-cadence", choices=notes_mod.EFFORT_CADENCES, default=None)
    n.add_argument("--effort-level", choices=notes_mod.EFFORT_LEVELS, default=None)
    n.add_argument("--clear-effort", action="store_true")
    n.add_argument("--tags", default=None, help="replace tags with comma-separated values")
    n.add_argument("--clear-tags", action="store_true")
    n.add_argument("--source", default=None, help=f"one of: {', '.join(routing.SOURCES)}")
    n.add_argument("--author", default=None, help=f"one of: {', '.join(routing.AUTHORS)}")
    n.add_argument("--link", default=None)
    n.add_argument("--clear-link", action="store_true")
    n.add_argument("--chosen-location", dest="chosen_location", default=None)
    n.add_argument("--clear-chosen-location", action="store_true")
    n.add_argument("--project", default=None)
    n.add_argument("--area", default=None)
    n.add_argument("--resource", default=None)
    n.add_argument("--clear-project", action="store_true")
    n.add_argument("--clear-area", action="store_true")
    n.add_argument("--clear-resource", action="store_true")
    n.add_argument("--inbox", action="store_true", help="clear project/area/resource")
    n.add_argument("--body", default=None)
    n.add_argument("--stdin", action="store_true", help="replace body from stdin")
    n.add_argument("--dry-run", action="store_true", help="show exact before/after metadata and paths without domain mutation")
    n.add_argument("--json", action="store_true", help="print the edit plan as JSON")
    n.add_argument("--plan-hash", default=None, help=PLAN_HASH_HELP)
    n.set_defaults(func=cmd_note_edit)

    n = note.add_parser(
        "ingest",
        help="losslessly plan or ingest a raw inbox file",
        description=(
            "Convert UTF-8 text or malformed frontmatter into a complete structured "
            "note, preserving all source text. A binary stays byte-for-byte untouched "
            "and cannot contain YAML; --attachment moves it to the selected home's "
            "attachments/ and creates a separate Markdown companion reference note."
        ),
    )
    n.add_argument("inbox_path", help="vault-relative file path under 00_inbox/")
    n.add_argument("--title", required=True)
    n.add_argument("--type", default=None, help="defaults to note for text and reference for attachments")
    n.add_argument("--status", default=None, help=f"one of: {', '.join(routing.STATUSES)}")
    n.add_argument("--effort-cadence", choices=notes_mod.EFFORT_CADENCES, default=None)
    n.add_argument("--effort-level", choices=notes_mod.EFFORT_LEVELS, default=None)
    n.add_argument("--project", default=None)
    n.add_argument("--area", default=None)
    n.add_argument("--resource", default=None)
    n.add_argument("--source", default="manual", help=f"one of: {', '.join(routing.SOURCES)}")
    n.add_argument("--author", default="user", help=f"one of: {', '.join(routing.AUTHORS)}")
    n.add_argument("--description", default=None)
    n.add_argument("--link", default=None)
    n.add_argument("--chosen-location", dest="chosen_location", default=None)
    n.add_argument("--tags", default=None, help="comma-separated")
    n.add_argument("--depth", type=int, choices=range(1, 6), default=None)
    n.add_argument("--attachment", action="store_true", help="move a binary source into the selected home's attachments folder")
    n.add_argument("--source-hash", default=None, help="reject apply unless the source still has this SHA-256")
    n.add_argument("--dry-run", action="store_true", help="show exact paths and metadata without mutation")
    n.add_argument("--json", action="store_true", help="print the ingestion plan as JSON")
    n.add_argument("--yes", action="store_true", help=CONFIRMATION_HELP)
    n.set_defaults(func=cmd_note_ingest)

    n = note.add_parser("extract", help="extract a typed child from a linear note")
    n.add_argument("linear_id")
    n.add_argument("--type", required=True, choices=notes_mod.EXTRACTABLE_TYPES)
    n.add_argument("--title", required=True)
    n.add_argument("--status", default=None, choices=routing.STATUSES)
    n.add_argument("--author", default="user", choices=routing.AUTHORS)
    n.add_argument("--project", default=None)
    n.add_argument("--area", default=None)
    n.add_argument("--resource", default=None)
    n.add_argument("--inbox", action="store_true")
    body_input = n.add_mutually_exclusive_group()
    body_input.add_argument("--body", default=None, help="autonomous child-note body")
    body_input.add_argument("--stdin", action="store_true", help="read the child-note body from stdin")
    n.add_argument("--after", default=None, help="insert the source wikilink after this exact passage")
    n.add_argument("--yes", action="store_true", help=CONFIRMATION_HELP)
    n.set_defaults(func=cmd_note_extract)

    n = note.add_parser("dissolve", help="archive a decomposed linear note")
    n.add_argument("linear_id")
    n.add_argument("--yes", action="store_true", help="confirm the deliberate dissolution")
    n.set_defaults(func=cmd_note_dissolve)

    session = sub.add_parser("session", help="local continuity operations").add_subparsers(dest="session_cmd", required=True)
    s = session.add_parser(
        "end",
        help="close a session into context and an optional explicit memory log",
        description=(
            "By default, record summary, decisions, and next steps in project/area "
            "_context.md. The cross-project MEMORY.md log is disabled unless "
            "--memory-log is passed, and agents must not read it later without a separate "
            "explicit read request. A no-target close requires --memory-log. "
            "This CLI operation is full-mode only."
        ),
    )
    s.add_argument("--project", default=None)
    s.add_argument("--area", default=None, help="owning area or area-only session target")
    s.add_argument("--summary", required=True)
    s.add_argument("--decision", action="append", default=[])
    s.add_argument("--next-step", action="append", default=[])
    s.add_argument("--memory-log", action="store_true", help="request one create or update of the optional cross-project MEMORY.md log")
    s.add_argument("--yes", action="store_true", help=CONFIRMATION_HELP)
    s.set_defaults(func=cmd_session_end)

    tools = sub.add_parser("tools", help="tools registry operations").add_subparsers(dest="tools_cmd", required=True)
    t = tools.add_parser("list", help="list registered tools")
    t.add_argument("--category", default=None)
    t.add_argument("--status", default=None)
    t.set_defaults(func=cmd_tools_list)
    t = tools.add_parser("show", help="show one registered tool")
    t.add_argument("name")
    t.set_defaults(func=cmd_tools_show)

    cron = sub.add_parser("cron", help="cron registry operations").add_subparsers(dest="cron_cmd", required=True)
    c = cron.add_parser("run", help="run cron jobs")
    c.add_argument("--tick", action="store_true", help="run due jobs from cron.json")
    c.add_argument("--dry-run", action="store_true")
    c.add_argument("--yes", action="store_true", help="confirm execution when required by the local policy")
    c.add_argument(
        "--allow-local-code",
        action="store_true",
        help="enable execution of jobs carrying the local-code declaration",
    )
    c.set_defaults(func=cmd_cron_run)

    sweep = sub.add_parser("sweep", help="lifecycle sweep operations").add_subparsers(dest="sweep_cmd", required=True)
    sw = sweep.add_parser("ephemeral", help="apply configured ephemeral lifecycle rules")
    sw.add_argument("--dry-run", action="store_true")
    sw.add_argument("--yes", action="store_true", help=CONFIRMATION_HELP)
    sw.set_defaults(func=cmd_sweep_ephemeral)
    sw = sweep.add_parser("status", help="show the latest completed ephemeral sweep")
    sw.add_argument("--json", action="store_true")
    sw.set_defaults(func=cmd_sweep_status)

    todo = sub.add_parser("todo", help="SQLite-backed todo operations").add_subparsers(
        dest="todo_cmd", required=True
    )
    td = todo.add_parser("add", help="create a todo and its Markdown record")
    td.add_argument("content")
    td.add_argument("--priority", default=None)
    td.add_argument("--status", choices=todo_mod.TODO_STATUSES, default=None)
    td.add_argument("--due", dest="due_date", default=None, help="dd-MM-YYYY-HH-mm UTC")
    td.add_argument("--do", dest="do_date", default=None, help="dd-MM-YYYY-HH-mm UTC")
    td.add_argument("--duration", default=None)
    td.add_argument("--project", dest="linked_project_id", default=None)
    td.add_argument("--depends-on", dest="depends_on_id", default=None)
    td.add_argument("--optional", dest="is_optional", action="store_true")
    td.add_argument("--frequency", default=None)
    td.add_argument("--list-order", default=None)
    td.add_argument("--assignee", dest="assignee_id", default=None)
    td.add_argument("--dry-run", action="store_true", help="show the complete todo plan without mutation")
    td.add_argument("--plan-hash", default=None, help=PLAN_HASH_HELP)
    td.add_argument("--json", action="store_true", help="emit a versioned creation plan or result")
    td.set_defaults(func=cmd_todo_add)

    td = todo.add_parser("list", help="list current todos")
    td.add_argument("--status", choices=todo_mod.TODO_STATUSES, default=None)
    td.add_argument("--include-archived", action="store_true")
    td.add_argument("--json", action="store_true")
    _add_page_arguments(td, default_limit=50)
    td.set_defaults(func=cmd_todo_list)

    td = todo.add_parser("show", help="show one todo")
    td.add_argument("id")
    td.add_argument("--json", action="store_true")
    td.set_defaults(func=cmd_todo_show)

    td = todo.add_parser("edit", help="edit todo fields")
    td.add_argument("id")
    td.add_argument("--content", default=None)
    priority = td.add_mutually_exclusive_group()
    priority.add_argument("--priority", default=None)
    priority.add_argument("--clear-priority", action="store_true")
    td.add_argument("--status", choices=todo_mod.TODO_STATUSES, default=None)
    due = td.add_mutually_exclusive_group()
    due.add_argument("--due", dest="due_date", default=None, help="dd-MM-YYYY-HH-mm UTC")
    due.add_argument("--clear-due", action="store_true")
    do_date = td.add_mutually_exclusive_group()
    do_date.add_argument("--do", dest="do_date", default=None, help="dd-MM-YYYY-HH-mm UTC")
    do_date.add_argument("--clear-do", action="store_true")
    duration = td.add_mutually_exclusive_group()
    duration.add_argument("--duration", default=None)
    duration.add_argument("--clear-duration", action="store_true")
    project = td.add_mutually_exclusive_group()
    project.add_argument("--project", dest="linked_project_id", default=None)
    project.add_argument("--clear-project", action="store_true")
    dependency = td.add_mutually_exclusive_group()
    dependency.add_argument("--depends-on", dest="depends_on_id", default=None)
    dependency.add_argument("--clear-dependency", action="store_true")
    optional = td.add_mutually_exclusive_group()
    optional.add_argument("--optional", dest="is_optional", action="store_true")
    optional.add_argument("--required", dest="is_optional", action="store_false")
    optional.set_defaults(is_optional=None)
    frequency = td.add_mutually_exclusive_group()
    frequency.add_argument("--frequency", default=None)
    frequency.add_argument("--clear-frequency", action="store_true")
    order = td.add_mutually_exclusive_group()
    order.add_argument("--list-order", default=None)
    order.add_argument("--clear-list-order", action="store_true")
    assignee = td.add_mutually_exclusive_group()
    assignee.add_argument("--assignee", dest="assignee_id", default=None)
    assignee.add_argument("--clear-assignee", action="store_true")
    td.add_argument("--yes", action="store_true", help=CONFIRMATION_HELP)
    td.set_defaults(func=cmd_todo_edit)

    td = todo.add_parser("done", help="mark a todo done")
    td.add_argument("id")
    td.add_argument("--yes", action="store_true", help=CONFIRMATION_HELP)
    td.set_defaults(func=cmd_todo_done)

    td = todo.add_parser("defer", help="set the UTC time at which to do a todo")
    td.add_argument("id")
    td.add_argument("--to", dest="to_date", required=True, help="dd-MM-YYYY-HH-mm UTC")
    td.add_argument("--yes", action="store_true", help=CONFIRMATION_HELP)
    td.set_defaults(func=cmd_todo_defer)

    td = todo.add_parser("block", help="mark a todo waiting on an object ID")
    td.add_argument("id")
    td.add_argument("--on", dest="dependency_id", required=True)
    td.add_argument("--yes", action="store_true", help=CONFIRMATION_HELP)
    td.set_defaults(func=cmd_todo_block)

    td = todo.add_parser("archive", help="archive a completed todo without deleting its DB row")
    td.add_argument("id")
    td.add_argument("--yes", action="store_true", help=CONFIRMATION_HELP)
    td.set_defaults(func=cmd_todo_archive)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    started_at, started_monotonic = usage_mod.start_timing()
    exit_code = 1
    success = False
    try:
        with _vault_mode_guard(args):
            args.func(args)
        exit_code = 0
        success = True
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
        success = exit_code == 0
        raise
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"arpent: {exc}", file=sys.stderr)
        exit_code = 1
        success = False
    except BaseException:
        exit_code = 1
        raise
    finally:
        usage_mod.append_usage(
            args,
            exit_code=exit_code,
            success=success,
            started_at=started_at,
            started_monotonic=started_monotonic,
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

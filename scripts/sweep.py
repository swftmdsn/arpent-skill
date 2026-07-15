"""Ephemeral lifecycle processing driven by the tools registry."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import file_transaction
from . import frontmatter as fmlib
from . import notes as notes_mod
from . import routing
from . import todo as todo_mod
from . import tools as tools_mod


PROTECTED_STATUSES = {"active", "stable", "ongoing"}
ARCHIVE_ACTIONS = {"archive", "archive-with-trace", "delete-after-review"}
ALLOWED_WRITE_BUCKETS = {"00_inbox", "01_projects", "02_areas", "03_resources", "05_tools"}
MAX_AFTER_DAYS = 999_999_999
TRANSACTION_RELPATH = "06_indexes/logs/sweep-transaction.json"


def run_ephemeral(vault, *, dry_run=False, now=None) -> dict:
    """Apply at most one due lifecycle rule to each configured note."""
    now = _aware_utc(now or datetime.now(timezone.utc))
    plans = _load_plans(vault)
    timestamp = _iso(now)
    summary = {
        "event": "summary",
        "run_at": timestamp,
        "dry_run": bool(dry_run),
        "result": "ok",
        "scanned": 0,
        "transitioned": 0,
        "archived": 0,
        "traced": 0,
        "proposed": 0,
        "skipped": 0,
        "errors": 0,
        "tools": {},
    }
    events = []

    with vault.exclusive_lock("mutations"), _sweep_lock(vault, timestamp):
        _recover_sweep_transaction(vault)
        vault.refuse_foreign_transactions()
        _check_log_writable(vault)
        all_notes = list(vault.iter_notes())
        for plan in plans:
            tool_counts = {
                "scanned": 0,
                "transitioned": 0,
                "archived": 0,
                "traced": 0,
                "proposed": 0,
                "skipped": 0,
                "errors": 0,
            }
            summary["tools"][plan["name"]] = tool_counts
            existing_roots = [root for root in plan["roots"] if root.exists()]
            missing_roots = len(plan["roots"]) - len(existing_roots)
            tool_counts["skipped"] += missing_roots
            summary["skipped"] += missing_roots

            owned = []
            for note in all_notes:
                path = note[0]
                root = next((candidate for candidate in existing_roots if _is_under(path, candidate)), None)
                if root is not None:
                    owned.append((*note, root))

            for path, fm, body, root in sorted(owned, key=lambda row: row[0].as_posix()):
                tool_counts["scanned"] += 1
                summary["scanned"] += 1
                rel = path.relative_to(vault.root).as_posix()
                foundational_area_note = (
                    rel.startswith("02_areas/") and path.name == "philosophy.md"
                )
                if (
                    path.name == "_context.md"
                    or foundational_area_note
                    or fm.get("type") in {"map", "linear"}
                    or fm.get("status") in PROTECTED_STATUSES
                ):
                    tool_counts["skipped"] += 1
                    summary["skipped"] += 1
                    continue

                try:
                    rule = _due_rule(fm, plan["rules"], now)
                    if rule is None:
                        continue
                    event = _apply_rule(
                        vault,
                        plan,
                        root,
                        path,
                        fm,
                        body,
                        rule,
                        now,
                        dry_run=dry_run,
                    )
                except (OSError, ValueError, sqlite3.Error) as exc:
                    if vault.safe_output_path(TRANSACTION_RELPATH).exists():
                        raise ValueError(
                            "Sweep stopped because its transaction requires recovery."
                        ) from exc
                    tool_counts["errors"] += 1
                    summary["errors"] += 1
                    events.append({
                        "event": "error",
                        "run_at": timestamp,
                        "tool": plan["name"],
                        "path": rel,
                        "error": str(exc),
                    })
                    continue

                if event is None:
                    continue
                count_key = event["count_key"]
                tool_counts[count_key] += 1
                summary[count_key] += 1
                event.pop("count_key")
                events.append(event)

        if summary["errors"]:
            summary["result"] = "partial"
        _append_log(vault, [*events, summary])
    return summary


def latest_status(vault) -> dict | None:
    """Return the latest complete sweep summary from the JSONL log."""
    path = vault.root / "06_indexes" / "logs" / "sweep.log"
    if not path.exists():
        return None
    safe = vault.safe_source_path(path.relative_to(vault.root).as_posix())
    latest = None
    for raw in safe.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("event") == "summary":
            latest = event
    return latest


def _load_plans(vault) -> list[dict]:
    plans = []
    claimed_roots = []
    for name, raw_cfg in sorted(tools_mod.load_tools(vault).items()):
        if not isinstance(raw_cfg, dict):
            raise ValueError(f"Tool '{name}' configuration must be a mapping.")
        if raw_cfg.get("ephemeral") is not True or raw_cfg.get("status") != "installed":
            continue
        rules = raw_cfg.get("lifecycle") or []
        if not isinstance(rules, list):
            raise ValueError(f"Tool '{name}' lifecycle must be a list.")
        parsed_rules = [_validate_rule(name, rule) for rule in rules]

        writes_to = raw_cfg.get("writes_to") or []
        if isinstance(writes_to, str):
            writes_to = [writes_to]
        if not isinstance(writes_to, list) or any(not isinstance(item, str) for item in writes_to):
            raise ValueError(f"Tool '{name}' writes_to must be a path or list of paths.")
        roots = []
        for raw_root in writes_to:
            rel = Path(raw_root.rstrip("/")).as_posix()
            parts = Path(rel).parts
            if not parts or parts[0] not in ALLOWED_WRITE_BUCKETS:
                raise ValueError(f"Tool '{name}' has unsafe sweep root '{raw_root}'.")
            root = vault.root / rel
            vault._safe_relative_path(rel)
            if root.is_symlink():
                raise ValueError(f"Tool '{name}' sweep root is a symlink: {rel}")
            for owner, claimed in claimed_roots:
                if _is_under(root, claimed) or _is_under(claimed, root):
                    raise ValueError(f"Sweep roots overlap between '{owner}' and '{name}': {rel}")
            claimed_roots.append((name, root))
            roots.append(root)

        database = raw_cfg.get("database") or raw_cfg.get("db")
        if any(rule.get("action") == "archive-with-trace" for rule in parsed_rules):
            if not isinstance(database, str) or not database:
                raise ValueError(f"Tool '{name}' needs database for archive-with-trace.")
            database_path = Path(database).as_posix()
            if not database_path.startswith("06_indexes/databases/"):
                raise ValueError(f"Tool '{name}' database must be under 06_indexes/databases/.")
            vault._safe_relative_path(database_path)
        else:
            database_path = None

        plans.append({
            "name": name,
            "roots": roots,
            "rules": parsed_rules,
            "database": database_path,
        })
    return plans


def _validate_rule(tool_name: str, rule) -> dict:
    if not isinstance(rule, dict):
        raise ValueError(f"Tool '{tool_name}' lifecycle rules must be mappings.")
    source_status = rule.get("from")
    if source_status not in routing.STATUSES:
        raise ValueError(f"Tool '{tool_name}' has unknown lifecycle status '{source_status}'.")
    if source_status == "archived":
        raise ValueError(f"Tool '{tool_name}' cannot reactivate archived content.")
    if source_status in PROTECTED_STATUSES:
        raise ValueError(f"Tool '{tool_name}' cannot sweep protected status '{source_status}'.")
    after_days = rule.get("after_days")
    if (
        isinstance(after_days, bool)
        or not isinstance(after_days, int)
        or not 0 <= after_days <= MAX_AFTER_DAYS
    ):
        raise ValueError(
            f"Tool '{tool_name}' after_days must be an integer from 0 to {MAX_AFTER_DAYS}."
        )
    target = rule.get("to")
    action = rule.get("action")
    if (target is None) == (action is None):
        raise ValueError(f"Tool '{tool_name}' rules need exactly one of 'to' or 'action'.")
    if target is not None and target != "stale":
        raise ValueError(f"Tool '{tool_name}' automatic status target must be 'stale'.")
    if action is not None:
        if action not in ARCHIVE_ACTIONS:
            raise ValueError(f"Tool '{tool_name}' has unknown lifecycle action '{action}'.")
        if source_status not in {"done", "stale"}:
            raise ValueError(f"Tool '{tool_name}' may archive only done or stale content.")
    return {
        "from": source_status,
        "after_days": after_days,
        "to": target,
        "action": action,
    }


def _due_rule(fm: dict, rules: list[dict], now: datetime) -> dict | None:
    matching = [rule for rule in rules if rule["from"] == fm.get("status")]
    if not matching:
        return None
    modified = _parse_timestamp(fm.get("modified"))
    for rule in matching:
        if now - modified >= timedelta(days=rule["after_days"]):
            return rule
    return None


def _apply_rule(vault, plan, root, path, fm, body, rule, now, *, dry_run):
    rel = path.relative_to(vault.root).as_posix()
    if plan["name"] == "todo":
        todo_mod.validate_database_status(vault, fm.get("id"), fm.get("status"))
    if not dry_run:
        current_path = vault.safe_source_path(rel)
        current_fm, current_body = fmlib.read_note(current_path)
        if current_fm != fm or current_body != body:
            raise ValueError("Lifecycle item changed during the sweep; retry on the next run.")
        path = current_path
    base_event = {
        "run_at": _iso(now),
        "tool": plan["name"],
        "path": rel,
        "dry_run": bool(dry_run),
    }
    if rule["to"] is not None:
        updated = dict(fm)
        updated["status"] = rule["to"]
        updated["modified"] = fmlib.format_note_timestamp(now)
        notes_mod.validate_frontmatter_values(updated)
        if not dry_run:
            updated_content = fmlib.compose_note(updated, body)
            journal = _start_sweep_transaction(
                vault,
                [rel],
                expected_contents={rel: updated_content},
            )
            try:
                vault.atomic_write_text(rel, updated_content)
            except Exception:
                _rollback_sweep_transaction(vault, journal)
                raise
            _commit_sweep_transaction(vault, journal)
        return {
            **base_event,
            "event": "transition",
            "from": fm.get("status"),
            "to": rule["to"],
            "count_key": "transitioned",
        }

    if rule["action"] == "delete-after-review":
        return {
            **base_event,
            "event": "deletion-proposal",
            "from": fm.get("status"),
            "count_key": "proposed",
        }

    quarter = f"{now.year}_q{(now.month - 1) // 3 + 1}"
    owned_rel = path.relative_to(root).as_posix()
    dest_rel = f"04_archives/{quarter}/{plan['name']}/{owned_rel}"
    dest = _check_output_path(vault, dest_rel) if dry_run else vault.safe_output_path(dest_rel)
    if dest.exists():
        raise ValueError(f"Sweep archive destination already exists: {dest_rel}")
    archived = dict(fm)
    archived["status"] = "archived"
    archived["modified"] = fmlib.format_note_timestamp(now)
    archived["archived_at"] = archived["modified"]
    archived["archived_from"] = rel
    notes_mod.validate_frontmatter_values(archived)
    if not dry_run:
        trace = None
        if rule["action"] == "archive-with-trace":
            trace = {
                "database": plan["database"],
                "tool": plan["name"],
                "note_id": fm.get("id"),
                "source_rel": rel,
            }
        content = fmlib.compose_note(archived, body)
        journal = _start_sweep_transaction(
            vault,
            [rel, dest_rel],
            trace=trace,
            expected_contents={rel: content, dest_rel: content},
        )
        try:
            vault.atomic_create_text(dest_rel, content)
            if rule["action"] == "archive-with-trace":
                _write_trace(vault, plan, fm, body, rel, dest_rel, now)
            latest_fm, latest_body = fmlib.read_note(vault.safe_source_path(rel))
            if latest_fm != fm or latest_body != body:
                raise ValueError("Lifecycle item changed before archival; retry on the next run.")
            path.unlink()
            vault.fsync_directory(path.parent)
        except Exception:
            _rollback_sweep_transaction(vault, journal)
            raise
        _commit_sweep_transaction(vault, journal)
    traced = rule["action"] == "archive-with-trace"
    return {
        **base_event,
        "event": "archive-with-trace" if traced else "archive",
        "from": fm.get("status"),
        "archive_path": dest_rel,
        "count_key": "traced" if traced else "archived",
    }


def _write_trace(vault, plan, fm, body, source_rel, dest_rel, now):
    database_rel = plan["database"]
    database = vault.safe_output_path(database_rel)
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sweep_archive_history (
                tool TEXT NOT NULL,
                note_id TEXT NOT NULL,
                archived_at TEXT NOT NULL,
                archived_from TEXT NOT NULL,
                archive_path TEXT NOT NULL,
                frontmatter_json TEXT NOT NULL,
                body TEXT NOT NULL,
                PRIMARY KEY (tool, note_id, archived_from)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO sweep_archive_history
            (tool, note_id, archived_at, archived_from, archive_path, frontmatter_json, body)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan["name"],
                fm.get("id"),
                _iso(now),
                source_rel,
                dest_rel,
                json.dumps(fm, sort_keys=True),
                body,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def _remove_trace(vault, plan, note_id, source_rel, *, suppress_errors=True):
    database = vault.safe_output_path(plan["database"])
    if not database.exists():
        return
    try:
        with sqlite3.connect(database) as connection:
            table = connection.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'sweep_archive_history'
                """
            ).fetchone()
            if table is None:
                return
            connection.execute(
                "DELETE FROM sweep_archive_history WHERE tool = ? AND note_id = ? AND archived_from = ?",
                (plan["name"], note_id, source_rel),
            )
    except sqlite3.Error:
        if not suppress_errors:
            raise


def _start_sweep_transaction(vault, relpaths, *, trace=None, expected_contents=None):
    expected_contents = expected_contents or {}
    if vault.safe_output_path(TRANSACTION_RELPATH).exists():
        raise ValueError("A previous sweep transaction must be recovered before continuing.")
    return file_transaction.prepare(
        vault,
        TRANSACTION_RELPATH,
        file_transaction.snapshot_files(
            vault, relpaths, expected_contents=expected_contents,
        ),
        metadata={"trace": trace},
    )


def _commit_sweep_transaction(vault, journal):
    file_transaction.commit(vault, TRANSACTION_RELPATH, journal)


def _rollback_sweep_transaction(vault, journal):
    file_transaction.rollback(
        vault,
        TRANSACTION_RELPATH,
        journal,
        after_restore=lambda current: _remove_journal_trace(
            vault, current.get("trace"),
        ),
    )


def _recover_sweep_transaction(vault):
    vault.refuse_foreign_transactions(TRANSACTION_RELPATH)
    try:
        file_transaction.recover(
            vault,
            TRANSACTION_RELPATH,
            after_restore=lambda journal: _remove_journal_trace(
                vault, journal.get("trace"),
            ),
        )
    except (OSError, ValueError, json.JSONDecodeError, AttributeError) as exc:
        raise ValueError(f"Cannot recover interrupted sweep transaction: {exc}") from exc


def _remove_journal_trace(vault, trace):
    if not isinstance(trace, dict):
        return
    plan = {"database": trace.get("database"), "name": trace.get("tool")}
    if not all(isinstance(value, str) and value for value in plan.values()):
        raise ValueError("invalid sweep transaction trace")
    _remove_trace(
        vault,
        plan,
        trace.get("note_id"),
        trace.get("source_rel"),
        suppress_errors=False,
    )


def _remove_sweep_transaction(vault):
    file_transaction.remove_journal(vault, TRANSACTION_RELPATH)


def _append_log(vault, events: list[dict]) -> None:
    path = vault.safe_output_path("06_indexes/logs/sweep.log")
    with path.open("a", encoding="utf-8") as stream:
        for event in events:
            stream.write(json.dumps(event, sort_keys=True) + "\n")


def _check_log_writable(vault) -> None:
    path = vault.safe_output_path("06_indexes/logs/sweep.log")
    with path.open("a", encoding="utf-8"):
        pass


@contextmanager
def _sweep_lock(vault, timestamp: str):
    path = vault.safe_output_path("06_indexes/logs/sweep.lock")
    descriptor = None
    for attempt in range(2):
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            break
        except FileExistsError as exc:
            if attempt == 0 and _remove_stale_lock(path):
                continue
            raise ValueError("Another ephemeral sweep is already running.") from exc
    try:
        owner = json.dumps({"pid": os.getpid(), "started_at": timestamp}) + "\n"
        os.write(descriptor, owner.encode("utf-8"))
        os.close(descriptor)
        descriptor = None
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        path.unlink(missing_ok=True)


def _remove_stale_lock(path: Path) -> bool:
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


def _parse_timestamp(value) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Lifecycle item has no valid modified timestamp.")
    try:
        parsed = fmlib.parse_note_timestamp(value)
    except ValueError as exc:
        raise ValueError(f"Invalid modified timestamp '{value}'.") from exc
    return parsed.astimezone(timezone.utc)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Sweep time must include a timezone.")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _check_output_path(vault, relpath: str) -> Path:
    """Validate an output path for dry-run without creating its parents."""
    target = vault._safe_relative_path(relpath)
    current = vault.root
    for part in target.relative_to(vault.root).parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Refusing generated output through symlink: {relpath}")
        if current.exists() and not current.is_dir():
            raise ValueError(f"Generated output parent is not a directory: {relpath}")
    if target.is_symlink():
        raise ValueError(f"Refusing to replace generated-output symlink: {relpath}")
    return target

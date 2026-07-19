"""Privacy-preserving CLI usage events and local usage reporting."""

from __future__ import annotations

import json
import math
import os
import re
import time
import uuid
from collections import Counter, defaultdict, deque
from datetime import date, datetime, time as datetime_time, timezone
from pathlib import Path

from . import frontmatter as fmlib
from . import import_manifest
from . import routing
from . import views
from .vault import Vault


USAGE_RELPATH = "06_indexes/logs/usage.log"
MAX_USAGE_EVENTS = 100_000
MAX_USAGE_LINE_BYTES = 1024 * 1024
MAX_USAGE_RETAINED_BYTES = 32 * 1024 * 1024
SUBJECT_KINDS = {
    "import", "index", "ingestion", "note", "project", "search", "session", "todo",
    "triage", "vault",
}
SUBJECT_TYPES = set(routing.TYPES)
STATUSES = set(routing.STATUSES) | {"active", "waiting", "done", "archived"}
OUTCOMES = {
    "added", "archived", "blocked", "captured", "completed", "created",
    "deferred", "dissolved", "done", "dry_run", "edited", "extracted", "failed",
    "imported", "indexed", "ingested", "no_change", "read", "routed", "searched",
    "session_closed", "status_changed", "triaged",
}
RESULT_FIELDS = {
    "subject_kind", "subject_type", "status_before", "status_after", "outcome",
    "changed", "count", "ingestion_kind",
}
UNAVAILABLE_METRICS = [
    (
        "Resume is a documentary protocol; automatic resume starts, context reads, "
        "resume quality, re-explanation time, and re-explanation measurement are unavailable. "
        "Record these qualitatively in usage-journal.md."
    ),
]


def start_timing() -> tuple[str, float]:
    """Capture UTC wall-clock start and a monotonic duration origin."""
    return fmlib.now_iso(), time.monotonic()


def set_result(args, **metadata) -> None:
    """Attach allowlisted effective command metadata for the final event."""
    unknown = set(metadata) - RESULT_FIELDS
    if unknown:
        raise ValueError(f"Unknown usage result fields: {', '.join(sorted(unknown))}")
    result = {key: value for key, value in metadata.items() if _valid_result(key, value)}
    args._usage_result = result


def append_usage(
    args,
    *,
    exit_code: int = 0,
    success: bool | None = None,
    started_at: str | None = None,
    started_monotonic: float | None = None,
) -> None:
    """Append one complete v2 line; logging failures never affect the command."""
    try:
        root = _usage_root(args)
        if root is None:
            return
        vault = Vault(root)
        vault.marker_data()
        completed_at = fmlib.now_iso()
        duration_ms = 0
        if started_monotonic is not None:
            duration_ms = max(0, round((time.monotonic() - started_monotonic) * 1000))
        success = exit_code == 0 if success is None else bool(success)
        result = dict(getattr(args, "_usage_result", {}) or {})
        if not success:
            result["outcome"] = "failed"

        event = {
            "schema_version": 2,
            "event": "command",
            "event_id": uuid.uuid4().hex,
            "timestamp": completed_at,
            "started_at": started_at or completed_at,
            "duration_ms": duration_ms,
            "command": _command_name(args),
            "exit_code": int(exit_code),
            "success": success,
            "argument_type": _categorical(getattr(args, "type", None), SUBJECT_TYPES),
            "argument_status": _categorical(getattr(args, "status", None), STATUSES),
            "subject_kind": result.get("subject_kind"),
            "subject_type": result.get("subject_type"),
            "status_before": result.get("status_before"),
            "status_after": result.get("status_after"),
            "outcome": result.get("outcome", "completed"),
            "changed": result.get("changed"),
        }
        if "ingestion_kind" in result:
            event["ingestion_kind"] = result["ingestion_kind"]
        if "count" in result:
            event["count"] = result["count"]
        session_id = os.environ.get("ARPENT_SESSION_ID")
        if session_id and re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", session_id):
            event["session_id"] = session_id

        with vault.shared_lock("mode"):
            if (
                vault.marker_data()["mode"] == "minimal"
                and getattr(args, "command", None) != "mode"
            ):
                return
            line = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
            with vault.exclusive_lock("mutations"):
                path = vault.safe_output_path(USAGE_RELPATH)
                with vault.exclusive_lock("usage"):
                    with path.open("a", encoding="utf-8") as stream:
                        stream.write(line)
                        stream.flush()
                        os.fsync(stream.fileno())
    except (OSError, ValueError):
        return


def read_usage(vault: Vault, *, since=None, max_events=MAX_USAGE_EVENTS) -> dict:
    """Read mixed v1/v2 JSONL, skipping and counting malformed records."""
    if (
        isinstance(max_events, bool)
        or not isinstance(max_events, int)
        or not 1 <= max_events <= MAX_USAGE_EVENTS
    ):
        raise ValueError(f"max_events must be between 1 and {MAX_USAGE_EVENTS}.")
    threshold = parse_since(since) if since is not None else None
    path = vault.safe_output_path(USAGE_RELPATH)
    events = deque()
    event_sizes = deque()
    retained_bytes = 0
    malformed = 0
    v1_count = 0
    v2_count = 0
    dropped_events = 0
    if not path.exists():
        return {
            "events": [],
            "malformed_lines": malformed,
            "v1_count": v1_count,
            "v2_count": v2_count,
            "dropped_events": dropped_events,
            "event_limit": max_events,
            "retained_byte_limit": MAX_USAGE_RETAINED_BYTES,
        }

    try:
        source = vault.safe_source_path(USAGE_RELPATH)
        stream = source.open("rb")
    except (OSError, ValueError):
        return {
            "events": [], "malformed_lines": 1, "v1_count": 0, "v2_count": 0,
            "dropped_events": 0, "event_limit": max_events,
            "retained_byte_limit": MAX_USAGE_RETAINED_BYTES,
        }
    with stream:
        for line in _bounded_lines(stream):
            if line is None:
                malformed += 1
                continue
            try:
                event = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
                malformed += 1
                continue
            if not isinstance(event, dict):
                malformed += 1
                continue
            if not isinstance(event.get("command"), str) or _parse_timestamp(event.get("timestamp")) is None:
                malformed += 1
                continue
            version = event.get("schema_version", 1)
            if version not in (None, 1, 2):
                malformed += 1
                continue
            if version == 2 and not _valid_v2_event(event):
                malformed += 1
                continue
            if threshold is not None:
                timestamp = _parse_timestamp(event.get("timestamp"))
                if timestamp is None or timestamp < threshold:
                    continue
            if version == 2:
                v2_count += 1
            else:
                v1_count += 1
            events.append(event)
            event_sizes.append(len(line))
            retained_bytes += len(line)
            while len(events) > max_events or retained_bytes > MAX_USAGE_RETAINED_BYTES:
                events.popleft()
                retained_bytes -= event_sizes.popleft()
                dropped_events += 1
    return {
        "events": list(events),
        "malformed_lines": malformed,
        "v1_count": v1_count,
        "v2_count": v2_count,
        "dropped_events": dropped_events,
        "event_limit": max_events,
        "retained_byte_limit": MAX_USAGE_RETAINED_BYTES,
    }


def _bounded_lines(stream):
    while True:
        line = stream.readline(MAX_USAGE_LINE_BYTES + 1)
        if not line:
            return
        if len(line) > MAX_USAGE_LINE_BYTES:
            while line and not line.endswith(b"\n"):
                line = stream.readline(MAX_USAGE_LINE_BYTES + 1)
            yield None
            continue
        yield line


def usage_report(vault: Vault, *, since=None, now=None) -> dict:
    """Aggregate observable command events and the current triage inventory."""
    threshold = parse_since(since) if since is not None else None
    log = read_usage(vault, since=threshold)
    events = log["events"]
    v2_events = [event for event in events if event.get("schema_version") == 2]
    successes = sum(_event_success(event) for event in events)
    durations = [
        event["duration_ms"] for event in v2_events
        if type(event.get("duration_ms")) in (int, float) and event["duration_ms"] >= 0
    ]
    active_days = {
        timestamp.date().isoformat()
        for event in events
        if (timestamp := _parse_timestamp(event.get("timestamp"))) is not None
    }
    by_command = Counter(
        event.get("command") for event in events
        if isinstance(event.get("command"), str) and event["command"]
    )
    detail_durations = defaultdict(list)
    detail_successes = Counter()
    for event in events:
        command = event.get("command")
        if not isinstance(command, str) or not command:
            continue
        detail_successes[command] += _event_success(event)
        if (
            event.get("schema_version") == 2
            and type(event.get("duration_ms")) in (int, float)
            and event["duration_ms"] >= 0
        ):
            detail_durations[command].append(event["duration_ms"])
    command_details = {}
    for command in sorted(by_command):
        command_durations = detail_durations[command]
        command_successes = detail_successes[command]
        command_details[command] = {
            "count": by_command[command],
            "success": command_successes,
            "failure": by_command[command] - command_successes,
            "duration_ms": {
                "covered": len(command_durations),
                "p50": _percentile(command_durations, 50),
                "p95": _percentile(command_durations, 95),
            },
        }
    subject_types = Counter(
        event.get("subject_type") for event in v2_events
        if event.get("subject_type") in SUBJECT_TYPES
    )
    transitions = Counter(
        f"{event['status_before']} -> {event['status_after']}"
        for event in v2_events
        if event.get("status_before") in STATUSES
        and event.get("status_after") in STATUSES
        and event["status_before"] != event["status_after"]
    )
    successful_v2 = [event for event in v2_events if _event_success(event)]
    session_durations = [
        event["duration_ms"] for event in successful_v2
        if event.get("outcome") == "session_closed"
        and type(event.get("duration_ms")) in (int, float)
    ]

    triage_items = views.triage_items(vault, now=now)
    ages = [max(0, int(item.get("age_seconds") or 0)) for item in triage_items]
    buckets = {"under_1_day": 0, "1_to_7_days": 0, "8_to_30_days": 0, "over_30_days": 0}
    for age in ages:
        if age < 86400:
            buckets["under_1_day"] += 1
        elif age <= 7 * 86400:
            buckets["1_to_7_days"] += 1
        elif age <= 30 * 86400:
            buckets["8_to_30_days"] += 1
        else:
            buckets["over_30_days"] += 1

    observed_total = log["v1_count"] + log["v2_count"]
    return {
        "since": fmlib.format_note_timestamp(threshold) if threshold else None,
        "commands": {
            "total": len(events),
            "success": successes,
            "failure": len(events) - successes,
            "active_days": len(active_days),
            "by_command": dict(sorted(by_command.items())),
            "details": command_details,
            "duration_ms": {
                "covered": len(durations),
                "p50": _percentile(durations, 50),
                "p95": _percentile(durations, 95),
            },
        },
        "effective_subject_types": dict(sorted(subject_types.items())),
        "status_transitions": dict(sorted(transitions.items())),
        "counts": {
            "captures": _count_outcome(successful_v2, "captured"),
            "ingestions": _count_outcome(successful_v2, "ingested"),
            "project_creations": _count_outcome(successful_v2, "created", "project"),
            "productions": sum(
                1 for event in successful_v2
                if event.get("subject_type") == "production"
                and event.get("changed") is True
                and event.get("outcome") in {"captured", "edited", "ingested", "extracted"}
            ),
            "session_closes": _count_outcome(successful_v2, "session_closed"),
        },
        "session_close": {
            "count": _count_outcome(successful_v2, "session_closed"),
            "duration_ms": {
                "p50": _percentile(session_durations, 50),
                "p95": _percentile(session_durations, 95),
            },
        },
        "triage": {
            "count": len(triage_items),
            "oldest_age_seconds": max(ages) if ages else None,
            "age_buckets": buckets,
        },
        "log": {
            "v1_events": log["v1_count"],
            "v2_events": log["v2_count"],
            "malformed_lines": log["malformed_lines"],
            "dropped_events": log["dropped_events"],
            "event_limit": log["event_limit"],
            "v2_coverage_percent": round(log["v2_count"] * 100 / observed_total, 1) if observed_total else 0.0,
        },
        "unavailable_metrics": list(UNAVAILABLE_METRICS),
    }


def format_report(report: dict) -> str:
    """Render the JSON report data without recomputing any metrics."""
    commands = report["commands"]
    duration = commands["duration_ms"]
    counts = report["counts"]
    session_close = report["session_close"]
    triage = report["triage"]
    log = report["log"]
    lines = [
        "Arpent usage report",
        f"Commands: {commands['total']} ({commands['success']} successful, {commands['failure']} failed)",
        f"Active days: {commands['active_days']}",
        "Command counts: " + _display_counts(commands["by_command"]),
        f"V2 duration: p50={_display(duration['p50'])} ms, p95={_display(duration['p95'])} ms ({duration['covered']} covered)",
        "Counts: "
        f"captures={counts['captures']}, ingestions={counts['ingestions']}, "
        f"project creations={counts['project_creations']}, productions={counts['productions']}, "
        f"session closes={counts['session_closes']}",
        "Session close duration: "
        f"p50={_display(session_close['duration_ms']['p50'])} ms, "
        f"p95={_display(session_close['duration_ms']['p95'])} ms",
        f"Triage now: {triage['count']} item(s), oldest age={_display(triage['oldest_age_seconds'])} seconds",
        "Triage age buckets: " + ", ".join(
            f"{name}={count}" for name, count in triage["age_buckets"].items()
        ),
        f"Log coverage: v1={log['v1_events']}, v2={log['v2_events']} ({log['v2_coverage_percent']}%), malformed={log['malformed_lines']}, retained-limit-drops={log['dropped_events']}",
        "Effective subject types: " + _display_counts(report["effective_subject_types"]),
        "Status transitions: " + _display_counts(report["status_transitions"]),
        "Unavailable metrics:",
    ]
    detail_lines = []
    for command, detail in commands["details"].items():
        duration = detail["duration_ms"]
        detail_lines.append(
            f"- {command}: count={detail['count']}, success={detail['success']}, "
            f"failure={detail['failure']}, p50={_display(duration['p50'])} ms, "
            f"p95={_display(duration['p95'])} ms"
        )
    lines[4:4] = ["By command:", *(detail_lines or ["- none available"])]
    lines.extend(f"- {note}" for note in report["unavailable_metrics"])
    return "\n".join(lines) + "\n"


def parse_since(value) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime_time.min, tzinfo=timezone.utc)
    elif isinstance(value, str):
        try:
            parsed = fmlib.parse_note_timestamp(value)
        except ValueError as exc:
            raise ValueError(
                f"--since must use {fmlib.NOTE_TIMESTAMP_LABEL} (UTC)"
            ) from exc
    else:
        raise ValueError(f"--since must use {fmlib.NOTE_TIMESTAMP_LABEL} (UTC)")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _usage_root(args) -> Path | None:
    if getattr(args, "command", None) == "skill":
        return None
    if getattr(args, "command", None) == "init":
        return Path(args.path).expanduser().resolve()
    vault = Vault.find()
    if (
        vault
        and vault.marker_data()["mode"] == "minimal"
        and getattr(args, "command", None) != "mode"
    ):
        return None
    if vault and getattr(args, "command", None) == "import":
        try:
            if getattr(args, "import_cmd", None) == "scan":
                source = Path(args.source).expanduser().resolve()
            else:
                _, plan = import_manifest.load_plan(Path(args.plan))
                source = Path(plan["source"]["root"]).resolve()
            if _paths_overlap(source, vault.root):
                return None
        except (OSError, ValueError):
            return None
    return vault.root if vault else None


def _paths_overlap(first: Path, second: Path) -> bool:
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


def _command_name(args) -> str:
    parts = [getattr(args, "command", None)]
    for attr in (
        "note_cmd", "project_cmd", "context_cmd", "backup_cmd", "session_cmd",
        "tools_cmd", "cron_cmd", "sweep_cmd", "todo_cmd", "usage_cmd", "import_cmd",
        "mode_cmd", "skill_cmd",
    ):
        value = getattr(args, attr, None)
        if value:
            parts.append(value)
    return " ".join(part for part in parts if part)


def _valid_result(key, value) -> bool:
    if value is None:
        return True
    if key == "subject_kind":
        return value in SUBJECT_KINDS
    if key == "subject_type":
        return value in SUBJECT_TYPES
    if key in {"status_before", "status_after"}:
        return value in STATUSES
    if key == "outcome":
        return value in OUTCOMES
    if key == "changed":
        return type(value) is bool
    if key == "count":
        return type(value) is int and value >= 0
    if key == "ingestion_kind":
        return value in {"binary", "malformed", "text"}
    return False


def _categorical(value, allowed):
    return value if value in allowed else None


def _parse_timestamp(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _event_success(event: dict) -> bool:
    if event.get("schema_version") == 2 and type(event.get("success")) is bool:
        return event["success"]
    return event.get("exit_code", 0) == 0


def _valid_v2_event(event: dict) -> bool:
    return (
        event.get("event") == "command"
        and isinstance(event.get("event_id"), str)
        and bool(event["event_id"])
        and _parse_timestamp(event.get("started_at")) is not None
        and type(event.get("duration_ms")) in (int, float)
        and event["duration_ms"] >= 0
        and type(event.get("exit_code")) is int
        and type(event.get("success")) is bool
    )


def _percentile(values, percentile):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile / 100 * len(ordered)) - 1)]


def _count_outcome(events, outcome, subject_kind=None):
    return sum(
        1 for event in events
        if event.get("outcome") == outcome
        and (subject_kind is None or event.get("subject_kind") == subject_kind)
    )


def _display(value):
    return "unavailable" if value is None else str(value)


def _display_counts(counts):
    return ", ".join(f"{key}={value}" for key, value in counts.items()) or "none available"

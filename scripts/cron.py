"""Cron registry support for the no-daemon Phase 1 CLI."""

from __future__ import annotations

import json
import os
import signal
import shlex
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

TRUST_VALUE = "local-code"
DEFAULT_TIMEOUT_SECONDS = 300
CRON_FIELDS = (
    ("minute", 0, 59),
    ("hour", 0, 23),
    ("day-of-month", 1, 31),
    ("month", 1, 12),
    ("day-of-week", 0, 7),
)


def run_tick(vault, *, dry_run=False, allow_local_code=False, now=None) -> list[dict]:
    """Run due enabled jobs from 06_indexes/cron.json."""
    with vault.exclusive_lock("cron"):
        return _run_tick(
            vault, dry_run=dry_run, allow_local_code=allow_local_code, now=now,
        )


def _run_tick(vault, *, dry_run=False, allow_local_code=False, now=None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    path = vault.root / "06_indexes" / "cron.json"
    if not path.exists():
        return []

    relpath = path.relative_to(vault.root).as_posix()
    safe_path = vault.safe_source_path(relpath)
    original = safe_path.read_text(encoding="utf-8")
    data = json.loads(original)
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
        raise ValueError("cron.json must contain a jobs list.")
    jobs = data["jobs"]
    results = []
    current_text = original

    job_ids = []
    for job in jobs:
        _validate_job(job)
        job_ids.append(job["id"])
    if len(job_ids) != len(set(job_ids)):
        raise ValueError("cron.json job ids must be unique.")
    for job in jobs:
        if not job.get("enabled"):
            continue
        if not _is_due(job, now):
            continue
        if not dry_run and not allow_local_code:
            raise ValueError(
                "Cron execution requires --allow-local-code in addition to each job's trust declaration."
            )
        if not dry_run and os.name == "nt":  # pragma: no cover - Windows only
            raise ValueError(
                "Cron execution is disabled on Windows because descendant process termination is not guaranteed."
            )
        if vault.safe_source_path(relpath).read_text(encoding="utf-8") != current_text:
            raise ValueError("cron.json changed while jobs were running; no further jobs were dispatched.")
        if not dry_run:
            job["last_started"] = _iso(now)
            current_text = _persist_registry(
                vault,
                relpath,
                data,
                expected_text=current_text,
                conflict_message="cron.json changed before dispatch; the job was not started.",
            )
        result = _run_job(vault, job, dry_run=dry_run, now=now)
        results.append(result)
        if not dry_run and result["returncode"] == 0:
            job["last_run"] = _iso(now)
            current_text = _persist_registry(
                vault,
                relpath,
                data,
                expected_text=current_text,
                conflict_message="cron.json changed while a job was running; last_run was not overwritten.",
            )
    return results


def _run_job(vault, job: dict, *, dry_run: bool, now: datetime) -> dict:
    command = job.get("command") or ""
    if dry_run:
        message = f"DRY RUN {job.get('id')}"
        _notify(vault, job, message)
        return {"id": job.get("id"), "command": command, "returncode": 0, "dry_run": True}

    argv, internal = _command_argv(command)
    if not argv:
        return {"id": job.get("id"), "command": command, "returncode": 2, "dry_run": False}
    timeout = job.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    cwd = vault.root
    env = None
    if internal:
        cwd = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["ARPENT_VAULT_ROOT"] = str(vault.root)
    try:
        returncode = _run_process(argv, cwd=cwd, env=env, timeout=timeout)
    except OSError:
        returncode = 127
    message = f"{_iso(now)} {job.get('id')} exited {returncode}"
    try:
        _notify(vault, job, message)
    except (OSError, ValueError):
        pass
    return {
        "id": job.get("id"),
        "command": command,
        "returncode": returncode,
        "dry_run": False,
    }


def _command_argv(command: str) -> tuple[list[str], bool]:
    parts = shlex.split(command)
    if not parts:
        return [], False
    executable_name = Path(parts[0]).name.lower()
    if executable_name in {"arpent", "arp", "arpent.exe", "arp.exe"}:
        return [sys.executable, "-m", "scripts.cli", *parts[1:]], True
    if Path(parts[0]).stem.lower().startswith("python"):
        try:
            module_flag = parts.index("-m", 1)
        except ValueError:
            module_flag = -1
        if module_flag >= 1 and parts[module_flag + 1:module_flag + 2] == ["scripts.cli"]:
            return [sys.executable, "-m", "scripts.cli", *parts[module_flag + 2:]], True
    return parts, False


def _run_process(argv, *, cwd, env, timeout: int) -> int:
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        start_new_session=os.name == "posix",
    )
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:  # pragma: no cover - Windows only
            process.kill()
        process.wait()
        return 124


def _validate_job(job) -> None:
    if not isinstance(job, dict):
        raise ValueError("Each cron job must be an object.")
    job_id = job.get("id")
    if not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("Each cron job must have a non-empty id.")
    if type(job.get("enabled")) is not bool:
        raise ValueError(f"Cron job '{job_id}' enabled must be a boolean.")
    _parse_schedule(job.get("schedule"), job_id=job_id)
    if job.get("enabled") and job.get("trust") != TRUST_VALUE:
        raise ValueError(
            f"Enabled cron job '{job_id}' must declare trust: '{TRUST_VALUE}' because its command executes local code."
        )
    command = job.get("command")
    if not isinstance(command, str) or not command.strip():
        raise ValueError(f"Cron job '{job_id}' must have a non-empty command.")
    try:
        argv, internal = _command_argv(command)
    except ValueError as exc:
        raise ValueError(f"Cron job '{job_id}' has invalid command quoting: {exc}") from exc
    if not argv:
        raise ValueError(f"Cron job '{job_id}' must have a non-empty command.")
    if internal and len(argv) > 3 and argv[3] in {"cron", "init", "mode"}:
        raise ValueError(
            f"Cron job '{job_id}' cannot recursively run cron, initialize a vault, "
            "or change vault mode."
        )
    timeout = job.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 86400:
        raise ValueError(f"Cron job '{job_id}' timeout_seconds must be between 1 and 86400.")
    if job.get("notify_channel") not in {None, "stdout", "file"}:
        raise ValueError(
            f"Cron job '{job_id}' notify_channel must be null, 'stdout', or 'file'."
        )


def _persist_registry(vault, relpath, data, *, expected_text, conflict_message):
    with _full_mode_mutation(vault):
        if vault.safe_source_path(relpath).read_text(encoding="utf-8") != expected_text:
            raise ValueError(conflict_message)
        updated = json.dumps(data, indent=2) + "\n"
        vault.atomic_write_text(relpath, updated)
        return updated


@contextmanager
def _full_mode_mutation(vault):
    """Protect cron-owned writes without locking out internal CLI jobs."""
    with vault.shared_lock("mode"):
        if vault.marker_data()["mode"] != "full":
            raise ValueError("Cron stopped because the vault is no longer in full mode.")
        with vault.exclusive_lock("mutations"):
            yield


def _is_due(job: dict, now: datetime) -> bool:
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("Cron tick time must be a timezone-aware datetime.")
    schedule = job["schedule"]
    fields, values = _parse_schedule(schedule, job_id=job.get("id"))
    minute, hour, day, month, weekday = values
    if now.minute not in minute:
        return False
    if now.hour not in hour:
        return False
    if now.month not in month:
        return False
    day_matches = now.day in day
    weekday_matches = (now.weekday() + 1) % 7 in weekday
    # Vixie/POSIX cron semantics: when both DOM and DOW are restricted, either
    # may select the day. A wildcard-leading field leaves selection to the other.
    if not fields[2].startswith("*") and not fields[4].startswith("*"):
        if not (day_matches or weekday_matches):
            return False
    elif not (day_matches and weekday_matches):
        return False
    last_run = job.get("last_run")
    last_started = job.get("last_started")
    minute = _iso(now)[:16]
    return not (
        (last_run and str(last_run)[:16] == minute)
        or (last_started and str(last_started)[:16] == minute)
    )


def _parse_schedule(schedule, *, job_id=None) -> tuple[list[str], list[set[int]]]:
    label = f"Cron job '{job_id}'" if job_id else "Cron schedule"
    if not isinstance(schedule, str):
        raise ValueError(f"{label} schedule must be a string.")
    fields = schedule.split()
    if len(fields) != 5:
        raise ValueError(f"{label} schedule must contain exactly five fields.")
    values = [
        _parse_field(field, name=name, minimum=minimum, maximum=maximum, label=label)
        for field, (name, minimum, maximum) in zip(fields, CRON_FIELDS)
    ]
    values[4] = {0 if value == 7 else value for value in values[4]}
    return fields, values


def _parse_field(field: str, *, name: str, minimum: int, maximum: int, label: str) -> set[int]:
    if not field or any(part == "" for part in field.split(",")):
        raise ValueError(f"{label} has invalid {name} field '{field}'.")
    values = set()
    for part in field.split(","):
        pieces = part.split("/")
        if len(pieces) > 2:
            raise ValueError(f"{label} has invalid {name} field '{field}'.")
        base = pieces[0]
        if len(pieces) == 2:
            if not pieces[1].isdigit() or int(pieces[1]) < 1:
                raise ValueError(f"{label} has invalid {name} step in '{field}'.")
            step = int(pieces[1])
        else:
            step = 1

        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            bounds = base.split("-")
            if len(bounds) != 2 or not all(bound.isdigit() for bound in bounds):
                raise ValueError(f"{label} has invalid {name} range in '{field}'.")
            start, end = map(int, bounds)
        elif base.isdigit():
            start = int(base)
            end = maximum if len(pieces) == 2 else start
        else:
            raise ValueError(f"{label} has invalid {name} field '{field}'.")

        if not minimum <= start <= end <= maximum:
            raise ValueError(
                f"{label} {name} values must be between {minimum} and {maximum}."
            )
        values.update(range(start, end + 1, step))
    return values


def _notify(vault, job: dict, message: str) -> None:
    channel = job.get("notify_channel")
    if channel == "stdout":
        print(message)
    elif channel == "file":
        with _full_mode_mutation(vault):
            log = vault.safe_output_path("06_indexes/logs/cron.log")
            with log.open("a", encoding="utf-8") as f:
                f.write(message + "\n")


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

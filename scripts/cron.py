"""Cron registry support for the no-daemon Phase 1 CLI."""

from __future__ import annotations

import json
import os
import signal
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

TRUST_VALUE = "local-code"
DEFAULT_TIMEOUT_SECONDS = 300


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
    if not isinstance(data, dict) or not isinstance(data.get("jobs", []), list):
        raise ValueError("cron.json must contain a jobs list.")
    jobs = data.get("jobs") or []
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
    if parts[0] in ("arpent", "arp"):
        return [sys.executable, "-m", "scripts.cli", *parts[1:]], True
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
    if job.get("enabled") and job.get("trust") != TRUST_VALUE:
        raise ValueError(
            f"Enabled cron job '{job_id}' must declare trust: '{TRUST_VALUE}' because its command executes local code."
        )
    command = job.get("command")
    if not isinstance(command, str) or not command.strip():
        raise ValueError(f"Cron job '{job_id}' must have a non-empty command.")
    try:
        argv, _ = _command_argv(command)
    except ValueError as exc:
        raise ValueError(f"Cron job '{job_id}' has invalid command quoting: {exc}") from exc
    if not argv:
        raise ValueError(f"Cron job '{job_id}' must have a non-empty command.")
    timeout = job.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 86400:
        raise ValueError(f"Cron job '{job_id}' timeout_seconds must be between 1 and 86400.")


def _persist_registry(vault, relpath, data, *, expected_text, conflict_message):
    if vault.safe_source_path(relpath).read_text(encoding="utf-8") != expected_text:
        raise ValueError(conflict_message)
    updated = json.dumps(data, indent=2) + "\n"
    vault.atomic_write_text(relpath, updated)
    return updated


def _is_due(job: dict, now: datetime) -> bool:
    schedule = job.get("schedule") or ""
    fields = schedule.split()
    if len(fields) != 5:
        return False
    minute, hour, day, month, weekday = fields
    if not _field_matches(minute, now.minute):
        return False
    if not _field_matches(hour, now.hour):
        return False
    if not _field_matches(day, now.day):
        return False
    if not _field_matches(month, now.month):
        return False
    if not _field_matches(weekday, (now.weekday() + 1) % 7):
        return False
    last_run = job.get("last_run")
    last_started = job.get("last_started")
    minute = _iso(now)[:16]
    return not (
        (last_run and str(last_run)[:16] == minute)
        or (last_started and str(last_started)[:16] == minute)
    )


def _field_matches(field: str, value: int) -> bool:
    if field == "*":
        return True
    for part in field.split(","):
        if part.isdigit() and int(part) == value:
            return True
    return False


def _notify(vault, job: dict, message: str) -> None:
    channel = job.get("notify_channel")
    if channel == "stdout":
        print(message)
    elif channel == "file":
        log = vault.safe_output_path("06_indexes/logs/cron.log")
        with log.open("a", encoding="utf-8") as f:
            f.write(message + "\n")


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

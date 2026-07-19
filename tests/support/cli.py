"""Subprocess helpers for exercising the real module entry point."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class CliResult:
    command: tuple
    returncode: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        return self.stdout + self.stderr


def run_cli(
    *arguments: object,
    cwd: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
    input_text: Optional[str] = None,
    timeout: int = 60,
) -> CliResult:
    """Run Arpent without a shell, preserving paths containing spaces."""
    child_env = dict(os.environ if env is None else env)
    child_env["PYTHONDONTWRITEBYTECODE"] = "1"
    python_path = child_env.get("PYTHONPATH")
    child_env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(REPOSITORY_ROOT), python_path) if part
    )
    command = (sys.executable, "-m", "scripts.cli", *(str(arg) for arg in arguments))
    completed = subprocess.run(
        command,
        cwd=str(cwd or REPOSITORY_ROOT),
        env=child_env,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        shell=False,
    )
    return CliResult(command, completed.returncode, completed.stdout, completed.stderr)

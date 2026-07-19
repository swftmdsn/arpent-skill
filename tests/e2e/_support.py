from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional


ROOT = Path(__file__).resolve().parents[2]


def _environment(
    vault: Optional[Path] = None,
    extra: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(ROOT) if not existing else f"{ROOT}{os.pathsep}{existing}"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if vault is None:
        env.pop("ARPENT_VAULT_ROOT", None)
    else:
        env["ARPENT_VAULT_ROOT"] = str(vault)
    if extra:
        env.update(extra)
    return env


def run_cli(
    vault: Path,
    *args: str,
    input_text: Optional[str] = None,
    extra_env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.cli", *args],
        cwd=ROOT,
        env=_environment(vault, extra_env),
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )


def initialize(parent: Path, *, name: str = "vault", minimal: bool = False) -> Path:
    root = parent / name
    command = [sys.executable, "-m", "scripts.cli", "init", str(root)]
    if minimal:
        command.append("--minimal")
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=_environment(),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if result.returncode != 0:
        raise AssertionError(f"init failed: {result.stderr or result.stdout}")
    return root


def require_success(result: subprocess.CompletedProcess[str]) -> subprocess.CompletedProcess[str]:
    if result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode})\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def json_result(result: subprocess.CompletedProcess[str]):
    require_success(result)
    return json.loads(result.stdout)

"""Hermetic temporary paths and process environments."""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator


@dataclass(frozen=True)
class IsolatedEnvironment:
    root: Path
    workspace: Path
    home: Path
    env: Dict[str, str]

    def path(self, name: str) -> Path:
        return self.workspace / name


@contextmanager
def isolated_environment() -> Iterator[IsolatedEnvironment]:
    """Provide isolated HOME, temp, and working directories with spaces."""
    with tempfile.TemporaryDirectory(prefix="arpent tests ") as temporary:
        root = Path(temporary)
        workspace = root / "workspace with spaces"
        home = root / "home with spaces"
        temp = root / "temporary files"
        for directory in (workspace, home, temp):
            directory.mkdir()

        env = os.environ.copy()
        env.pop("ARPENT_SESSION_ID", None)
        env.pop("ARPENT_VAULT_ROOT", None)
        env.update({
            "HOME": str(home),
            "USERPROFILE": str(home),
            "TMPDIR": str(temp),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
        })
        yield IsolatedEnvironment(root, workspace, home, env)

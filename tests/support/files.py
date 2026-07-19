"""Deterministic JSON, tree, file, and SQLite helpers."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence, Tuple


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_json_text(text: str):
    return json.loads(text)


@dataclass(frozen=True)
class TreeSnapshot:
    directories: Tuple[str, ...]
    files: Tuple[str, ...]
    symlinks: Tuple[Tuple[str, str], ...]

    @property
    def paths(self) -> Tuple[str, ...]:
        return tuple(sorted((*self.directories, *self.files)))


def snapshot_tree(root: Path, *, exclude: Iterable[str] = ()) -> TreeSnapshot:
    """Capture a sorted relative tree without following symlinks."""
    root = Path(root)
    excluded = tuple(str(item).strip("/") for item in exclude)
    directories = []
    files = []
    symlinks = []

    def is_excluded(relpath: str) -> bool:
        return any(relpath == item or relpath.startswith(item + "/") for item in excluded)

    for current, dir_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current)
        kept = []
        for name in sorted(dir_names):
            path = current_path / name
            relpath = path.relative_to(root).as_posix()
            if is_excluded(relpath):
                continue
            if path.is_symlink():
                symlinks.append((relpath, os.readlink(path)))
            else:
                directories.append(relpath + "/")
                kept.append(name)
        dir_names[:] = kept
        for name in sorted(file_names):
            path = current_path / name
            relpath = path.relative_to(root).as_posix()
            if is_excluded(relpath):
                continue
            if path.is_symlink():
                symlinks.append((relpath, os.readlink(path)))
            else:
                files.append(relpath)
    return TreeSnapshot(
        tuple(sorted(directories)),
        tuple(sorted(files)),
        tuple(sorted(symlinks)),
    )


class FileAssertionsMixin:
    """Assertions shared by unittest test cases."""

    def assertFileExists(self, root: Path, relpath: str) -> Path:
        path = Path(root) / relpath
        self.assertTrue(path.is_file(), "missing file: {}".format(path))
        return path

    def assertDirectoryExists(self, root: Path, relpath: str) -> Path:
        path = Path(root) / relpath
        self.assertTrue(path.is_dir(), "missing directory: {}".format(path))
        return path

    def assertFileContains(self, root: Path, relpath: str, expected: str) -> Path:
        path = self.assertFileExists(root, relpath)
        self.assertIn(expected, path.read_text(encoding="utf-8"))
        return path

    def assertJsonFile(self, root: Path, relpath: str, expected: Mapping[str, object]):
        value = load_json(self.assertFileExists(root, relpath))
        for key, expected_value in expected.items():
            self.assertEqual(value.get(key), expected_value, "{} in {}".format(key, relpath))
        return value

    def assertSqliteRows(
        self,
        path: Path,
        statement: str,
        expected: Sequence[Sequence[object]],
        parameters: Sequence[object] = (),
    ) -> None:
        self.assertTrue(Path(path).is_file(), "missing SQLite database: {}".format(path))
        with sqlite3.connect(str(path)) as connection:
            rows = connection.execute(statement, parameters).fetchall()
        self.assertEqual(rows, [tuple(row) for row in expected])

    def assertSqliteScalar(
        self,
        path: Path,
        statement: str,
        expected,
        parameters: Sequence[object] = (),
    ) -> None:
        self.assertTrue(Path(path).is_file(), "missing SQLite database: {}".format(path))
        with sqlite3.connect(str(path)) as connection:
            row = connection.execute(statement, parameters).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], expected)

    def assertSqliteIntegrity(self, path: Path) -> None:
        self.assertSqliteRows(path, "PRAGMA integrity_check", [("ok",)])

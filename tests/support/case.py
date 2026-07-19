"""A small unittest base for isolated CLI smoke tests."""

from __future__ import annotations

import unittest
from pathlib import Path

from .cli import CliResult, run_cli
from .environment import isolated_environment
from .files import FileAssertionsMixin


class CliTestCase(FileAssertionsMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._isolation = isolated_environment()
        self.isolated = self._isolation.__enter__()
        self.addCleanup(self._isolation.__exit__, None, None, None)

    def cli(self, *arguments: object, cwd: Path = None, input_text: str = None) -> CliResult:
        return run_cli(
            *arguments,
            cwd=cwd or self.isolated.workspace,
            env=self.isolated.env,
            input_text=input_text,
        )

    def assertCliSuccess(self, result: CliResult) -> CliResult:
        self.assertEqual(
            result.returncode,
            0,
            "command failed: {}\nstdout:\n{}\nstderr:\n{}".format(
                " ".join(result.command), result.stdout, result.stderr
            ),
        )
        return result

    def assertCliFailure(self, result: CliResult, code: int = 1) -> CliResult:
        self.assertEqual(
            result.returncode,
            code,
            "unexpected exit: {}\nstdout:\n{}\nstderr:\n{}".format(
                " ".join(result.command), result.stdout, result.stderr
            ),
        )
        self.assertNotIn("Traceback (most recent call last)", result.output)
        return result

    def initVault(self, *, minimal: bool = False, name: str = "vault with spaces") -> Path:
        vault = self.isolated.path(name)
        arguments = ["init", vault]
        if minimal:
            arguments.append("--minimal")
        self.assertCliSuccess(self.cli(*arguments))
        return vault

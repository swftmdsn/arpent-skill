#!/usr/bin/env python3
"""Stdlib test-suite runner for local and CI use."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import unittest
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = TEST_ROOT.parent
SUITE_PATHS = {
    "unit": (TEST_ROOT / "tests",),
    "smoke": (TEST_ROOT / "smoke",),
    "e2e": (TEST_ROOT / "e2e",),
    "regression": (TEST_ROOT / "regression",),
    "benchmark-offline": (TEST_ROOT / "benchmarks",),
}
ALL_SUITES = ("unit", "smoke", "e2e", "regression", "benchmark-offline")


def load_suite(names):
    loader = unittest.defaultTestLoader
    combined = unittest.TestSuite()
    seen = set()
    for name in names:
        for directory in SUITE_PATHS[name]:
            directory = directory.resolve()
            if directory in seen or not directory.is_dir():
                continue
            seen.add(directory)
            combined.addTests(loader.discover(
                str(directory),
                pattern="test*.py",
                top_level_dir=str(REPOSITORY_ROOT),
            ))
    return combined


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "suite",
        choices=(*SUITE_PATHS, "all"),
        nargs="?",
        default="all",
    )
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("-f", "--failfast", action="store_true")
    args = parser.parse_args(argv)

    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    if str(REPOSITORY_ROOT) not in sys.path:
        sys.path.insert(0, str(REPOSITORY_ROOT))
    names = ALL_SUITES if args.suite == "all" else (args.suite,)
    suite = load_suite(names)
    runner = unittest.TextTestRunner(
        verbosity=1 if args.quiet else 2,
        failfast=args.failfast,
    )
    tests_passed = runner.run(suite).wasSuccessful()
    benchmark_passed = True
    if args.suite in {"all", "benchmark-offline"}:
        benchmark = subprocess.run(
            [sys.executable, str(TEST_ROOT / "benchmarks" / "run.py"), "validate"],
            cwd=REPOSITORY_ROOT,
            env=os.environ.copy(),
            check=False,
            timeout=30,
        )
        benchmark_passed = benchmark.returncode == 0
    return 0 if tests_passed and benchmark_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

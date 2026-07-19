#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

BENCHMARK_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = BENCHMARK_DIR.parent.parent
if str(BENCHMARK_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_DIR))
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from benchlib.adapters import CommandJsonlAdapter, ReplayAdapter
from benchlib.corpus import load_bundle
from benchlib.errors import BenchmarkError
from benchlib.performance import run_performance, write_performance
from benchlib.reports import compare_reports, write_comparison, write_report
from benchlib.runner import evaluate


def _parser():
    parser = argparse.ArgumentParser(description="Arpent deterministic benchmark harness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="strictly validate corpus, goldens, and ideal traces")

    offline = subparsers.add_parser("offline", help="score ideal traces and emit static reports")
    offline.add_argument("--output", required=True, help="report output directory")

    live = subparsers.add_parser("live", help="evaluate scenarios through an adapter")
    live.add_argument("--adapter", required=True, choices=("replay", "command-jsonl"))
    live.add_argument("--adapter-command", help="quoted command for the command-jsonl adapter")
    live.add_argument("--adapter-timeout", type=float, default=120.0, help="seconds per adapter response")
    live.add_argument("--output", required=True, help="report output directory")

    compare = subparsers.add_parser("compare", help="compare a candidate report with a baseline")
    compare.add_argument("--baseline", required=True, help="baseline report.json")
    compare.add_argument("--candidate", required=True, help="candidate report.json")
    compare.add_argument("--output", required=True, help="comparison output directory")
    compare.add_argument("--score-tolerance", type=float, default=0.0)
    compare.add_argument("--byte-tolerance", type=int, default=0)

    performance = subparsers.add_parser(
        "performance", help="measure deterministic vault operations at several scales",
    )
    performance.add_argument(
        "--sizes", default="10,100,1000",
        help="comma-separated note counts (use 10,100,1000,5000 for a full run)",
    )
    performance.add_argument("--repeat", type=int, default=3)
    performance.add_argument("--output", required=True)
    return parser


def _performance_sizes(raw):
    try:
        sizes = [int(value.strip()) for value in raw.split(",") if value.strip()]
    except ValueError as exc:
        raise BenchmarkError("--sizes must contain comma-separated integers") from exc
    if not sizes or any(value < 1 for value in sizes) or len(sizes) != len(set(sizes)):
        raise BenchmarkError("--sizes must contain unique positive integers")
    return sizes


def _validate_ideal_scores(bundle):
    adapter = ReplayAdapter(bundle.traces)
    report, _ = evaluate(bundle, adapter, REPOSITORY_ROOT, "validation")
    failed = [result["scenario_id"] for result in report["scenarios"] if not result["passed"]]
    if failed:
        raise BenchmarkError("ideal traces do not satisfy goldens: %s" % ", ".join(failed))
    return report


def main(argv=None):
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "performance":
            if arguments.repeat < 1:
                raise BenchmarkError("--repeat must be positive")
            report = run_performance(_performance_sizes(arguments.sizes), arguments.repeat)
            write_performance(arguments.output, report)
            print("performance: %d scale(s), passed=%s; reports: %s" % (
                len(report["scales"]), str(report["passed"]).lower(),
                Path(arguments.output).resolve(),
            ))
            return 0 if report["passed"] else 1
        if arguments.command == "compare":
            if arguments.score_tolerance < 0 or arguments.byte_tolerance < 0:
                raise BenchmarkError("comparison tolerances must be non-negative")
            comparison = compare_reports(
                arguments.baseline,
                arguments.candidate,
                arguments.score_tolerance,
                arguments.byte_tolerance,
            )
            write_comparison(arguments.output, comparison)
            print("comparison: %d regression(s); reports: %s" % (
                comparison["regression_count"], Path(arguments.output).resolve()
            ))
            return 1 if comparison["regression_count"] else 0

        bundle = load_bundle(BENCHMARK_DIR, require_traces=True)
        if arguments.command == "validate":
            report = _validate_ideal_scores(bundle)
            print("valid: %d scenarios, %d goldens, %d ideal traces; ideal mean score %.2f" % (
                len(bundle.scenarios), len(bundle.goldens), len(bundle.traces), report["summary"]["mean_score"]
            ))
            return 0

        if arguments.command == "offline":
            adapter = ReplayAdapter(bundle.traces)
            mode = "offline"
        else:
            mode = "live"
            if arguments.adapter == "replay":
                if arguments.adapter_command:
                    raise BenchmarkError("--adapter-command is invalid with replay")
                adapter = ReplayAdapter(bundle.traces)
            else:
                if not arguments.adapter_command:
                    raise BenchmarkError("--adapter-command is required with command-jsonl")
                if arguments.adapter_timeout <= 0:
                    raise BenchmarkError("--adapter-timeout must be positive")
                adapter = CommandJsonlAdapter(arguments.adapter_command, arguments.adapter_timeout)

        try:
            report, traces = evaluate(bundle, adapter, REPOSITORY_ROOT, mode)
        finally:
            adapter.close()
        write_report(arguments.output, report, traces)
        print("%s/%s: %d/%d passed, mean score %.2f; reports: %s" % (
            mode, adapter.name, report["summary"]["passed"], report["summary"]["scenario_count"],
            report["summary"]["mean_score"], Path(arguments.output).resolve(),
        ))
        return 1 if report["summary"]["failed"] else 0
    except (BenchmarkError, OSError) as exc:
        print("benchmark error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

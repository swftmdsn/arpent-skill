import json
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

from scripts import context as context_mod
from scripts import frontmatter
from scripts import index as index_mod
from scripts import notes
from scripts import views
from scripts.vault import init_vault

from .jsonio import atomic_write_text


COMMON_TERM = "benchmarkcommon"


def _percentile(samples, percentile):
    ordered = sorted(samples)
    if not ordered:
        return 0.0
    rank = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * percentile)))
    return ordered[rank]


def _encoded_size(value):
    return len(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8"))


def _materialize_vault(parent, note_count):
    started = time.perf_counter()
    vault = init_vault(Path(parent) / "vault", minimal=True)
    destination = vault.root / "03_resources" / "benchmark"
    destination.mkdir(parents=True, exist_ok=True)
    fixture_bytes = 0
    for number in range(note_count):
        title = "benchmark_note_%06d" % number
        body = "%s unique%06d\n" % (COMMON_TERM, number)
        metadata = notes._blank_frontmatter()
        metadata.update({
            "title": title,
            "id": "note-20260101-%06d" % number,
            "created": "01-01-2026-00-00",
            "modified": "01-01-2026-00-00",
            "description": "Deterministic performance fixture.",
            "type": "note",
            "resource": "benchmark",
            "status": "stable",
            "source": "generated",
            "author": "agent",
        })
        notes.validate_frontmatter_values(metadata)
        content = frontmatter.compose_note(metadata, body)
        (destination / (title + ".md")).write_text(content, encoding="utf-8")
        fixture_bytes += len(content.encode("utf-8"))

    inbox_count = max(1, note_count // 100)
    for number in range(inbox_count):
        content = "raw performance inbox item %d\n" % number
        (vault.root / "00_inbox" / ("raw_%06d.txt" % number)).write_text(
            content, encoding="utf-8",
        )
        fixture_bytes += len(content.encode("utf-8"))
    return vault, inbox_count, fixture_bytes, time.perf_counter() - started


def _measure(operation, repeat):
    samples = []
    result = None
    for _ in range(repeat):
        started = time.perf_counter()
        result = operation()
        samples.append((time.perf_counter() - started) * 1000)
    return {
        "samples_ms": [round(value, 3) for value in samples],
        "p50_ms": round(statistics.median(samples), 3),
        "p95_ms": round(_percentile(samples, 0.95), 3),
        "min_ms": round(min(samples), 3),
        "max_ms": round(max(samples), 3),
        "result_utf8_bytes": _encoded_size(result),
    }, result


def run_scale(note_count, repeat):
    with tempfile.TemporaryDirectory() as temporary:
        vault, inbox_count, fixture_bytes, setup_seconds = _materialize_vault(
            temporary, note_count,
        )
        operations = {}
        operations["status"], status = _measure(lambda: views.status(vault), repeat)
        operations["index"], index = _measure(lambda: index_mod.build_index(vault), repeat)
        operations["search"], hits = _measure(
            lambda: views.search(vault, COMMON_TERM), repeat,
        )
        operations["context_pending"], pending = _measure(
            lambda: context_mod.pending_summaries(vault), repeat,
        )
        operations["triage"], triage = _measure(lambda: views.triage_items(vault), repeat)

        checks = {
            "status_note_count": status["total"] == note_count,
            "index_note_count": index["note_count"] == note_count,
            "search_complete": len(hits) == note_count,
            "search_ids_unique": len({item["id"] for item in hits}) == note_count,
            "context_covers_notes": sum(
                item.get("kind") == "note" for item in pending
            ) >= note_count,
            "triage_raw_count": len(triage) == inbox_count,
        }
        return {
            "note_count": note_count,
            "inbox_count": inbox_count,
            "fixture_utf8_bytes": fixture_bytes,
            "fixture_setup_seconds_excluded": round(setup_seconds, 3),
            "repeat": repeat,
            "passed": all(checks.values()),
            "checks": checks,
            "operations": operations,
        }


def run_performance(sizes, repeat):
    scales = [run_scale(size, repeat) for size in sizes]
    return {
        "schema_version": 1,
        "kind": "arpent-performance-benchmark",
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "passed": all(scale["passed"] for scale in scales),
        "scales": scales,
    }


def write_performance(output_dir, report):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        output / "performance.json",
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    lines = [
        "# Arpent Performance Benchmark",
        "",
        "Fixture construction time is reported but excluded from operation timings.",
        "Absolute latency is environment-dependent and must not gate ordinary CI.",
        "",
        "| Notes | Operation | p50 ms | p95 ms | Result bytes |",
        "|---:|---|---:|---:|---:|",
    ]
    for scale in report["scales"]:
        for name, metrics in scale["operations"].items():
            lines.append("| %d | `%s` | %.3f | %.3f | %d |" % (
                scale["note_count"], name, metrics["p50_ms"], metrics["p95_ms"],
                metrics["result_utf8_bytes"],
            ))
    lines.append("")
    atomic_write_text(output / "performance.md", "\n".join(lines))

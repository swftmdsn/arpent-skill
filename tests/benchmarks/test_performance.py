import tempfile
import unittest
from pathlib import Path

from .benchlib.performance import run_performance, write_performance


class PerformanceBenchmarkTests(unittest.TestCase):
    def test_small_scale_exercises_all_operations_and_writes_reports(self):
        report = run_performance([10], 1)
        self.assertTrue(report["passed"])
        scale = report["scales"][0]
        self.assertEqual(10, scale["note_count"])
        self.assertEqual(
            {"status", "index", "search", "context_pending", "triage"},
            set(scale["operations"]),
        )
        with tempfile.TemporaryDirectory() as temporary:
            write_performance(temporary, report)
            self.assertTrue((Path(temporary) / "performance.json").is_file())
            self.assertTrue((Path(temporary) / "performance.md").is_file())


if __name__ == "__main__":
    unittest.main()

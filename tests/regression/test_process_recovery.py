from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from scripts import frontmatter, notes, todo
from scripts.vault import MUTATION_TRANSACTION_PATHS, set_vault_mode
from tests.regression._support import ROOT, initialized, run_cli


PROCESS_TIMEOUT = 15
CRASH_EXIT = 91

NOTE_CRASH_CHILD = r"""
import os
import sys

from scripts import notes
from scripts.cli import main


def crash_before_commit(vault, journal):
    os._exit(91)


notes._commit_note_transaction = crash_before_commit
raise SystemExit(main([
    "note", "new", sys.argv[1], "--body", sys.argv[2], "--json",
]))
"""

TODO_CRASH_CHILD = r"""
import os
import sys

from scripts import todo
from scripts.cli import main


def crash_after_database_commit(vault, journal):
    os._exit(91)


todo._commit_transaction = crash_after_database_commit
raise SystemExit(main([
    "todo", "edit", sys.argv[1], "--content", sys.argv[2], "--yes",
]))
"""

CONCURRENT_NOTE_CHILD = r"""
import os
import sys
import time
from pathlib import Path

from scripts.cli import main


ready = Path(sys.argv[1])
gate = Path(sys.argv[2])
ready.write_text("ready\n", encoding="utf-8")
deadline = time.monotonic() + 10
while not gate.exists():
    if time.monotonic() >= deadline:
        os._exit(97)
    time.sleep(0.01)
raise SystemExit(main([
    "note", "new", sys.argv[3], "--body", sys.argv[4], "--json",
]))
"""

PROJECT_CRASH_CHILD = r"""
import os
import sys

from scripts.cli import main
from scripts.vault import Vault


original_create = Vault.atomic_create_text


def crash_after_staged_context(vault, relpath, content):
    result = original_create(vault, relpath, content)
    if relpath.endswith("/.process-recovery-project.arpent-project-staging/_context.md"):
        os._exit(91)
    return result


Vault.atomic_create_text = crash_after_staged_context
raise SystemExit(main(["project", "create", sys.argv[1], "--yes"]))
"""


def _environment(vault: Path) -> dict[str, str]:
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(ROOT) if not existing else f"{ROOT}{os.pathsep}{existing}"
    )
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["ARPENT_VAULT_ROOT"] = str(vault)
    return environment


def _run_child(vault: Path, source: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", source, *args],
        cwd=ROOT,
        env=_environment(vault),
        capture_output=True,
        text=True,
        check=False,
        shell=False,
        timeout=PROCESS_TIMEOUT,
    )


class RealProcessRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.vault = initialized(Path(self.temporary.name))
        set_vault_mode(self.vault, "full")

    def assertNoTraceback(self, *outputs: str) -> None:
        for output in outputs:
            self.assertNotIn("Traceback", output)

    def assertNoTransactionJournal(self) -> None:
        remaining = [
            relpath
            for relpath in MUTATION_TRANSACTION_PATHS
            if (self.vault.root / relpath).exists()
        ]
        self.assertEqual([], remaining)

    def test_note_create_recovers_after_process_exit_before_durable_commit(self):
        title = "Process recovery note"
        body = "body retained exactly once"

        crashed = _run_child(self.vault.root, NOTE_CRASH_CHILD, title, body)

        self.assertEqual(CRASH_EXIT, crashed.returncode, crashed.stderr)
        self.assertNoTraceback(crashed.stdout, crashed.stderr)
        journal_path = self.vault.root / notes.TRANSACTION_RELPATH
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        self.assertEqual("prepared", journal["phase"])
        self.assertTrue((self.vault.root / "00_inbox/process_recovery_note.md").is_file())

        recovered = run_cli(
            self.vault.root, "note", "new", title, "--body", body, "--json",
        )

        self.assertEqual(0, recovered.returncode, recovered.stderr)
        self.assertNoTraceback(recovered.stdout, recovered.stderr)
        result = json.loads(recovered.stdout)
        path = self.vault.root / result["path"]
        metadata, recovered_body = frontmatter.read_note(path)
        self.assertEqual(result["id"], metadata["id"])
        self.assertEqual(body, recovered_body)
        matching = [
            (note_path, note_metadata)
            for note_path, note_metadata, _ in self.vault.iter_notes()
            if note_metadata.get("title") == "process_recovery_note"
        ]
        self.assertEqual([(path, metadata)], matching)
        self.assertNoTransactionJournal()

    def test_todo_recovery_keeps_commit_after_process_exit_before_journal_removal(self):
        created_process = run_cli(
            self.vault.root, "todo", "add", "Before process crash", "--json",
        )
        self.assertEqual(0, created_process.returncode, created_process.stderr)
        created = json.loads(created_process.stdout)
        todo_id = created["id"]
        changed_content = "After durable process commit"

        crashed = _run_child(
            self.vault.root,
            TODO_CRASH_CHILD,
            todo_id,
            changed_content,
        )

        self.assertEqual(CRASH_EXIT, crashed.returncode, crashed.stderr)
        self.assertNoTraceback(crashed.stdout, crashed.stderr)
        journal_path = self.vault.root / todo.TRANSACTION_RELPATH
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        self.assertEqual("prepared", journal["phase"])
        self.assertEqual(changed_content, journal["expected_db"]["content"])

        recovered_process = run_cli(
            self.vault.root, "todo", "show", todo_id, "--json",
        )

        self.assertEqual(0, recovered_process.returncode, recovered_process.stderr)
        self.assertNoTraceback(recovered_process.stdout, recovered_process.stderr)
        recovered = json.loads(recovered_process.stdout)
        self.assertEqual(changed_content, recovered["content"])
        self.assertEqual(
            "02_areas/area__perso__todo__active/active/after_durable_process_commit.md",
            recovered["path"],
        )
        records = [
            (path, metadata)
            for path, metadata, _ in self.vault.iter_notes()
            if metadata.get("id") == todo_id
        ]
        self.assertEqual(1, len(records))
        self.assertEqual(self.vault.root / recovered["path"], records[0][0])
        self.assertNoTransactionJournal()

    def test_independent_processes_create_unique_notes_without_residue(self):
        process_count = 6
        barrier = Path(self.temporary.name) / "process-barrier"
        barrier.mkdir()
        gate = barrier / "go"
        processes = []
        try:
            for index in range(process_count):
                ready = barrier / f"ready-{index}"
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        CONCURRENT_NOTE_CHILD,
                        str(ready),
                        str(gate),
                        f"Concurrent process note {index}",
                        f"body from process {index}",
                    ],
                    cwd=ROOT,
                    env=_environment(self.vault.root),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=False,
                )
                processes.append(process)

            ready_deadline = time.monotonic() + PROCESS_TIMEOUT
            while len(list(barrier.glob("ready-*"))) != process_count:
                failed = [process.returncode for process in processes if process.poll() is not None]
                if failed:
                    self.fail(f"note process exited before the barrier: {failed}")
                if time.monotonic() >= ready_deadline:
                    self.fail("timed out waiting for concurrent note processes")
                time.sleep(0.01)
            gate.write_text("go\n", encoding="utf-8")

            results = []
            completion_deadline = time.monotonic() + PROCESS_TIMEOUT
            for process in processes:
                remaining = max(0.01, completion_deadline - time.monotonic())
                stdout, stderr = process.communicate(timeout=remaining)
                results.append((process.returncode, stdout, stderr))
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate()

        for returncode, stdout, stderr in results:
            self.assertEqual(0, returncode, stderr)
            self.assertNoTraceback(stdout, stderr)
        created = [json.loads(stdout) for _, stdout, _ in results]
        self.assertEqual(process_count, len({item["id"] for item in created}))
        self.assertEqual(process_count, len({item["path"] for item in created}))
        self.assertTrue(all((self.vault.root / item["path"]).is_file() for item in created))
        self.assertNoTransactionJournal()

    def test_project_staging_survives_process_exit_and_retry(self):
        name = "Process recovery project"
        crashed = _run_child(self.vault.root, PROJECT_CRASH_CHILD, name)

        self.assertEqual(CRASH_EXIT, crashed.returncode, crashed.stderr)
        self.assertNoTraceback(crashed.stdout, crashed.stderr)
        staging = (
            self.vault.root
            / "01_projects/.process-recovery-project.arpent-project-staging"
        )
        staged_metadata, _ = frontmatter.read_note(staging / "_context.md")

        recovered = run_cli(
            self.vault.root, "project", "create", name, "--yes",
        )

        self.assertEqual(0, recovered.returncode, recovered.stderr)
        self.assertNoTraceback(recovered.stdout, recovered.stderr)
        project = self.vault.root / "01_projects/process-recovery-project"
        final_metadata, _ = frontmatter.read_note(project / "_context.md")
        self.assertEqual(staged_metadata["id"], final_metadata["id"])
        self.assertFalse(staging.exists())
        for child in ("notes", "drafts", "attachments"):
            self.assertTrue((project / child).is_dir())
        self.assertNoTransactionJournal()


if __name__ == "__main__":
    unittest.main()

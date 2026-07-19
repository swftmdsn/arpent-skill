import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import cli
from scripts import index as index_mod
from scripts import notes
from scripts.vault import init_vault
from tests.support.cli import run_cli


class PaginationTests(unittest.TestCase):
    def test_pages_are_complete_without_duplicates(self):
        items = [{"path": f"item-{index}"} for index in range(5)]

        first = cli._page_items(items, view="test", limit=2)
        second = cli._page_items(
            items,
            view="test",
            limit=2,
            cursor=first["page"]["next_cursor"],
        )
        third = cli._page_items(
            items,
            view="test",
            limit=2,
            cursor=second["page"]["next_cursor"],
        )

        combined = first["items"] + second["items"] + third["items"]
        self.assertEqual(combined, items)
        self.assertTrue(first["page"]["has_more"])
        self.assertFalse(third["page"]["has_more"])
        self.assertEqual(first["summary"]["total"], 5)

    def test_cursor_rejects_changed_results_and_queries(self):
        items = [{"path": "a"}, {"path": "b"}]
        first = cli._page_items(
            items,
            view="test",
            limit=1,
            query={"status": "active"},
        )
        cursor = first["page"]["next_cursor"]

        with self.assertRaisesRegex(ValueError, "stale"):
            cli._page_items(
                items + [{"path": "c"}],
                view="test",
                limit=1,
                cursor=cursor,
                query={"status": "active"},
            )
        with self.assertRaisesRegex(ValueError, "does not match"):
            cli._page_items(
                items,
                view="test",
                limit=1,
                cursor=cursor,
                query={"status": "done"},
            )

    def test_utf8_content_pages_reconstruct_exact_text(self):
        text = "début\n" + "élément " * 20 + "\nfin"
        pages = []
        cursor = None
        while True:
            page = cli._page_text(
                text,
                view="note-read",
                path="note.md",
                max_bytes=17,
                cursor=cursor,
            )
            pages.append(page["content"])
            cursor = page["page"]["next_cursor"]
            if cursor is None:
                break

        self.assertEqual("".join(pages), text)

    def test_tiny_page_advances_past_multibyte_character(self):
        first = cli._page_text(
            "😀x",
            view="note-read",
            path="note.md",
            max_bytes=1,
        )
        self.assertEqual(first["content"], "😀")
        self.assertGreater(first["page"]["end_byte_exclusive"], 0)

    def test_volatile_display_age_does_not_stale_stable_snapshot(self):
        first_items = [{"path": "a", "sha256": "1", "age_seconds": 1}]
        stable = [{"path": "a", "sha256": "1"}]
        first = cli._page_items(
            first_items + [{"path": "b", "sha256": "2", "age_seconds": 1}],
            view="triage",
            limit=1,
            snapshot_items=stable + [{"path": "b", "sha256": "2"}],
        )
        second = cli._page_items(
            [{"path": "a", "sha256": "1", "age_seconds": 5},
             {"path": "b", "sha256": "2", "age_seconds": 5}],
            view="triage",
            limit=1,
            cursor=first["page"]["next_cursor"],
            snapshot_items=stable + [{"path": "b", "sha256": "2"}],
        )
        self.assertEqual(second["items"][0]["path"], "b")

    def test_content_cursor_rejects_source_change(self):
        first = cli._page_text(
            "one two three four",
            view="note-read",
            path="note.md",
            max_bytes=5,
        )
        with self.assertRaisesRegex(ValueError, "stale"):
            cli._page_text(
                "one changed three four",
                view="note-read",
                path="note.md",
                max_bytes=5,
                cursor=first["page"]["next_cursor"],
            )

    def _populate_search_notes(self, root):
        vault = init_vault(root / "vault", minimal=False)
        for index in range(55):
            plan = notes.plan_note_new(
                vault,
                title=f"Search result {index}",
                ntype="note",
                body="shared-search-token",
            )
            notes.apply_note_new(vault, plan)
        return vault

    def _disable_fts_for_build(self, vault):
        real_connect = index_mod.sqlite3.connect

        def connect_without_fts(*args, **kwargs):
            connection = real_connect(*args, **kwargs)
            wrapped = mock.Mock(wraps=connection)

            def execute(sql, *parameters):
                if "CREATE VIRTUAL TABLE" in sql:
                    raise index_mod.sqlite3.OperationalError("no such module: fts5")
                return connection.execute(sql, *parameters)

            wrapped.execute.side_effect = execute
            return wrapped

        with mock.patch.object(index_mod.sqlite3, "connect", side_effect=connect_without_fts):
            search_available = index_mod.build_search_db(vault)
        self.assertFalse(search_available)
        self.assertFalse((vault.root / "06_indexes/databases/search.db").exists())

    def test_search_fallback_follows_real_cli_cursors_to_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = self._populate_search_notes(Path(temporary))
            self._disable_fts_for_build(vault)
            items = []
            cursor = None
            pages = 0
            while True:
                arguments = [
                    "search", "shared-search-token", "--json-page", "--limit", "13",
                ]
                if cursor is not None:
                    arguments.extend(("--cursor", cursor))
                result = run_cli(*arguments, cwd=vault.root)
                self.assertEqual(0, result.returncode, result.output)
                page = json.loads(result.stdout)
                self.assertEqual({"text-fallback": 55}, page["summary"]["by_backend"])
                items.extend(page["items"])
                pages += 1
                cursor = page["page"]["next_cursor"]
                if cursor is None:
                    self.assertFalse(page["page"]["has_more"])
                    break
            self.assertEqual(5, pages)
            self.assertEqual(55, len(items))
            self.assertEqual(55, len({item["path"] for item in items}))
            self.assertEqual({"text-fallback"}, {item["backend"] for item in items})

    def test_fts5_backend_is_required_when_sqlite_provides_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = self._populate_search_notes(Path(temporary))
            if not index_mod.build_search_db(vault):
                self.skipTest("SQLite FTS5 is unavailable in this Python build")
            result = run_cli(
                "search", "shared-search-token", "--json-page", "--all", cwd=vault.root,
            )
            self.assertEqual(0, result.returncode, result.output)
            page = json.loads(result.stdout)
            self.assertEqual({"fts5": 55}, page["summary"]["by_backend"])
            self.assertEqual(55, len(page["items"]))
            self.assertEqual({"fts5"}, {item["backend"] for item in page["items"]})

    def test_search_includes_frontmatter_link_in_fts_and_live_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            link = "https://example.test/unique-prior-art-source"
            plan = notes.plan_note_new(
                vault,
                title="Opaque reference",
                ntype="reference",
                body="No searchable source token in this body.",
                source="captured",
                link=link,
            )
            notes.apply_note_new(vault, plan)

            fallback = run_cli(
                "search", link, "--json-page", "--all", cwd=vault.root,
            )
            self.assertEqual(0, fallback.returncode, fallback.output)
            fallback_page = json.loads(fallback.stdout)
            self.assertEqual({"text-fallback": 1}, fallback_page["summary"]["by_backend"])
            self.assertEqual(plan["frontmatter"]["id"], fallback_page["items"][0]["id"])

            built = index_mod.build_index(vault)
            sidecar = json.loads(
                (vault.root / "06_indexes/sidecar.json").read_text(encoding="utf-8")
            )
            self.assertEqual(link, sidecar[plan["destination_path"]]["link"])
            if built["search_backend"] != "fts5":
                self.skipTest("SQLite FTS5 is unavailable in this Python build")
            indexed = run_cli(
                "search", link, "--json-page", "--all", cwd=vault.root,
            )
            self.assertEqual(0, indexed.returncode, indexed.output)
            indexed_page = json.loads(indexed.stdout)
            self.assertEqual({"fts5": 1}, indexed_page["summary"]["by_backend"])
            self.assertEqual(plan["frontmatter"]["id"], indexed_page["items"][0]["id"])


if __name__ == "__main__":
    unittest.main()

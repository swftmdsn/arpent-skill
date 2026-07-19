import tempfile
import unittest
from pathlib import Path

from scripts import cli
from scripts import index as index_mod
from scripts import notes
from scripts import views
from scripts.vault import init_vault


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

    def test_fts_search_is_not_silently_limited_to_fifty(self):
        with tempfile.TemporaryDirectory() as temporary:
            vault = init_vault(Path(temporary) / "vault", minimal=False)
            for index in range(55):
                plan = notes.plan_note_new(
                    vault,
                    title=f"Search result {index}",
                    ntype="note",
                    body="shared-search-token",
                )
                notes.apply_note_new(vault, plan)
            index_mod.build_index(vault)

            hits = views.search(vault, "shared-search-token")

            self.assertEqual(len(hits), 55)
            self.assertTrue(all(hit["backend"] == "fts5" for hit in hits))


if __name__ == "__main__":
    unittest.main()

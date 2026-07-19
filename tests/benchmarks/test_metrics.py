import tempfile
import unittest

from .benchlib.metrics import MetricState, calculate_metrics, common_prefix_bytes, utf8_bytes


def scenario(identifier, conversation, prompt="Prompt é"):
    return {
        "id": identifier,
        "conversation_id": conversation,
        "prompt": prompt,
        "fixture": {
            "documents": [{"path": "doc.md", "content": "café"}],
        },
    }


def usage():
    return {
        "input_tokens": 10,
        "output_tokens": 4,
        "total_tokens": 14,
        "cached_input_tokens": 3,
        "cache_read_input_tokens": 2,
        "cache_creation_input_tokens": 1,
        "provider_reported_cost": 0.01,
        "currency": "USD",
        "source": "test-host",
        "raw": {"cache": "fixture"},
    }


class MetricTests(unittest.TestCase):
    def test_utf8_accounting_and_repeated_documents_are_exact(self):
        value = {
            "provider_usage": usage(),
            "events": [
                {"type": "request", "content": "Prompt é"},
                {"type": "read", "path": "doc.md"},
                {"type": "read", "path": "doc.md"},
                {"type": "final", "text": "ok"},
            ],
        }
        with tempfile.TemporaryDirectory() as root:
            metrics = calculate_metrics(scenario("one", "thread"), value, root)
        self.assertEqual(utf8_bytes("café") * 2, metrics["document_utf8_bytes"])
        self.assertEqual(utf8_bytes("café"), metrics["unique_document_utf8_bytes"])
        self.assertEqual(utf8_bytes("café"), metrics["repeated_document_utf8_bytes"])
        self.assertEqual((utf8_bytes("Prompt é") + 3) // 4, metrics["utf8_byte_quarter_estimate"])
        self.assertEqual(14, metrics["provider_total_tokens"])
        self.assertEqual(3, metrics["provider_cached_input_tokens"])
        self.assertEqual(2, metrics["provider_cache_read_input_tokens"])
        self.assertEqual(1, metrics["provider_cache_creation_input_tokens"])
        self.assertEqual(0.01, metrics["provider_reported_cost"])

    def test_write_then_read_is_resolved_without_touching_disk(self):
        value = {
            "provider_usage": None,
            "events": [
                {"type": "request", "content": "Prompt é"},
                {"type": "write", "path": "new.md", "content": "written"},
                {"type": "read", "path": "new.md"},
                {"type": "final", "text": "ok"},
            ],
        }
        with tempfile.TemporaryDirectory() as root:
            metrics = calculate_metrics(scenario("one", "thread"), value, root)
        self.assertEqual(7, metrics["document_utf8_bytes"])
        self.assertEqual(7, metrics["write_utf8_bytes"])

    def test_stable_prefix_crosses_scenarios_in_one_conversation(self):
        state = MetricState()
        first = {
            "provider_usage": None,
            "events": [
                {"type": "request", "content": "stable prefix: first"},
                {"type": "final", "text": "ok"},
            ],
        }
        second = {
            "provider_usage": None,
            "events": [
                {"type": "request", "content": "stable prefix: second"},
                {"type": "final", "text": "ok"},
            ],
        }
        with tempfile.TemporaryDirectory() as root:
            calculate_metrics(scenario("one", "thread"), first, root, state)
            metrics = calculate_metrics(scenario("two", "thread"), second, root, state)
        self.assertEqual(common_prefix_bytes("stable prefix: first", "stable prefix: second"), metrics["stable_prefix_utf8_bytes"])


if __name__ == "__main__":
    unittest.main()

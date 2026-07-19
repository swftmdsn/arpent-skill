import hashlib
import re
from pathlib import Path

from .errors import ValidationError


CLI_RE = re.compile(r"(?:^|\s)(?:arpent|arp)(?:\s|$)")
METRIC_KEYS = {
    "prompt_utf8_bytes", "request_utf8_bytes", "document_utf8_bytes",
    "unique_document_utf8_bytes", "repeated_document_utf8_bytes",
    "command_utf8_bytes", "command_output_utf8_bytes", "write_utf8_bytes",
    "claim_utf8_bytes", "final_utf8_bytes", "cumulative_input_proxy_utf8_bytes",
    "utf8_byte_quarter_estimate", "stable_prefix_utf8_bytes", "request_count",
    "tool_count", "command_count", "cli_count", "provider_input_tokens",
    "provider_output_tokens", "provider_total_tokens", "provider_cached_input_tokens",
    "provider_cache_read_input_tokens", "provider_cache_creation_input_tokens",
    "provider_reported_cost", "provider_reported_cost_currency",
}


def utf8_bytes(text):
    return len(text.encode("utf-8"))


def common_prefix_bytes(left, right):
    left_bytes = left.encode("utf-8")
    right_bytes = right.encode("utf-8")
    count = 0
    for left_byte, right_byte in zip(left_bytes, right_bytes):
        if left_byte != right_byte:
            break
        count += 1
    return count


class DocumentResolver:
    def __init__(self, repository_root, scenario):
        self.repository_root = Path(repository_root).resolve()
        self.scenario = scenario
        self.fixture_documents = {
            document["path"]: document["content"]
            for document in scenario["fixture"]["documents"]
        }

    def write(self, relative_path, content):
        self.fixture_documents[relative_path] = content

    def read(self, relative_path):
        if relative_path in self.fixture_documents:
            return self.fixture_documents[relative_path]
        if relative_path == "06_indexes/cli/operations.yaml":
            content = (self.repository_root / "scripts" / "operations.yaml").read_text(encoding="utf-8")
            policy = self.scenario["fixture"]["confirmation"]
            if policy in ("always", "explicit-intent", "never"):
                content = re.sub(r"(?m)^(  policy: ).+$", r"\g<1>" + policy, content, count=1)
            return content
        candidate = (self.repository_root / relative_path).resolve()
        try:
            candidate.relative_to(self.repository_root)
        except ValueError as exc:
            raise ValidationError("read path escapes repository: %s" % relative_path) from exc
        if not candidate.is_file():
            raise ValidationError("read event cannot be resolved: %s" % relative_path)
        try:
            return candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ValidationError("read event is not a UTF-8 document: %s" % relative_path) from exc


class MetricState:
    def __init__(self):
        self.previous_request_by_conversation = {}
        self.seen_documents = set()


def calculate_metrics(scenario, trace, repository_root, state=None):
    state = state or MetricState()
    resolver = DocumentResolver(repository_root, scenario)
    requests = [event["content"] for event in trace["events"] if event["type"] == "request"]
    reads = [event for event in trace["events"] if event["type"] == "read"]
    commands = [event for event in trace["events"] if event["type"] == "command"]
    writes = [event for event in trace["events"] if event["type"] == "write"]
    claims = [event for event in trace["events"] if event["type"] == "claim"]
    finals = [event for event in trace["events"] if event["type"] == "final"]

    document_bytes = 0
    unique_document_bytes = 0
    for event in trace["events"]:
        if event["type"] == "write":
            resolver.write(event["path"], event["content"])
        elif event["type"] == "read":
            content = resolver.read(event["path"])
            size = utf8_bytes(content)
            document_bytes += size
            identity = (event["path"], hashlib.sha256(content.encode("utf-8")).hexdigest())
            if identity not in state.seen_documents:
                unique_document_bytes += size
                state.seen_documents.add(identity)

    stable_prefix = 0
    previous = state.previous_request_by_conversation.get(scenario["conversation_id"])
    for request in requests:
        if previous is not None:
            stable_prefix += common_prefix_bytes(previous, request)
        previous = request
    if previous is not None:
        state.previous_request_by_conversation[scenario["conversation_id"]] = previous

    cumulative_input_proxy = sum(utf8_bytes(request) for request in requests)
    usage = trace["provider_usage"]
    return {
        "prompt_utf8_bytes": utf8_bytes(scenario["prompt"]),
        "request_utf8_bytes": cumulative_input_proxy,
        "document_utf8_bytes": document_bytes,
        "unique_document_utf8_bytes": unique_document_bytes,
        "repeated_document_utf8_bytes": document_bytes - unique_document_bytes,
        "command_utf8_bytes": sum(utf8_bytes(event["command"]) for event in commands),
        "command_output_utf8_bytes": sum(utf8_bytes(event["output"]) for event in commands),
        "write_utf8_bytes": sum(utf8_bytes(event["content"]) for event in writes),
        "claim_utf8_bytes": sum(utf8_bytes(event["text"]) for event in claims),
        "final_utf8_bytes": sum(utf8_bytes(event["text"]) for event in finals),
        "cumulative_input_proxy_utf8_bytes": cumulative_input_proxy,
        "utf8_byte_quarter_estimate": (cumulative_input_proxy + 3) // 4,
        "stable_prefix_utf8_bytes": stable_prefix,
        "request_count": len(requests),
        "tool_count": len(reads) + len(commands) + len(writes),
        "command_count": len(commands),
        "cli_count": sum(1 for event in commands if CLI_RE.search(event["command"])),
        "provider_input_tokens": None if usage is None else usage["input_tokens"],
        "provider_output_tokens": None if usage is None else usage["output_tokens"],
        "provider_total_tokens": None if usage is None else usage["total_tokens"],
        "provider_cached_input_tokens": None if usage is None else usage["cached_input_tokens"],
        "provider_cache_read_input_tokens": (
            None if usage is None else usage["cache_read_input_tokens"]
        ),
        "provider_cache_creation_input_tokens": (
            None if usage is None else usage["cache_creation_input_tokens"]
        ),
        "provider_reported_cost": None if usage is None else usage["provider_reported_cost"],
        "provider_reported_cost_currency": None if usage is None else usage["currency"],
    }

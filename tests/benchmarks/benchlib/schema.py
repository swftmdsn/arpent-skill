import re
from pathlib import PurePosixPath

from . import PROTOCOL_VERSION, SCHEMA_VERSION
from .errors import ValidationError


SCENARIO_KEYS = {
    "schema_version", "id", "title", "category", "description",
    "conversation_id", "turn_index", "prompt", "fixture", "tags",
    "stateful_eligible",
}
FIXTURE_KEYS = {"vault_mode", "skill_loaded", "confirmation", "documents"}
DOCUMENT_KEYS = {"path", "content"}
GOLDEN_KEYS = {
    "schema_version", "scenario_id", "required_reads", "forbidden_reads",
    "required_commands", "forbidden_commands", "required_claims",
    "forbidden_claims", "required_writes", "forbidden_writes",
    "command_results", "write_results", "final_size", "hard_failures",
    "command_bindings", "postconditions",
}
OPTIONAL_GOLDEN_KEYS = {
    "command_results", "write_results", "command_bindings", "postconditions",
}
COMMAND_RESULT_KEYS = {"command", "exit_code", "output_json"}
WRITE_RESULT_KEYS = {"path", "content", "sha256"}
COMMAND_BINDING_KEYS = {
    "source_command", "source_json_field", "target_command", "target_option",
}
POSTCONDITION_KEYS = {
    "command_json_fields": {"kind", "command", "fields"},
    "command_json_path_exists": {"kind", "command", "field"},
    "path_exists": {"kind", "path"},
}
FINAL_SIZE_KEYS = {"min_utf8_bytes", "max_utf8_bytes"}
USAGE_KEYS = {
    "input_tokens", "output_tokens", "total_tokens", "cached_input_tokens",
    "cache_read_input_tokens", "cache_creation_input_tokens",
    "provider_reported_cost", "currency", "source", "raw",
}
HARD_FAILURES = {
    "forbidden_read", "forbidden_command", "forbidden_claim",
    "forbidden_write", "missing_final", "command_failure", "write_mismatch",
}
EVENT_KEYS = {
    "request": {"type", "content"},
    "read": {"type", "path"},
    "command": {"type", "command", "output", "exit_code"},
    "write": {"type", "path", "content"},
    "claim": {"type", "text"},
    "final": {"type", "text"},
}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


def _object(value, where):
    if not isinstance(value, dict):
        raise ValidationError("%s must be an object" % where)
    return value


def _exact_keys(value, keys, where):
    _object(value, where)
    actual = set(value)
    if actual != keys:
        missing = sorted(keys - actual)
        extra = sorted(actual - keys)
        raise ValidationError("%s keys differ; missing=%s extra=%s" % (where, missing, extra))


def _string(value, where, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value):
        raise ValidationError("%s must be %sa string" % (where, "" if allow_empty else "a non-empty "))
    return value


def _integer(value, where, minimum=None):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("%s must be an integer" % where)
    if minimum is not None and value < minimum:
        raise ValidationError("%s must be >= %d" % (where, minimum))
    return value


def _number_or_none(value, where):
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValidationError("%s must be null or a non-negative number" % where)


def _json_value(value, where):
    if value is None or isinstance(value, (str, bool, int, float)):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _json_value(item, "%s[%d]" % (where, index))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _string(key, where + " key")
            _json_value(item, "%s.%s" % (where, key))
        return
    raise ValidationError("%s must contain only JSON values" % where)


def _safe_path(value, where):
    _string(value, where)
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value.startswith("~"):
        raise ValidationError("%s must be a safe relative POSIX path" % where)
    return value


def _string_list(value, where, allow_empty=True):
    if not isinstance(value, list) or (not allow_empty and not value):
        raise ValidationError("%s must be a list%s" % (where, "" if allow_empty else " with at least one item"))
    for index, item in enumerate(value):
        _string(item, "%s[%d]" % (where, index))
    if len(set(value)) != len(value):
        raise ValidationError("%s contains duplicates" % where)


def validate_scenario(value, where="scenario"):
    _exact_keys(value, SCENARIO_KEYS, where)
    if value["schema_version"] != SCHEMA_VERSION:
        raise ValidationError("%s.schema_version must be %d" % (where, SCHEMA_VERSION))
    scenario_id = _string(value["id"], where + ".id")
    if not SLUG_RE.fullmatch(scenario_id):
        raise ValidationError("%s.id must be a lowercase underscore slug" % where)
    for key in ("title", "category", "description", "conversation_id", "prompt"):
        _string(value[key], "%s.%s" % (where, key))
    _integer(value["turn_index"], where + ".turn_index", 1)
    _string_list(value["tags"], where + ".tags", allow_empty=False)
    if type(value["stateful_eligible"]) is not bool:
        raise ValidationError(where + ".stateful_eligible must be a boolean")
    fixture = value["fixture"]
    _exact_keys(fixture, FIXTURE_KEYS, where + ".fixture")
    if fixture["vault_mode"] not in ("full", "minimal", "none"):
        raise ValidationError("%s.fixture.vault_mode is invalid" % where)
    if type(fixture["skill_loaded"]) is not bool:
        raise ValidationError("%s.fixture.skill_loaded must be a boolean" % where)
    if fixture["confirmation"] not in ("always", "explicit-intent", "never", "none"):
        raise ValidationError("%s.fixture.confirmation is invalid" % where)
    if not isinstance(fixture["documents"], list):
        raise ValidationError("%s.fixture.documents must be a list" % where)
    paths = []
    for index, document in enumerate(fixture["documents"]):
        document_where = "%s.fixture.documents[%d]" % (where, index)
        _exact_keys(document, DOCUMENT_KEYS, document_where)
        paths.append(_safe_path(document["path"], document_where + ".path"))
        _string(document["content"], document_where + ".content", allow_empty=True)
    if len(paths) != len(set(paths)):
        raise ValidationError("%s.fixture.documents contains duplicate paths" % where)
    return value


def validate_golden(value, where="golden"):
    _object(value, where)
    missing = (GOLDEN_KEYS - OPTIONAL_GOLDEN_KEYS) - set(value)
    extra = set(value) - GOLDEN_KEYS
    if missing or extra:
        raise ValidationError("%s keys differ; missing=%s extra=%s" % (where, sorted(missing), sorted(extra)))
    if value["schema_version"] != SCHEMA_VERSION:
        raise ValidationError("%s.schema_version must be %d" % (where, SCHEMA_VERSION))
    _string(value["scenario_id"], where + ".scenario_id")
    pattern_keys = (
        "required_reads", "forbidden_reads", "required_commands",
        "forbidden_commands", "required_claims", "forbidden_claims",
        "required_writes", "forbidden_writes",
    )
    for key in pattern_keys:
        _string_list(value[key], "%s.%s" % (where, key))
        for index, pattern in enumerate(value[key]):
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValidationError("%s.%s[%d] invalid regex: %s" % (where, key, index, exc)) from exc
    if not isinstance(value.get("command_results", []), list):
        raise ValidationError(where + ".command_results must be a list")
    for index, result in enumerate(value.get("command_results", [])):
        result_where = "%s.command_results[%d]" % (where, index)
        _exact_keys(result, COMMAND_RESULT_KEYS, result_where)
        pattern = _string(result["command"], result_where + ".command")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValidationError(result_where + ".command invalid regex: %s" % exc) from exc
        _integer(result["exit_code"], result_where + ".exit_code")
        if result["exit_code"] != 0:
            raise ValidationError(result_where + ".exit_code must be 0")
        output_json = result["output_json"]
        if output_json is not None:
            _object(output_json, result_where + ".output_json")
            _string(output_json.get("format"), result_where + ".output_json.format")
            _integer(output_json.get("version"), result_where + ".output_json.version", 1)
            _json_value(output_json, result_where + ".output_json")
    if not isinstance(value.get("write_results", []), list):
        raise ValidationError(where + ".write_results must be a list")
    for index, result in enumerate(value.get("write_results", [])):
        result_where = "%s.write_results[%d]" % (where, index)
        _exact_keys(result, WRITE_RESULT_KEYS, result_where)
        pattern = _string(result["path"], result_where + ".path")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValidationError(result_where + ".path invalid regex: %s" % exc) from exc
        if result["content"] is not None:
            _string(result["content"], result_where + ".content", allow_empty=True)
        digest = result["sha256"]
        if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)):
            raise ValidationError(result_where + ".sha256 must be a lowercase SHA-256 digest or null")
        if result["content"] is None and digest is None:
            raise ValidationError(result_where + " must declare content, sha256, or both")
    if not isinstance(value.get("command_bindings", []), list):
        raise ValidationError(where + ".command_bindings must be a list")
    for index, binding in enumerate(value.get("command_bindings", [])):
        binding_where = "%s.command_bindings[%d]" % (where, index)
        _exact_keys(binding, COMMAND_BINDING_KEYS, binding_where)
        for key in COMMAND_BINDING_KEYS:
            item = _string(binding[key], "%s.%s" % (binding_where, key))
            if key.endswith("command"):
                try:
                    re.compile(item)
                except re.error as exc:
                    raise ValidationError("%s.%s invalid regex: %s" % (binding_where, key, exc)) from exc
        if not binding["source_json_field"].replace("_", "a").replace(".", "a").isalnum():
            raise ValidationError(binding_where + ".source_json_field must be a dotted field path")
        if not binding["target_option"].startswith("--"):
            raise ValidationError(binding_where + ".target_option must be a long option")
    if not isinstance(value.get("postconditions", []), list):
        raise ValidationError(where + ".postconditions must be a list")
    for index, postcondition in enumerate(value.get("postconditions", [])):
        postcondition_where = "%s.postconditions[%d]" % (where, index)
        _object(postcondition, postcondition_where)
        kind = postcondition.get("kind")
        if kind not in POSTCONDITION_KEYS:
            raise ValidationError(postcondition_where + ".kind is invalid")
        _exact_keys(postcondition, POSTCONDITION_KEYS[kind], postcondition_where)
        if kind == "path_exists":
            _safe_path(postcondition["path"], postcondition_where + ".path")
            continue
        pattern = _string(postcondition["command"], postcondition_where + ".command")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValidationError(postcondition_where + ".command invalid regex: %s" % exc) from exc
        if kind == "command_json_fields":
            _object(postcondition["fields"], postcondition_where + ".fields")
            _json_value(postcondition["fields"], postcondition_where + ".fields")
        else:
            _string(postcondition["field"], postcondition_where + ".field")
    _exact_keys(value["final_size"], FINAL_SIZE_KEYS, where + ".final_size")
    minimum = _integer(value["final_size"]["min_utf8_bytes"], where + ".final_size.min_utf8_bytes", 0)
    maximum = _integer(value["final_size"]["max_utf8_bytes"], where + ".final_size.max_utf8_bytes", 1)
    if minimum > maximum:
        raise ValidationError("%s.final_size minimum exceeds maximum" % where)
    _string_list(value["hard_failures"], where + ".hard_failures")
    unknown = set(value["hard_failures"]) - HARD_FAILURES
    if unknown:
        raise ValidationError("%s.hard_failures has unknown values: %s" % (where, sorted(unknown)))
    return value


def validate_usage(value, where="provider_usage"):
    if value is None:
        return None
    _exact_keys(value, USAGE_KEYS, where)
    for key in (
        "input_tokens", "output_tokens", "total_tokens", "cached_input_tokens",
        "cache_read_input_tokens", "cache_creation_input_tokens",
    ):
        item = value[key]
        if item is not None:
            _integer(item, "%s.%s" % (where, key), 0)
    _number_or_none(value["provider_reported_cost"], where + ".provider_reported_cost")
    if value["currency"] is not None:
        _string(value["currency"], where + ".currency")
    if (value["provider_reported_cost"] is None) != (value["currency"] is None):
        raise ValidationError(
            "%s provider_reported_cost and currency must both be null or both be set" % where
        )
    _string(value["source"], where + ".source")
    _object(value["raw"], where + ".raw")
    known = value["input_tokens"] is not None and value["output_tokens"] is not None
    if known and value["total_tokens"] is not None:
        if value["total_tokens"] != value["input_tokens"] + value["output_tokens"]:
            raise ValidationError("%s.total_tokens must equal input_tokens + output_tokens" % where)
    return value


def validate_event(value, where="event"):
    _object(value, where)
    event_type = value.get("type")
    if event_type not in EVENT_KEYS:
        raise ValidationError("%s.type is invalid" % where)
    _exact_keys(value, EVENT_KEYS[event_type], where)
    if event_type == "request":
        _string(value["content"], where + ".content")
    elif event_type == "read":
        _safe_path(value["path"], where + ".path")
    elif event_type == "command":
        _string(value["command"], where + ".command")
        _string(value["output"], where + ".output", allow_empty=True)
        _integer(value["exit_code"], where + ".exit_code")
    elif event_type == "write":
        _safe_path(value["path"], where + ".path")
        _string(value["content"], where + ".content", allow_empty=True)
    else:
        _string(value["text"], where + ".text", allow_empty=event_type == "final")
    return value


def validate_trace(value, scenario=None, where="trace"):
    _exact_keys(value, {"schema_version", "scenario_id", "provider_usage", "events"}, where)
    if value["schema_version"] != SCHEMA_VERSION:
        raise ValidationError("%s.schema_version must be %d" % (where, SCHEMA_VERSION))
    _string(value["scenario_id"], where + ".scenario_id")
    validate_usage(value["provider_usage"], where + ".provider_usage")
    if not isinstance(value["events"], list) or not value["events"]:
        raise ValidationError("%s.events must be a non-empty list" % where)
    for index, event in enumerate(value["events"]):
        validate_event(event, "%s.events[%d]" % (where, index))
    request_events = [event for event in value["events"] if event["type"] == "request"]
    final_events = [event for event in value["events"] if event["type"] == "final"]
    if not request_events:
        raise ValidationError("%s must contain at least one request event" % where)
    if len(final_events) != 1 or value["events"][-1]["type"] != "final":
        raise ValidationError("%s must end with exactly one final event" % where)
    if scenario is not None:
        if value["scenario_id"] != scenario["id"]:
            raise ValidationError("%s scenario_id does not match scenario" % where)
        if scenario["prompt"] not in request_events[-1]["content"]:
            raise ValidationError("%s final request must contain the scenario prompt verbatim" % where)
    return value


def validate_adapter_response(value, scenario, where="adapter response"):
    keys = {"protocol_version", "type", "scenario_id", "events", "provider_usage"}
    _exact_keys(value, keys, where)
    if value["protocol_version"] != PROTOCOL_VERSION or value["type"] != "trace":
        raise ValidationError("%s has unsupported protocol_version or type" % where)
    trace = {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": value["scenario_id"],
        "provider_usage": value["provider_usage"],
        "events": value["events"],
    }
    return validate_trace(trace, scenario, where)

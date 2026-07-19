import hashlib
import json
import re
import shlex


def _check(kind, pattern, passed, hard, detail):
    return {
        "kind": kind,
        "pattern": pattern,
        "passed": passed,
        "hard": hard and not passed,
        "detail": detail,
    }


def _patterns(checks, kind, patterns, values, required, hard_failure, hard_failures):
    for pattern in patterns:
        matches = [value for value in values if re.search(pattern, value)]
        passed = bool(matches) if required else not matches
        checks.append(_check(
            kind,
            pattern,
            passed,
            hard_failure in hard_failures,
            ("matched %d event(s)" % len(matches)) if matches else "no matching event",
        ))


def _ordered_command_patterns(checks, patterns, commands):
    next_index = 0
    for pattern in patterns:
        match_index = next(
            (index for index in range(next_index, len(commands))
             if re.search(pattern, commands[index])),
            None,
        )
        passed = match_index is not None
        checks.append(_check(
            "required_command",
            pattern,
            passed,
            False,
            "matched command %d in order" % (match_index + 1)
            if passed else "no matching command at or after position %d" % (next_index + 1),
        ))
        if passed:
            next_index = match_index + 1


def _json_contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _json_contains(actual[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            _json_contains(actual_item, expected_item)
            for actual_item, expected_item in zip(actual, expected)
        )
    return actual == expected


def _json_field(value, dotted_path):
    current = value
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(dotted_path)
        current = current[part]
    return current


def _command_result_checks(checks, commands, golden, hard_failures):
    expectations = golden.get("command_results", [])
    for event in commands:
        passed = event["exit_code"] == 0
        checks.append(_check(
            "command_exit_code",
            event["command"],
            passed,
            True,
            "exit %d; expected 0" % event["exit_code"],
        ))
    next_index = 0
    for expectation in expectations:
        matching = [
            (index, commands[index])
            for index in range(next_index, len(commands))
            if re.search(expectation["command"], commands[index]["command"])
        ]
        passed = False
        details = "no matching command event"
        matched_index = None
        for index, event in matching:
            if event["exit_code"] != expectation["exit_code"]:
                details = "exit %d; expected %d" % (event["exit_code"], expectation["exit_code"])
                continue
            expected_json = expectation["output_json"]
            if expected_json is None:
                passed = True
                details = "exit code matched in order"
                matched_index = index
                break
            try:
                actual_json = json.loads(event["output"])
            except (json.JSONDecodeError, UnicodeError) as exc:
                details = "output is not JSON: %s" % exc
                continue
            passed = _json_contains(actual_json, expected_json)
            details = "versioned JSON matched in order" if passed else "JSON does not contain declared values"
            if passed:
                matched_index = index
                break
        checks.append(_check(
            "command_result",
            expectation["command"],
            passed,
            "command_failure" in hard_failures,
            details,
        ))
        if matched_index is not None:
            next_index = matched_index + 1


def _command_binding_checks(checks, commands, golden, hard_failures):
    for binding in golden.get("command_bindings", []):
        source = next(
            ((index, event) for index, event in enumerate(commands)
             if re.search(binding["source_command"], event["command"])),
            None,
        )
        passed = False
        detail = "source command not found"
        if source is not None:
            source_index, source_event = source
            target = next(
                ((index, event) for index, event in enumerate(commands[source_index + 1:], source_index + 1)
                 if re.search(binding["target_command"], event["command"])),
                None,
            )
            detail = "target command not found after source"
            if target is not None:
                try:
                    source_json = json.loads(source_event["output"])
                    expected = str(_json_field(source_json, binding["source_json_field"]))
                    arguments = shlex.split(target[1]["command"])
                    option_index = arguments.index(binding["target_option"])
                    actual = arguments[option_index + 1]
                    passed = actual == expected
                    detail = "bound value matched" if passed else "bound value mismatch"
                except (json.JSONDecodeError, KeyError, ValueError, IndexError, UnicodeError) as exc:
                    detail = "cannot resolve binding: %s" % exc
        checks.append(_check(
            "command_binding",
            "%s -> %s" % (binding["source_json_field"], binding["target_option"]),
            passed,
            "command_failure" in hard_failures,
            detail,
        ))


def _write_result_checks(checks, writes, golden, hard_failures):
    for expectation in golden.get("write_results", []):
        matching = [event for event in writes if re.search(expectation["path"], event["path"])]
        passed = False
        detail = "no matching write event"
        for event in matching:
            content_ok = expectation["content"] is None or event["content"] == expectation["content"]
            actual_hash = hashlib.sha256(event["content"].encode("utf-8")).hexdigest()
            hash_ok = expectation["sha256"] is None or actual_hash == expectation["sha256"]
            passed = content_ok and hash_ok
            detail = "content/hash matched" if passed else "content or SHA-256 mismatch"
            if passed:
                break
        checks.append(_check(
            "write_result",
            expectation["path"],
            passed,
            "write_mismatch" in hard_failures,
            detail,
        ))


def score_trace(trace, golden):
    reads = [event["path"] for event in trace["events"] if event["type"] == "read"]
    command_events = [event for event in trace["events"] if event["type"] == "command"]
    commands = [event["command"] for event in command_events]
    write_events = [event for event in trace["events"] if event["type"] == "write"]
    writes = [event["path"] for event in write_events]
    claims = [event["text"] for event in trace["events"] if event["type"] in ("claim", "final")]
    hard_failures = set(golden["hard_failures"])
    checks = []
    _patterns(checks, "required_read", golden["required_reads"], reads, True, "", hard_failures)
    _patterns(checks, "forbidden_read", golden["forbidden_reads"], reads, False, "forbidden_read", hard_failures)
    _ordered_command_patterns(checks, golden["required_commands"], commands)
    _patterns(checks, "forbidden_command", golden["forbidden_commands"], commands, False, "forbidden_command", hard_failures)
    _patterns(checks, "required_claim", golden["required_claims"], claims, True, "", hard_failures)
    _patterns(checks, "forbidden_claim", golden["forbidden_claims"], claims, False, "forbidden_claim", hard_failures)
    _patterns(checks, "required_write", golden["required_writes"], writes, True, "", hard_failures)
    _patterns(checks, "forbidden_write", golden["forbidden_writes"], writes, False, "forbidden_write", hard_failures)
    _command_result_checks(checks, command_events, golden, hard_failures)
    _command_binding_checks(checks, command_events, golden, hard_failures)
    _write_result_checks(checks, write_events, golden, hard_failures)
    finals = [event["text"] for event in trace["events"] if event["type"] == "final"]
    final_bytes = len(finals[0].encode("utf-8")) if finals else 0
    final_present = bool(finals)
    checks.append(_check(
        "final_present",
        None,
        final_present,
        "missing_final" in hard_failures,
        "one final event" if final_present else "final event missing",
    ))
    size = golden["final_size"]
    size_passed = final_present and size["min_utf8_bytes"] <= final_bytes <= size["max_utf8_bytes"]
    checks.append(_check(
        "final_size",
        "%d..%d" % (size["min_utf8_bytes"], size["max_utf8_bytes"]),
        size_passed,
        False,
        "%d UTF-8 bytes" % final_bytes,
    ))
    hard = [check for check in checks if check["hard"]]
    passed_count = sum(1 for check in checks if check["passed"])
    score = 0.0 if hard else round(100.0 * passed_count / len(checks), 2)
    return {
        "score": score,
        "passed": all(check["passed"] for check in checks),
        "hard_failures": hard,
        "checks": checks,
    }

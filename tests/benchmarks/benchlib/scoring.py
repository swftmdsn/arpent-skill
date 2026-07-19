import re


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


def score_trace(trace, golden):
    reads = [event["path"] for event in trace["events"] if event["type"] == "read"]
    commands = [event["command"] for event in trace["events"] if event["type"] == "command"]
    writes = [event["path"] for event in trace["events"] if event["type"] == "write"]
    claims = [event["text"] for event in trace["events"] if event["type"] in ("claim", "final")]
    hard_failures = set(golden["hard_failures"])
    checks = []
    _patterns(checks, "required_read", golden["required_reads"], reads, True, "", hard_failures)
    _patterns(checks, "forbidden_read", golden["forbidden_reads"], reads, False, "forbidden_read", hard_failures)
    _patterns(checks, "required_command", golden["required_commands"], commands, True, "", hard_failures)
    _patterns(checks, "forbidden_command", golden["forbidden_commands"], commands, False, "forbidden_command", hard_failures)
    _patterns(checks, "required_claim", golden["required_claims"], claims, True, "", hard_failures)
    _patterns(checks, "forbidden_claim", golden["forbidden_claims"], claims, False, "forbidden_claim", hard_failures)
    _patterns(checks, "required_write", golden["required_writes"], writes, True, "", hard_failures)
    _patterns(checks, "forbidden_write", golden["forbidden_writes"], writes, False, "forbidden_write", hard_failures)
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

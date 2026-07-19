import hashlib
import json
import os
import tempfile
from pathlib import Path

from .errors import ValidationError


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("duplicate JSON key: %s" % key)
        result[key] = value
    return result


def parse_json(text, source):
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except ValidationError:
        raise
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValidationError("%s: invalid JSON: %s" % (source, exc)) from exc


def load_json(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValidationError("%s: cannot read UTF-8 JSON: %s" % (path, exc)) from exc
    return parse_json(text, str(path))


def load_jsonl(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValidationError("%s: cannot read UTF-8 JSONL: %s" % (path, exc)) from exc
    records = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            raise ValidationError("%s:%d: blank JSONL lines are not allowed" % (path, line_number))
        records.append(parse_json(line, "%s:%d" % (path, line_number)))
    if not records:
        raise ValidationError("%s: JSONL file is empty" % path)
    return records


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def atomic_write_text(path, text):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".%s." % destination.name,
        dir=str(destination.parent),
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise

"""
frontmatter.py - zero-dependency frontmatter parsing and serialization.

Arpent frontmatter is a small, well-defined subset of YAML. Rather than
take a pyyaml dependency, we implement a minimal parser/serializer that handles
exactly what the schema uses: scalars (str/int/float/bool/null), inline lists
([a, b, c]), block lists (- item), and nested mappings.

This keeps the core dependency-free (stdlib only), as the design requires.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

OPENING_FENCE_RE = re.compile(r"^---[ \t]*\r?\n")
VERBATIM_BODY_MARKER = "<!-- arpent:verbatim-body -->"
FRONTMATTER_RE = re.compile(
    r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n(?:\r?\n)?)?(.*)$",
    re.DOTALL,
)

# Canonical key order, mirroring the schema in frontmatter.md.
KEY_ORDER = [
    # Identity and system timestamps
    "title", "id", "created", "modified",
    # Classification and routing
    "description", "type", "project", "area", "resource",
    "status", "effort_cadence", "effort_level", "tags", "chosen_location",
    # Provenance
    "source", "link", "author",
    # Enriched
    "depth", "appreciated", "importance", "pinned",
    # Lifecycle
    "expires_at",
    # Graph
    "related", "relations", "parent", "observations", "extracted_to",
]

RELATION_TYPES = ["supports", "contradicts", "depends_on", "derived_from", "example_of"]


def now_iso() -> str:
    """Current UTC time in ISO-8601 with a trailing Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_note_timestamp(value: datetime) -> str:
    """Format a user-facing note timestamp with the date written day-first."""
    if value.tzinfo is None:
        raise ValueError("note timestamp must include a timezone")
    return value.astimezone(timezone.utc).strftime("%d-%m-%YT%H:%M:%SZ")


def now_note_timestamp() -> str:
    """Current UTC time in Arpent's note-facing timestamp format."""
    return format_note_timestamp(datetime.now(timezone.utc))


def parse_note_timestamp(value: str) -> datetime:
    """Parse canonical day-first or legacy ISO note dates and timestamps."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("note timestamp must be a non-empty string")
    text = value.strip()
    for pattern in ("%d-%m-%YT%H:%M:%SZ", "%d-%m-%Y"):
        try:
            parsed = datetime.strptime(text, pattern).replace(tzinfo=timezone.utc)
            break
        except ValueError:
            continue
    else:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"invalid note timestamp '{value}'") from exc
        if parsed.tzinfo is None:
            if len(text) == 10:
                parsed = parsed.replace(tzinfo=timezone.utc)
            else:
                raise ValueError(f"note timestamp must include a timezone: '{value}'")
    return parsed.astimezone(timezone.utc)


# --------------------------------------------------------------------------- #
# Scalar parsing
# --------------------------------------------------------------------------- #

def _parse_scalar(raw: str):
    s = raw.strip()
    if s == "" or s in ("null", "~", "None"):
        return None
    if s == "{}":
        return {}
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    # JSON strings are valid YAML double-quoted scalars and give us a strict,
    # dependency-free escaping format for generated frontmatter.
    if s.startswith('"'):
        if not s.endswith('"'):
            raise ValueError("unterminated double-quoted scalar")
        try:
            value = json.loads(s)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid double-quoted scalar: {exc.msg}") from exc
        if not isinstance(value, str):
            raise ValueError("double-quoted scalar must decode to a string")
        return value
    if s.startswith("'"):
        if not s.endswith("'"):
            raise ValueError("unterminated single-quoted scalar")
        return s[1:-1].replace("''", "'")
    # inline list
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(p) for p in _split_inline(inner)]
    if s.startswith(("[", "{")):
        raise ValueError("unterminated or unsupported inline collection")
    # int
    if re.fullmatch(r"-?\d+", s):
        try:
            return int(s)
        except ValueError:
            pass
    # float
    if re.fullmatch(r"-?\d+\.\d+", s):
        try:
            return float(s)
        except ValueError:
            pass
    return s


def _split_inline(inner: str):
    """Split an inline list body on commas not inside brackets/quotes."""
    parts, buf, depth, quote, escaped = [], [], 0, None, False
    for ch in inner:
        if quote:
            buf.append(ch)
            if quote == '"' and ch == "\\" and not escaped:
                escaped = True
            elif ch == quote and not escaped:
                quote = None
            else:
                escaped = False
        elif ch in ("'", '"'):
            quote = ch
            buf.append(ch)
        elif ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if quote or depth != 0:
        raise ValueError("unterminated quote or bracket in inline list")
    if buf:
        parts.append("".join(buf))
    return [p.strip() for p in parts]


# --------------------------------------------------------------------------- #
# Block parsing (indentation-aware, recursive)
# --------------------------------------------------------------------------- #

def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_block(lines, i, base_indent):
    """Parse a mapping at a given indent level. Returns (dict, next_index)."""
    result = {}
    while i < len(lines):
        raw = lines[i]
        if raw.strip() == "" or raw.lstrip().startswith("#"):
            i += 1
            continue
        ind = _indent(raw)
        if ind < base_indent:
            break
        if ind > base_indent:
            raise ValueError(f"unexpected indentation on line {i + 1}")

        line = raw.strip()
        if ":" not in line:
            raise ValueError(f"expected 'key: value' on line {i + 1}")
        key, _, after = line.partition(":")
        key = key.strip()
        after = after.strip()
        if not key:
            raise ValueError(f"empty mapping key on line {i + 1}")
        if key in result:
            raise ValueError(f"duplicate mapping key '{key}' on line {i + 1}")

        if after == "":
            # Could be a block list or a nested mapping; peek ahead.
            j = i + 1
            while j < len(lines) and (lines[j].strip() == "" or lines[j].lstrip().startswith("#")):
                j += 1
            child_indent = _indent(lines[j]) if j < len(lines) else None
            if child_indent is not None and child_indent > base_indent:
                if child_indent != base_indent + 2:
                    raise ValueError(f"unexpected nested indentation on line {j + 1}")
            if j < len(lines) and child_indent > base_indent and lines[j].lstrip().startswith("- "):
                items, j2 = _parse_block_list(lines, j, child_indent)
                result[key] = items
                i = j2
            elif j < len(lines) and child_indent > base_indent:
                sub, j2 = _parse_block(lines, j, child_indent)
                result[key] = sub
                i = j2
            else:
                result[key] = None
                i += 1
        else:
            result[key] = _parse_scalar(after)
            i += 1
    return result, i


_MAPPING_LIST_ITEM_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:(?:\s+|$)(.*)$")


def _parse_block_list(lines, i, base_indent):
    items = []
    while i < len(lines):
        raw = lines[i]
        if raw.strip() == "" or raw.lstrip().startswith("#"):
            i += 1
            continue
        ind = _indent(raw)
        if ind < base_indent or not raw.lstrip().startswith("- "):
            break
        if ind > base_indent:
            raise ValueError(f"unexpected list indentation on line {i + 1}")
        text = raw.lstrip()[2:].strip()
        match = _MAPPING_LIST_ITEM_RE.match(text)
        if match:
            key, after = match.group(1), match.group(2).strip()
            item = {key: _parse_scalar(after)}
            i += 1
            if i < len(lines):
                next_ind = _indent(lines[i])
                if next_ind > base_indent:
                    if next_ind != base_indent + 2:
                        raise ValueError(f"unexpected mapping-list indentation on line {i + 1}")
                    nested, i = _parse_block(lines, i, next_ind)
                    item.update(nested)
            items.append(item)
            continue
        items.append(_parse_scalar(text))
        i += 1
    return items, i


def parse_frontmatter_block(text: str) -> dict:
    """Parse a raw frontmatter string (without the --- fences) into a dict."""
    lines = text.split("\n")
    if any("\t" in line for line in lines):
        raise ValueError("tabs are not supported in YAML-lite indentation")
    data, _ = _parse_block(lines, 0, 0)
    return data


# --------------------------------------------------------------------------- #
# Serialization
# --------------------------------------------------------------------------- #

def _needs_quotes(s: str) -> bool:
    if s == "":
        return True
    if s.strip() != s:
        return True
    # leading chars that YAML-ish readers treat specially, or our parser would mis-read
    if s[0] in "-?:,[]{}#&*!|>%@`\"'":
        return True
    if s.casefold() in {
        "null", "none", "true", "false", "yes", "no", "on", "off", ".nan", ".inf", "-.inf",
    } or s == "~":
        return True
    if re.fullmatch(
        r"[-+]?(?:(?:\d[\d_]*)(?:\.\d[\d_]*)?|\.\d[\d_]*)(?:[eE][-+]?\d+)?",
        s,
    ):
        return True
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[Tt ].*)?", s):
        return True
    if s in ("---", "...") or any(ch in s for ch in "\n\r\t"):
        return True
    if any(ch in s for ch in ':#,[]{}"'):
        return True
    return False


def _dump_scalar(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        if not v:
            return "[]"
        return "[" + ", ".join(_dump_scalar(x) for x in v) + "]"
    s = str(v)
    if _needs_quotes(s):
        return json.dumps(s, ensure_ascii=True)
    return s


def _is_mapping_list(v) -> bool:
    return isinstance(v, list) and bool(v) and all(isinstance(item, dict) for item in v)


def _dump_mapping_list(key: str, items: list[dict], out: list[str], indent: int = 0) -> None:
    pad = " " * indent
    out.append(f"{pad}{key}:")
    item_pad = " " * (indent + 2)
    field_pad = " " * (indent + 4)
    for item in items:
        pairs = list(item.items())
        if not pairs:
            out.append(f"{item_pad}- {{}}")
            continue
        first_key, first_value = pairs[0]
        out.append(f"{item_pad}- {first_key}: {_dump_scalar(first_value)}")
        for sub_key, sub_value in pairs[1:]:
            out.append(f"{field_pad}{sub_key}: {_dump_scalar(sub_value)}")


def _dump_mapping(key: str, value: dict, out: list[str], indent: int = 0) -> None:
    pad = " " * indent
    if not value:
        out.append(f"{pad}{key}: {{}}")
        return
    out.append(f"{pad}{key}:")
    for sub_key, sub_value in value.items():
        if isinstance(sub_value, dict):
            _dump_mapping(sub_key, sub_value, out, indent + 2)
        elif _is_mapping_list(sub_value):
            _dump_mapping_list(sub_key, sub_value, out, indent + 2)
        else:
            out.append(f"{' ' * (indent + 2)}{sub_key}: {_dump_scalar(sub_value)}")


def dump_frontmatter(data: dict) -> str:
    """Serialize a frontmatter dict to a YAML-lite string (with --- fences)."""
    keys = [k for k in KEY_ORDER if k in data]
    keys += [k for k in data if k not in KEY_ORDER]
    out = ["---"]
    for k in keys:
        v = data[k]
        if isinstance(v, dict):
            _dump_mapping(k, v, out)
        elif _is_mapping_list(v):
            _dump_mapping_list(k, v, out)
        else:
            out.append(f"{k}: {_dump_scalar(v)}")
    out.append("---")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# File-level read / write
# --------------------------------------------------------------------------- #

def read_note(path) -> tuple[dict, str]:
    """Read a markdown file, return (frontmatter_dict, body). Empty dict if none."""
    return parse_note_text(path.read_text(encoding="utf-8"))


def parse_note_text(text: str) -> tuple[dict, str]:
    """Parse already-loaded markdown into frontmatter and body."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        if OPENING_FENCE_RE.match(text):
            raise ValueError("frontmatter opening fence has no closing fence")
        return {}, text
    body = m.group(2)
    marker = VERBATIM_BODY_MARKER + "\n"
    if body.startswith(marker):
        body = body[len(marker):]
    return parse_frontmatter_block(m.group(1)), body


def compose_note(frontmatter: dict, body: str) -> str:
    """Compose a full markdown file from frontmatter + body."""
    body = body or ""
    return dump_frontmatter(frontmatter) + "\n\n" + body.lstrip("\n")


def compose_note_verbatim(frontmatter: dict, body: str) -> str:
    """Compose a note whose parsed body preserves every source character."""
    body = body or ""
    return dump_frontmatter(frontmatter) + "\n" + VERBATIM_BODY_MARKER + "\n" + body


def write_note(path, frontmatter: dict, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(compose_note(frontmatter, body), encoding="utf-8")

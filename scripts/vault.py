"""
vault.py - vault location, scaffolding, and discovery helpers.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None
    import msvcrt
else:  # pragma: no cover - not used on Windows
    msvcrt = None

from . import frontmatter as fmlib
from . import operations as operations_mod

MARKER = ".arpent"  # presence of this file marks a vault root
MUTATION_TRANSACTION_PATHS = {
    "06_indexes/logs/note-transaction.json": "a note mutation",
    "06_indexes/logs/note-ingest-transaction.json": "a note ingestion",
    "06_indexes/logs/session-transaction.json": "a session mutation",
    "06_indexes/logs/sweep-transaction.json": "a lifecycle sweep mutation",
    "06_indexes/logs/todo-transaction.json": "a todo mutation",
}

INDEX_EXCLUDED_DIR_NAMES = {".git", ".venv", "__pycache__", "node_modules"}
INDEX_EXCLUDED_DIR_PATHS = {
    "06_indexes/backup",
    "06_indexes/databases",
    "06_indexes/imports",
    "06_indexes/logs",
    "06_indexes/secrets",
}

# Minimal mode keeps the complete note contract and deterministic routing while
# omitting optional modules and their local surfaces.
MINIMAL_SCAFFOLD = [
    "00_inbox",
    "00_inbox/unsure",
    "01_projects",
    "02_areas",
    "03_resources",
    "04_archives",
    "05_tools",
    "06_indexes",
    "06_indexes/cli",
    "06_indexes/global_skills",
    "06_indexes/schemas",
    "06_indexes/databases",
    "06_indexes/imports",
    "06_indexes/logs",
]

# The 7 buckets + the seed subfolders that full mode creates.
SCAFFOLD = [
    "00_inbox",
    "00_inbox/fleeting",
    "00_inbox/captures",
    "00_inbox/unsure",
    "01_projects",
    "02_areas",
    "02_areas/area__perso__todo__active",
    "02_areas/area__perso__todo__active/active",
    "02_areas/area__perso__todo__active/waiting",
    "02_areas/area__perso__todo__active/done",
    "03_resources",
    "03_resources/concepts",
    "03_resources/maps-of-content",
    "03_resources/integrations",
    "03_resources/templates",
    "03_resources/agent_wiki",
    "03_resources/agent_wiki/drafts",
    "03_resources/agent_infrastructure",
    "03_resources/agent_infrastructure/agent_roles",
    "03_resources/agent_infrastructure/agent_skills",
    "03_resources/agent_infrastructure/agent_workflows",
    "03_resources/agent_infrastructure/agent_prompts",
    "03_resources/agent_infrastructure/agent_templates",
    "03_resources/agent_infrastructure/agent_style",
    "03_resources/agent_infrastructure/capabilities",
    "04_archives",
    "04_archives/linear_notes",
    "05_tools",
    "05_tools/artefacts",
    "06_indexes",
    "06_indexes/cli",
    "06_indexes/global_skills",
    "06_indexes/schemas",
    "06_indexes/docs",
    "06_indexes/docs/architecture",
    "06_indexes/databases",
    "06_indexes/imports",
    "06_indexes/memory",
    "06_indexes/memory/wiki",
    "06_indexes/memory/wiki/raw",
    "06_indexes/memory/wiki/pages",
    "06_indexes/backup",
    "06_indexes/logs",
]

RESERVED_RESOURCE_SLUGS = [
    "concepts", "maps-of-content", "integrations", "templates",
    "agent_wiki", "books", "articles", "portraits", "productions",
]

class Vault:
    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()
        self._lock_state = threading.local()

    # ---- discovery ----------------------------------------------------- #

    @classmethod
    def find(cls, start: Path | None = None) -> "Vault | None":
        configured_root = os.environ.get("ARPENT_VAULT_ROOT") if start is None else None
        if configured_root:
            root = Path(configured_root).expanduser().resolve()
            vault = cls(root)
            try:
                vault.marker_data()
            except (OSError, ValueError):
                return None
            return vault
        cur = (start or Path.cwd()).resolve()
        for path in [cur, *cur.parents]:
            vault = cls(path)
            try:
                vault.marker_data()
            except (OSError, ValueError):
                continue
            return vault
        return None

    def marker_data(self) -> dict:
        """Read and validate the single current marker format."""
        source = self.safe_source_path(MARKER)
        try:
            content = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid .arpent marker: {exc}") from exc
        if (
            not isinstance(content, dict)
            or set(content) != {"version", "name", "mode"}
            or type(content.get("version")) is not int
            or content["version"] != 1
            or content.get("name") != "arpent"
            or content.get("mode") not in {"full", "minimal"}
        ):
            raise ValueError("Invalid .arpent marker: expected the current Arpent format.")
        return content

    def project_slugs(self):
        base = self.root / "01_projects"
        return [p.name for p in base.iterdir() if p.is_dir() and not p.is_symlink()] if base.exists() else []

    def area_slugs(self):
        base = self.root / "02_areas"
        return [p.name for p in base.iterdir() if p.is_dir() and not p.is_symlink()] if base.exists() else []

    def resource_slugs(self):
        base = self.root / "03_resources"
        found = [p.name for p in base.iterdir() if p.is_dir() and not p.is_symlink()] if base.exists() else []
        return sorted(set(found) | set(RESERVED_RESOURCE_SLUGS))

    def iter_notes(self, *, skip_invalid=False):
        """Yield (path, frontmatter, body) for every .md note in the vault."""
        for current, dir_names, file_names in os.walk(
            self.root,
            followlinks=False,
            onerror=raise_walk_error,
        ):
            current_path = Path(current)
            kept_dirs = []
            for name in sorted(dir_names):
                child = current_path / name
                rel = child.relative_to(self.root).as_posix()
                if not child.is_symlink() and not is_index_excluded(rel, directory=True):
                    kept_dirs.append(name)
            dir_names[:] = kept_dirs

            for name in sorted(file_names):
                if not name.lower().endswith(".md"):
                    continue
                path = current_path / name
                rel = path.relative_to(self.root).as_posix()
                if rel.startswith(("06_indexes/docs/", "06_indexes/global_skills/")):
                    continue
                try:
                    safe_path = self.safe_source_path(rel)
                    fm, body = fmlib.read_note(safe_path)
                except (OSError, UnicodeDecodeError, ValueError) as exc:
                    if skip_invalid:
                        continue
                    raise ValueError(f"Cannot read vault note '{rel}': {exc}") from exc
                if fm.get("id"):
                    yield safe_path, fm, body

    def existing_ids(self):
        ids = set()
        for _, fm, _ in self.iter_notes(skip_invalid=True):
            if fm.get("id"):
                ids.add(fm["id"])
        return ids

    def operations_path(self) -> Path:
        return self.root / "06_indexes" / "cli" / "operations.yaml"

    def safe_source_path(self, relpath: str) -> Path:
        """Return an existing vault file only when no path component is a symlink."""
        target = self._safe_relative_path(relpath)
        current = self.root
        for part in target.relative_to(self.root).parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(f"Refusing to follow symlink inside vault: {relpath}")
        if not target.is_file():
            raise ValueError(f"Vault source is not a regular file: {relpath}")
        return target

    def safe_directory_path(self, relpath: str) -> Path:
        """Return an existing vault directory without following symlink components."""
        target = self._safe_relative_path(relpath)
        current = self.root
        for part in target.relative_to(self.root).parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(f"Refusing to follow symlink inside vault: {relpath}")
        if not target.is_dir():
            raise ValueError(f"Vault directory does not exist: {relpath}")
        return target

    def safe_output_path(self, relpath: str) -> Path:
        """Prepare a generated output path without traversing symlink components."""
        target = self._safe_relative_path(relpath)
        current = self.root
        parts = target.relative_to(self.root).parts
        for part in parts[:-1]:
            current = current / part
            if current.is_symlink():
                raise ValueError(f"Refusing generated output through symlink: {relpath}")
            current.mkdir(exist_ok=True)
        if target.is_symlink():
            raise ValueError(f"Refusing to replace generated-output symlink: {relpath}")
        return target

    def safe_ensure_directory(self, relpath: str) -> Path:
        """Create a vault directory without traversing symlink components."""
        target = self._safe_relative_path(relpath)
        current = self.root
        if current.is_symlink():
            raise ValueError(f"Refusing vault root symlink: {self.root}")
        for part in target.relative_to(self.root).parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(f"Refusing directory creation through symlink: {relpath}")
            current.mkdir(exist_ok=True)
            if not current.is_dir():
                raise ValueError(f"Vault directory path is not a directory: {relpath}")
        return target

    def refuse_foreign_transactions(self, owner_relpath: str | None = None) -> None:
        """Prevent one subsystem from overwriting another interrupted mutation."""
        for relpath, label in MUTATION_TRANSACTION_PATHS.items():
            if relpath == owner_relpath:
                continue
            path = self.safe_output_path(relpath)
            if path.exists() or path.is_symlink():
                raise ValueError(
                    f"Cannot mutate the vault while {label} requires recovery ({relpath})."
                )

    def atomic_write_text(self, relpath: str, content: str) -> Path:
        target = self.safe_output_path(relpath)
        fd, temporary_name = tempfile.mkstemp(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
            self.fsync_directory(target.parent)
        finally:
            temporary.unlink(missing_ok=True)
        return target

    def atomic_create_text(self, relpath: str, content: str) -> Path:
        """Atomically create a file and fail rather than replace an existing path."""
        target = self.safe_output_path(relpath)
        fd, temporary_name = tempfile.mkstemp(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, target)
            self.fsync_directory(target.parent)
        finally:
            temporary.unlink(missing_ok=True)
        return target

    def atomic_move_no_replace(self, source_relpath: str, destination_relpath: str) -> Path:
        """Move a file without ever replacing an existing destination."""
        source = self.safe_source_path(source_relpath)
        destination = self.safe_output_path(destination_relpath)
        os.link(source, destination)
        self.fsync_directory(destination.parent)
        try:
            source.unlink()
            self.fsync_directory(source.parent)
        except Exception:
            destination.unlink(missing_ok=True)
            self.fsync_directory(destination.parent)
            raise
        return destination

    @contextmanager
    def exclusive_lock(self, name: str):
        """Serialize a vault mutation across processes without stale PID locks."""
        if not re.fullmatch(r"[a-z0-9_-]+", name):
            raise ValueError(f"Invalid vault lock name: {name}")
        held = getattr(self._lock_state, "held", None)
        if held is None:
            held = self._lock_state.held = {}
        if name in held:
            held[name] += 1
            try:
                yield
            finally:
                held[name] -= 1
            return
        path = self.safe_output_path(f"06_indexes/logs/{name}.lock")
        with path.open("a+b") as stream:
            if fcntl is not None:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            elif msvcrt is not None:  # pragma: no cover - Windows only
                stream.seek(0, os.SEEK_END)
                if stream.tell() == 0:
                    stream.write(b"\0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            try:
                held[name] = 1
                yield
            finally:
                held.pop(name, None)
                if fcntl is not None:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                elif msvcrt is not None:  # pragma: no cover - Windows only
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)

    @staticmethod
    def fsync_directory(path: Path) -> None:
        """Best-effort durability barrier for a changed directory entry."""
        try:
            descriptor = os.open(path, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError:
            pass

    def _safe_relative_path(self, relpath: str) -> Path:
        candidate = Path(relpath)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError("Vault path must be relative and cannot contain '..'.")
        return self.root / candidate


def is_index_excluded(relpath: str, *, directory=False) -> bool:
    parts = Path(relpath).parts
    if any(part in INDEX_EXCLUDED_DIR_NAMES for part in parts):
        return True
    for prefix in INDEX_EXCLUDED_DIR_PATHS:
        if relpath == prefix or relpath.startswith(prefix + "/"):
            return True
    return False


def raise_walk_error(error: OSError) -> None:
    raise error


# --------------------------------------------------------------------------- #
# init
# --------------------------------------------------------------------------- #

COMPASS_STUB = Path(__file__).with_name("COMPASS.md").read_text(encoding="utf-8")

MINIMAL_COMPASS_STUB = """# COMPASS.md - the path to follow

This is a minimal Arpent vault. Classify the user's intent before locating or
changing files, read `me.md` early, and use only the installed core capability.

## Available operations

- Capture, read, edit, route, find, and archive ordinary notes.
- Create projects with canonical local context.
- Close sessions into project or area `_context.md`; use `--memory-log` only for an explicitly requested optional cross-project log.
- Inspect status, triage, efforts, health, search, and indexes.
- Scan, review, validate, and resumably copy external folder trees with `arpent import`.
- Create and verify logical backups.

Context summaries, todo, tools, cron, sweep, delegated-memory queues, the memory
wiki, and portable agent-infrastructure modules are not installed in this vault.
Do not create or simulate them implicitly.

## Routing

Use complete universal frontmatter and deterministic precedence:
`project > resource > area > inbox`. `project` and `resource` are mutually
exclusive; `area` may accompany either. Missing or conflicting destinations go
to `00_inbox/unsure/` with a written reason.
The schema is closed during normal use: do not invent per-project fields.
Body sections, project files, and project subfolders remain user-extensible.

## Operating protocol

1. Identify the intent and required destination.
2. To resume work, read `me.md`, then the target `_context.md`, then only needed notes/sources. Never read optional `MEMORY.md` without explicit user opt-in.
3. Read `06_indexes/global_skills/arpent.skill.md` and only the contract needed.
4. Preview mutations, destination, metadata, and side effects.
5. Ask once when a user-owned or routing decision is required.
6. Prefer the Arpent CLI, execute, and verify the resulting path and state.
7. Close useful work with targeted `arpent session end`; a no-target close needs `--memory-log`. Rebuild indexes after direct changes.

## Copy-paste frontmatter reference

Use this quick reference when a human or agent needs to paste a complete note
header. Keep the field order intact. Replace placeholders, leave unknown
optional values as `null`, and never fill `appreciated` or `importance` for the
user.

```yaml
---
title: <lowercase_ascii_snake_case>
id: <type>-<YYYYMMDD>-<letter>
created: <dd-mm-yyyyTHH:MM:SSZ>
modified: <dd-mm-yyyyTHH:MM:SSZ>

description: <useful standalone summary or null>
type: <note|concept|journal|log|checklist|reference|draft|template|meeting|idea|fleeting|linear|integration|angle|production|map|artefact>
project: <slug or null>
area: <slug or null>
resource: <slug or null>
status: <inbox|maturing|active|stable|ongoing|standby|waiting|to-start|done|stale|archived>
effort_cadence: <heavylift|slowburn|null>
effort_level: <low|medium|high|null>
tags: [<lowercase-hyphen-tag>, <lowercase-hyphen-tag>]
chosen_location: <one-line placement rationale or null>

source: <manual|generated|imported|captured|conversation|derived>
link: <URL, path, external id, session id, or null>
author: <user|agent|imported>

depth: <1|2|3|4|5|null>
appreciated: null
importance: null
pinned: false

expires_at: <dd-mm-yyyyTHH:MM:SSZ or null>

related: []
relations:
  - type: <supports|contradicts|depends_on|derived_from|example_of>
    target: <note_id>
parent: <note_id or null>
observations: []
extracted_to: []
---
```

Field value summary:

| Field | Allowed shape or values |
|---|---|
| `title` | lowercase ASCII `snake_case`; ordinary note filename follows it |
| `id` | `<type>-<YYYYMMDD>-<letter>`; stable graph anchor |
| `created`, `modified` | `dd-mm-yyyyTHH:MM:SSZ`, UTC |
| `description` | useful standalone summary or `null` |
| `type` | `note`, `concept`, `journal`, `log`, `checklist`, `reference`, `draft`, `template`, `meeting`, `idea`, `fleeting`, `linear`, `integration`, `angle`, `production`, `map`, `artefact` |
| `project` | project slug or `null`; mutually exclusive with `resource` |
| `area` | area slug or `null`; may accompany `project` or `resource` as context |
| `resource` | resource slug or `null`; mutually exclusive with `project` |
| `status` | `inbox`, `maturing`, `active`, `stable`, `ongoing`, `standby`, `waiting`, `to-start`, `done`, `stale`, `archived` |
| `effort_cadence` | `heavylift`, `slowburn`, or `null`; active actionables only; never infer |
| `effort_level` | `low`, `medium`, `high`, or `null`; active actionables only; never infer |
| `tags` | list of lowercase hyphenated tags, or `[]` |
| `chosen_location` | one-line placement rationale or `null`; documentary only |
| `source` | `manual`, `generated`, `imported`, `captured`, `conversation`, `derived` |
| `link` | `null`, URL, local path, external identifier, or session identifier; required for `captured` and `imported` |
| `author` | `user`, `agent`, or `imported` |
| `depth` | `1`, `2`, `3`, `4`, `5`, or `null`; do not score if arbitrary |
| `appreciated` | `null` for agents; user-only value |
| `importance` | `null` for agents; user-only value |
| `pinned` | `false` by default; user may set `true` |
| `expires_at` | `dd-mm-yyyyTHH:MM:SSZ` or `null`; mostly for buffer items |
| `related` | list of note IDs for weak/non-qualified links, or `[]` |
| `relations` | list of `{type, target}` objects; relation type is `supports`, `contradicts`, `depends_on`, `derived_from`, or `example_of` |
| `parent` | source note ID or `null`; required for extracted child notes |
| `observations` | memory-provider observation IDs, or `[]` |
| `extracted_to` | extracted child note IDs, or `[]`; maintained during extraction/dissolution |

Never delete user content, infer subjective fields, guess routing, rewrite
`me.md` from inference, or report an unavailable capability as successful.
"""

ARPENT_STUB = """# Arpent Constitution

This vault is an Arpent vault: a filesystem-native personal life OS.

- Files over apps. Markdown + JSON are the source of truth.
- Delegated memory is optional and disabled by default; the vault is a clean knowledge base, not a memory dump.
- Routing is deterministic. Nothing is ever deleted - only archived.
- The agent announces moves; the user owns the vault.

See 06_indexes/global_skills/ for the operating skill.
"""

AGENT_STUB = """# .agent - Entry point for AI agents working in this Arpent vault

Read this first, completely, before doing anything else.

## Reading order

1. Read `me.md`.
2. Read `COMPASS.md`.
3. Read `06_indexes/docs/ARPENT.md`.
4. Read `06_indexes/docs/mental-model.md`.
5. Read `06_indexes/global_skills/arpent.skill.md`.
6. Skim `06_indexes/schemas/frontmatter_policy.yaml`.

When resuming concrete work, read `me.md`, then the target project or area
`_context.md`, then only the specific notes or sources needed. This is a reading
protocol, not a resume command. `MEMORY.md` is disabled and unseeded by default;
never read it unless the user explicitly asks for or enables it.

## Hard rules

- Never delete files. Archive.
- Never fill subjective fields: `appreciated`, `importance`. Leave them `null`.
- Never guess routing. Use `00_inbox/unsure/` with a reason.
- Never dump facts into the vault. Delegated memory requires explicit user opt-in; the vault is a clean knowledge base.
- Never rewrite `me.md` from inference. Propose changes and wait for explicit user confirmation.
- Keep all tool know-how in `06_indexes/`; `05_tools/` is runtime-only.
- Always announce moves and renames before executing.
- Always use the Arpent CLI for state changes when available.
- Keep the universal frontmatter schema closed; bodies, project files, and project subfolders remain extensible.
- Follow the primary/adaptive language settings in the installed Arpent skill.
- Write dates as `dd-mm-yyyy` and note timestamps as `dd-mm-yyyyTHH:MM:SSZ`.
- Binary attachments remain byte-for-byte untouched and use separate Markdown companion reference notes.

## Continuity commands

- `arpent project create <name>`
- `arpent triage --json`
- `arpent note edit <id> ... --dry-run --json`, then apply with its `--plan-hash`
- `arpent note ingest <inbox-path> --title <title> ... --dry-run --json`
- `arpent import scan <source> --output <plan>`, then review, validate, dry-run, and confirmed apply
- `arpent session end --summary <text> ...`
- `arpent session end --summary <text> --memory-log` only for an explicitly requested optional cross-project log
- `arpent usage report [--json]`
"""

MINIMAL_AGENT_STUB = """# .agent - Entry point for AI agents working in this Arpent vault

Read this first, completely, before doing anything else.

1. Read `me.md`.
2. Read `COMPASS.md`.
3. Read `06_indexes/global_skills/arpent.skill.md`.
4. Skim `06_indexes/schemas/frontmatter_policy.yaml`.

This is a minimal vault. Use complete universal frontmatter and deterministic
routing. For continuity, read `me.md`, then the target project or area
`_context.md`, then only needed notes/sources; close work with targeted
`arpent session end`. `MEMORY.md` is disabled and unseeded by default. Only
`--memory-log` writes it, and later reads require explicit user opt-in.
Use `arpent project create`, `arpent triage --json`, `note edit --dry-run`
followed by its reviewed `--plan-hash`, `note ingest --dry-run`, and
`arpent import`, and `arpent usage report` as needed.
Do not create delegated-memory queues, a memory wiki, context summaries, cron,
todo, tools, sweep, or agent-infrastructure modules unless the user deliberately
initializes a full vault elsewhere.
Never delete files, infer subjective fields, guess routing, or rewrite `me.md`
from inference. Do not invent frontmatter fields; freely extensible context
bodies and project files/subfolders are not schema fields. Never imply YAML is
embedded in a binary; attachments use separate Markdown companion notes.
"""

MENTAL_MODEL_STUB = """# Arpent Mental Model

When information arrives, decide which role it plays:

| Information | Destination |
|---|---|
| Long-form content to open, read, and edit | Vault |
| Stable trait or preference | Delegated memory: profile |
| Durable fact or observation | Delegated memory: observations |
| Time-bound reminder or commitment | Delegated memory: buffer |
| Unsupervised agent research scratch | `06_indexes/memory/wiki/` |
| Default cross-session operational continuity | project/area `_context.md` |
| Optional cross-project log | `06_indexes/memory/MEMORY.md`, only after explicit opt-in |
| User-approved orientation for agents | `me.md` |

Delegated-memory destinations are disabled by default in minimal and full vault
modes. Use them only after explicit user opt-in at the host level.

The vault is not memory. It is the clean shared knowledge base.

`MEMORY.md` is disabled and unseeded by default. Normal resume must not read it;
use `me.md`, the target `_context.md`, then only the notes/sources needed.
"""

MEMORY_STUB = """# MEMORY - optional working log

Created only by explicit `session end --memory-log`. Never read without user opt-in.
"""

USAGE_JOURNAL_STUB = """# Usage Journal

Add a dated entry after a meaningful Arpent session.

Usage events stay in `06_indexes/logs/usage.log`. A vault may itself be in a
synchronized folder, and logical backups include ordinary log files.

- What did you try to accomplish?
- Where was capture slow or awkward?
- Was the resume context sufficient?
- How many minutes of re-explanation did you estimate?
- Was useful work produced?
- Where did close or triage create friction?
- What is one change to test next?
"""

WIKI_SCHEMA_STUB = """# Memory wiki - conventions

This zone holds the agent's unsupervised, short-to-medium-term research.
High tolerance for drafts and mess. Not the clean vault.

- raw/   immutable source clippings (never edited)
- pages/ agent-written, interlinked topic/entity pages
"""

AGENT_INFRA_README_STUB = """# Agent Infrastructure

Portable agent definitions live here. Their discovery registry is
`06_indexes/agent_infrastructure_index.yaml`; the index is not their canonical
home.

| Directory | Purpose |
|---|---|
| `agent_roles/` | Role, instructions, boundaries, and permitted capabilities for a role-based agent |
| `agent_skills/` | Reusable methods for accomplishing a task |
| `agent_workflows/` | Predetermined sequences that orchestrate roles, skills, prompts, and capabilities |
| `agent_prompts/` | Small reusable instructions |
| `agent_templates/` | Reusable output structures |
| `agent_style/` | Shared writing and interaction rules |
| `capabilities/` | Portable declarations for CLI, MCP, API, and harness-plugin access |

Capabilities describe means of action; they do not contain implementations or
secrets. Store only references such as `credential_ref: env:OPENAI_API_KEY`.
Actual credentials belong in environment variables, a keychain, or a secret
manager outside Git.

This portable infrastructure is distinct from Arpent tool know-how in
`06_indexes/` and from runtime material in `05_tools/`.

See `06_indexes/docs/architecture/agent-infrastructure.md` for the complete
hierarchy.
"""

AGENT_INFRA_DOC_STUB = """# Agent Infrastructure

Arpent separates portable agent definitions, executable tools, discovery
indexes, and harness-specific configuration.

## Layers

| Layer | Location | Responsibility |
|---|---|---|
| Portable definitions | `03_resources/agent_infrastructure/` | Roles, skills, workflows, prompts, templates, styles, and capability manifests |
| Arpent tool control plane | `06_indexes/` | Skills, CLI contracts, schemas, migrations, registry, documentation, and databases |
| Tool runtime material | `05_tools/` or the relevant area | Declared artifacts, queues, captures, caches, outputs, and user content |
| Discovery registry | `06_indexes/agent_infrastructure_index.yaml` | IDs, paths, and relations between portable definitions |
| Vault tool registry | `06_indexes/tools.yaml` | Installed Arpent sub-tools only |
| Harness configuration | Outside the vault or generated from portable definitions | Harness-specific activation |
| Secrets | Environment, keychain, or secret manager | Credentials and private tokens; never committed to the vault |

## Definitions

- `agent_roles/<id>/AGENT.md`: role, instructions, boundaries, and allowed IDs.
- `agent_skills/<id>/SKILL.md`: reusable method for accomplishing a task.
- `agent_prompts/`: small reusable instructions.
- `agent_workflows/<id>/WORKFLOW.md`: predetermined orchestration using the
  standard sections Trigger, Input, Steps, Output, and Method.
- `capabilities/<id>/CAPABILITY.yaml`: declaration of CLI, MCP, API, or plugin
  access. It may contain public connection metadata, but never credentials.

The capability folder is canonical; the index makes capabilities discoverable.
Roles and workflows reference capability IDs instead of embedding secrets or
harness-specific configuration.

Vault-wide instructions live in `.agent`, `me.md`, and
`06_indexes/docs/ARPENT.md`. Automatic injection remains the responsibility of
the active harness.

## Decision Rule

- Defines or operates an Arpent sub-tool: `06_indexes/`.
- Stores declared transversal runtime material: `05_tools/`.
- Defines portable agent behavior or access: `03_resources/agent_infrastructure/`.
- Generates discovery indexes: generated index files under `06_indexes/`.
- Contains a secret or harness-specific runtime setting: outside the vault.
"""

INDEXING_CONTEXT_DOC_STUB = """# Indexing and Context

## Core rule

`arpent index` is deterministic and local. It inventories folders and files,
computes hashes, rebuilds search data, and refreshes L0/L2 context. It never
invokes an AI model.

AI-generated L1 summaries belong to the explicit `context_summary` module. The
module runs only after a user request and only for entries reported as missing
or stale.

## Generated outputs

| Output | Content |
|---|---|
| `06_indexes/index.json` | Indexed folders and files, including non-note files, with sizes and hashes |
| `06_indexes/sidecar.json` | Frontmatter metadata for recognized notes |
| `06_indexes/databases/search.db` | FTS5 note search index |
| `06_indexes/context_index.json` | L0/L1/L2 context cache keyed by relative path |

## Hashes and levels

Files have an exact SHA-256. Notes additionally hash their body and all
frontmatter except volatile timestamps (`created`, `modified`). Folders use a recursive hash of their path and children.

- L0: deterministic one-line orientation, safe to load broadly.
- L1: optional AI summary tied to a semantic source hash.
- L2: original source or direct folder children, loaded only on demand.

An unchanged context hash preserves its L1. A changed hash marks it `stale` but
does not trigger generation.

## Commands

```bash
arpent index
arpent context pending [--path <path>] [--kind folder|note|text] [--json]
arpent context show <path> --level l0|l1|l2
arpent context set <path> --source-hash <hash> --summary "..." --provider <id>
arpent context set <path> --source-hash <hash> --stdin --provider <id>
```

See `06_indexes/global_skills/context_summary.skill.md` for the explicit AI workflow.
"""

TOOLS_ARCHITECTURE_DOC_STUB = """# Tool Control Plane

Arpent separates tool know-how from tool runtime material.

## Boundary

`06_indexes/` contains everything required to define, create, validate,
operate, and evolve a sub-tool: the registry, skills, mirrored CLI contracts,
schemas, migrations, documentation, and centralized databases. The executable
CLI package is installed outside the vault.

`05_tools/` is runtime-only. It may contain artifacts, queues, captures,
caches, and outputs declared by an installed tool's `writes_to`. It must never
contain a `SKILL.md`, schema, migration, creation template, command contract, or
maintenance instructions.

Area-bound tools normally write user content to `02_areas/<area>/` and may need
no folder in `05_tools/`. Transversal tools may use `05_tools/<tool>/`, but all
of their know-how remains in `06_indexes/`.

## Minimal activation contract

Every tool starts as `planned` and declares a stable ID, category, skill under
`06_indexes/global_skills/`, `writes_to`, optional database, ephemeral flag, and
lifecycle rules. Empty storage and lifecycle values are explicit; future
commands and directories are not created speculatively.

## Progressive creation

1. A real need selects one tool.
2. The agent proposes the smallest useful commands and output boundary.
3. After confirmation, it creates a skill from
   `06_indexes/global_skills/_template_tool.skill.md` and registers the tool as
   `planned`.
4. It adds only required CLI contracts, schemas, and migrations in
   `06_indexes/`.
5. Installation validates paths, commands, storage, and lifecycle.
6. User confirmation changes the tool to `installed` and creates runtime paths.

Only installed tools may be dispatched, scheduled, or swept. Control-plane
changes are always announced and confirmed.

## Maintenance

The agent may maintain runtime content according to an installed skill. Changes
to skills, commands, storage, schemas, or lifecycle are proposed and confirmed.
Database evolution uses migrations; definitions are never copied into runtime
folders.
"""

AGENT_INFRA_INDEX_STUB = """version: 0.2.0
# Canonical definitions live in 03_resources/agent_infrastructure/.
# This file is their discovery registry, not their source of truth.
agent_roles: []
agent_skills: []
agent_workflows: []
agent_prompts: []
agent_templates: []
agent_style: []
capabilities: []
"""

AGENT_ROLE_TEMPLATE_STUB = """---
name: template-role-agent
description: Replace with the role and situations in which this agent should be used.
skills: []
workflows: []
capabilities: []
---

# Template Role Agent

## Role

The responsibility and perspective this agent adopts.

## Instructions

The concise prompt that governs its behavior.

## Tool Policy

Which declared capabilities it may use and when confirmation is required.

## Boundaries

Actions and decisions outside this role.

## Output

The expected result or handoff.
"""

AGENT_SKILL_TEMPLATE_STUB = """---
name: template-personal-agent-skill
description: Replace with the trigger and purpose for this portable personal-agent command.
---

# Template Personal-Agent Skill

## Trigger

When to use this skill.

## Input

What the user or environment provides.

## Steps

1. Read the relevant context.
2. Execute the task.
3. Report outputs and follow-ups.

## Output

What the skill returns or creates.

## Method

Constraints, invariants, and quality bar.
"""

AGENT_WORKFLOW_TEMPLATE_STUB = """---
name: template-workflow
description: Replace with the trigger and outcome of this portable workflow.
uses:
  agent_roles: []
  agent_skills: []
  prompts: []
  capabilities: []
---

# Template Workflow

## Trigger

When to use this workflow.

## Input

Required files, context, or user data.

## Steps

1. Prepare context.
2. Execute the workflow.
3. Record the result.

## Output

Expected final artifact or state change.

## Method

Workflow-specific constraints, decision points, and failure handling.
"""

CAPABILITY_TEMPLATE_STUB = """id: template-capability
# Supported kinds: cli, mcp, api, plugin.
kind: cli
description: Replace with the action this capability makes available.
connection:
  command: null
  endpoint: null
  config_ref: null
credential_refs: []
requires_confirmation: false
"""

ME_STUB = """# me.md - User Orientation

This file is human-owned. It gives agents a concise, user-approved orientation before they operate the vault.

It is not the delegated memory profile, not an observations log, and not a place for agents to accumulate inferred traits. Agents may propose edits, but should not rewrite this file from inference without explicit user confirmation.

## Identity

Write the stable self-description you want agents to know.

## Operating Preferences

Write interaction preferences, collaboration style, and recurring constraints that should shape agent behavior.

Optional: record a vault-specific note-language override here. Otherwise agents use the primary and adaptive language settings in the Arpent skill.

## Current North Star

Write the current high-level direction, season, or strategic focus.

## Important Boundaries

Write what agents should avoid assuming, changing, or optimizing for.

## Useful Links

- Add links to key projects, areas, maps, or external references.
"""

GITIGNORE_STUB = """.DS_Store
**/.DS_Store
node_modules/
**/node_modules/
06_indexes/backup/
06_indexes/imports/
06_indexes/logs/
*.db
*.db-journal
*.db-wal
*.db-shm
06_indexes/index.json
06_indexes/sidecar.json
06_indexes/context_index.json
05_tools/artefacts/*
!05_tools/artefacts/.gitkeep
"""

CRON_STUB = """{
  "version": "0.1.0",
  "jobs": [
    {
      "id": "ephemeral-sweep",
      "enabled": false,
      "schedule": "0 6 * * *",
      "command": "arpent sweep ephemeral",
      "trust": "local-code",
      "timeout_seconds": 300,
      "notify_channel": null,
      "tags": ["lifecycle", "ephemeral"],
      "last_started": null,
      "last_run": null,
      "description": "Apply lifecycle rules from tools.yaml."
    }
  ]
}
"""

TOOLS_STUB = """version: 0.2.0
tools:
  context_summary:
    category: transversal
    ephemeral: false
    skill: 06_indexes/global_skills/context_summary.skill.md
    writes_to:
      - 06_indexes/context_index.json
    database: null
    status: installed
    lifecycle: []
  todo:
    category: daily-flow
    ephemeral: true
    skill: 06_indexes/global_skills/todo.skill.md
    writes_to:
      - 02_areas/area__perso__todo__active
    database: 06_indexes/databases/todo.db
    status: installed
    lifecycle:
      - from: done
        after_days: 30
        action: archive-with-trace
  reader:
    category: transversal
    ephemeral: true
    skill: 06_indexes/global_skills/reader.skill.md
    writes_to:
      - 05_tools/reader/
    database: 06_indexes/databases/reader.db
    status: planned
    lifecycle:
      - from: done
        after_days: 60
        action: archive-with-trace
  review:
    category: transversal
    ephemeral: false
    skill: 06_indexes/global_skills/review.skill.md
    writes_to:
      - 05_tools/review/
    database: null
    status: planned
    lifecycle: []
  z_backup:
    category: transversal
    ephemeral: false
    skill: 06_indexes/global_skills/z_backup.skill.md
    writes_to:
      - 06_indexes/backup/
    database: null
    status: planned
    lifecycle: []
"""

ARPENT_SKILL_STUB = """---
name: arpent
description: Operate an Arpent vault using deterministic routing, universal frontmatter, optional delegated memory, and archive-only lifecycle rules.
---

# Arpent

## Trigger

Use whenever the user asks to capture, organize, import, route, archive, retrieve,
mature, extract personal knowledge, create/resume a project, close a session,
or manage actionable todos.

## Input

Free-form content, a file path, a retrieval query, or a vault operation request.

## Steps

1. Read `.agent`, then `me.md` when present.
2. Resume by reading `me.md`, then the target `_context.md`, then only needed notes/sources. Never read optional `MEMORY.md` without explicit user opt-in.
3. Identify the operation and route it through the Arpent CLI when available.
4. For triage, preview one complete plan with `triage --json`, `note edit
   --dry-run --json`, and `note ingest --dry-run --json`; carry each structured
   edit's `plan_sha256` into `--plan-hash` and apply items separately.
5. For an external tree, use `import scan`, reviewed folder roles, validation,
   dry-run, and one confirmed copy-only apply; never overlap source and vault.
6. Announce destination, complete frontmatter, and side effects before changes.
7. Confirm what changed, including partial batch outcomes.

## Output

A natural-language summary plus structured confirmation of changed files.

## Method

- Language settings: `Primary language: English`; `Adaptive languages: French`. Write note prose in the primary language by default, adapting to a listed language when explicitly requested or when the conversation/source is contextually in that language. Replace the list with `auto` to allow any contextual language. Do not add a frontmatter language field.
- Dates use `dd-mm-yyyy`; note-facing UTC timestamps use `dd-mm-yyyyTHH:MM:SSZ`.
- Files first; routing is deterministic; never delete.
- Never fill `appreciated` or `importance`.
- Delegated memory is disabled by default and requires explicit user opt-in; the vault is not a memory dump.
- Keep all tool know-how in `06_indexes/`.
- `05_tools/` contains declared runtime material only and never a `SKILL.md`.
- Read `06_indexes/docs/architecture/tools.md` before creating or evolving a tool.
- Create projects deliberately with `arpent project create`; routing never invents them.
- The universal schema is closed during normal use; body sections, project files, and project subfolders remain extensible.
- Binary attachments remain byte-for-byte untouched and use separate Markdown companion reference notes.
- `_context.md` and `session end` work in both modes. `MEMORY.md` is disabled and unseeded by default; only `--memory-log` writes it, and later reads require explicit user opt-in. Delegated queue writes are full-only.
- `arpent usage report` is local and cannot measure documentary resume quality.
"""

MINIMAL_ARPENT_SKILL_STUB = """---
name: arpent
description: Operate a minimal Arpent vault with deterministic routing, complete frontmatter, and archive-only lifecycle rules.
---

# Arpent Minimal

Use the Arpent CLI for project creation, capture, routing, retrieval, indexing,
triage/ingestion, reviewed external import, usage reporting, session closure,
and archival.
Every note uses the complete universal frontmatter contract. Announce
destinations and side effects before state changes, never infer subjective
fields, never guess a missing route, and never delete when archival is possible.
Language settings: `Primary language: English`; `Adaptive languages: French`.
Use the primary language by default and adapt to a listed language only when
explicitly requested or contextually supported by the conversation/source;
replace the list with `auto` to allow any contextual language. Dates use
`dd-mm-yyyy`; note-facing UTC timestamps use `dd-mm-yyyyTHH:MM:SSZ`.
For structured triage, carry `plan_sha256` from `note edit --dry-run --json`
into `--plan-hash` when applying.

Resume by reading `me.md`, then the target `_context.md`, then only needed
notes/sources. `session end` maintains target context. `MEMORY.md` is disabled
and unseeded by default; only `--memory-log` writes it, and later reads require
explicit user opt-in.
This profile does not install delegated-memory queues, a memory wiki, context
summaries, cron, todo, tools, sweep, or portable-agent infrastructure modules.
Do not invent frontmatter fields; body sections and project files/subfolders are
extensible. Binary attachments remain byte-for-byte untouched and use separate
Markdown companion reference notes.
"""

CONTEXT_SUMMARY_SKILL_STUB = """---
name: arpent-context-summary
description: Generate compact L1 summaries only when explicitly requested and only for missing or stale semantic hashes.
---

# Context Summary

## Trigger

Use only when the user explicitly asks to build or refresh intelligent context
summaries. `arpent index` never triggers this skill automatically.

## Input

- An initialized and indexed Arpent vault.
- Entries returned by `arpent context pending`.

## Steps

1. Run `arpent index` to refresh deterministic inventory and hashes.
2. List work with `arpent context pending --json`, optionally scoped by path or kind.
3. Skip every entry whose L1 status is already `fresh`.
4. Load only the required source with `arpent context show <path> --level l2`.
5. Produce a factual, standalone summary of 2-5 sentences and at most 180 words.
6. Store it with `arpent context set <path> --source-hash <hash-from-pending> --stdin --provider <agent-or-model-id>`.
7. Confirm that the path no longer appears in `arpent context pending`.

## Output

Fresh L1 entries in `06_indexes/context_index.json`, tied to their semantic
source hashes.

## Method

- L0 is deterministic orientation generated by `arpent index`.
- L1 is optional AI output and is never generated implicitly.
- L2 is loaded only on demand.
- Never regenerate a fresh L1 whose source hash still matches.
- Never summarize binary files or infer facts absent from the source.
- Follow the Arpent skill's primary/adaptive language settings for summaries.
"""

READER_SKILL_STUB = """---
name: reader
description: Transversal tool placeholder for captured articles, books, podcasts, and reading workflows.
---

# Reader

## Trigger

Use when capturing, reading, summarizing, or archiving external content.

## Input

A URL, file, book, podcast, transcript, or reading note.

## Steps

1. Capture source material.
2. Store runtime artifacts under the declared `05_tools/reader/` workspace.
3. Create clean vault notes only when they become reusable knowledge.

## Output

Captured artifacts plus routed notes when appropriate.

## Method

This skill remains in `06_indexes/global_skills/`. `05_tools/reader/` contains runtime
material only. Structured state lives in `06_indexes/databases/reader.db`.
"""

REVIEW_SKILL_STUB = """---
name: review
description: Transversal tool placeholder for reviews and synthesis across projects, areas, and resources.
---

# Review

## Trigger

Use for periodic review, synthesis, and vault health checks.

## Input

Projects, areas, notes, indexes, and user priorities.

## Steps

1. Read relevant indexes and context files.
2. Identify stale, active, and high-value items.
3. Propose changes before modifying files.

## Output

Review summary, suggested updates, and confirmed state changes.

## Method

Keep this skill in `06_indexes/global_skills/`. Write runtime output only to registered
`writes_to` paths and never mutate the vault without confirmation.
"""

BACKUP_SKILL_STUB = """---
name: z_backup
description: Transversal workflow for local snapshot creation, verification, and restoration.
---

# Backup

## Trigger

Use when creating, verifying, or restoring local snapshots.

## Input

Vault root and backup destination.

## Steps

1. Run `arpent backup [--destination <dir>]`.
2. Verify the snapshot with `arpent backup verify <snapshot>`.
3. Restore only to a new directory with `arpent backup restore <snapshot> --to <new-dir>`.

## Output

Backup record and verification summary.

## Method

Keep this skill in `06_indexes/global_skills/`. Snapshots default to
`06_indexes/backup/`. They exclude rebuildable/runtime state and do not include
Git history, delegated memory, or external files. Never delete originals.
"""

TOOL_SKILL_TEMPLATE_STUB = """---
name: replace-with-tool-name
description: Replace with the concrete purpose and trigger boundary of this Arpent sub-tool.
---

# Tool Name

## Trigger

State exactly when the agent should use this tool.

## Input

List the minimum accepted inputs.

## Steps

1. Describe only the first useful workflow.
2. Use registered CLI commands for state changes.
3. Write only to paths declared by `writes_to`.

## Output

Describe the user-visible result and structured confirmation.

## Method

- Keep all know-how in `06_indexes/`; never place instructions in `05_tools/`.
- Keep the tool `planned` until commands, storage, paths, and lifecycle validate.
- Do not add speculative behavior before real usage requires it.
- Require user confirmation before changing the tool to `installed`.
"""

TODO_SKILL_STUB = """---
name: arpent-todo
description: Operate the SQLite-backed Arpent todo list when creating, listing, editing, completing, deferring, blocking, or archiving tasks.
---

# Todo

## Trigger

Use when the user asks to capture or manage an actionable task in the Arpent
todo list.

## Input

- Task content.
- Optional selection keys, dates, and stable project/person references.
- An existing `todo-*` ID for updates.

## Steps

1. Use `arpent todo add` for capture and `arpent todo list` or `show` for retrieval.
2. Use `edit`, `defer`, or `block` for structured updates.
3. Use `done` to complete a task.
4. Use `archive` only after completion; never delete the SQLite row or Markdown record.

## Output

A SQLite todo row plus a Markdown lifecycle record under the todo area or
quarterly archives.

## Method

- `todo.db` stores structured fields; Markdown preserves a readable trace.
- Selection values are configurable text keys, not hard-coded enums.
- Project, dependency, and assignee fields are stable soft references.
- Dates use `dd-mm-yyyy`; creation timestamps are automatic and immutable.
- Todo records are tool-owned and must be changed through `arpent todo`.
"""

PENDING_WRITES_STUB = """version: 0.1.0
pending: []
"""

FRONTMATTER_POLICY_STUB = """version: 0.3.0
serialization:
  shape: complete_all_fields
  unused_scalar: null
  unused_list: []
subjective_user_only:
  - appreciated
  - importance
defaults:
  pinned: false
  relations: []
rules:
  dates: date values use dd-mm-yyyy; note-facing UTC timestamps use dd-mm-yyyyTHH:MM:SSZ
  routing: project and resource are mutually exclusive homes; area may accompany either as context
  source_link: warn on mismatch
  title: ordinary-note filename equals lowercase ASCII snake_case title; reserved system filenames are exceptions; id remains in frontmatter only
  description: null when redundant with title or body
  depth: integer from 1 to 5 when meaningful
  effort: active actionables may use effort_cadence heavylift|slowburn and effort_level low|medium|high; never infer missing values
  relations: list of mappings with type and target; type must be in enums.relation_type
  sweep: archive only done or stale; active, stable, and ongoing remain
enums:
  status:
    - inbox
    - maturing
    - active
    - stable
    - ongoing
    - standby
    - waiting
    - to-start
    - done
    - stale
    - archived
  effort_cadence:
    - heavylift
    - slowburn
  effort_level:
    - low
    - medium
    - high
  relation_type:
    - supports
    - contradicts
    - depends_on
    - derived_from
    - example_of
  type:
    - note
    - concept
    - journal
    - log
    - checklist
    - reference
    - draft
    - template
    - meeting
    - idea
    - fleeting
    - linear
    - integration
    - angle
    - production
    - map
    - artefact
"""


def _ensure_marker(vault: Vault, *, mode: str) -> None:
    marker = vault.safe_output_path(MARKER)
    if not marker.exists() and not marker.is_symlink():
        content = {"version": 1, "name": "arpent", "mode": mode}
        vault.atomic_create_text(MARKER, json.dumps(content, sort_keys=True) + "\n")
        return

    content = vault.marker_data()
    existing_mode = content.get("mode")
    if existing_mode != mode:
        raise ValueError(
            f"Vault is already initialized in {existing_mode} mode; "
            f"refusing an implicit change to {mode} mode."
        )


def _initialize_git(root: Path) -> None:
    git_path = root / ".git"
    if git_path.is_symlink():
        raise ValueError(f"Refusing a symlinked Git directory: {git_path}")
    executable = shutil.which("git")
    if executable is None:
        raise ValueError("Git is required to initialize an Arpent vault.")
    result = subprocess.run(
        [executable, "init", "--quiet", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "git init failed"
        raise ValueError(f"Cannot initialize Git repository: {detail}")


def init_vault(root: Path, *, minimal: bool = False) -> "Vault":
    root = Path(root).expanduser()
    if root.is_symlink():
        raise ValueError(f"Refusing to initialize a vault through a symlink: {root}")
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not root.is_dir():
        raise ValueError(f"Vault root is not a directory: {root}")
    vault = Vault(root)
    mode = "minimal" if minimal else "full"
    marker = vault.safe_output_path(MARKER)
    marker_exists = marker.exists() or marker.is_symlink()
    if marker_exists:
        _ensure_marker(vault, mode=mode)
    _initialize_git(root)
    for rel in MINIMAL_SCAFFOLD if minimal else SCAFFOLD:
        vault.safe_ensure_directory(rel)

    _seed(vault, root / "06_indexes/cli/operations.yaml", operations_mod.default_operations_text())
    _seed(vault, root / "06_indexes/schemas/frontmatter_policy.yaml", FRONTMATTER_POLICY_STUB)
    _seed(vault, root / "06_indexes/logs/usage-journal.md", USAGE_JOURNAL_STUB)
    if minimal:
        _seed(vault, root / ".agent", MINIMAL_AGENT_STUB)
        _seed(vault, root / "COMPASS.md", MINIMAL_COMPASS_STUB)
        _seed(
            vault,
            root / "06_indexes/global_skills/arpent.skill.md",
            MINIMAL_ARPENT_SKILL_STUB,
        )
    else:
        _seed(vault, root / ".agent", AGENT_STUB)
        _seed(vault, root / "COMPASS.md", COMPASS_STUB)
        _seed(vault, root / "06_indexes/docs/ARPENT.md", ARPENT_STUB)
        _seed(vault, root / "06_indexes/docs/mental-model.md", MENTAL_MODEL_STUB)
        _seed(vault, root / "06_indexes/docs/architecture/agent-infrastructure.md", AGENT_INFRA_DOC_STUB)
        _seed(vault, root / "06_indexes/docs/architecture/indexing-and-context.md", INDEXING_CONTEXT_DOC_STUB)
        _seed(vault, root / "06_indexes/docs/architecture/tools.md", TOOLS_ARCHITECTURE_DOC_STUB)
        _seed(vault, root / "06_indexes/memory/wiki/SCHEMA.md", WIKI_SCHEMA_STUB)
        _seed(vault, root / "06_indexes/cron.json", CRON_STUB)
        _seed(vault, root / "06_indexes/tools.yaml", TOOLS_STUB)
        _seed(vault, root / "06_indexes/agent_infrastructure_index.yaml", AGENT_INFRA_INDEX_STUB)
        _seed(vault, root / "06_indexes/pending_db_writes.yaml", PENDING_WRITES_STUB)
        _seed(
            vault,
            root / "06_indexes/schemas/todo_schema.sql",
            Path(__file__).with_name("todo_schema.sql").read_text(encoding="utf-8"),
        )
        _seed(vault, root / "06_indexes/global_skills/arpent.skill.md", ARPENT_SKILL_STUB)
        _seed(vault, root / "06_indexes/global_skills/todo.skill.md", TODO_SKILL_STUB)
        _seed(vault, root / "06_indexes/global_skills/context_summary.skill.md", CONTEXT_SUMMARY_SKILL_STUB)
        _seed(vault, root / "06_indexes/global_skills/reader.skill.md", READER_SKILL_STUB)
        _seed(vault, root / "06_indexes/global_skills/review.skill.md", REVIEW_SKILL_STUB)
        _seed(vault, root / "06_indexes/global_skills/z_backup.skill.md", BACKUP_SKILL_STUB)
        _seed(vault, root / "06_indexes/global_skills/_template_tool.skill.md", TOOL_SKILL_TEMPLATE_STUB)
        _seed(vault, root / "05_tools/artefacts/.gitkeep", "")
        _seed(vault, root / "03_resources/agent_infrastructure/_README.md", AGENT_INFRA_README_STUB)
        _seed(
            vault,
            root / "03_resources/agent_infrastructure/agent_roles/_template_agent/AGENT.md",
            AGENT_ROLE_TEMPLATE_STUB,
        )
        _seed(
            vault,
            root / "03_resources/agent_infrastructure/agent_skills/_template_skill/SKILL.md",
            AGENT_SKILL_TEMPLATE_STUB,
        )
        _seed(
            vault,
            root / "03_resources/agent_infrastructure/agent_workflows/_template_workflow/WORKFLOW.md",
            AGENT_WORKFLOW_TEMPLATE_STUB,
        )
        _seed(
            vault,
            root / "03_resources/agent_infrastructure/capabilities/_template_capability/CAPABILITY.yaml",
            CAPABILITY_TEMPLATE_STUB,
        )
    _seed(vault, root / "me.md", ME_STUB)
    _seed(vault, root / ".gitignore", GITIGNORE_STUB)
    if not marker_exists:
        _ensure_marker(vault, mode=mode)
    return vault


def _seed(vault: Vault, path: Path, content: str) -> None:
    relpath = path.relative_to(vault.root).as_posix()
    safe_path = vault.safe_output_path(relpath)
    if not safe_path.exists():
        vault.atomic_create_text(relpath, content)

"""
vault.py - vault location, scaffolding, and discovery helpers.
"""

from __future__ import annotations

import errno
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
MARKER_VERSION = 2
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
_LOCK_STATE = threading.local()

# Both modes retain the same information and skills. Minimal changes how the
# agent operates the vault, not what the vault may contain.
SCAFFOLD = [
    "00_inbox",
    "00_inbox/fleeting",
    "00_inbox/captures",
    "00_inbox/unsure",
    "01_projects",
    "01_projects/_template_project",
    "02_areas",
    "02_areas/area__perso__todo__active",
    "02_areas/area__perso__todo__active/active",
    "02_areas/area__perso__todo__active/waiting",
    "02_areas/area__perso__todo__active/done",
    "03_resources",
    "03_resources/concepts",
    "03_resources/maps-of-content",
    "03_resources/how-tos",
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

WINDOWS_RESERVED_NAMES = {
    "aux", "clock$", "con", "conin$", "conout$", "nul", "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}
_UNSUPPORTED_LINK_ERRNOS = {
    errno.EACCES,
    errno.EPERM,
    errno.EXDEV,
    getattr(errno, "ENOSYS", -1),
    getattr(errno, "ENOTSUP", -1),
    getattr(errno, "EOPNOTSUPP", -1),
}

class Vault:
    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()

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
            or set(content) != {"version", "name", "mode", "auto_full"}
            or type(content.get("version")) is not int
            or content["version"] != MARKER_VERSION
            or content.get("name") != "arpent"
            or content.get("mode") not in {"full", "minimal"}
            or type(content.get("auto_full")) is not bool
            or (content.get("mode") == "full" and content.get("auto_full"))
        ):
            raise ValueError("Invalid .arpent marker: expected the current Arpent format.")
        return content

    def project_slugs(self):
        base = self.root / "01_projects"
        return [
            p.name for p in base.iterdir()
            if p.is_dir() and not p.is_symlink() and not p.name.startswith(("_", "."))
        ] if base.exists() else []

    def area_slugs(self):
        base = self.root / "02_areas"
        return [p.name for p in base.iterdir() if p.is_dir() and not p.is_symlink()] if base.exists() else []

    def resource_slugs(self):
        base = self.root / "03_resources"
        found = [p.name for p in base.iterdir() if p.is_dir() and not p.is_symlink()] if base.exists() else []
        operations_path = self.safe_source_path("06_indexes/cli/operations.yaml")
        reserved = operations_mod.routing_contract(operations_path)["reserved_resources"]
        return sorted(set(found) | set(reserved))

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
            self._link_or_copy_no_replace(temporary, target)
            self.fsync_directory(target.parent)
        finally:
            temporary.unlink(missing_ok=True)
        return target

    def atomic_move_no_replace(self, source_relpath: str, destination_relpath: str) -> Path:
        """Move a file without ever replacing an existing destination."""
        source = self.safe_source_path(source_relpath)
        destination = self.safe_output_path(destination_relpath)
        self._link_or_copy_no_replace(source, destination)
        self.fsync_directory(destination.parent)
        try:
            source.unlink()
            self.fsync_directory(source.parent)
        except Exception:
            destination.unlink(missing_ok=True)
            self.fsync_directory(destination.parent)
            raise
        return destination

    @staticmethod
    def _link_or_copy_no_replace(source: Path, destination: Path) -> None:
        try:
            os.link(source, destination)
            return
        except OSError as exc:
            if exc.errno not in _UNSUPPORTED_LINK_ERRNOS:
                raise

        descriptor = None
        created = False
        try:
            with source.open("rb") as input_stream:
                before = os.fstat(input_stream.fileno())
                before_signature = (
                    before.st_dev, before.st_ino, before.st_size,
                    before.st_mtime_ns, before.st_ctime_ns,
                )
                descriptor = os.open(
                    destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600,
                )
                created = True
                with os.fdopen(descriptor, "wb") as output_stream:
                    descriptor = None
                    shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)
                    output_stream.flush()
                    os.fsync(output_stream.fileno())
                after = os.fstat(input_stream.fileno())
                current = source.lstat()
                after_signature = (
                    after.st_dev, after.st_ino, after.st_size,
                    after.st_mtime_ns, after.st_ctime_ns,
                )
                if (
                    before_signature != after_signature
                    or (current.st_dev, current.st_ino) != before_signature[:2]
                ):
                    raise ValueError(
                        f"Source changed while copying without replacement: {source}"
                    )
        except BaseException:
            if descriptor is not None:
                os.close(descriptor)
            if created:
                destination.unlink(missing_ok=True)
            raise

    @contextmanager
    def exclusive_lock(self, name: str):
        """Serialize a vault mutation across processes without stale PID locks."""
        with self._file_lock(name, shared=False):
            yield

    @contextmanager
    def shared_lock(self, name: str):
        """Hold a process-shared read lease; Windows conservatively uses exclusive."""
        with self._file_lock(name, shared=True):
            yield

    @contextmanager
    def _file_lock(self, name: str, *, shared: bool):
        if not re.fullmatch(r"[a-z0-9_-]+", name):
            raise ValueError(f"Invalid vault lock name: {name}")
        held = getattr(_LOCK_STATE, "held", None)
        if held is None:
            held = _LOCK_STATE.held = {}
        key = (self.root, name)
        if key in held:
            state = held[key]
            if state["shared"] and not shared:
                raise RuntimeError(
                    f"Cannot upgrade shared vault lock '{name}' to exclusive."
                )
            state["count"] += 1
            try:
                yield
            finally:
                state["count"] -= 1
            return
        path = self.safe_output_path(f"06_indexes/logs/{name}.lock")
        with path.open("a+b") as stream:
            if fcntl is not None:
                operation = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
                fcntl.flock(stream.fileno(), operation)
            elif msvcrt is not None:  # pragma: no cover - Windows only
                stream.seek(0, os.SEEK_END)
                if stream.tell() == 0:
                    stream.write(b"\0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            try:
                held[key] = {"count": 1, "shared": shared}
                yield
            finally:
                held.pop(key, None)
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
        if candidate.is_absolute() or ".." in candidate.parts or "\\" in str(relpath):
            raise ValueError("Vault path must be relative and cannot contain '..'.")
        for part in candidate.parts:
            portable = part.rstrip(" .")
            device_name = portable.split(".", 1)[0].casefold()
            if portable != part or device_name in WINDOWS_RESERVED_NAMES:
                raise ValueError(f"Vault path uses a Windows-reserved name: {part}")
        return self.root / candidate


def is_index_excluded(relpath: str, *, directory=False) -> bool:
    parts = Path(relpath).parts
    if (
        len(parts) >= 3
        and parts[:2] == ("00_inbox", "captures")
        and parts[2].startswith(".arpent-import-")
    ):
        return True
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

ARPENT_STUB = """# Arpent Constitution

This vault is an Arpent vault: a filesystem-native local continuity and
administration layer.

- Files over apps. Markdown is canonical for documents; `todo.db` is
  authoritative for coordinated todo state.
- Delegated memory is optional and disabled by default; the vault is a clean knowledge base, not a memory dump.
- Routing is deterministic. Prevent silent replacement or destruction; explicit
  checked atomic edits are allowed, and lifecycle retention uses archives.
- Confirmation follows the local operation policy; the user owns the vault.

See 06_indexes/global_skills/ for the operating skill.
"""

AGENT_WIKI_README_STUB = """# Agent Wiki

This is the separate scope for notes created by agents without explicit user request.

Agent-authored notes start here with:

```yaml
type: draft
status: maturing
author: agent
```

Review uses the normal lifecycle status. Promotion changes the standard type and
routing fields while preserving `author: agent` so lineage remains clear. No
agent-wiki-only frontmatter key is introduced.
"""

AGENT_STUB = """# .agent - Arpent vault entry point

Read this file completely. Then load only what the current operation needs.

## Start

1. Read the small `.arpent` marker.
2. If an Arpent host skill is active, do not reload the local skill.
3. Otherwise read `06_indexes/global_skills/arpent.skill.md`.
4. Use the active skill's hot path for ordinary note, todo, or fleeting capture.
5. Read `COMPASS.md` only to select a less common operation.
6. Read `me.md` for interaction preferences and when resuming work.
7. On resume, read target `_context.md`, then only needed notes or sources.

In `minimal`, use direct-file operations; mode-gated CLI commands require
vault-mode promotion. In `full`, use CLI-mediated vault operations. If
`auto_full` is true, the first mode-gated command requests promotion. If the
confirmation policy requires it, run `arpent mode full --yes` first. An explicit
return to minimal cancels the pending request.

The confirmation policy lives in `06_indexes/cli/operations.yaml`.

## Hard Rules

- Prevent silent loss: never silently replace a destination or destroy user
  content. Explicit edits may use checked atomic replacement; archive for
  lifecycle retention.
- Never fill `appreciated` or `importance`; do not infer effort values.
- Never guess a missing route; use `00_inbox/unsure/` with a reason.
- Reserved resource homes may materialize on first write; never invent another
  missing project, area, or resource.
- Never invent frontmatter fields, relation types, memory activation, or side effects.
- Write public timestamps as `dd-MM-YYYY-HH-mm` in UTC.
- Keep binary attachments untouched with separate Markdown companions.
- Do not rewrite `me.md` from inference.
- A tool skill is not executable unless its registry status is `installed` and
  its runtime implementation and prerequisites are available.

`_context.md` is the default local continuity surface. Minimal keeps approved
orientation and context in files. External host memory remains opt-in and is not
enabled by vault mode.
Actionable reminders are todo; non-actionable buffer context is provider-bound
and is not persisted when no provider is enabled.
"""

MENTAL_MODEL_STUB = """# Arpent Mental Model

When information arrives, decide which role it plays:

| Information | Destination |
|---|---|
| Long-form content to open, read, and edit | Vault |
| User-provided orientation | `me.md` in both modes |
| Durable readable knowledge | Vault note in both modes |
| Action or reminder to execute, follow, complete, defer, or block | Todo (coordinated in full; clearly untracked inbox note in minimal) |
| Personal trait or fact for opportunistic recall | External profile/observation only when a host provider is explicitly enabled |
| Time-bound operational context | target `_context.md` in both modes |
| Temporary recall context without execution state | External buffer only when a host provider is explicitly enabled |
| Unsupervised agent research scratch | `06_indexes/memory/wiki/` in full; retained dormant in minimal |
| Default cross-session operational continuity | project/area `_context.md` |
| Optional cross-project log | `06_indexes/memory/MEMORY.md`, only after explicit full-mode `session end --memory-log` |

External-memory destinations require provider opt-in and confirmed persistence;
vault mode does not enable them. When no provider is enabled, report that
provider-bound information was not persisted; do not silently substitute a note
or fallback store.

“Remember to do X” is a todo, not a buffer. Use a buffer only when no action or
completion state must be tracked.

The vault is a clean shared document and continuity layer, not an automatic
memory log. Markdown is canonical for documents; `todo.db` is authoritative for
coordinated todo state.

`MEMORY.md` is unseeded. The delivered `session end` command writes it only when
`--memory-log` is explicitly passed. Normal resume reads `me.md`, then the target
`_context.md`, then only needed notes/sources; reading the optional log requires
a separate explicit request.

`me.md` is a root-level orientation file. It is read early by agents, but it is not a dump for inferred traits or automatic memory writes.
"""

MEMORY_STUB = """# MEMORY - optional working log

Created only by a one-use full-mode `session end --memory-log` write request.
Reading it later requires a separate explicit request.
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
| Vault tool registry | `06_indexes/tools.yaml` | Declared Arpent tools and their `planned` or `installed` status |
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

A declaration does not make a capability available. Runtime availability also
requires an implementation, a vault mode that permits use, satisfied
dependencies, and host configuration or enablement where applicable.
Unavailable declarations remain retained and dormant.

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

ROUTING_DOC_STUB = """# Routing

Routing is a pure function of frontmatter.

Lifecycle status and physical location are decoupled. Status alone does not
assert a path or perform a move.

- `project` set -> `01_projects/<project>/notes/`; use `drafts/` for drafts,
  `meetings/` for meetings, and `sessions/` for logs
- `area` set -> the exact area folder, or one unambiguous
  `area__*__<slug>__*`; meetings/logs use configured subfolders
- `resource` set -> `03_resources/<resource>/`
- all three null -> `00_inbox/`, except captured sources go to
  `00_inbox/captures/`
- `project + area` -> the project home; `area` remains contextual metadata
- `resource + area` -> the resource home; `area` remains contextual metadata
- `project + resource` -> `00_inbox/unsure/` with a reason

Special types may override subfolders:

- `fleeting` -> `00_inbox/fleeting/dd-mm-yyyy.md`
- `map` -> `03_resources/maps-of-content/`
- `howto` -> `03_resources/how-tos/`
- `integration` -> `03_resources/integrations/`
- `artefact` -> `05_tools/artefacts/`
- an agent-authored draft without a project -> `03_resources/agent_wiki/drafts/`
- `linear` source notes archive to `04_archives/linear_notes/` after dissolution

Routing never invents a missing home. Full creates a deliberate project with
`arpent project create <name>`. Minimal follows the direct project procedure in
the local Arpent skill.

Reserved resource homes (`concepts`, `maps-of-content`, `how-tos`, `integrations`,
`templates`, `agent_wiki`, `books`, `articles`, `portraits`, `productions`) are
declared by the contract and may materialize on first write. Any other missing
resource, project, or area remains unresolved and routes to `unsure/`.

Triage and transactional ingestion are full-only CLI operations. In minimal,
inventory inbox files directly, preserve raw sources, and do not claim an atomic
multi-file disposition. In full, `arpent triage --json` inventories structured,
text, malformed, and binary items; use reviewed `note edit` or `note ingest`
plans and report partial batch outcomes honestly.

A binary/non-text source remains byte-for-byte untouched and cannot contain
YAML. In full, `note ingest --attachment` moves it transactionally to the
selected home's `attachments/` and creates a separate Markdown companion
reference note with complete frontmatter and a `link` to the attachment. Without
a final home, the original remains in inbox and the companion is untriaged.

Minimal archive preserves one non-linear note, sets `status: archived`, updates
`modified`, adds lifecycle-event metadata `archived_at` and `archived_from`, and
moves without silently replacing a destination to
`04_archives/<YYYY_qN>/<title>.md`. `archived` is the status; the two extension
fields record when and from where the move happened. Inspect source and
destination immediately before the move and verify afterward. Extraction and
linear dissolution remain full-only because they coordinate multiple notes.
"""

INDEXING_CONTEXT_DOC_STUB = """# Indexing and Context

## Core rule

`arpent index` is deterministic and local. It inventories folders and files,
computes hashes, rebuilds search data, and refreshes L0/L2 context. It never
invokes an AI model.

AI-generated L1 summaries run only after a user request and only for entries
reported as missing or stale.

## Generated outputs

| Output | Content |
|---|---|
| `06_indexes/index.json` | Complete folder and file inventory with sizes and hashes |
| `06_indexes/sidecar.json` | Frontmatter metadata for recognized notes |
| `06_indexes/databases/search.db` | FTS5 note search index, created only when SQLite exposes FTS5; otherwise search uses a live text fallback |
| `06_indexes/context_index.json` | L0/L1/L2 context cache keyed by relative path |

Generated derivatives remain complete. Agents use bounded query commands rather
than byte-truncating those JSON artifacts. Markdown remains canonical for
documents; `todo.db` remains authoritative for coordinated todo state.

## Hashes and levels

Files have an exact SHA-256. Notes additionally hash their body and all
frontmatter except volatile timestamps. Folders use a recursive child hash.

- L0: deterministic one-line orientation, safe to load broadly.
- L1: optional AI summary tied to a semantic source hash.
- L2: original source or direct folder children, loaded on demand.

An unchanged context hash preserves its L1. A changed hash marks it stale.

## Commands

```bash
arpent index [--yes]
arpent context pending --json-page --limit 100
arpent context show <path> --level l0|l1
arpent context show <path> --level l2 --json-page --max-bytes 32768
arpent context set <path> --source-hash <hash> --stdin --provider <id> [--yes]
```

Every page reports total or total bytes, source/snapshot hash, completeness, and
the next cursor. Follow all same-hash chunks before summarizing a complete
source. Use `--all` for complete collections and `--full` for complete content.

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
caches, and outputs declared by a tool's `writes_to`. It must never
contain a `SKILL.md`, schema, migration, creation template, command contract, or
maintenance instructions.

Area-bound tools normally write user content to `02_areas/<area>/` and may need
no folder in `05_tools/`. Transversal tools may use `05_tools/<tool>/`, but all
of their know-how remains in `06_indexes/`.

## Minimum tool definition

Every tool starts as `planned` and declares a stable ID, category, skill under
`06_indexes/global_skills/`, `writes_to`, optional database, ephemeral flag, and
lifecycle rules. Empty storage and lifecycle values are explicit; future
commands and directories are not created speculatively.

`planned` and `installed` are registry states only. They do not prove
implementation, that the current vault mode permits use, configuration
enablement, dependencies, or runtime availability. The current CLI inspects but
does not mutate this status.

## Progressive creation

1. A real need selects one tool.
2. The agent proposes the smallest useful commands and output boundary.
3. Under the local confirmation policy, it creates a skill from
   `06_indexes/global_skills/_template_tool.skill.md` and registers the tool as
   `planned`.
4. It adds only required CLI contracts, schemas, and migrations in
   `06_indexes/`.
5. Installation validates paths, commands, storage, and lifecycle.
6. Policy-governed installation changes the tool to `installed` and creates runtime paths.

Installation is one prerequisite for dispatch. Sweep executes only ephemeral
tools with `status: installed`; cron enablement is separate in `cron.json`.
Control-plane changes follow the confirmation policy.

## Maintenance

The agent may maintain runtime content according to the skill declared by a tool
with `status: installed`. Changes to skills, commands, storage, schemas, or
lifecycle follow that policy.
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
description: Replace with the action this capability is intended to expose.
connection:
  command: null
  endpoint: null
  config_ref: null
credential_refs: []
requires_confirmation: false
"""

ME_STUB = """# me.md - User Orientation

This file is human-owned. It gives agents concise, user-provided orientation before they operate the vault.

It is not the delegated memory profile, not an observations log, and not a place for agents to accumulate inferred traits. Agents may propose edits, but should not rewrite this file from inference without an explicit user request.

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

PROJECT_CONTEXT_TEMPLATE_STUB = """---
title: REPLACE_WITH_SNAKE_CASE_PROJECT_CONTEXT_TITLE
id: null
created: REPLACE_WITH_CURRENT_UTC_TIMESTAMP
modified: REPLACE_WITH_CURRENT_UTC_TIMESTAMP
description: REPLACE_WITH_PROJECT_SPECIFIC_DESCRIPTION
type: note
project: REPLACE_WITH_PROJECT_SLUG
area: null
resource: null
status: active
effort_cadence: null
effort_level: null
tags: [context]
chosen_location: Maintained at the project root so agents read it before acting.

source: generated
link: null
author: agent

depth: null
appreciated: null
importance: null
pinned: false

expires_at: null

related: []
relations: []
parent: null
observations: []
extracted_to: []
---

## Vision

## Current state

## Resume here

## Deliverables / definition of done

## Key resources

## Next steps

## Working rhythm and time budget

## Session history
"""

AREA_CONTEXT_TEMPLATE_STUB = """---
title: REPLACE_WITH_SNAKE_CASE_AREA_CONTEXT_TITLE
id: null
created: REPLACE_WITH_CURRENT_UTC_TIMESTAMP
modified: REPLACE_WITH_CURRENT_UTC_TIMESTAMP
description: REPLACE_WITH_AREA_SPECIFIC_DESCRIPTION
type: note
project: null
area: REPLACE_WITH_AREA_SLUG
resource: null
status: ongoing
effort_cadence: null
effort_level: null
tags: [context]
chosen_location: Maintained at the area root so agents read it before acting.

source: generated
link: null
author: agent

depth: null
appreciated: null
importance: null
pinned: false

expires_at: null

related: []
relations: []
parent: null
observations: []
extracted_to: []
---

## Purpose

## Current state

## Routines

## Key resources
"""

HOWTO_TEMPLATE_STUB = """## Current conclusion

State the currently applicable answer directly.

Last explicit review: REPLACE_WITH_DD-MM-YYYY-HH-MM_UTC

## Why

Summarize only the reasons and tradeoffs needed to apply the answer today.

## How

1. Add a concrete step.
2. Add a verification criterion.

## Examples

Add short, reproducible examples.

## Applicability and limits

State prerequisites, exceptions, and signals that require another explicit
review.

## Linked notes

- [[subject_map]] - navigation for the broader subject
- [[detailed_decision]] - full reasoning or evidence
- [[historical_note]] - superseded conclusions or alternatives
"""

GITIGNORE_STUB = """# Databases and SQLite runtime files
*.db
*.db-journal
*.db-wal
*.db-shm

# Generated or redundant indexes
06_indexes/backup/*
!06_indexes/backup/.gitkeep
06_indexes/imports/*
!06_indexes/imports/.gitkeep
06_indexes/logs/*
!06_indexes/logs/.gitkeep
!06_indexes/logs/usage-journal.md
06_indexes/index.json
06_indexes/sidecar.json
06_indexes/context_index.json

# Python artifacts
__pycache__/
*.pyc
.venv/
*.egg-info/

# Node artifacts
node_modules/
**/node_modules/

# Heavy or regeneratable tool artifacts
05_tools/artefacts/*
!05_tools/artefacts/.gitkeep
05_tools/*/cache/
05_tools/*/articles/*/archive.html
05_tools/*/articles/*/.meta.json

# Secrets
06_indexes/secrets/
*.pem
*.key
credentials.json

# OS/editor cruft
.DS_Store
Thumbs.db
*.swp
.obsidian/workspace.json
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
    # Planned/in construction; not invocable and not processed by sweep.
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
    # Planned/in construction; no generic review workflow is delivered.
    category: transversal
    ephemeral: false
    skill: 06_indexes/global_skills/review.skill.md
    writes_to:
      - 05_tools/review/
    database: null
    status: planned
    lifecycle: []
  z_backup:
    # Planned extension; core `arpent backup` is delivered independently.
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
description: Operate an Arpent vault.
---

# Arpent

Use for capture, retrieval, routing, archival, project continuity, import, and todo.

## Load Progressively

1. Read `.agent` and the small `.arpent` marker once.
2. Use the note, todo, or fleeting hot path without loading full documentation.
3. Read `COMPASS.md` only to classify a less common operation.
4. Read one relevant detailed document only for an edge case.

## Modes

- `minimal`: use direct-file operations on canonical files; mode-gated CLI
  commands require vault-mode promotion.
- `full`: use CLI-mediated vault operations.
- If minimal has `auto_full: true`, the first mode-gated command requests
  promotion. Use `arpent mode full --yes` first when the confirmation policy
  requires it.

## Capture

- Full note: `arpent note new <title> --type <type> ... --json`; `howto` is
  current global guidance, `map` navigation.
- Exact-plan note: add `--dry-run --json`, then use `--plan-hash`.
- Full-mode todo: `arpent todo add <content> ... --json`.
- Full-mode fleeting: `arpent note new <text> --type fleeting --json`.

## Minimal Hot Paths

### Note

1. Read `06_indexes/schemas/frontmatter_policy.yaml` and the routing contract.
2. Build complete frontmatter, normalize the title, and compute the route.
3. Reserved resource homes may materialize on first write; never invent another
   missing home.
4. Recheck the destination, create without silently replacing it, read back, and
   verify frontmatter, body, and path.

### Untracked Todo

1. State that coordinated todo is unavailable in minimal mode.
2. If the user still wants capture, create an ordinary inbox note clearly
   labeled as an untracked action; do not claim a todo ID, database row, status
   tracking, or reminder delivery.
3. Suggest promotion to full mode when execution tracking is required.

### Fleeting Append

1. Use the current UTC file `00_inbox/fleeting/dd-mm-yyyy.md`.
2. Preserve the complete existing file and append one `## HH:MM` block.
3. Verify the final block. If safe append cannot be guaranteed, create an
   ordinary inbox note instead of risking previous captures.

Canonical field order: `title, id, created, modified, description, type,
project, area, resource, status, effort_cadence, effort_level, tags,
chosen_location, source, link, author, depth, appreciated, importance, pinned,
expires_at, related, relations, parent, observations, extracted_to`. Use explicit
`null`, `[]`, and `false` defaults. Generate IDs as
`<type>-<UTC YYYYMMDD>-<a..z,aa..>` after scanning all existing IDs.

## Project And Context

- Full: use `arpent project create <name>` and `arpent session end`.
- Minimal: normalize the project name to lowercase ASCII kebab-case, require the
  destination to be absent, and reject `aux`, `clock$`, `con`, `nul`, `prn`,
  `template-project`, `com1..9`, and `lpt1..9`. Create `notes/`, `drafts/`, and
  `attachments/`, then instantiate `01_projects/_template_project/_context.md`
  at `01_projects/<slug>/_context.md`. Replace every placeholder, convert the
  context title to lowercase ASCII snake_case, assign a globally unique note ID
  and current UTC timestamps, and leave the template itself unchanged.
- For a missing area context in minimal, instantiate
  `02_areas/_context.template.md` at the existing area's root with its resolved
  slug, a snake_case title, unique ID, and current UTC timestamps.
- On a direct session close, update `modified` and append the timestamped
  summary, decisions, and next steps without replacing existing body sections.

The confirmation policy is in `06_indexes/cli/operations.yaml`.

## Method

- Markdown is canonical for documents; `todo.db` is authoritative for
  coordinated todo state. All ordinary notes use complete frontmatter.
- Prevent silent loss: never silently replace a destination or destroy user
  content. Explicit edits may use checked atomic replacement. Never guess
  routing, invent schema fields, infer subjective fields, or use delegated
  memory without provider opt-in.
- `project` and `resource` are mutually exclusive; `area` may accompany either.
- Keep source URLs in `link`, titles in lowercase ASCII `snake_case`, and public
  timestamps in `dd-MM-YYYY-HH-mm` UTC format.
- Agent-authored unrequested drafts use `author: agent`, `type: draft`, and the
  standard lifecycle status.
- Resume from `me.md`, then target `_context.md`, then only needed sources.
- Minimal continuity uses `me.md` for approved orientation, `_context.md` for
  work state, and notes for durable content.
- External memory requires provider opt-in; full-mode state remains dormant in
  minimal.
- Status and location are independent. `archived` is a status;
  `archived_at`/`archived_from` describe archive events.

Report concise paths and outcomes. Do not run status, index, triage, search, or a
full reread after an ordinary successful capture.
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
2. List work with `arpent context pending --json-page --limit 100`, optionally
   scoped by path or kind. Follow cursors or use `--all` before claiming the
   pending set is complete.
3. Skip every entry whose L1 status is already `fresh`.
4. Load the source with `arpent context show <path> --level l2 --json-page
   --max-bytes 32768`. Follow every same-hash chunk needed for a complete
   summary. For folders, start from child L0/L1 context.
5. Produce a factual standalone summary of 2-5 sentences and at most 180 words.
6. Store it with `arpent context set <path> --source-hash <hash-from-pending>
   --stdin --provider <agent-or-model-id>`.
7. Verify that the path no longer appears in pending results.

## Output

Fresh L1 entries tied to their exact semantic source hashes.

## Method

- Never summarize a partial source as complete.
- Never combine chunks from different source hashes.
- Never regenerate a fresh L1 whose source hash still matches.
- Never summarize binary files or infer facts absent from the source.
- Follow the Arpent skill's primary/adaptive language settings.
"""

READER_SKILL_STUB = """---
name: reader
status: planned
description: Planned/in-construction reader design. Not an invocable workflow in the current release.
---

# Reader

> **Planned / in construction.** Do not invoke this skill. It becomes eligible
> only after the registry says `status: installed` and an implementation,
> dependencies, configuration, and permitted vault mode are all present.

## Intended Trigger

Future scope: capturing, reading, summarizing, or archiving external content.

## Input

A URL, file, book, podcast, transcript, or reading note.

## Steps

1. Validate an installed implementation and dependencies.
2. Capture source material through that implementation.
3. Store runtime artifacts only under declared paths.
4. Create clean vault notes only when they become reusable knowledge.

## Output

Captured artifacts plus routed notes when appropriate.

## Method

This file is design know-how in `06_indexes/global_skills/`, not evidence of
runtime availability. Its future workspace and database must not be created or
used before installation.
"""

REVIEW_SKILL_STUB = """---
name: review
status: planned
description: Planned/in-construction review design. Not an invocable workflow in the current release.
---

# Review

> **Planned / in construction.** Do not invoke this skill. It becomes eligible
> only after the registry says `status: installed` and an implementation,
> configuration, and permitted vault mode are available.

## Intended Trigger

Future scope: periodic review and synthesis across vault material.

## Input

Projects, areas, notes, indexes, and user priorities.

## Steps

1. Validate an installed implementation.
2. Read relevant indexes and context files.
3. Identify stale, active, and high-value items.
4. Apply the local confirmation policy before modifying files.

## Output

Review summary, suggested updates, and policy-governed state changes.

## Method

This file remains design know-how in `06_indexes/global_skills/`. It does not
make a generic review command or runtime path available. Future mutations would
follow the local operation contract.
"""

BACKUP_SKILL_STUB = """---
name: z_backup
status: planned
description: Planned/in-construction backup extension. Not the delivered core backup command and not currently invocable.
---

# Backup Extension

> **Planned / in construction.** Do not invoke this skill. The core `arpent
> backup`, `backup verify`, and `backup restore` commands are already delivered
> independently. This extension requires registry `status: installed` plus an
> implementation and configuration before it can be used.

## Intended Trigger

Future scope: policy or orchestration around core local snapshots.

## Input

Vault root and backup destination.

## Steps

1. Validate an installed extension implementation.
2. Delegate snapshot creation and verification to the delivered core commands.
3. Restore only to a new directory.

## Output

Backup record and verification summary.

## Method

Keep this design in `06_indexes/global_skills/`. Its presence does not activate
or wrap the delivered core command. Core snapshots default to
`06_indexes/backup/`; they exclude rebuildable/runtime state and do not include
Git history, delegated memory, or external files.
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
- Apply the confirmation policy before changing the tool to `installed`.
"""

TODO_SKILL_STUB = """---
name: arpent-todo
description: Operate the SQLite-backed Arpent todo list when creating, listing, editing, completing, deferring, blocking, or archiving tasks.
---

# Todo

## Trigger

Use when the user asks to capture or manage an actionable task in the Arpent
todo list.
“Remember to do X” is actionable and belongs here, not in an external memory
buffer.

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

- `todo.db` is authoritative for coordinated structured todo state; Markdown
  preserves the durable readable counterpart and must remain consistent.
- Selection values are configurable text keys, not hard-coded enums.
- Project, dependency, and assignee fields are stable soft references.
- Due/do timestamps use `dd-MM-YYYY-HH-mm` UTC; creation timestamps are automatic and immutable.
- Todo records are tool-owned and must be changed through `arpent todo`.
"""

FRONTMATTER_POLICY_STUB = """version: 0.4.1
serialization:
  shape: complete_all_fields
  unused_scalar: null
  unused_list: []
fields:
  title:
    filler: user_or_agent
    required: true
    format: lowercase_ascii_snake_case
  id:
    filler: system
    required: true
    immutable: true
  created:
    filler: system
    required: true
    immutable: true
    format: dd-MM-YYYY-HH-mm
  modified:
    filler: system
    required: true
    format: dd-MM-YYYY-HH-mm
  description:
    filler: user_or_agent
    required: false
    policy: null_when_redundant_with_title_or_body
  type:
    filler: user_or_agent
    required: true
  project:
    filler: user_or_agent
    required: conditional
    policy: mutually_exclusive_with_resource
  area:
    filler: user_or_agent
    required: conditional
    policy: may_accompany_project_or_resource_as_context
  resource:
    filler: user_or_agent
    required: conditional
    policy: mutually_exclusive_with_project
  status:
    filler: user_or_agent
    required: true
    policy: active_for_actionable_stable_for_knowledge_ongoing_for_evolving
  effort_cadence:
    filler: user_or_agent
    required: false
    policy: active_actionables_only_never_infer
  effort_level:
    filler: user_or_agent
    required: false
    policy: active_actionables_only_never_infer
  tags:
    filler: user_or_agent
    required: false
  chosen_location:
    filler: user_or_agent
    required: false
  source:
    filler: user_agent_or_system
    required: true
  link:
    filler: user_or_agent
    required: conditional
  author:
    filler: user_agent_or_system
    required: true
  depth:
    filler: user_or_agent
    required: false
    range: 1-5
    policy: detail_level_null_when_not_meaningful
  appreciated:
    filler: user_only
    required: false
    agent_forbidden: true
  importance:
    filler: user_only
    required: false
    agent_forbidden: true
  pinned:
    filler: user_or_agent
    required: false
    default: false
  expires_at:
    filler: user_or_agent
    required: false
    format: dd-MM-YYYY-HH-mm
  related:
    filler: user_or_agent
    required: false
  relations:
    filler: user_or_agent
    required: false
    item_shape:
      type: relation_type
      target: note_id
  parent:
    filler: user_or_agent
    required: conditional
  observations:
    filler: user_agent_or_system
    required: false
  extracted_to:
    filler: user_agent_or_system
    required: conditional
subjective_user_only:
  - appreciated
  - importance
lifecycle_extensions:
  archive_event:
    applies_when_status: archived
    capture_required: false
    fields:
      archived_at:
        type: timestamp
        format: dd-MM-YYYY-HH-mm
        meaning: archive_event_time
      archived_from:
        type: string
        meaning: pre_archive_vault_path
defaults:
  type: note
  status: inbox
  source: manual
  author: user
  tags: []
  pinned: false
  related: []
  relations: []
  observations: []
  extracted_to: []
rules:
  dates: public timestamps use dd-MM-YYYY-HH-mm in UTC; machine-owned values may retain ISO 8601
  routing: project and resource are mutually exclusive homes; area may accompany either as context
  source_link: manual and derived normally use null; captured requires an external URL; imported requires a URL, path, or external identifier; generated and conversation may use an internal reference
  title: ordinary-note filename equals lowercase ASCII snake_case title; reserved system filenames are exceptions; id remains in frontmatter only
  description: null when redundant with title or body
  depth: integer from 1 to 5 when meaningful
  effort: active actionables may use effort_cadence heavylift|slowburn and effort_level low|medium|high; never infer missing values
  relations: list of mappings with type and target; type must be in enums.relation_type
  howto: one explicitly reviewed current practical answer; project and resource remain null; detailed and superseded material remains in annotated linked notes
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
    - howto
    - artefact
  source:
    - manual
    - generated
    - imported
    - captured
    - conversation
    - derived
  author:
    - user
    - agent
    - imported
"""


def _marker_content(mode: str, *, auto_full: bool = False) -> str:
    if mode not in {"full", "minimal"}:
        raise ValueError("Vault mode must be 'full' or 'minimal'.")
    content = {
        "version": MARKER_VERSION,
        "name": "arpent",
        "mode": mode,
        "auto_full": auto_full if mode == "minimal" else False,
    }
    return json.dumps(content, sort_keys=True) + "\n"


def _ensure_marker(vault: Vault, *, mode: str, auto_full: bool = False) -> None:
    marker = vault.safe_output_path(MARKER)
    if not marker.exists() and not marker.is_symlink():
        vault.atomic_create_text(MARKER, _marker_content(mode, auto_full=auto_full))
        return

    content = vault.marker_data()
    existing_mode = content.get("mode")
    if existing_mode != mode:
        raise ValueError(
            f"Vault is already initialized in {existing_mode} mode; "
            f"refusing an implicit change to {mode} mode."
        )


def set_vault_mode(vault: Vault, mode: str) -> bool:
    """Set an explicit current-format mode without removing any vault state."""
    desired = json.loads(_marker_content(mode, auto_full=False))
    with vault.exclusive_lock("mode"):
        with vault.exclusive_lock("mutations"):
            current = vault.marker_data()
            if current == desired:
                return False
            vault.refuse_foreign_transactions()
            vault.atomic_write_text(MARKER, _marker_content(mode, auto_full=False))
            return True


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


def _seed_vault(vault: Vault) -> None:
    root = vault.root
    for rel in SCAFFOLD:
        vault.safe_ensure_directory(rel)

    _seed(vault, root / "06_indexes/cli/operations.yaml", operations_mod.default_operations_text())
    _seed(vault, root / "06_indexes/schemas/frontmatter_policy.yaml", FRONTMATTER_POLICY_STUB)
    _seed(vault, root / "06_indexes/logs/usage-journal.md", USAGE_JOURNAL_STUB)
    _seed(vault, root / ".agent", AGENT_STUB)
    _seed(vault, root / "COMPASS.md", COMPASS_STUB)
    _seed(vault, root / "06_indexes/docs/ARPENT.md", ARPENT_STUB)
    _seed(vault, root / "06_indexes/docs/mental-model.md", MENTAL_MODEL_STUB)
    _seed(vault, root / "03_resources/agent_wiki/_README.md", AGENT_WIKI_README_STUB)
    _seed(vault, root / "06_indexes/docs/architecture/agent-infrastructure.md", AGENT_INFRA_DOC_STUB)
    _seed(vault, root / "06_indexes/docs/architecture/routing.md", ROUTING_DOC_STUB)
    _seed(vault, root / "06_indexes/docs/architecture/indexing-and-context.md", INDEXING_CONTEXT_DOC_STUB)
    _seed(vault, root / "06_indexes/docs/architecture/tools.md", TOOLS_ARCHITECTURE_DOC_STUB)
    _seed(vault, root / "06_indexes/memory/wiki/SCHEMA.md", WIKI_SCHEMA_STUB)
    _seed(vault, root / "06_indexes/cron.json", CRON_STUB)
    _seed(vault, root / "06_indexes/tools.yaml", TOOLS_STUB)
    _seed(vault, root / "06_indexes/agent_infrastructure_index.yaml", AGENT_INFRA_INDEX_STUB)
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
    _seed(vault, root / "06_indexes/backup/.gitkeep", "")
    _seed(vault, root / "06_indexes/imports/.gitkeep", "")
    _seed(vault, root / "06_indexes/logs/.gitkeep", "")
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
    _seed(
        vault,
        root / "01_projects/_template_project/_context.md",
        PROJECT_CONTEXT_TEMPLATE_STUB,
    )
    _seed(vault, root / "02_areas/_context.template.md", AREA_CONTEXT_TEMPLATE_STUB)
    _seed(vault, root / "03_resources/templates/howto.template.md", HOWTO_TEMPLATE_STUB)
    _seed(vault, root / ".gitignore", GITIGNORE_STUB)


def prepare_full_mode(vault: Vault) -> None:
    """Ensure full-mode infrastructure exists without changing the marker."""
    with vault.exclusive_lock("mutations"):
        vault.refuse_foreign_transactions()
        _seed_vault(vault)
        _initialize_git(vault.root)


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
    if not minimal:
        _initialize_git(root)
    _seed_vault(vault)
    if not marker_exists:
        _ensure_marker(vault, mode=mode)
    return vault


def _seed(vault: Vault, path: Path, content: str) -> None:
    relpath = path.relative_to(vault.root).as_posix()
    safe_path = vault.safe_output_path(relpath)
    if not safe_path.exists():
        vault.atomic_create_text(relpath, content)

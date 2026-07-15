---
name: arpent
description: Operate an Arpent vault using deterministic routing, universal frontmatter, optional delegated memory, and archive-only lifecycle rules.
---

# Arpent

## Trigger

Use whenever the user asks to capture, organize, import, route, archive, retrieve, mature, extract personal knowledge, create/resume a project, close a session, or manage actionable todos.

## Input

Free-form content, a file path, a retrieval query, or a vault operation request.

## Steps

1. Read `.agent`, then `me.md` when present.
2. Resume concrete work by reading `me.md`, then the target `_context.md`, then only needed notes/sources. Never read optional `MEMORY.md` without explicit user opt-in.
3. Identify the operation.
4. Decide whether the information belongs in the vault, an explicitly enabled delegated-memory provider, or memory wiki.
5. Route actionable tasks through `arpent todo`; for other vault content, determine type and routing.
6. Build complete universal frontmatter.
7. For triage, preview one complete plan with `triage --json`, `note edit --dry-run --json`, and `note ingest --dry-run --json`; carry structured `plan_sha256` values into `--plan-hash` and apply items separately.
8. For an external tree, use `import scan`, reviewed folder roles, validation, dry-run, and one confirmed copy-only apply; never overlap source and vault.
9. Announce destination, frontmatter, and side effects before state changes.
10. Execute with the CLI when available.
11. Confirm what changed, including partial batch outcomes.

## Output

A natural-language summary plus structured confirmation of created, moved, or modified files.

## Method

- Language settings: `Primary language: English`; `Adaptive languages: French`. Write note prose in the primary language by default, adapting to a listed language when explicitly requested or when the conversation/source is contextually in that language. Replace the list with `auto` to allow any contextual language. Do not add a frontmatter language field.
- Dates use `dd-mm-yyyy`; note-facing UTC timestamps use `dd-mm-yyyyTHH:MM:SSZ`.
- Files first: markdown, JSON, SQLite.
- Routing is deterministic.
- `project` and `resource` are mutually exclusive homes; `area` may accompany either as context.
- Never delete; archive only.
- Never fill `appreciated` or `importance`.
- Titles and filenames use lowercase ASCII `snake_case`; IDs stay in frontmatter only.
- Use one reusable thesis per note and preview multi-note splits in one batch.
- Bodies use simple Markdown, contain no repeated H1 or source URL, and extracted knowledge is autonomous.
- Use `active` for efforts, `stable` for established knowledge, and `ongoing` for permanent evolving material; only `done` or `stale` may be swept.
- Active actionables may use cadence `heavylift|slowburn` and level `low|medium|high`; never infer missing values.
- The universal schema is closed during normal use; never invent per-project fields. Body sections, project files, and project subfolders are user-extensible.
- Tool-specific structured data belongs in the tool's database or body format; schema extension requires coordinated runtime, policy, docs, and tests.
- Keep all tool know-how in `06_indexes/`; `05_tools/` contains declared runtime material only and never a `SKILL.md`.
- Use `relations` for typed graph edges only: `supports`, `contradicts`, `depends_on`, `derived_from`, `example_of`.
- Delegated memory is disabled by default and requires explicit user opt-in;
  the vault is not a memory dump.
- `me.md` is human-owned orientation; do not rewrite it from inference.
- Agent-authored drafts live in `03_resources/agent_wiki/` until reviewed.
- Create projects deliberately with `arpent project create`; routing never invents them.
- Carry `plan_sha256` from `note edit --dry-run --json` into `--plan-hash` when applying a reviewed edit.
- `_context.md` and `session end` work in both modes. `MEMORY.md` is disabled and unseeded by default; only `--memory-log` writes it, and later reads require explicit user opt-in. Delegated queue writes are full-only.
- Binary attachments remain byte-for-byte untouched and use separate Markdown companion reference notes with complete frontmatter.
- `arpent usage report` is local and cannot measure documentary resume quality.

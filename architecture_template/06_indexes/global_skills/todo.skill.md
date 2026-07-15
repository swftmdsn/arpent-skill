---
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

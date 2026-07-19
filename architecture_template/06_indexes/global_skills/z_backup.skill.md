---
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

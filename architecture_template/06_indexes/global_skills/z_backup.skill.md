---
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

---
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

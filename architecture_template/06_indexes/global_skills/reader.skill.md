---
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

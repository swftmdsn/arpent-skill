---
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
3. Apply the local confirmation policy before modifying files.

## Output

Review summary, suggested updates, and policy-governed state changes.

## Method

This skill remains in `06_indexes/global_skills/`; any runtime output must use
the tool's declared `writes_to` paths. Mutations follow `always`,
`explicit-intent`, or `never` from the local operation contract.

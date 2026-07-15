---
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
2. Use the registered CLI commands for state changes.
3. Write only to paths declared by `writes_to`.

## Output

Describe the user-visible result and structured confirmation.

## Method

- Keep all know-how in `06_indexes/`; never place instructions in `05_tools/`.
- Keep the tool `planned` until its paths, commands, storage, and lifecycle validate.
- Do not add speculative commands or storage before real usage requires them.
- Require user confirmation before changing the tool to `installed`.

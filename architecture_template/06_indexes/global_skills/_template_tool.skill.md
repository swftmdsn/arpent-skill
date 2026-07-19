---
name: replace-with-tool-name
status: planned
description: Replace with the concrete purpose and trigger boundary of this Arpent sub-tool.
---

# Tool Name

> This template starts `planned` and is not invocable. Registry
> `status: installed` plus an implementation and all runtime prerequisites are
> mandatory before an agent may use the resulting skill.

## Intended Trigger

State the future trigger boundary without presenting the planned tool as active.

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
- The current CLI cannot install a tool or change its status. Treat installation
  as Arpent development until an installer is delivered.

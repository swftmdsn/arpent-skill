---
title: template_project_context
id: note-00000000-a
created: REPLACE_WITH_DD_MM_YYYY_TIMESTAMP
modified: REPLACE_WITH_DD_MM_YYYY_TIMESTAMP
description: Living context file for an Arpent project.
type: note
project: _template_project
area: REPLACE_WITH_AREA_SLUG
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

What this project is meant to accomplish and why it exists.

## Current state

Where the project stands now.

## Resume here

The exact next place from which useful work can continue.

## Deliverables / definition of done

What must be true for this project to be complete.

## Key resources

- Add relevant note IDs, paths, and links here.

## Next steps

- Replace this with the next concrete actions.

## Working rhythm and time budget

Record the user-approved cadence or ritual budget for this project.

## Session history

`arpent session end --project <slug>` appends timestamped session updates here.

This body is user-extensible: add or reorder sections freely. Keep the complete
universal frontmatter field set and do not invent per-project fields because CLI
validation rejects unsupported keys. This static file is documentation; it does
not currently control the code-generated `arpent project create` body. During
normal use, edit the created `_context.md` directly. During Arpent development,
update both this template and the runtime builder when changing the generated
design.

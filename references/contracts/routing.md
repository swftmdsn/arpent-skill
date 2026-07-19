# Routing contract

This is the compact executable routing order. The complete rationale and tree
remain in `../routing.md` and `../architecture.md`.

1. An archived `linear` note routes to `04_archives/linear_notes/`.
2. Simultaneous `project` and `resource` route to `00_inbox/unsure/` with a
   reason.
3. Resolve `area` against an exact folder or one unambiguous
   `area__*__<slug>__*` folder. Missing or multiple matches route to unsure.
4. Apply type homes: `fleeting`, `map`, `integration`, and `artefact` use their
   configured override in `operations.yaml`.
5. An agent-authored `draft` without a project routes to
   `03_resources/agent_wiki/drafts/`.
6. With no home fields, `source: captured` routes to `00_inbox/captures/`; other
   notes route to `00_inbox/`.
7. A project note routes under `01_projects/<project>/`, using `drafts/`,
   `meetings/`, `sessions/`, or `notes/` according to type.
8. A resource routes to `03_resources/<resource>/`.
9. An area routes to `02_areas/<resolved-area>/`, with its configured type
   subfolder when present.

Never create a missing home as a side effect of routing. Use `project create`
for deliberate projects. The local `routing_overrides` section may refine
mechanical destinations and must remain inside the vault.

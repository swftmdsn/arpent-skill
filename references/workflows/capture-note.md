# Capture a note

## Trigger

Use for readable knowledge: a thought, idea, meeting, source, journal entry,
reference, observation, draft, concept, integration, map, how-to, or production.
Actions belong in todo in full mode. In minimal, user-provided orientation belongs in
`me.md`, work state in `_context.md`, and durable readable material in notes.

## Decide

1. Use one reusable thesis per note. Preview a split only when independent parts
   remain useful on their own.
2. Select a type from the contract. Default to `note` when no more specific type
   is materially useful.
3. Set `project` or `resource`, never both. `area` may accompany either.
4. Route by the complete order in `../contracts/routing.md`.
5. Use `source: captured` with a URL in `link` for external web material;
   otherwise use the provenance table in
   `../contracts/provenance-and-body.md`.
6. Use `howto` for one explicitly reviewed current practical answer and `map`
   for subject navigation. Follow `maintain-howto.md` for creation or revision.

## Reconcile first

Before every durable note (`fleeting` exempt), derive narrow queries from its
thesis, title, aliases, key terms, and exact `link`. Full uses `arpent search
<query> --json-page --all`; minimal searches live filenames, frontmatter, and
bodies. Treat the maintained search index as the efficient whole-vault overview;
do not rebuild it for each capture. Read plausible candidates completely.

Classify the result as covered/no change, same thesis/enrich or revise, adjacent
thesis/new linked note, or no match/create. Tags or emotions alone are
insufficient. Journals, logs, and meetings remain separate unless they describe
the same event, but may suggest a reusable note.

For a creation request, propose the candidate before editing unless the user
authorized reconciliation; this is meaning clarification. Preserve the ID,
creation date, provenance, user-owned fields, and useful body material.

## Full path

For an explicit bounded capture under `explicit-intent`, or any capture under
`never`, create directly:

```text
arpent note new <title> --type <type> [routing/provenance options] --body <body> --json
```

When the confirmation policy requires a second checkpoint:

```text
arpent note new <same arguments> --dry-run --json
arpent note new <same arguments> --plan-hash <plan_sha256> --json
```

Present the returned frontmatter, destination, warnings, and side effects once.
The plan hash binds semantics and destination but does not prove review. Do not
reconstruct defaults or reread the created note merely to verify it.

## Minimal path

1. Read the complete frontmatter and routing contracts.
2. Build all canonical fields in canonical order.
3. Normalize the title and compute the destination.
4. Scan existing frontmatter before selecting an ID and recheck the destination
   immediately before creating the file.
5. Create without silently replacing an existing destination.
6. Write ordinary Markdown without a repeated H1 or source URL.
7. Read the result back and verify its frontmatter, body, route, and filename.
8. Mention that generated indexes can be rebuilt later; do not maintain them by
   hand.

## Result

Report the created ID, relative path, type, status, routing home, and warnings.
Keep the response short unless the user asks for the metadata.

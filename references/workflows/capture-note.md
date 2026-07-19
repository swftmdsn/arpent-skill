# Capture a note

## Trigger

Use for readable knowledge: a thought, idea, meeting, source, journal entry,
reference, observation, draft, concept, integration, map, or production.
Actions belong in todo; durable facts or traits belong only in explicitly
enabled host memory.

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

## CLI path

For an explicit bounded capture under `explicit-intent`, or any capture under
`never`, create directly:

```text
arpent note new <title> --type <type> [routing/provenance options] --body <body> --json
```

When policy requires review:

```text
arpent note new <same arguments> --dry-run --json
arpent note new <same arguments> --plan-hash <plan_sha256> --json
```

Present the returned frontmatter, destination, warnings, and side effects once.
The plan binds the durable ID, semantic metadata, body hash, and destination;
`apply_generated_fields` identifies timestamps assigned by the transaction and
returned in the final result. Do not reconstruct defaults manually and do not
reread the created note merely to verify it.

## Filesystem path

1. Read the complete frontmatter and routing contracts.
2. Build all canonical fields in canonical order.
3. Normalize the title and compute the destination.
4. Scan existing frontmatter before selecting an ID and recheck the destination
   immediately before creating the file.
5. Create without replacing an existing path.
6. Write ordinary Markdown without a repeated H1 or source URL.
7. Read the result back and verify its frontmatter, body, route, and filename.
8. Mention that generated indexes can be rebuilt later; do not maintain them by
   hand.

## Result

Report the created ID, relative path, type, status, routing home, and warnings.
Keep the response short unless the user asks for the metadata.

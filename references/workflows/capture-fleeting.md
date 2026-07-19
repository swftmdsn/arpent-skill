# Capture a fleeting thought

## Trigger

Use for short-lived, append-only material that does not yet warrant a structured
note. Durable or reusable material should become an ordinary typed note.

## Contract

- The UTC daily file is `00_inbox/fleeting/dd-mm-yyyy.md`.
- Each entry has a `## HH:MM` heading and body.
- The daily stream has no per-entry frontmatter or per-entry ID.
- Fleeting entries do not appear in structured note status, search-by-ID, or
  routing operations.

## CLI path

```text
arpent note new <text> --type fleeting --json
```

The command uses the title as body when no body is supplied.

## Filesystem path

Read the current UTC day file when it exists, preserve every existing entry,
append one `## HH:MM` block, then verify the final entry. When the available
file tool cannot safely preserve an existing append stream, create an ordinary
inbox note instead of risking prior captures.

## Result

Report the daily relative path and captured time. Do not invent structured
frontmatter for an individual fleeting entry.

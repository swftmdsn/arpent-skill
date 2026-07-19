# Capture a todo

## Trigger

Use when the information requires execution, tracking, completion, deferral, or
blocking. A todo is structured state, not an ordinary knowledge note.

## CLI path

For direct capture:

```text
arpent todo add <content> [--priority ...] [--due dd-mm-yyyy] [--do dd-mm-yyyy] --json
```

When confirmation policy requires review:

```text
arpent todo add <same arguments> --dry-run --json
arpent todo add <same arguments> --plan-hash <plan_sha256> --json
```

Do not infer optional priority, dates, duration, cadence, project, dependency,
or assignee fields. Omit values the user did not provide.
The plan binds the todo ID, normalized values, Markdown destination, and side
effects. `apply_generated_fields` lists timestamps assigned during commit.

## Filesystem path

> Attention: this feature is not supported in filesystem mode because it needs
> coordinated database or multi-file state. The current files remain readable
> and unchanged; use the CLI adapter for that operation.

If the user primarily needs easy capture while the CLI is absent, capture the
request as a normal inbox note and label it honestly as untracked content. Do
not claim it is present in the todo system.

## Result

Report the todo ID, lifecycle path, effective status, and supplied dates. Do not
run `todo list` after creation solely for verification.

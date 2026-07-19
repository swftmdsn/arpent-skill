# Maintain a how-to

## Trigger

Use when the user wants one current practical answer to a specific recurring
problem. A `howto` is global, permanent, and revised in place. Use a `map`
instead when the primary purpose is to navigate a broad subject.

## Decide

1. State one actionable problem in the title; never name the file `how-to.md`.
2. Keep only currently applicable guidance in the how-to. Detailed reasoning,
   research, alternatives, case studies, and superseded conclusions remain in
   annotated linked notes.
3. Do not infer validity from `modified` or elapsed time. Create or change the
   current conclusion only after the user explicitly requests or confirms the
   review.
4. Keep the same note ID when revising the answer. Before removing useful
   material, verify that it already exists in a linked note or preserve it in
   one.
5. Let a subject MOC link to its how-tos, concepts, evidence, and history. The
   how-to links back to that MOC without duplicating its navigation role.

## Body

Use `03_resources/templates/howto.template.md` as the body skeleton. It contains:

- `Current conclusion`
- `Why`
- `How`
- `Examples`
- `Applicability and limits`
- `Linked notes`

Record `Last explicit review` in the body using the public UTC timestamp format.
Do not add a changelog, raw research, or obsolete recommendations to the current
guide.

## Create

```text
arpent note new <specific-problem-title> --type howto --source derived --body <body> --json
```

The type routes globally to `03_resources/how-tos/` and defaults to
`status: ongoing`; leave both `project` and `resource` null. An `area` may remain
as contextual metadata.

## Revise

Use `arpent note edit <id> --body <body> --json` in full mode, with a reviewed
plan when the local confirmation policy requires one. In minimal mode, perform
one checked atomic replacement and verify that the ID and routing remain
unchanged.

## Result

Report the stable ID, global path, explicit review timestamp, conclusion changed,
and linked notes added or preserved.

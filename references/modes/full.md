# Full mode

Full mode uses CLI-mediated vault operations. The `.arpent` marker, not mere CLI
availability, selects this mode. Documentary reads such as `me.md` and
`_context.md` remain direct file reads.

## Rules

- Use workflow-provided syntax; consult command help only after a syntax error or
  when using an option not covered by the workflow.
- Let mutating commands read the vault confirmation policy; do not open the full
  operation registry before an ordinary single capture.
- Use `--dry-run --json` only when confirmation policy requires a preview or the
  user explicitly asks for one.
- Carry the returned `plan_sha256` into an exact-plan apply.
- Prefer versioned JSON results and trust their post-transaction path/hash
  fields instead of rereading full content.
- Do not run status, triage, index, search, or full note reads as a ritual after
  capture.
- Keep command output bounded and follow cursors when completeness is required.

The CLI owns locking, confinement, collision checks, canonical serialization,
database coordination, transaction recovery, and generated indexes.

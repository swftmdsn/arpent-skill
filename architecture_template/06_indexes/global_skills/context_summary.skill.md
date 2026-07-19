---
name: arpent-context-summary
description: Generate compact L1 summaries only when explicitly requested and only for missing or stale semantic hashes.
---

# Context Summary

## Trigger

Use only when the user explicitly asks to build or refresh intelligent context
summaries. `arpent index` never triggers this skill automatically.

## Input

- An initialized and indexed Arpent vault.
- Entries returned by `arpent context pending`.

## Steps

1. Run `arpent index` to refresh deterministic inventory and hashes.
2. List work with `arpent context pending --json-page --limit 100`, optionally
   scoped by path or kind. Follow cursors or use `--all` before claiming the
   pending set is complete.
3. Skip every entry whose L1 status is already `fresh`.
4. Load the source with `arpent context show <path> --level l2 --json-page
   --max-bytes 32768`. Follow every same-hash chunk needed for a complete
   summary. For folders, start from child L0/L1 context.
5. Produce a factual standalone summary of 2-5 sentences and at most 180 words.
6. Store it with `arpent context set <path> --source-hash <hash-from-pending>
   --stdin --provider <agent-or-model-id>`.
7. Verify that the path no longer appears in pending results.

## Output

Fresh L1 entries tied to their exact semantic source hashes.

## Method

- Never summarize a partial source as complete.
- Never combine chunks from different source hashes.
- Never regenerate a fresh L1 whose source hash still matches.
- Never summarize binary files or infer facts absent from the source.
- Follow the Arpent skill's primary/adaptive language settings.

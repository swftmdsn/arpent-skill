# Arpent Constitution

This vault is an Arpent vault: a filesystem-native local continuity and
administration layer.

- Files over apps. Markdown is canonical for documents; `todo.db` is
  authoritative for coordinated todo state.
- Delegated memory is optional and disabled by default; the vault is a clean knowledge base, not a memory dump.
- Routing is deterministic. Prevent silent replacement or destruction; explicit
  checked atomic edits are allowed, and lifecycle retention uses archives.
- Confirmation follows the local operation policy; the user owns the vault.

See 06_indexes/global_skills/ for the operating skill.

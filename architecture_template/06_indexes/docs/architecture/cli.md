# CLI Architecture

The CLI has explicit, layered authorities.

The installed package's `scripts/operations.yaml` is authoritative for routing
enums, default routes, and the operation inventory. This vault-local
`06_indexes/cli/operations.yaml` may refine route maps, but cannot redefine the
packaged enums. Refinements belong only under the explicit
`routing_overrides` mapping; the mirrored `routing` block never overrides newer
packaged defaults. The installed argparse tree is authoritative for current
command syntax and `arpent <command> --help` is its rendered reference.

Generated parsers or MCP definitions are only a planned/in-construction design,
not current invocable behavior. Any future implementation must not treat the
vault-local routing overlay as a command schema.

`arpent index` is deterministic and never invokes AI. The `arpent context`
commands expose the optional L0/L1/L2 summary cache documented in
`indexing-and-context.md`.

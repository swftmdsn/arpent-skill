# Tool Control Plane

Arpent separates tool know-how from tool runtime material.

This is an explanatory architecture document. `06_indexes/tools.yaml` declares
registry state; the installed CLI determines which commands are actually
available. Future tool design is planned/in construction and is not invocable
behavior.

## Non-negotiable boundary

`06_indexes/` is the control plane. It contains everything required to define,
create, validate, operate, and evolve a sub-tool:

- `06_indexes/tools.yaml` - canonical registry and declared tool status
- `06_indexes/global_skills/<tool>.skill.md` - agent operating method
- `06_indexes/cli/` - deterministic command contracts mirrored into the vault
- `06_indexes/schemas/` - schemas and migrations
- `06_indexes/docs/` - architecture and operational documentation
- `06_indexes/databases/` - centralized structured runtime state

`05_tools/` is a runtime surface only. It may contain artifacts,
captures, caches, and other outputs explicitly declared by `writes_to`. It must
never contain a `SKILL.md`, schema, migration, tool template, command contract,
or instructions for creating and maintaining tools.

The executable Arpent CLI is installed outside the vault. The vault owns its
reviewable operation contract and any future local extension declarations in
`06_indexes/cli/`, not a second copy of the executable package.

An area-bound tool normally writes user content to `02_areas/<area>/` and may
need no folder in `05_tools/`. A transversal tool may use
`05_tools/<tool>/`, but that folder still contains runtime material only.

## Minimum tool definition

Every tool starts as `planned`. Its registry entry must define, before it can be
installed:

```yaml
tools:
  example:
    category: transversal
    status: planned
    skill: 06_indexes/global_skills/example.skill.md
    writes_to:
      - 05_tools/example
    database: null
    ephemeral: false
    lifecycle: []
```

The mapping key is the stable tool ID. `database` may be null. `lifecycle` may
be empty, but an ephemeral tool must declare the rules the sweep will apply.
No future command, field, database, or directory is created speculatively.

`planned` and `installed` are registry states only. They do not by themselves
prove implementation, that the current vault mode permits use, configuration
enablement, dependencies, or runtime availability. The current CLI can inspect
this registry but does not provide install, uninstall, enable, or disable
commands.

## Future Installation Design

The current CLI has no install, uninstall, enable, disable, or registry-status
mutation command. The following is a planned/in-construction design, not a
procedure an agent may execute today:

1. A real usage need or phase retro selects one tool.
2. The agent proposes its smallest useful command set and output boundary.
3. A future development change creates the skill from
   `06_indexes/global_skills/_template_tool.skill.md` and registers the tool as
   `planned`.
4. The agent adds only the required CLI contract, schema, and migrations in
   `06_indexes/`.
5. A future installer validates the skill, commands, dependencies, storage,
   non-overlapping `writes_to` paths, and lifecycle dry-run.
6. Only that delivered installation step may change `status` to `installed` and
   create missing runtime directories in `05_tools/` or an area.

`status: installed` is mandatory but not sufficient for tool dispatch. The
implementation, permitted mode, dependencies, and configuration must also be
available. The current sweep executes
only ephemeral tools with `status: installed`; cron jobs are enabled separately
in `cron.json` and are not dispatched from this registry.

## Current Maintenance Boundary

The agent may maintain runtime content only for a tool with `status: installed`
and an actually available implementation. Reader, review, and z_backup are
planned/in construction and are not invocable. Core `arpent backup` remains
delivered independently of z_backup. Control-plane changes are Arpent
development work; definitions are never copied into runtime folders.

# Tool Control Plane

Arpent separates tool know-how from tool runtime material.

## Non-negotiable boundary

`06_indexes/` is the control plane. It contains everything required to define,
create, validate, operate, and evolve a sub-tool:

- `06_indexes/tools.yaml` - canonical registry and declared tool status
- `06_indexes/global_skills/<tool>.skill.md` - agent operating method
- `06_indexes/cli/` - deterministic command contracts mirrored into the vault
- `06_indexes/schemas/` - schemas and migrations
- `06_indexes/docs/` - architecture and operational documentation
- `06_indexes/databases/` - centralized structured runtime state

`05_tools/` is a runtime surface only. It may contain artifacts, queues,
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

## Progressive creation

1. A real usage need or phase retro selects one tool.
2. The agent proposes its smallest useful command set and output boundary.
3. Under the local confirmation policy, the agent creates the skill from
   `06_indexes/global_skills/_template_tool.skill.md` and registers the tool as
   `planned`.
4. The agent adds only the required CLI contract, schema, and migrations in
   `06_indexes/`.
5. Installation validates the skill, commands, dependencies, storage,
   non-overlapping `writes_to` paths, and lifecycle dry-run.
6. The policy-governed installation step may change `status` to `installed` and
   create missing runtime directories in `05_tools/` or an area.

Installation is one prerequisite for tool dispatch. The current sweep executes
only ephemeral tools with `status: installed`; cron jobs are enabled separately
in `cron.json` and are not dispatched from this registry.

## Maintenance

The agent may maintain runtime content according to the skill declared by a tool
with `status: installed`. It may
propose changes to tool know-how, commands, storage, schemas, or lifecycle, but
those control-plane changes follow the local confirmation policy. Database evolution
uses migrations; definitions are never copied into runtime folders.

# Agent Infrastructure

Arpent separates portable agent definitions, executable tools, discovery
indexes, and harness-specific configuration.

## Layers

| Layer | Location | Responsibility |
|---|---|---|
| Portable definitions | `03_resources/agent_infrastructure/` | Roles, skills, workflows, prompts, templates, styles, and capability manifests |
| Arpent tool control plane | `06_indexes/` | Skills, CLI contracts, schemas, migrations, registry, documentation, and databases |
| Tool runtime material | `05_tools/` or the relevant area | Declared artifacts, captures, caches, outputs, and user content |
| Discovery registry | `06_indexes/agent_infrastructure_index.yaml` | IDs, paths, and relations between portable definitions |
| Vault tool registry | `06_indexes/tools.yaml` | Declared Arpent tools and their `planned` or `installed` status |
| Harness configuration | Outside the vault or generated from portable definitions | OpenCode, Claude Code, or other harness-specific activation |
| Secrets | Environment, keychain, or secret manager | Credentials and private tokens; never committed to the vault |

## Definitions

### Role-based agent

`agent_roles/<id>/AGENT.md` contains a concise role prompt, instructions,
boundaries, and references to allowed skills, workflows, and capabilities. It
defines a role; it is not a running process.

### Agent skill

`agent_skills/<id>/SKILL.md` is a reusable method packaged with enough detail,
scripts, and attachments for an agent to perform a type of task reliably.

### Simple prompt

`agent_prompts/` contains small reusable instructions that do not need their
own package or lifecycle.

### Workflow

`agent_workflows/<id>/WORKFLOW.md` defines a predetermined sequence. A workflow
may invoke roles, skills, prompts, capabilities, and Arpent sub-tools. Its
standard sections are `Trigger`, `Input`, `Steps`, `Output`, and `Method`.

### Capability

`capabilities/<id>/CAPABILITY.yaml` declares a means of action an agent may use.
Supported kinds are `cli`, `mcp`, `api`, and `plugin`. A declaration may contain
a public endpoint, command name, or harness configuration reference, but never
a credential value.

A declaration makes a capability discoverable, not available. Runtime
availability additionally requires an implementation, a vault mode that permits
use, satisfied dependencies, and host configuration or enablement where
applicable. Unavailable declarations remain retained and dormant.

Capabilities and the index are complementary:

- The capability folder is the canonical, portable definition.
- `agent_infrastructure_index.yaml` makes definitions discoverable and records
  their relationships.
- A role references capability IDs rather than embedding tool configuration.
- A workflow references the roles, skills, prompts, and capability IDs it uses.

### System instructions

Vault-wide operating instructions live in `.agent`,
`06_indexes/global_skills/arpent.skill.md`, and `06_indexes/docs/ARPENT.md`.
`me.md` is human-owned orientation, while
`COMPASS.md` selects only less common operations. Automatic injection remains
the responsibility of the active harness; Arpent provides the portable source
of truth.

## Decision Rule

- Defines or operates an Arpent sub-tool: `06_indexes/`.
- Stores declared transversal runtime material: `05_tools/`.
- Defines portable agent behavior or access: `03_resources/agent_infrastructure/`.
- Generates discovery indexes: generated index files under `06_indexes/`.
- Contains a secret or harness-specific runtime setting: outside the vault.

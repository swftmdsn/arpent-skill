# Agent Infrastructure

Portable agent definitions live here. Their discovery registry is
`06_indexes/agent_infrastructure_index.yaml`; the index is not their canonical
home.

| Directory | Purpose |
|---|---|
| `agent_roles/` | Role, instructions, boundaries, and permitted capabilities for a role-based agent |
| `agent_skills/` | Reusable methods for accomplishing a task |
| `agent_workflows/` | Predetermined sequences that orchestrate roles, skills, prompts, and capabilities |
| `agent_prompts/` | Small reusable instructions |
| `agent_templates/` | Reusable output structures |
| `agent_style/` | Shared writing and interaction rules |
| `capabilities/` | Portable declarations for CLI, MCP, API, and harness-plugin access |

Capabilities describe means of action; they do not contain implementations or
secrets. Store only references such as `credential_ref: env:OPENAI_API_KEY`.
Actual credentials belong in environment variables, a keychain, or a secret
manager outside Git.

This portable infrastructure is distinct from Arpent tool know-how in
`06_indexes/` and from runtime material in `05_tools/`.

Use the test:

- Defines or operates an Arpent sub-tool: `06_indexes/`
- Stores declared transversal runtime material: `05_tools/`
- Defines portable agent behavior or access: this directory

See `06_indexes/docs/architecture/agent-infrastructure.md` for the complete
hierarchy.

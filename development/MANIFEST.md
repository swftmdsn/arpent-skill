# Skill refactor manifest

Working document for the token-oriented skill refactor. This file is not part
of the runtime skill surface.

## Loading architecture

| Previous surface | New operational home | Complete retained source |
|---|---|---|
| Root reading order and trigger | `SKILL.md` | Root skill plus this mapping |
| Operation discrimination | `references/workflows/COMPASS.md` | `scripts/COMPASS.md` |
| Note capture steps | `references/workflows/capture-note.md` | `references/frontmatter.md`, `references/routing.md`, `references/architecture.md` |
| Todo capture steps | `references/workflows/capture-todo.md` | `references/tools-and-cron.md`, installed todo skill |
| Fleeting capture steps | `references/workflows/capture-fleeting.md` | `references/ingestion-and-degraded-mode.md`, `references/routing.md` |
| Universal schema hot rules | `references/contracts/frontmatter.md` | `references/frontmatter.md` |
| Routing order | `references/contracts/routing.md` | `references/routing.md`, `references/architecture.md`, `scripts/routing.py` |
| Provenance and body rules | `references/contracts/provenance-and-body.md` | `references/frontmatter.md` |
| CLI behavior | `references/adapters/cli.md` | `references/tools-and-cron.md`, CLI implementation |
| Direct-file behavior | `references/adapters/filesystem.md` | `references/ingestion-and-degraded-mode.md` |
| Capability differences | `references/assurance/capability-matrix.md` | Implementation and complete references |
| Full-method navigation | `references/appendices/complete-reference-index.md` | All retained long-form references |

## Former root method coverage

| Rule group | Current canonical location |
|---|---|
| Files first | `SKILL.md`, filesystem adapter, architecture |
| Deterministic routing and unsure | Routing contract and `scripts/routing.py` |
| Archive instead of delete | `SKILL.md`, lifecycle reference |
| Confirmation | `scripts/operations.yaml`, workflow COMPASS |
| Subjective fields | Frontmatter contract and validator |
| Stable title/path and metadata identity | Frontmatter contract and complete frontmatter reference |
| Source/link coherence | Provenance contract and warnings implementation |
| Memory separation | Root skill and memory-layers reference |
| Tool homes | Root skill, architecture, tools reference |
| Ephemeral lifecycle | Lifecycle and tools references |
| Linear extraction/dissolution | Lifecycle reference and note transactions |
| Maps of Content | Routing and lifecycle references |
| Project/area continuity | Workflow COMPASS and lifecycle reference |
| Binary companions | Root skill and ingestion reference |
| Usage evidence | README and tools reference |
| Agent-authored drafts | Local/root skill, architecture, standard schema |
| Density/health | README and health implementation |
| Progressive context | Indexing-and-context reference |
| Portable agent infrastructure | Architecture reference |

## Contract corrections made during refactor

- Removed `agent_wiki_status`; agent wiki uses `type: draft`, ordinary `status`,
  `author: agent`, and normal routing fields.
- Corrected the filesystem fleeting example to `dd-mm-yyyy.md`.
- Corrected the linear reading example to `source: imported` with an external
  ISBN identifier.
- Chose the generated compact `.agent`, local Arpent skill, COMPASS, operation
  contract, and constitution as the canonical template versions.

## No-loss rule

Long-form references are retained until this manifest, template-equality tests,
frontmatter-example tests, and behavioral tests establish that every rule has a
canonical destination. Compact cards may paraphrase but never replace the
complete references during system development.

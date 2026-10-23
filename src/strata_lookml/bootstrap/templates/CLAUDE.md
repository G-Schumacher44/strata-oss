# {{PROJECT_NAME}} — Claude Agent Rules

See `AGENTS.md` for the full Conductor rules. This file adds Claude-specific guidance.

## Authority Order

1. `AGENTS.md`
2. `conductor/index.md`
3. Active `conductor/slice-*.md`
4. `conductor/handoff-log.md` (latest block when resuming)

## Turn 1 Rule

```
git status -sb && git log -n 5 --oneline && cat conductor/handoff-log.md
```

## Key Constraints

- Deterministic layers must never call any LLM or external API
- MCP server is stdio-only; no HTTP transport, no cloud dependency
- Read-only enforcement is non-negotiable

## Mode Selection

Start in the smallest safe mode:

| Mode | Use for |
|------|---------|
| Patch | Bug fix, one-file change, doc update |
| Slice | Planned work inside an existing slice spec |
| Full Conductor | Cross-layer change, new phase, architecture decision |
| Audit | Review only — no implementation |

## Build

```bash
python -m pytest
```

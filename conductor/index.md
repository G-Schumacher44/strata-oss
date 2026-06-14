# Conductor Index — my-looker-project

Date: 2026-06-07
Status: active
Type: conductor-index

Machine-first routing entry for Conductor-aware agents.

## Control Hierarchy

- [Root Charter](../AGENTS.md)
- [Conductor Modes](./CONDUCTOR_MODES.md)
- [Conductor Overview](./README.md)

## Execution Mode

Default to **Slice Mode** for planned Conductor work. Use **Patch Mode** for
narrow fixes. Use **Full Conductor Mode** for cross-layer changes or architecture
decisions. Use **Audit Mode** for review only.

Resolve mode from `conductor/CONDUCTOR_MODES.md` before widening context.

Avoid reading `conductor/archive/**` and `handoff-archive.md` unless the
active slice requires history.

## Active Strategy

### Track A — Foundation (active)

First slices go here. Add master-plan docs as phases span multiple slices.

## Active Slice

Active slice: conductor/slice-03-decouple-conductor-ci-into-soft-gated-pr-comment.md

## Phase Status

| Phase | Name | Status |
|---|---|---|
| 0 | Project setup + governance | ✅ bootstrapped |
| CI Governance | Soft-Gate PR Comments | stable |
| Governance Cleanup | Refactor Brick to Phase | stable |
| Governance Tooling | Conductor Management Skill | stable |

## Reading Order

1. `AGENTS.md` — root charter + conductor loop
2. `conductor/CONDUCTOR_MODES.md` — choose mode before widening context
3. `conductor/index.md` — this file
4. `conductor/README.md` — directory conventions
5. Active `conductor/slice-*.md` — implementation contract
6. `conductor/handoff-log.md` — latest block when resuming

## Reference

- [Handoff Log](./handoff-log.md)
- [Conductor README](./README.md)

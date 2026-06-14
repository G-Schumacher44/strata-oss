# Strata — Governance Framework

This document defines the rules every agent operating in this repo must follow.
It is the expanded reference behind `AGENTS.md`. When the two conflict, `AGENTS.md`
wins — but `AGENTS.md` should never contradict this document.

---

## The Conductor Loop

Every session runs the same cycle:

1. Agent reads the active slice spec
2. Agent executes bounded work
3. Agent writes a handoff (Exact Next Steps, gates checked)
4. Operator reviews, approves or redirects, starts the next session

The handoff's **Exact Next Steps** field is the agent's recommendation for the next
unit of work. The operator's role is approval, not generation. Agents hand off to
each other through `conductor/handoff-log.md`.

---

## Conductor Modes

Choose mode before widening context. Use the smallest mode that covers the work.

| Mode | When to use | Context loaded |
|---|---|---|
| **Patch** | Bug fix, one-file change, doc update | AGENTS.md + affected file + handoff-log latest block |
| **Slice** | Bounded feature work, one slice spec | AGENTS.md + intent.md + index.md + active slice + handoff-log |
| **Full Conductor** | Cross-cutting change, new layer, API boundary change | Everything in reading order |
| **Audit** | Review only, no implementation | Read-only pass; no commits |

---

## Authority Order

When planning or implementing work, use sources in this order:

1. `AGENTS.md` (root)
2. `intent.md`
3. `conductor/index.md`
4. active `conductor/slice-*.md`
5. `conductor/handoff-log.md` (latest block when resuming)
6. subdirectory `AGENTS.md` for the layer being modified
7. `GOVERNANCE.md` (this file)
8. code reality in the repo

---

## Layer Responsibilities

These are hard boundaries. Never cross them.

| Layer | Location | Rule |
|---|---|---|
| **L0 — IR** | `src/strata/ir/` | Pure Python. Zero tokens. No LLM. No network. No external calls of any kind. |
| **L1 — Usage enrichment** | `src/strata/l1/` (Phase 2) | Deterministic. Read-only Looker API/MCP only. No LLM. |
| **L2 — Synthesis** | `src/strata/synthesis/` (Phase 3) | The only LLM layer. Cheapest model. One explore = one slice. Evidence required for every verdict. |
| **L3 — Governance** | `conductor/`, `strata validate` | Conductor wraps L2. No verdict ships without its evidence trail. |
| **MCP server** | `src/strata/mcp/` | Exposes L0–L1 as read-only tools. stdio only. No HTTP. Never calls write operations. |
| **Vendor** | `src/vendor/` | Frozen. Do not modify. Cherry-pick from upstream only. |

---

## Execution Rules

- **Read Code First.** Read the existing code before proposing structural changes.
  Discover current behavior before writing new policy.
- **Spec Before Build.** Update or create the governing Conductor artifact before
  implementation for any slice, layer, or API boundary change.
- **Reuse The Real Seam.** Extend existing patterns (IR graph, MCP tools, validate gate)
  instead of inventing a parallel control system.
- **Write To Current Reality.** Formalize the working baseline where it already exists;
  only redesign when the current seam is provably broken.
- **Mode Discipline.** Choose mode before widening context. See Conductor Modes above.
- **No Implicit Context.** Do not assume the next agent has your session state unless
  it is written down in the handoff.

---

## Design Rules

- **Read-only, always.** Strata never writes to prod, the LookML repo, or any live
  instance. This is enforced by governance, not by convention.
- **Deterministic core.** L0 and L1 must be reproducible given the same inputs.
  No randomness, no model calls, no non-deterministic external state.
- **Generic engine / private config separation.** Zero org fingerprints in the public
  engine. No internal table names, schema, proprietary SQL, or instance config.
- **Correctness over speed.** On an ~80-explore instance with dense extends chains,
  a wrong verdict is a named incident. Governance matters more here, not less.
- **Mine, don't marry.** Read prior art for patterns; write our own. No runtime
  dependency on immature tooling.
- **Fail loudly on broken extends chains.** Never emit an orphan verdict on a node
  whose extends/refinement chain has not fully resolved. Surface the resolution failure
  explicitly instead of silently propagating a wrong answer.

---

## Testing Rules

- **Hit the seams.** Focus on integration boundaries: parser↔builder, builder↔resolver,
  resolver↔orphan detector, IR↔MCP tools.
- **Fixtures before implementation.** Write synthetic LookML fixtures before writing
  the code that consumes them — especially for resolver.py.
- **The hard problem first.** The three-level extends chain test must pass before any
  orphan-detection verdict is trusted. This is the correctness oracle for the whole system.
- **Bug-driven tests.** Write a regression test for every bug after it occurs.
- **Test colocation.** Keep `test_*.py` files in `tests/` mirroring `src/strata/` structure.
- **No mocking the graph.** IR graph tests must use real parsed fixtures, not mocked
  NetworkX objects. The mock/real divergence is exactly the class of bug Strata is
  designed to catch in LookML repos.
- **CI enforcement.** `.venv/bin/pytest` must pass before any handoff is written.

---

## Build Rules

- **Venv always.** Use `.venv/bin/python` and `.venv/bin/pytest` — never the system Python.
- **Targeted first.** Run the smallest sufficient test set for the seam changed before
  widening to the full suite.
- **Validate after every slice.** `python3 strata validate` must pass (10+ checks,
  0 failures) before writing a handoff.
- **Gate is the gate.** Unchecked acceptance criteria in the active slice spec = handoff
  blocked. Do not write "STABLE" until all gates are `[x]`.

```bash
# Standard build sequence
.venv/bin/pytest
python3 strata validate
```

---

## Handoff Rules

- **Turn 1 Rule.** Before any plan:
  ```
  git status -sb && git log -n 5 --oneline && cat conductor/handoff-log.md
  ```
- **Commit Anchor.** Every `handoff-log.md` entry MUST include `Commit: [7-char-hash]`.
- **Atomic.** Every implementation commit MUST include the corresponding handoff-log update.
- **Reality Check.** If local HEAD does not match the latest handoff hash, reconcile
  the documentation before writing code.
- **Thin Active Handoff.** `handoff-log.md` holds only the current block. Move older
  entries to `handoff-archive.md`.
- **Exact Next Steps required.**
- **Blockers must be explicit.** If work is incomplete, state exactly what is blocked,
  what was verified, and what remains.
- **Mode Handoff.** Record Conductor mode, context loaded/skipped, validation result,
  and next safe action.

---

## Git Discipline

- `main` — stable releases only.
- `dev` — stable working baseline; slice work lands here.
- Feature branches for longer experimental tracks; merge back to `dev` via PR when stable.
- Sliced, scoped, focused commits.
- Never commit vendored lkml changes without an explicit upstream cherry-pick reference
  in the commit message.

---

## Output Expectations

When producing plans or code, call out which layer the change belongs to:

- **L0 (IR)** — parser, builder, resolver, store
- **L1 (Usage)** — System Activity enrichment, PDT cost (Phase 2+)
- **L2 (Synthesis)** — LLM slice execution, verdicts (Phase 3+)
- **L3 (Governance)** — Conductor, validate gate
- **MCP** — server, tools
- **Vendor** — lkml source

When working with Conductor artifacts, also state:

- **Conductor** — slice specs, index, tracks
- **Handoff** — log, archive

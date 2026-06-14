# L0 — Deterministic IR Layer

**Layer:** L0 (the foundation)
**Full governance:** `GOVERNANCE.md`
**Authority:** `AGENTS.md` (root) → `intent.md` → `conductor/index.md` → active slice → this file

---

## What this layer is

The deterministic intermediate representation of an entire LookML repo.
Every downstream layer (L1, L2, MCP tools) reasons over this — never raw files.

Parse once. Cache. Serve forever.

## Hard constraints (non-negotiable)

- **Zero tokens.** No LLM calls. No model API calls. Not even a local model.
- **No network.** No HTTP, no external API, no subprocess that touches the network.
- **No side effects.** This layer reads files and builds a graph. It does not write
  to the LookML repo, to prod, or to any live instance.
- **Deterministic.** Given the same repo state, the output must be identical every run.
- **In-house parser only.** `lkml` may be read as prior art from a temporary clone, but
  it is not a runtime dependency. Never vendor `lkml`, never `import lkml` from pip,
  and never copy its source into this repo.

## Files in this layer

| File | Responsibility |
|---|---|
| `types.py` | `IRNode`, `IREdge`, `IRGraph` dataclasses — the contract every other layer depends on |
| `parser.py` | Parse LookML files → raw dict trees with Strata's in-house parser |
| `builder.py` | Build NetworkX DiGraph from parsed trees (nodes + edges per `intent.md §3`) |
| `resolver.py` | **The hard problem.** Full extends + refinement chain resolution before any orphan signal |
| `store.py` | Serialize/deserialize `IRGraph` ↔ SQLite cache (stdlib sqlite3 only) |

## The hard problem — resolver.py

Do not emit a structural-orphan verdict on any node until its extends/refinement chain
is fully resolved. A node that looks dead may be extended three files away.

Resolution order: base → extended → refined (later wins on scalars; field lists merge
by name). Cycles must be detected and reported — never crash, never silently propagate.

**The correctness oracle:** `tests/test_ir_resolver.py::test_three_level_chain` must
pass before any orphan verdict from this layer is trusted.

## Testing rules for this layer

- Write `tests/fixtures/` before writing `resolver.py`. The fixture IS the spec.
- Tests must use real parsed fixtures — no mocked NetworkX graphs.
- Cover: simple parse, extends chain (2-level, 3-level), refinement merge, cycle detection,
  orphan detection, store round-trip.

## What does NOT belong here

- Usage data (query counts, last-queried) — that is L1
- Verdicts (keep / deprecate / kill) — that is L2
- MCP tool wiring — that is `src/strata/mcp/`
- Any call to an LLM — that is L2 only, never here

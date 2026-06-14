# L2 — Synthesis and Verdict Layer

**Layer:** L2 (synthesis — the only layer that may call an LLM)
**Sits between:** L1 enriched IR → L2 (this) → output artifacts / agent recommendations

---

## What this layer is

Takes an enriched `IRGraph` and produces structured verdicts and evidence slices for each
explore. Deterministic verdicts require no LLM. Narrative synthesis (L2 proper) may use
one — but that path is agent-driven, not automated.

## Hard constraints

- **L2 is the only layer that may call an LLM.** L0 and L1 are zero-token by contract.
- **Deterministic verdicts first.** `deterministic_verdict()` must run before any LLM call.
  If the deterministic signal is conclusive, skip the LLM entirely.
- **Evidence-backed verdicts only.** Every verdict must carry `evidence_ids` — references
  to specific IR nodes or L1 records. A verdict without evidence is invalid.
- **No side effects.** This layer reads graph data and returns dicts. It does not write
  to the IR, to Looker, or to any external system.

## Files

| File | Responsibility |
|---|---|
| `slices.py` | `build_explore_slice()` — assembles structured context dict for one explore: usage, dead code evidence, PDT evidence, content references |
| `verdicts.py` | `deterministic_verdict()` — rules-based kill/keep/deprecate signal; `validate_verdict()` — checks evidence completeness |

## Verdict types

| Verdict | Meaning |
|---|---|
| `kill` | Dead by both signals (0 queries + no content references) |
| `deprecate` | Stale usage but referenced content — soft deprecation candidate |
| `hide` | Low usage, no content — hide from UI before removing |
| `keep` | Active usage or content references present |
| `review` | Ambiguous signal — needs human or LLM review |

## Evidence IDs

`evidence_ids` is a list of string IDs that reference specific records in the L1 output:
- `explore:<model>.<name>` — IR node
- `schema_table:<physical_table>` — schema drift record
- `field:<view>.<field>` — field-level evidence

`validate_verdict()` checks that all claimed evidence IDs exist in the slice. A missing
evidence ID is a test failure, not just a warning.

## The explore slice

`build_explore_slice(graph, model, explore)` returns everything an agent (or the deterministic
rules) needs to evaluate one explore — no further graph queries required. This is the
structured context contract between L1 and L2.

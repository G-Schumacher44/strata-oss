# L1 — Usage and Schema Enrichment Layer

**Layer:** L1 (enrichment)
**Sits between:** L0 IR (foundation) → L1 (this) → L2 synthesis / MCP tools

---

## What this layer is

Takes an `IRGraph` from L0 and enriches it with real-world facts: query counts, PDT build
costs, content references, and schema drift. The result is an `IRGraph` with a populated
`metadata["l1"]` dict that all downstream layers read from.

L1 never touches raw LookML files. It only enriches the graph L0 built.

## Hard constraints

- **No LLM calls.** All enrichment is deterministic — SQL queries, JSON parsing, arithmetic.
- **No writes.** This layer reads from Looker/BQ/fixtures and writes only to `graph.metadata`.
- **No LookML parsing.** L0 owns the IR. L1 adds facts on top.
- **Provider pattern.** Live Looker and fixture replay implement the same `UsageProvider`
  protocol. Tests always use the fixture path.

## Files

| File | Responsibility |
|---|---|
| `provider.py` | `UsageProvider` protocol + `UsageFacts` dataclass — the L1 contract |
| `types.py` | `PDTBuild`, `PDTLedgerRecord`, `ExploreUsage`, `ContentReference` dataclasses |
| `looker.py` | `LookerSystemActivityProvider` — live Looker System Activity API; OAuth token management |
| `replay.py` | `ReplayLookerUsageProvider` — reads fixture JSON, implements `UsageProvider` |
| `enrich.py` | `enrich_graph()` — merges usage facts into IR; dead code detection; PDT cost calc |
| `schema.py` | `FixtureSchemaProvider` + `enrich_schema_drift()` — column-level drift detection |
| `fixtures.py` | `load_usage_facts()` / `load_schema_facts()` — fixture JSON → typed dataclasses |

## PDT cost estimation

```python
estimated_cost_usd += bytes_processed / 1_000_000_000_000 * 5.0
```

`bytes_processed` = bytes BigQuery reads from disk storage when building the PDT (from
`pdt_event_log.bytes_processed` in Looker System Activity). This is disk I/O, not RAM.
The `$5/TB` rate is standard BQ on-demand pricing. Always label as estimated — actual
invoice differs for flat-rate/committed-use customers.

## Dead code signal

An explore is dead when **both** conditions hold:
1. `query_count == 0` over the enrichment window (from usage facts)
2. No content references (dashboards, looks) reference it

Neither condition alone is sufficient. L2 synthesis (`synthesis/verdicts.py`) makes the
final `keep/kill/deprecate` call — L1 only produces the evidence.

## Adding a new provider

1. Implement `UsageProvider` protocol in a new file
2. Add tests using `tests/fixtures/` — no live API calls in CI
3. Wire into `build_graph_with_provider()` in `pipeline.py`

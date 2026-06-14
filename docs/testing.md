# Strata — Playgrounds and Testing

Three offline playgrounds ship with the repo. Every finding in the README is sourced from actual
output artifacts against these playgrounds. No Looker instance, no BigQuery credentials required.

---

## The Playgrounds

| | thelook | gcs_analytics | enterprise_mono |
|---|---|---|---|
| **Purpose** | Parser + resolver baseline | L1 enrichment + drift | Enterprise stress test |
| **Models** | 1 | 3 | 19 |
| **Explores** | ~9 | 7 | 34 |
| **PDTs** | 0 | 2 | 5 |
| **Cross-model extends** | No | No | Yes |
| **Schema fixtures** | No | Yes | Yes |
| **Legacy clusters** | No | No | Yes (3 decommissioned models) |

Each playground ships with matching fixture JSON files in `tests/fixtures/` that simulate
Looker System Activity API responses.

---

## Running the Playgrounds

```bash
# gcs_analytics (default — L1 enrichment, PDT cost, schema drift)
strata check \
  --repo tests/lookml/gcs_analytics \
  --usage-fixture tests/fixtures/gcs_usage_facts.json \
  --schema-fixture tests/fixtures/gcs_schema_facts.json

# thelook (structural baseline — parse, resolve, extends)
strata check \
  --repo tests/lookml/thelook \
  --usage-fixture tests/fixtures/playground_usage_facts.json \
  --schema-fixture tests/fixtures/playground_schema_facts.json

# enterprise_mono (full stress test — cross-model, zombie PDTs, drift at scale)
strata check \
  --repo tests/lookml/enterprise_mono \
  --usage-fixture tests/fixtures/enterprise_usage_facts.json \
  --schema-fixture tests/fixtures/enterprise_schema_facts.json

# Generate full output artifacts (catalog, dead code, PDT ledger, drift, roadmap)
strata outputs \
  --repo tests/lookml/enterprise_mono \
  --usage-fixture tests/fixtures/enterprise_usage_facts.json \
  --schema-fixture tests/fixtures/enterprise_schema_facts.json \
  --out output/enterprise_mono
```

---

## Developer Testing and Linting

Strata maintains a strict linting and type-checking standard.

### Local Checks

Before pushing changes, run the unified lint command:

```bash
strata lint
```

This runs:
1. **Ruff Check**: Catches style violations, unused imports, and common bugs.
2. **Mypy**: Validates type safety across `src/strata`.

To auto-fix style and format issues:

```bash
strata lint --fix --format
```

### Pre-commit

We use `pre-commit` to ensure all commits meet these standards. Install the hooks locally:

```bash
pip install pre-commit
pre-commit install
```

### CI Pipeline

Our GitHub Actions workflow (`strata-ci.yml`) executes the following on every push and PR:
- `ruff check src/ tests/`
- `ruff format --check src/ tests/`
- `mypy src/strata --ignore-missing-imports`
- `pytest`

---

## Scenario 1 — Structural (thelook)

**What it proves:** LookML parse, graph build, extends/refinement resolution, orphan detection.

**Expected:** 0 resolution errors. Every deterministic verdict has evidence. Validation scope
correctly reports offline tier.

**Findings:**
- 6 dead items: 4 dead explores + 1 orphan view + 1 zombie view
- 1 schema drift hit on `analytics.marketing_campaigns` (2-part name, ambiguous BQ project mapping)

---

## Scenario 2 — L1 Enrichment (gcs_analytics)

**What it proves:** Usage fixtures enrich the IR with dead-code evidence, PDT costs, schema
drift, and period metadata without any live dependency.

**Expected:** 8 output artifacts under `output/gcs_analytics/`.

**Findings:**
- 6 dead items: 2 dead explores + 2 orphan views + 2 zombie views
- 1 unused PDT: `pdt_retention_signals` — $156/30d, no explore backer
- 1 schema drift hit: `fct_demand_forecast` dropped from warehouse

---

## Scenario 3 — Enterprise at Scale (enterprise_mono)

**What it proves:** Cross-model extends chains, zombie PDT cost visibility, schema drift
across legacy views, legacy connection clusters, and dead-explore detection at scale.

**Expected:**
- 34 explores across 19 models, 0 resolution errors
- 6 dead explores (3 legacy_redshift + 2 zombie-PDT-backer + 1 broken connection)
- 5 zombie views
- 2 zombie PDTs: $63,750/30d (~$765K/year), backed exclusively by dead explores
- 14 real schema drift hits across 3 legacy tables

---

## Full Findings

See [`docs/testing-findings.md`](./testing-findings.md) for the complete findings including:
- Full dead code registers per playground
- PDT ledger detail
- Schema drift column-by-column breakdown
- Agentic Haiku benchmark results (~15K tokens per playground, 3/3 autonomous pass)
- CTE false positive analysis and fix
- Risk surface coverage matrix
- Known gaps

---

## Live Looker (opt-in)

Offline CI must pass without this. For live mode:

```bash
strata auth login --looker-url https://your-instance.looker.com
strata outputs --repo /path/to/your/lookml --looker-url https://your-instance.looker.com
```

Token stored at `~/.strata/tokens.json` (0600 permissions). HTTPS enforced — `http://` rejected
except for `localhost` OAuth callback.

---

[← Strata README](../README.md) · [Docs index](./README.md)

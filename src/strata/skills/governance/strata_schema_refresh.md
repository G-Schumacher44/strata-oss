# Strata Schema Refresh Skill

Workflow for updating `schema_facts.json` from live BigQuery INFORMATION_SCHEMA.
Use this when: a warehouse migration landed, drift hits exceed expected baseline,
or the quarterly governance review is due.

---

## Prerequisites

- Google Cloud SDK in PATH (`bq --version` must work)
- ADC configured: `gcloud auth application-default login`
- Strata installed: `.venv/bin/python -m strata --help`
- LookML repo cloned at a known path

---

## How It Works

The script is the context window firewall.

It extracts physical table names from the L0 IR — only the tables your LookML
actually references — groups them by BQ dataset, runs targeted
`INFORMATION_SCHEMA.COLUMNS` queries, and writes `schema_facts.json` to disk.

**Raw column data never enters the agent context.** Stdout is a ~25-line summary.
After the script runs, use `strata_schema_drift` via MCP to inspect hits.

---

## Step 1 — Dry-run: confirm query plan

```bash
strata generate-schema \
  --repo /path/to/lookml \
  --out /tmp/schema_facts_new.json \
  --dry-run
```

Read the output. You will see:
- How many physical tables the IR references
- Which tables are being skipped (no BQ dataset prefix — these are CTEs, expected)
- Which BQ datasets would be queried and how many tables per dataset

**Stop here if** the dataset list looks wrong. The `connection:` names in LookML
model files map to BQ projects — verify that mapping manually before proceeding.

### Connection → BQ project mapping (semi-manual)

Open the LookML model files and find `connection:` declarations:
```
connection: "acme-analytics"
connection: "legacy_redshift"
```

Map each connection name to the BQ project that holds the actual tables.
Legacy or decommissioned connections (e.g., `legacy_redshift`) may not exist
in BQ at all — skip those datasets intentionally.

---

## Step 2 — Run live refresh

```bash
strata generate-schema \
  --repo /path/to/lookml \
  --out /tmp/schema_facts_new.json \
  --existing tests/fixtures/schema_facts.json \
  --bq-project my-gcp-project  # only needed for 2-part table names
```

The script will:
1. Pull INFORMATION_SCHEMA for each dataset (one query per dataset)
2. Write `schema_facts_new.json`
3. Print a delta summary vs the existing fixture

---

## Step 3 — Interpret the delta summary

```
Tables pulled:   11 / 12
Columns indexed: 847

Delta vs existing fixture:
     8  unchanged
     2  updated   (column changes)
         removed: customer_status_v1, segment_score_v1
         added:   customer_status_v2
     1  missing   (not found in BQ — manual review)
```

**Decision rules:**

| Signal | Action |
|---|---|
| `updated` + columns removed | Real drift — run `strata_schema_drift` via MCP, review hits before committing |
| `updated` + columns added only | Additive change — safe to commit new fixture |
| `missing` table | Table dropped or renamed — investigate before committing; may be intentional decommission |
| `unchanged` only | No schema change since last refresh — commit to record the timestamp |
| CTE names in "skipped" list | Expected — these are false positives from `_sql_upstreams()` regex; ignore |

---

## Step 4 — Inspect drift hits (MCP)

If the delta shows removed columns, load Strata MCP and inspect:

```
strata_schema_drift → review missing_column hits
strata_dead_code_register → cross-ref: are the affected views already zombie views?
strata_impact(physical_table=...) → blast radius of the schema change
```

A removed column on a zombie view is low urgency (nobody queries it).
A removed column on an active view with high query count is urgent.

---

## Step 5 — Commit or flag

**Commit the new fixture** when:
- Delta is understood (planned migration, additive, or confirmed decommission)
- No surprises in the drift report

**Flag for human review** when:
- `missing` tables appear unexpectedly
- Removed columns affect active explores with high query counts
- Delta is larger than expected (>10% change in column inventory)

```bash
cp /tmp/schema_facts_new.json tests/fixtures/schema_facts.json
make ci REPO=/path/to/lookml SCHEMA=tests/fixtures/schema_facts.json
git add tests/fixtures/schema_facts.json
git commit -m "chore: refresh schema facts — <date>"
```

---

## Agentic Loop (token-efficient)

A low-end agent (Haiku) can safely run this workflow using only the compact
summary on stdout. Raw column data never enters the context window.

```
1. Read this skill
2. Run generate_schema_facts.py --dry-run → read 25-line summary
3. Confirm datasets match expected connections (apply connection mapping rules above)
4. Run live → read delta summary
5. Apply decision rules from Step 3
6. If drift hits present: call strata_schema_drift via MCP → read structured results
7. Surface recommendation: commit / flag / investigate
```

The script + MCP together give the agent everything it needs. No raw BQ output
enters the context at any point.

**Token profile (Haiku benchmark, enterprise_mono):**

| Stage | Tokens |
|---|---|
| Skill read | ~3,000 |
| Dry-run + filesystem nav | ~18,000 |
| Existing artifact read (schema_drift.json) | ~6,000 |
| Response | ~3,655 |
| **Total** | **~30,655 / 18 tool calls / 54s** |

For a dry-run-only pass (no artifact reads): target ~8,000 tokens.
Keep agents scoped to Step 1–2 of this skill unless drift investigation is needed.

---

## Reference

| Command | Purpose |
|---|---|
| `generate_schema_facts.py --dry-run` | See query plan, no BQ calls |
| `generate_schema_facts.py --existing <path>` | Diff against current fixture |
| `strata_schema_drift` (MCP) | Structured drift hits after refresh |
| `strata_dead_code_register` (MCP) | Cross-ref zombie views with drift |
| `make ci SCHEMA=<path>` | Full CI gate with new fixture |

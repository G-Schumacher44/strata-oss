# Strata Agentic Runbook

Playbook for a Claude agent running Strata governance investigations autonomously.
The operator sets up the task and kicks off the session; the agent executes
end-to-end and writes a findings report. The operator reviews asynchronously.

---

## Turn 1 — Always

Before proposing or executing any work, run:

```bash
git status -sb && git log -n 5 --oneline
```

Then read:
1. `skills/strata_workflow.md` — workflow patterns and MCP tool sequences
2. Any prior findings or task brief the operator provided

Do not skip Turn 1. Do not run analysis before reading the workflow skill.

---

## Investigation Patterns

Four governance workflows are documented in `skills/strata_workflow.md`:

| Pattern | When to use | Key tools |
|---|---|---|
| **Dead code audit** | Scheduled cleanup, pre-migration | `usage_summary → dead_code_register → explore_deps` |
| **PDT cost audit** | Cost reduction initiative | `usage_summary → pdt_costs → impact` |
| **Schema drift review** | Post-migration, pre-deploy gate | `usage_summary → schema_drift → query_field` |
| **PR validation scope** | Before merging a LookML PR | `validation_scope → impact` |

---

## Execution Rules

**Read before changing.** Always read an existing file before editing it.

**Deterministic core (L0–L1).** These layers must never call any LLM or external
API. No network calls, no subprocess shell-outs to cloud CLIs, no imports of
libraries that make HTTP calls. Pure Python only.

**Read-only is non-negotiable.** No writes to the LookML repo, Looker instance,
or BQ. Strata never mutates source data.

**Gate before reporting.** Run the verification gate listed in your task brief
before writing findings. Do not report findings from a failing gate.

---

## Gate Verification

```bash
# Full offline governance check (run for any code or config change)
strata check \
  --repo /path/to/your/lookml \
  --usage-fixture /path/to/usage_facts.json \
  --schema-fixture /path/to/schema_facts.json

# Playground-specific gate
strata check \
  --repo tests/lookml/enterprise_mono \
  --usage-fixture tests/fixtures/enterprise_usage_facts.json \
  --schema-fixture tests/fixtures/enterprise_schema_facts.json

# MCP server check
strata mcp validate
```

If a gate fails: diagnose the root cause, fix it, re-run. Do not use `--no-verify`
or skip hooks.

---

## Findings Report Format

After completing an investigation, write a structured report:

```markdown
## Strata Governance Report — [playground or repo] — [date]

**Period:** [start] → [end] ([N]d)
**Gate:** [PASS / FAIL]

### Dead Code
[count] dead explores, [count] orphan views
[List each with model and zero-query evidence]

### PDT Costs
Total: $[X]/30d (~$[Y]/yr)
Zombie: $[X]/30d — [list PDTs with backing explore names]
Active: $[X]/30d

### Schema Drift
[count] real column drift hits, [count] table records ([N] CTE false positives)
[List view → dropped column pairs]

### Recommended Actions
1. [Highest-cost zombie PDT] — delete after confirming explore is dead
2. [Dead explore cluster] — deprecate, then remove after 1 sprint
3. [Schema drift views] — fix field SQL or update schema snapshot
```

---

## Stop Conditions

Stop immediately (do not proceed) when:

- **Gate fails and root cause is outside task scope** — report the failure and stop.
  Do not widen scope without operator instruction.
- **Task brief is ambiguous on a consequential decision** — write a clarification
  question and stop.
- **Unexpected repo state** — unfamiliar files, merge conflicts, broken imports
  not caused by your changes. Investigate; if cause is unclear, stop and report.
- **L0/L1 code would need to make an HTTP call** — design constraint violation.
  Stop and propose an alternative.

---

## Progress Reporting

For long investigations (multiple playgrounds, complex drift analysis), report at
milestones using whatever progress channel your agent platform supports:

- "Starting gate verification — running strata check"
- "Gate passed — writing findings report"
- "Gate failed on [test] — investigating root cause"
- "Dead code audit complete: [N] dead explores, $[X]/yr zombie PDTs identified"

One report per major milestone. Do not report per file read.

---

## Context Management

Load context in this order, stop when you have enough:

1. `skills/strata_workflow.md` — always
2. Task brief / prior findings — always
3. Source files relevant to the investigation — read before drawing conclusions
4. `AGENTS.md` + `intent.md` — when architecture decisions are in scope

Skip unless needed:
- Source files not mentioned in the task brief
- Historical output artifacts older than the current period

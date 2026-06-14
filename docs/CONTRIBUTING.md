# Contributing

Strata changes should preserve the deterministic core:

- L0 and L1 must remain free of LLM/model calls.
- Ordinary CI must pass without live Looker, BigQuery, Slack, or Jira access.
- New verdicts or reports need evidence-backed tests.
- Do not commit secrets, generated outputs, local token files, or organization
  specific fixtures.

Run before opening a PR:

```bash
strata check \
  --repo tests/lookml/gcs_analytics \
  --usage-fixture tests/fixtures/gcs_usage_facts.json \
  --schema-fixture tests/fixtures/gcs_schema_facts.json

strata check \
  --repo tests/lookml/enterprise_mono \
  --usage-fixture tests/fixtures/enterprise_usage_facts.json \
  --schema-fixture tests/fixtures/enterprise_schema_facts.json
```

---

[← Strata README](../README.md) · [Docs index](./README.md)

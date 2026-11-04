# Input: sql_builder

**Context:** `jira_to_bi_spec` has processed DATA-204. Schema and grain have
already been confirmed by upstream skills in this session.

```
question: "Weekly new user signups by acquisition channel for the past 90 days"
tables:
  - acme-data.analytics.users
schema: (provided by bq_schema_probe — see session context)
grain:
  users: "one row = one user account"
date_range: "last 90 days"
bq_project: acme-data
output_format: time_series
```

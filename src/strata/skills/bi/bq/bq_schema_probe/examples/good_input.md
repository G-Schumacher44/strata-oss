# Input: bq_schema_probe

**Context:** Agent is about to write SQL joining orders to users. Neither table
has been inspected in this session.

```
table_refs:
  - acme-data.analytics.orders
  - acme-data.analytics.users
bq_project: acme-data
question: "What is the average order value by user acquisition channel?"
```

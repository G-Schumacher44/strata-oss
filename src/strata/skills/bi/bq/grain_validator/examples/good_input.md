# Input: grain_validator

**Context:** Agent is about to JOIN `analytics.orders` to `analytics.order_items`
and wants to confirm neither side will fan out.

```
table: acme-data.analytics.order_items
candidate_pk: order_item_id
bq_project: acme-data
```

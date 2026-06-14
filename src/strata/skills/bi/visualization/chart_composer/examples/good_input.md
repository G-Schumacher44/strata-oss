# Input: chart_composer

**Context:** Analyst has the data from a BQ query result and wants a quick viz
for a team standup.

```
question: "Weekly signups by acquisition channel over the last 12 weeks"
data: |
  [
    {"week_start": "2026-03-16", "acquisition_channel": "organic", "new_users": 1842},
    {"week_start": "2026-03-16", "acquisition_channel": "paid_search", "new_users": 934},
    {"week_start": "2026-03-16", "acquisition_channel": "referral", "new_users": 412},
    {"week_start": "2026-03-23", "acquisition_channel": "organic", "new_users": 1991},
    {"week_start": "2026-03-23", "acquisition_channel": "paid_search", "new_users": 1102},
    {"week_start": "2026-03-23", "acquisition_channel": "referral", "new_users": 387}
  ]
out_path: /tmp/signups_by_channel.html
```

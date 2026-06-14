# Output: chart_composer

## Chart: Weekly Signups by Acquisition Channel

**Type:** line
**File:** /tmp/signups_by_channel.html

### Spec used
```yaml
title: "Weekly Signups by Acquisition Channel"
mark: line
encoding:
  x:
    field: week_start
    type: ordinal
    title: "Week"
  y:
    field: new_users
    type: quantitative
    title: "New Users"
  color:
    field: acquisition_channel
    type: nominal
    title: "Channel"
show_labels: false
```

Open `/tmp/signups_by_channel.html` in a browser to view.

**Notes:**
- Used `type: ordinal` for `week_start` (not `temporal`) — ensures weeks display in data order rather than being sorted alphabetically. If you pass full ISO dates (YYYY-MM-DD) and want Vega-Lite's date axis formatting, switch to `type: temporal`.
- Color encodes `acquisition_channel` — 3 series (organic, paid_search, referral) will each get a distinct color.

To adjust: tell me which field, title, or label to change.

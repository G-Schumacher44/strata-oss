# .github — Workflows and Automation

## Workflows

| Workflow | Trigger | What it does |
|---|---|---|
| [`strata-ci.yml`](workflows/strata-ci.yml) | Push/PR to `dev`, `main` | Full test suite, fixture checks across all 3 playgrounds, MCP preflight, generate-schema dry run |
| [`strata-pr.yml`](workflows/strata-pr.yml) | PR touching `*.lkml` | **StrataBot** — posts LookML impact analysis as a PR comment |
| [`strata-weekly.yml`](workflows/strata-weekly.yml) | Monday 08:00 UTC (or manual) | Runs governance check + outputs against all 3 playgrounds; notification dry run |
| [`release.yml`](workflows/release.yml) | Tag push (`v*.*.*`) | Builds wheel + sdist via hatchling, creates GitHub Release with generated notes |
| [`sync-public.yml`](workflows/sync-public.yml) | Manual (`workflow_dispatch`) | Dry-run sync plan to public OSS remote — configure `strata-oss` remote before enabling push |

---

## StrataBot — LookML PR Impact Analysis

`strata-pr.yml` posts an automated comment on any PR that touches `.lkml` files. It runs
`strata_validation_scope` against the changed files and reports which explores are in the
minimum revalidation set.

**Example comment:**

```
## Strata LookML Impact Analysis

Changed files: `views/orders.view.lkml`, `views/users.view.lkml`

| Explore | Model | Impacted Views |
|---|---|---|
| orders | enterprise | orders, users, inventory |
| orders_daily | enterprise | orders, users |

3 explores in revalidation scope. Run `strata check` before merging.
```

### How it works

1. On PR open/update, diffs changed `.lkml` files against the PR base
2. Runs `scripts/pr_comment.py --repo . --changed <files> --pr <number>`
3. Posts or updates a comment via `GH_TOKEN` (auto-provided — no secrets to configure)

### Enabling StrataBot on your repo

The workflow fires automatically when `.lkml` files change. No setup required beyond having
the workflow file present. For offline fixture mode, no additional secrets are needed.

For live Looker enrichment (query counts in the impact comment), set:

| Secret | Value |
|---|---|
| `LOOKER_URL` | Your Looker instance URL |
| `LOOKER_TOKEN` | OAuth token from `strata auth login` |

---

## Required Secrets

| Secret | Used by | Notes |
|---|---|---|
| `GITHUB_TOKEN` | All workflows | Auto-provided by GitHub Actions |
| `LOOKER_URL` | `strata-weekly.yml` (live mode) | Optional — omit for fixture-only runs |
| `LOOKER_TOKEN` | `strata-weekly.yml` (live mode) | Optional — omit for fixture-only runs |

All CI steps that use the included playground fixtures run fully offline — no secrets needed
beyond the auto-provided `GITHUB_TOKEN`.

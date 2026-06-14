# scripts/

Helper scripts invoked by CI workflows and locally for maintenance tasks.
Not part of the installable package — all user-facing functionality lives in `strata` CLI.

## Scripts

| Script | Used by | What it does |
|---|---|---|
| `pr_comment.py` | `.github/workflows/strata-pr.yml` | **StrataBot backend.** Detects changed `.lkml` files in a PR, runs `strata_validation_scope`, posts a formatted markdown impact comment via `gh`. |
| `notify.py` | CI / manual | Builds Slack and Jira notification payloads from `strata outputs` artifacts. Pass `--dry-run` to print without sending. |
| `generate_schema_facts.py` | Manual | Queries BigQuery `INFORMATION_SCHEMA.COLUMNS` for tables referenced in a LookML repo and writes `schema_facts.json`. Predecessor to `strata generate-schema` CLI. |
| `test_mcp_live.py` | Manual | Governance investigation driver — calls all MCP tools against a playground and prints a human-readable findings report. Use to validate tool correctness against a live fixture. |
| `check_public_release.py` | Manual / `.github/workflows/public-release-audit.yml` | Read-only audit for candidate public releases. Fails when a `public/main..HEAD` diff includes `.publicignore` paths, local machine paths, or credential markers. |

## Running

```bash
# StrataBot — posts PR impact comment (requires GH_TOKEN)
python scripts/pr_comment.py --repo . --changed views/orders.view.lkml --pr 42

# Notifications dry run
python scripts/notify.py --artifacts output/enterprise_mono --dry-run

# Schema facts refresh
python scripts/generate_schema_facts.py \
  --repo tests/lookml/enterprise_mono \
  --out tests/fixtures/enterprise_schema_facts.json \
  --dry-run

# Live MCP tool validation
python scripts/test_mcp_live.py

# Public release audit
python scripts/check_public_release.py --base public/main --target HEAD
```

## Adding scripts

Scripts here are one-off tools and CI glue. If a script becomes a regular user-facing
operation, promote it to a `strata <command>` CLI subcommand instead.

# Enterprise Deployment

Strata is designed for read-only analysis of a LookML clone plus read-only
usage/schema facts. It should run as a separate tool, not inside the production
LookML repository or warehouse control plane.

## Identity And Access

- Use a read-only Looker OAuth client for live System Activity enrichment.
- Use GitHub OIDC or workload identity for CI integrations; do not commit service
  account keys.
- Keep Slack/Jira tokens scoped to notification delivery only.
- Store local Looker tokens under `~/.strata/tokens.json`; this file is outside
  the repo and written with user-only permissions.

## Network And Data Isolation

- CI defaults to fixtures and replay data, so ordinary test runs need no live
  network access.
- Live Looker runs are opt-in via `--looker-url` after `strata auth login`.
- Strata does not write to Looker, BigQuery, or the LookML repo. Generated
  artifacts are local JSON/HTML under `output/`.

## Google Workspace / GCP Controls

- Register the OAuth client with `client_guid=com.gsanalytics.strata.cli` and
  redirect `http://localhost:8765/oauth/callback`.
- Restrict the client to the smallest practical Looker group.
- Prefer OIDC over static secrets for scheduled GitHub workflows.
- Keep BigQuery schema fact export as a separate read-only producer feeding
  Strata JSON fixtures.

## Audit Trail

Every conductor run writes a handoff with a real commit anchor, exact next steps,
and gate results. Treat those handoffs as the operational audit trail.

---

[← Strata README](../README.md) · [Docs index](./README.md)

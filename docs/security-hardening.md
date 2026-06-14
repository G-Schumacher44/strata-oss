# Security Hardening

## Read-Only Contract

Strata never writes to the LookML repo, Looker instance, BigQuery, Slack, or Jira
as part of core analysis. Notification delivery is payload-first and opt-in;
the default gate is `--dry-run`.

## Credential Matrix

| Credential | Location | Required For | Notes |
|---|---|---|---|
| Looker OAuth token | `~/.strata/tokens.json` | Live System Activity | Redacted by status command; outside repo. |
| Slack token | GitHub secret | Notification delivery | Not used by dry-run payload generation. |
| Jira token | GitHub secret | Ticket creation | Not used by dry-run payload generation. |
| GCP identity | GitHub OIDC | Future schema/weekly integrations | Prefer workload identity, not key files. |

## MCP Model

The MCP server remains stdio-only. It exposes repo-brain queries over local IR/L1
data and does not provide HTTP transport.

## What Strata Never Does

- No LookML writes.
- No production warehouse mutations.
- No model/LLM calls in L0 or L1.
- No committed secrets or service account keys.
- No live dependency in ordinary CI.

---

[← Strata README](../README.md) · [Docs index](./README.md)

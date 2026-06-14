# Notifications Setup

Strata notifications are payload-first. The offline gate builds Slack Block Kit
and Jira issue JSON with `scripts/notify.py --dry-run`; delivery can be wired by
CI secrets after the payloads are reviewed.

## Slack

1. Create a Slack app with permission to post to the target channel.
2. Store the bot token as a GitHub secret, for example `SLACK_BOT_TOKEN`.
3. Run `python scripts/notify.py --artifacts output/gcs_analytics --dry-run` and
   review the `slack` payload before enabling delivery.

## Jira

1. Create a Jira API token with project-scoped issue creation rights.
2. Store the token and project key as GitHub secrets.
3. Review the `jira` array produced by the dry run; each cleanup item becomes a
   task payload with Strata evidence embedded in the description.

## Current Posture

Slice 13 intentionally stops at payload generation. Sending is a deployment
choice because every workspace differs on webhook, bot, approval, and routing
requirements.

---

[← Strata README](../README.md) · [Docs index](./README.md)

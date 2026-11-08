# Enterprise Deployment

Strata is designed for analysis of a LookML clone plus usage/schema facts; it never
modifies `.lkml` content, Looker, or BigQuery. It should run as a separate tool, not inside the production
LookML repository or warehouse control plane.

## Identity And Access

- Looker has no read-only OAuth client mode: an OAuth access token acts with the
  permissions of the Looker user who signs in. Strata itself only reads (System Activity
  queries via `queries/run/json`), so limit exposure through the user and the client app —
  sign in as a user whose role grants only what System Activity needs, and restrict the
  client app to a group (below).
- Use GitHub OIDC or workload identity for CI integrations; do not commit service
  account keys.
- Strata does not send Slack or Jira notifications (payload generation only), so it needs
  no Slack/Jira token. If you add delivery yourself, scope that token to it alone.
- Local Looker tokens live at `~/.strata/tokens.json`, outside the repo: file 0600,
  directory 0700 (POSIX), refused on read if group/world accessible, sent only to the
  Looker origin that issued them. `strata auth logout` deletes the local copy only;
  revocation is done by a Looker admin. Details:
  [Security Hardening](./security-hardening.md#token-storage).

## Network And Data Isolation

- CI defaults to fixtures and replay data, so ordinary test runs need no live
  network access.
- Live Looker runs are opt-in via `--looker-url` after `strata auth login`.
- Strata does not write to Looker or BigQuery, and never modifies `.lkml` files. It
  does write local files, some inside the LookML checkout: the IR cache
  (`strata_ir.db` in the repo root, from the MCP server or `strata build`, unless
  `STRATA_CACHE_PATH` / `--cache` is set), `conductor/` files (`strata bootstrap`,
  `strata conductor`, `strata validate`'s log), and `strata bootstrap`'s agent/MCP
  config files. `strata clean` deletes caches. The full list is in
  [Security Hardening](./security-hardening.md#what-strata-reads-and-writes).
- Local listeners: `strata dashboard` serves on `127.0.0.1` (default port 8765);
  `strata auth login` listens on its loopback redirect port until the redirect
  arrives or it times out. The MCP server
  is stdio-only.

## Google Workspace / GCP Controls

- A Looker admin registers the OAuth client app, either in **Admin > Authentication >
  Manage OAuth clients** or with the `register_oauth_client_app` API endpoint
  ([Looker OAuth guide](https://docs.cloud.google.com/looker/docs/api-cors)):
  - `client_guid`: `com.gsanalytics.strata.cli` (Strata's default `--client-id`; any
    value works if you pass it to `strata auth login --client-id`, but it cannot start
    with `com.looker.`).
  - `redirect_uris`: `http://127.0.0.1:48765/oauth/callback` (Strata's default
    `--redirect-uri`). Looker matches it exactly, so register precisely the URI users
    will pass, including the port. Use the `127.0.0.1` literal, not `localhost`.
  - `group_id`: the numeric ID of the Looker group allowed to authorize the app — set
    it to the smallest practical group.
- Looker OAuth support is implemented from that guide but **not yet validated against
  a live Looker instance**.
- Prefer OIDC over static secrets for scheduled GitHub workflows.
- Keep BigQuery schema fact export as a separate read-only producer feeding
  Strata JSON fixtures.

## Change Records (not an audit log)

By project convention, each Conductor work session ends with a handoff in
`conductor/handoff-log.md` recording a commit anchor, next steps, and gate results.
This is a process convention, not an enforced audit log: nothing in Strata requires a
handoff, and the files are ordinary repo text that can be edited. `strata validate`
checks that the latest handoff's `Commit:` hash exists in git, nothing more. For an
audit trail, rely on your git host's history and Looker's own System Activity.

---

[← Strata README](../README.md) · [Docs index](./README.md)

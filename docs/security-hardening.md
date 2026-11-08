# Security Hardening

## What Strata Reads And Writes

Strata never modifies `.lkml` content, and never writes to a Looker instance, BigQuery, Slack,
or Jira. Its writes are local files. Every command that writes or deletes files, as of 0.1.9:

| Command | Writes |
|---|---|
| MCP server (`strata-mcp`) | The IR cache: `~/.strata/cache/<repo-name>-<sha256(abs repo path)[:12]>.db` (directory 0700, file 0600 on POSIX), or the path in `STRATA_CACHE_PATH`. Never inside the LookML repo by default. Rebuilt unless it was built from the same repo (path + `.lkml` file count, newest mtime, total size, paths) and fixtures (paths + mtimes) and is younger than the cache max age; a missing, unparseable, or future timestamp also forces a rebuild. |
| `strata_render_chart` (MCP tool) | One `.html` file, only under `~/.strata/output/` or `/tmp/`; other paths and other extensions are refused. |
| `strata build` | The IR cache: the same `~/.strata/cache/` entry as the MCP server, or `--cache` / `STRATA_CACHE_PATH`. |
| `strata outputs` / `strata dashboard` | JSON artifacts and `dashboard.html` under `--out` (dashboard default: `./output/<repo-name>`). |
| `strata chart <type>` / `strata-chart` | One HTML file at `--out` (default: a fresh `strata_chart_*.html` in the system temp dir, path printed); any path the user names, never written through a symlink at the final component. |
| `strata query navigate` | `--out`: a Markdown brief at the path the user names. `--chart`: an HTML chart under `~/.strata/output/`. |
| `strata conductor init` / `new-slice` | `conductor/` files in the target repo. |
| `strata validate` | Appends one row to `<project>/conductor/.validation-log` (or `CONDUCTOR_VALIDATION_LOG`). |
| `strata clean` | **Deletes** `./output/`; the repo's IR cache entry under `~/.strata/cache/`; and every legacy `strata_ir.db` and every `__pycache__` directory under the repo (`--repo` / `STRATA_REPO_PATH`, default: the current directory). A cache at `STRATA_CACHE_PATH` / `--cache` is not deleted. |
| `strata bootstrap` | In the target repo: `AGENTS.md`, `CLAUDE.md`, `conductor/`, `.mcp.json`, `.cursor/mcp.json` (existing files skipped unless `--force`), and a Strata block appended to `.gitignore`. Outside it: `~/.strata/config.json`. |
| `strata generate-schema` | `schema_facts.json` at `--out`. |
| `strata auth login` / `logout` | `~/.strata/tokens.json` (or `--token-path`): created / deleted; `~/.strata/` created 0700 if missing. |

Notification delivery stops at payload generation: `scripts/notify.py` builds Slack/Jira
payloads and requires `--dry-run` to print them — sending is not implemented and the script
exits non-zero without that flag. See [Notifications Setup](./notifications-setup.md) for wiring
actual delivery yourself.

## Network Surface

- **Outbound, Looker:** only with `--looker-url` after `strata auth login`. Looker URLs must be
  `https://`; `http://` is accepted only when the host is `localhost` or `127.0.0.1` (for local
  testing). Requests do not follow HTTP redirects, so the `Authorization` header cannot be
  carried to another host.
- **Outbound, BigQuery:** `strata generate-schema` shells out to the `bq` CLI with your gcloud
  credentials; it does not use the Looker token.
- **Listening:** `strata dashboard` serves its output directory on `127.0.0.1` (default port
  8765) until you stop it, and answers 403 to any request whose `Host` header is not
  `127.0.0.1:<port>`, `localhost:<port>`, or `[::1]:<port>` (DNS-rebinding guard). `strata auth login` listens on
  `127.0.0.1` at the redirect port until a request with the matching `state` arrives on the
  redirect path, or `--timeout` passes (each connection gets at most 5 seconds to send its
  request); requests to other paths get 404 and requests with a wrong `state` get 400 and are
  ignored. On Windows the listener binds with `SO_EXCLUSIVEADDRUSE` and without
  `SO_REUSEADDR`, so another process cannot share the port; on POSIX it sets `SO_REUSEADDR`,
  which only lets a retry rebind while the previous connection is in TIME_WAIT. The MCP server is stdio-only
  and opens no port.

## Looker OAuth

Implemented from Looker's OAuth guide,
[https://docs.cloud.google.com/looker/docs/api-cors](https://docs.cloud.google.com/looker/docs/api-cors).
**Not yet validated against a live Looker instance.**

- Authorization code flow with PKCE (`code_challenge_method=S256`, RFC 7636) and a random
  `state` that is verified on the redirect before the code is used.
- The browser goes to `/auth` on the Looker UI host; the code is redeemed with a JSON POST to
  `/api/token` on the Looker API host (`--api-url`, defaulting to `--looker-url`).
- The redirect is captured by a one-shot listener on `127.0.0.1` (RFC 8252 §7.3). Looker matches
  redirect URIs exactly against those registered on the client app, so the port is fixed:
  default `http://127.0.0.1:48765/oauth/callback`, configurable with `--redirect-uri`. The
  receiver accepts only `http://127.0.0.1:<port>/...` redirect URIs (not `localhost`, which can
  resolve to `::1`); any other redirect URI needs `--no-browser`.
- `--no-browser` prints the URL and reads the full redirect URL from stdin (hidden input), so the
  code never appears in shell history or the process list.

## Token Storage

- Stored at `~/.strata/tokens.json` by default. On POSIX the file is created with mode 0600
  (exclusive create of a temporary file, then an atomic rename). A missing token directory is
  created 0700, and `~/.strata` itself is set to 0700 on every save. Strata never changes the
  mode of any other existing directory: a `--token-path` whose directory is accessible by group
  or others is refused, before the browser is opened.
- On read, a token file with any group or other permission bits is **refused** (POSIX). Windows
  has no POSIX mode bits, so this check is skipped there; protection relies on the user
  profile's ACLs.
- A token is bound to the Looker API origin (scheme, host, port) that issued it. Strata refuses
  to send it anywhere else, including when `--looker-url` names a different instance. So on
  `strata outputs` / `strata dashboard`, `--looker-url` is the API host URL — the same as the
  instance URL unless you passed a separate `--api-url` at login.
- Expiry is checked before every request. Looker's guide documents a refresh token but no
  refresh request, so Strata does not store the refresh token; an expired token means running
  `strata auth login` again.
- `strata auth status` shows at most the last four characters of the token. Looker API error
  messages report the status code and reason, not the response body.
- `strata auth logout` deletes the local file only. The token stays valid at Looker until it
  expires or a Looker admin revokes it ("All tokens in this system can be revoked by the Looker
  admin at any time." — Looker OAuth guide).

## BigQuery Query Construction

`strata generate-schema` (and `scripts/generate_schema_facts.py`, which uses the same code) builds
`INFORMATION_SCHEMA.COLUMNS` queries from table names found in LookML — repo-controlled text.

- Project, dataset, and table identifiers are checked against an allowlist (project: lowercase
  letters, digits, hyphens; dataset: letters, digits, underscores; table: letters, digits,
  underscores, hyphens). Names that fail are skipped and listed as rejected, never queried.
- Table names are passed as a query parameter (`--parameter=names:ARRAY<STRING>:[...]`,
  `WHERE table_name IN UNNEST(@names)`). The dataset path cannot be parameterized in BigQuery
  ("Parameters can't be used as substitutes for identifiers, column names, table names, or other
  parts of the query." —
  [BigQuery parameterized queries](https://docs.cloud.google.com/bigquery/docs/parameterized-queries)),
  so it is interpolated only after passing the allowlist.
- Each query runs with `--maximum_bytes_billed=1000000000` and `--max_rows=1000000`.

## LookML Parsing

The parser reads `.lkml` files under the repo root. Symlinks whose target resolves outside the
repo root are skipped. Parsing never executes LookML, SQL, or Liquid.

## Prompt Injection

LookML text (descriptions, SQL, labels), bundled skills, and Conductor handoff files are
returned to the calling model verbatim as data. Strata executes none of it: no tool runs SQL,
shells out, or follows instructions found in that text. A hostile LookML repo can still put
misleading text in front of an agent, so treat MCP answers from an untrusted repo as untrusted
input to your agent.

## Credential Matrix

| Credential | Location | Required For | Notes |
|---|---|---|---|
| Looker OAuth access token | `~/.strata/tokens.json` | Live System Activity (`--looker-url`) | 0600/0700, origin-bound, redacted by `auth status`. MCP tools never read it. |
| gcloud CLI credentials (`gcloud auth login`, or a service account via gcloud) | gcloud's own store | `strata generate-schema` | Used by the `bq` CLI, not by Strata directly. Application Default Credentials are not what `bq` uses. |
| GCP identity | GitHub OIDC | Future schema/weekly integrations | Prefer workload identity, not key files. |

Slack and Jira delivery is not implemented (see above), so Strata uses no Slack or Jira token
and no workflow references one. If you wire delivery yourself, the token is yours to scope.

## MCP Model

The MCP server is stdio-only. It exposes repo-brain queries over the local IR and fixture L1
data, does not read the Looker token, and makes no network calls. Diagnostic output goes to
stderr; stdout carries only JSON-RPC.

## What Strata Never Does

- No `.lkml` writes.
- No production warehouse mutations.
- No model/LLM calls in L0 or L1.
- No committed secrets or service account keys.
- No live dependency in ordinary CI.

---

[← Strata README](../README.md) · [Docs index](./README.md)

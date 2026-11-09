# Security Hardening

## What Strata Reads And Writes

Strata never modifies `.lkml` content, and never writes to a Looker instance, BigQuery, Slack,
or Jira. Its writes are local files. Every command that writes or deletes files, as of 0.1.9:

| Command | Writes |
|---|---|
| MCP server (`strata-mcp`) | The IR cache: `~/.strata/cache/<repo-name>-<sha256(abs repo path)[:12]>.db` (directory 0700, file 0600 on POSIX), or the path in `STRATA_CACHE_PATH`. Never inside the LookML repo by default. Rebuilt unless it was built from the same repo (path + `.lkml` file count, newest mtime, total size, paths) and fixtures (paths + mtimes) and is younger than the cache max age; a missing, unparseable, or future timestamp also forces a rebuild. |
| `strata_render_chart` (MCP tool) | One `.html` file, only under `~/.strata/output/` or `/tmp/`; other paths and other extensions are refused. |
| `strata build` | The IR cache: the same `~/.strata/cache/` entry as the MCP server, or `--cache` / `STRATA_CACHE_PATH` (refused if that path is a symlink, a `.lkml`/`.lookml` file, a directory, or an existing file that is not a Strata IR cache, such as an unrelated SQLite database). |
| `strata outputs` / `strata dashboard --out` | JSON artifacts and `dashboard.html` under `--out`. |
| `strata workbench` (and `strata dashboard` without `--out`) | The IR cache, exactly as the MCP server writes it (reused on a second start when its inputs are unchanged), and the triage acknowledgements store (next row) when a page acknowledges a finding (`POST /api/triage`). Nothing else: no artifacts, no files in the repo; a `--baseline` file is read, never written. |
| `strata chart <type>` / `strata-chart` | One HTML file at `--out` (default: a fresh `strata_chart_*.html` in the system temp dir, path printed); any path the user names, never written through a symlink at the final component. |
| `strata query navigate` | `--out`: a Markdown brief at the path the user names. `--chart`: an HTML chart under `~/.strata/output/`. |
| `strata conductor init` / `new-slice` | `conductor/` files in the target repo. |
| Triage acknowledgements (`strata_lookml.triage`, for the workbench and TUI) | `~/.strata/triage/<repo-name>-<sha256(abs repo path)[:12]>.json` (directory 0700, file 0600 on POSIX): the finding ids an engineer acknowledged, outside the LookML repo. Beside it, an empty `<same name>.lock` (0600) that writers hold an OS advisory lock on (`flock` / `msvcrt`); it is never deleted. Written to a temp file and `os.replace`d (an interrupted write keeps the previous file); refused through a symlink or over a file that is not a Strata triage store. Only ids a current finding carries (or already stored) are accepted. `strata check` never reads it: the gate uses the committed baseline only. |
| `strata validate` | Appends one row to `~/.strata/logs/validation-<repo-name>-<hash>.log` (dir 0700, file 0600), or to `CONDUCTOR_VALIDATION_LOG`. Nothing is written inside the project being validated. |
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
- **Listening:** `strata workbench` (alias `strata dashboard`) listens on `127.0.0.1` (default port
  8765, falling back to 8766-8785 if busy and `--port` was not passed) until you stop it, and answers 403 to any request whose `Host` header is not
  `127.0.0.1:<port>`, `localhost:<port>`, or `[::1]:<port>` (DNS-rebinding guard); see
  [Workbench Server](#workbench-server). `strata dashboard --out DIR` instead serves DIR (the
  static export) with the same bind and Host check. `strata auth login` listens on
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

## Workbench Server

`strata workbench` (`strata_lookml.workbench.server` + `app`) is a plain `BaseHTTPRequestHandler`
over a route table. It never serves a directory, never changes the working directory and never
builds a filesystem path from a request:

- **Host first.** Every request's `Host` must be on the allow-list for the bound port before any
  routing; otherwise 403 with a plain-text body (no page, so no token).
- **Methods.** GET and HEAD only, except `POST /api/triage` (below); any other method, including
  ones `http.server` does not know, gets 405 with `Allow: GET, HEAD` (after the Host check), and
  `/api/triage` answers every method but POST, OPTIONS included, with 405 `Allow: POST` and no
  CORS headers. No other request body is ever read.
- **Headers on every response**, errors included: `Content-Security-Policy: default-src 'self';
  script-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'`,
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`.
- **Static files** come from a fixed name -> packaged-asset map (the vendored Cytoscape/dagre
  bundles); any other `/static/` name, `..` included, is 404.
- **Paths** are exactly `/<kind>/<one percent-decoded segment>`; the segment is a lookup key into
  the in-memory graph, never a path. Unknown objects render the error contract (message + hint)
  as a 404; ambiguous names a 300 page linking each candidate.
- **Token.** Each server process generates a random token (`secrets.token_urlsafe(32)`) and puts
  it in a `<meta name="strata-token">` on its pages, for the triage POST to check. Only
  allow-listed Hosts receive a page.
- **The one write: `POST /api/triage`** (`App._triage_post`, an adapter over
  `strata_lookml.triage.TriageStore`). Body `{"action": "ack"|"unack", "ids": [...], "note"?}`.
  The store is called only if every check passes, in this order, all before the body is read:
  - the `Host` is allow-listed (as for every request; refused: plain-text 403);
  - `Origin` is present and equals `http://<that Host>`; missing, `null`, another host, another
    port, `https`, or a different allow-listed name is 403;
  - `Sec-Fetch-Site`, when sent, is `same-origin` (403 otherwise);
  - `Content-Type` is exactly `application/json` (415 otherwise). A cross-origin page cannot
    send that without a CORS preflight, and the workbench never grants one;
  - `X-Strata-Token` equals the process token (`hmac.compare_digest`; 403 otherwise);
  - `Content-Length` is present and numeric (411 if missing or with `Transfer-Encoding`, 400 if
    malformed) and at most 64 KB (413). The body then gets 5 seconds to arrive (the server is
    single-threaded), and one shorter than its length is 400;
  - the body is a UTF-8 JSON object with only those keys, `action` one of the two, `ids` a
    non-empty list of non-empty strings, and `note` a string sent only with `ack` (400).

  A duplicated checked header is 400. The store then applies its own id allowlist (an id no
  current finding carries, and not already stored, is 400 and nothing is written) and its
  concurrency retries (exhausted: 409). Every answer from this path is JSON (`{error, code,
  hint}` on failure; the updated rows on success), serialized with `<` escaped, never HTML, so
  nothing from a request reaches markup. Without JavaScript the pages stay read-only; `strata
  ack` / `strata unack` write the same store under the same lock.
- **Data.** The graph is loaded once at startup from the IR cache (`load_or_build`); while it
  runs the inputs are re-fingerprinted at most every 10 seconds and a change only shows a
  "restart to reload" banner. There is no reload endpoint.

`tests/test_workbench_server.py` enforces each point, and renders a fixture whose names, file
names and table names carry markup, quotes, `%2F` and `..` through every route, asserting no
response contains a tag, event attribute or link outside the page shell.
`tests/test_workbench_triage_post.py` covers the triage POST: every refusal asserts that no
`TriageStore` method ran and that the store file is byte-identical afterwards.

## Workbench Rendering And Escaping

Workbench pages render through one Jinja2 environment (`strata_lookml.workbench.render`) with autoescape on for every template regardless of extension and `StrictUndefined`; templates may not use `|safe` or `{% autoescape false %}`, and `markupsafe.Markup` is constructed only inside `safe_svg()` — all enforced by `tests/test_workbench_render.py`.

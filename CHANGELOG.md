# Changelog

All notable changes to `strata-lookml` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) (pre-1.0: minor versions may break).

## [Unreleased]

### Security

- `strata dashboard` now validates the HTTP `Host` header and returns 403 unless it is
  `127.0.0.1:<port>`, `localhost:<port>`, or `[::1]:<port>` for the bound port, closing a
  DNS-rebinding path to the artifact JSON.

## [0.1.9] - 2026-11-03

### Security

- `strata generate-schema` (and `scripts/generate_schema_facts.py`, which now shares its code)
  validates every project, dataset, and table identifier taken from LookML against an allowlist
  and skips + reports any that fail (e.g. names containing quotes, backticks, semicolons, or
  whitespace). Table names are now sent as a BigQuery query parameter (`IN UNNEST(@names)`),
  and each query runs with `--maximum_bytes_billed` and `--max_rows` (the `bq` default of 100
  rows had been truncating wide datasets).
- Looker OAuth (`strata auth login`): PKCE (S256) and a verified `state`; the redirect is
  captured by a one-shot `127.0.0.1` listener instead of a `--code` argument (removed —
  codes no longer land in shell history or the process list); `--no-browser` reads the pasted
  redirect URL from stdin. The flow now follows Looker's documented endpoints and parameters
  (`client_id` on `/auth`; JSON POST to `/api/token` on the API host, new `--api-url`).
  **BREAKING:** the default redirect URI is now `http://127.0.0.1:48765/oauth/callback` (it no
  longer shares the dashboard's port 8765) — update the OAuth client app's registered redirect
  URIs, or pass `--redirect-uri`. Not yet validated against a live Looker instance.
- Looker token handling: the token is bound to the origin that issued it and refused for any
  other `--looker-url`; HTTP redirects are not followed (so the `Authorization` header cannot be
  forwarded); expiry is checked before each request; the refresh token is no longer stored
  (Looker documents no refresh request). A token file without `looker_url` is refused; run
  `strata auth login` again.
- Token storage: written via an exclusive-create 0600 temp file and atomic rename; a missing
  token directory is created 0700 and `~/.strata` is kept 0700, while a custom `--token-path`
  in a directory shared with group/others is refused before the login starts. A
  group/world-accessible token file is now refused on read (POSIX) instead of warned about. `auth status` shows at most the last four characters;
  API errors no longer echo the response body. `auth logout` states that it is local-only.
- `strata mcp validate` checks the real token path (`~/.strata/tokens.json`), not
  `looker_token.json`.
- MCP server: an IR cache whose `built_at` is in the future (or unparseable) is rebuilt instead
  of being treated as fresh; `strata_render_chart` writes its path to stderr (stdout is the
  JSON-RPC channel) and requires an `.html` output path.
- `strata dashboard` binds `127.0.0.1` explicitly. `strata outputs` / `strata dashboard`
  report token and Looker API refusals as CLI errors instead of tracebacks.
- The LookML parser skips symlinks that resolve outside the repo root.
- Security docs (README, SECURITY.md, `docs/security-hardening.md`,
  `docs/enterprise-deployment.md`) now state exactly what Strata writes and where, which local
  ports it listens on, how the Looker OAuth client is registered and restricted (there is no
  read-only OAuth client mode in Looker), and how LookML/skill text is handled (returned to the
  model as data; never executed).

### Changed

- **BREAKING (Python importers only):** the import package is now `strata_lookml`; through 0.1.8
  it was `strata`. The unrelated PyPI projects `strata` and `strata-mcp` also ship a top-level
  `strata` package, so installing either beside `strata-lookml` overwrote files. Replace
  `import strata` / `from strata.x import y` with `strata_lookml`. The `strata`, `strata-mcp`
  and `strata-chart` commands, the MCP server name, and `~/.strata/` config are unchanged.
  No `strata` compatibility package ships, because it would recreate the collision.
  **Upgrading in an environment that also has `strata` or `strata-mcp`:** uninstalling 0.1.8
  removes the `strata/` files it shared with that package, so reinstall it afterwards
  (`pip install --force-reinstall --no-deps strata`).
  ([#45](https://github.com/G-Schumacher44/strata-oss/pull/45))
- Package metadata: SPDX `license = "Apache-2.0"` with `license-files` (PEP 639), keywords,
  more classifiers, and Documentation / Changelog project URLs.
- README: absolute links so it renders correctly on PyPI, Quick Start leads with
  `pipx install strata-lookml`, and a no-credentials path for your own LookML repo.
  ([#52](https://github.com/G-Schumacher44/strata-oss/pull/52))

### Added

- MCP Registry readiness: a `server.json` (registry name `io.github.G-Schumacher44/strata-oss`,
  PyPI package `strata-lookml`, stdio via `uvx`), the matching `mcp-name` token in the README,
  and a `strata-lookml` console script (same server as `strata-mcp`) so
  `uvx strata-lookml` resolves. ([#44](https://github.com/G-Schumacher44/strata-oss/pull/44))
- Every MCP tool now has a `title` and explicit `ToolAnnotations`: 17 are read-only;
  `strata_render_chart` is annotated as a destructive, idempotent writer (it writes, and may
  overwrite, one HTML file under `~/.strata/output` or `/tmp`). ([#44](https://github.com/G-Schumacher44/strata-oss/pull/44))
- Descriptions for the 8 MCP tools that reported an empty description in `tools/list`.
  ([#52](https://github.com/G-Schumacher44/strata-oss/pull/52))
- `strata-mcp --help` / `-h` prints usage and exits instead of starting the stdio server.
  ([#52](https://github.com/G-Schumacher44/strata-oss/pull/52))
- Release workflow publishes `server.json` to the official MCP Registry on the tag push via GitHub OIDC (after PyPI is live); no manual `mcp-publisher` step.

### Fixed

Ten correctness fixes, grouped by area ([#50](https://github.com/G-Schumacher44/strata-oss/pull/50)):

- PDT upstream SQL: backtick-quoted BigQuery tables are detected, including per-part quoting;
  `${view}` refs and backtick-quoted CTEs are no longer read as tables, and a per-part-quoted
  `sql_table_name` and the same PDT upstream resolve to one table node.
- Charts: `<` is escaped in chart HTML so data cannot close the script block.
- `strata query navigate`: the chart spec is built as data rather than a YAML template, the chart
  is written under the guarded output root (`~/.strata/output`), `dataset.table` anchors are
  classified as physical tables when the IR has them, and an exact `view.field` match wins over a
  same-named table (the brief flags `ambiguous_anchor`).
- `strata clean --repo` sweeps `__pycache__` under the repo, not the current directory.
- `load_ir` raises `FileNotFoundError` instead of creating an empty cache file, and opens the
  cache without ever creating it.
- ISO timestamps are compared as instants, with one shared, order-independent latest-timestamp
  rule.
- The source-line scan cache is cleared on every build.

Also:

- Dashboard: escape the remaining `innerHTML` sinks and harden the escaping guardrail
  ([#30](https://github.com/G-Schumacher44/strata-oss/pull/30)).
- Dashboard: evidence sentences, inlined L1 facts and deep links
  ([#28](https://github.com/G-Schumacher44/strata-oss/pull/28)); rich node detail, honest
  zombie vocabulary, live evidence links, graph layout and drift dedup
  ([#25](https://github.com/G-Schumacher44/strata-oss/pull/25)).
- An invalid `\]` escape in the dashboard HTML template (inside a JavaScript comment) raised a
  `SyntaxWarning` when the module was compiled, and a `SyntaxError` under `-W error`. The
  generated dashboard is byte-identical. ([#52](https://github.com/G-Schumacher44/strata-oss/pull/52))
- README naming note rewritten as bullets
  ([#24](https://github.com/G-Schumacher44/strata-oss/pull/24)).

## [0.1.8] - 2026-08-18

### Changed

- Migrated to the `mcp` 2.x SDK (`mcp.server.mcpserver.MCPServer`); dependency pinned to
  `mcp>=2,<3`. No tool behavior changed; all 18 tools register.
  ([#22](https://github.com/G-Schumacher44/strata-oss/pull/22))

## [0.1.7] - 2026-08-18

### Fixed

- PDT ledger status now reports a real `zombie` value (built PDTs whose every consumer is dead
  code); previously such PDTs showed as in use. Adds `zombie_pdt_count` to
  `strata_usage_summary`.
- MCP `initialize` reports Strata's own version in `serverInfo` instead of the SDK's.
- Docs corrected after a claim-by-claim docs-vs-code audit.
  ([#21](https://github.com/G-Schumacher44/strata-oss/pull/21))

## [0.1.6] - 2026-08-17

### Added

- Published to PyPI as `strata-lookml` with trusted publishing, plus a `.mcpb` bundle on each
  GitHub Release and install docs. ([#18](https://github.com/G-Schumacher44/strata-oss/pull/18))
- `strata_find_field` sets a `truncated` flag when results are capped
  ([#9](https://github.com/G-Schumacher44/strata-oss/pull/9), off-by-one fixed in
  [#13](https://github.com/G-Schumacher44/strata-oss/pull/13)).

### Fixed

- Path-traversal bypass in the `strata_render_chart` output allowlist
  ([#10](https://github.com/G-Schumacher44/strata-oss/pull/10)).
- README CI badge and Quick Start point at strata-oss
  ([#17](https://github.com/G-Schumacher44/strata-oss/pull/17)).

[Unreleased]: https://github.com/G-Schumacher44/strata-oss/compare/v0.1.9...HEAD
[0.1.9]: https://github.com/G-Schumacher44/strata-oss/compare/v0.1.8...v0.1.9
[0.1.8]: https://github.com/G-Schumacher44/strata-oss/compare/v0.1.7...v0.1.8
[0.1.7]: https://github.com/G-Schumacher44/strata-oss/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/G-Schumacher44/strata-oss/releases/tag/v0.1.6

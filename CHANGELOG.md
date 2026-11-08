# Changelog

All notable changes to `strata-lookml` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) (pre-1.0: minor versions may break).

## [Unreleased]

### Security

- `strata chart` / `strata-chart` no longer default to the fixed, world-guessable
  `/tmp/strata_chart.html`: the default is a fresh per-invocation `mkstemp` file
  (`strata_chart_*.html`), and the path written is printed. Chart output (CLI, MCP
  `strata_render_chart`, `strata query navigate`) is opened with `O_NOFOLLOW` and refuses a
  symlink at the final path component, so another local user can no longer redirect the write.
- `strata dashboard` now validates the HTTP `Host` header and returns 403 unless it is
  `127.0.0.1:<port>`, `localhost:<port>`, or `[::1]:<port>` for the bound port, closing a
  DNS-rebinding path to the artifact JSON.

### Added

- `strata chart bar|line|scatter|heatmap` take `--x`, `--y` and `--color` to map the template's
  channels onto your own columns, and each subcommand's help lists the template's required
  columns, read from its YAML.
- Shared identifier resolution (`strata_lookml/identifiers.py`) for the CLI and MCP tools. Tables
  resolve by exact name or unique suffix (`orders` -> `analytics.orders`; `strata_impact` echoes
  the resolved name, an ambiguous suffix lists candidates). `model` is optional for explores
  (`strata_explore_deps`, `strata query explore`), and `model.explore` / `view.field` work as one
  argument. `validation_scope` accepts `kind:name`, `{kind, name}`, `.lkml` paths and bare view
  names; `strata query scope` uses the same parser. An unknown model is `not_found`. Old
  positional forms still work.
- `strata check --write-baseline FILE` records the current finding ids (sorted JSON, one list
  per category) and `--baseline FILE` subtracts them before `--fail-on` applies, so a legacy
  repo can gate on new findings only. Stale baseline ids warn (text and `stale_baseline_ids`
  in `--json`); `--json` adds `baselined`; integrity failures are never baselined; an
  unreadable baseline is a usage error (exit 2).

### Changed

- `strata mcp validate` is honest about readiness: it builds the IR graph and reports node counts;
  a missing cache, missing Looker token or unset fixtures are `~` advisories (exit 0, no `✗`),
  while a missing repo, no `.lkml` files, a configured-but-missing or unparseable usage/schema
  fixture, or a graph build error is `✗` and exits 1. New `--json` emits
  `{ready, checks: [{name, status, message, hint}], counts}`. The cache check follows
  `STRATA_CACHE_PATH`.
- The IR cache moves out of the LookML repo: the default is
  `~/.strata/cache/<repo-name>-<sha256(abs repo path)[:12]>.db` (directory 0700, file 0600 on
  POSIX); `--cache` and `STRATA_CACHE_PATH` still win, and `strata build`, the MCP server and
  `strata mcp validate|config` now resolve it in one place (`mcp validate` and `strata build`
  previously ignored `STRATA_CACHE_PATH`). The cache records the repo path, a fingerprint of
  its `.lkml` files (count, newest mtime, total size, paths) and the fixture paths + mtimes it
  was built from, and the MCP server reuses it only when they match and it is younger
  than the max age: `strata build` without fixtures followed by a server start with
  `STRATA_USAGE_FIXTURE` no longer serves a graph with no usage data. `strata clean` removes
  the repo's cache entry, and `--repo` now reads `STRATA_REPO_PATH`. A `--cache` / `STRATA_CACHE_PATH` that is a
  symlink, a `.lkml`/`.lookml` file, a directory or an existing file that is not a Strata IR cache (an unrelated SQLite database included) is refused
  before anything is written (the same guard as `--write-baseline`). Compat: an existing
  `<repo>/strata_ir.db` is ignored (the first run rebuilds into `~/.strata/cache/`); `strata
  clean` deletes it.
- `strata dashboard` falls back to the next free port (8766-8785) when the default 8765 is busy and `--port` was not passed, and prints the URL it bound; the Host allow-list uses the bound port. An explicit `--port` that is busy exits 1 with a clear error.
- `strata lint` is hidden from `--help` and the docs (contributor-only; still invocable).
- `strata validate` resolves the user's project (`CONDUCTOR_PROJECT_ROOT` → configured repo → cwd), never Strata's own tree, and prints real relative paths.
- `strata generate-schema --repo` reads `STRATA_REPO_PATH`.

- `strata bootstrap` is non-interactive-capable and all-or-nothing. Every input is gathered
  before the first write; the writes are a planned list applied with temp file + `os.replace`
  and rolled back (created files removed, overwritten files restored) if any fails. New flags:
  `--yes/-y`, `--bq-project`, `--cost-threshold-gb`, `--set-default-repo/--no-set-default-repo`
  (with `--yes`, default sets `repo_path` only when no `~/.strata/config.json` exists),
  `--usage-fixture`, `--schema-fixture` (written into `.mcp.json` and `.cursor/mcp.json`),
  `--dry-run`. With no terminal and no `--yes` it exits 2 before writing anything, naming
  `--yes`; previously it wrote files and then died on the first prompt.
- `strata mcp config --client claude|cursor [--repo --usage-fixture --schema-fixture]` prints
  the exact client config bootstrap writes (one shared renderer). `strata conductor init`
  uses the same plan/apply path (`plan_conductor_init`).
- **Breaking, MCP output shape** (release will be 0.2.0). The six list tools
  (`strata_list_orphans`, `strata_dead_code_register`, `strata_pdt_costs`,
  `strata_schema_drift`, `strata_list_skills`, `strata_chart_templates`) now return one JSON
  object `{"items": [...], "count": N}` instead of a bare list, which the SDK split into one
  content block per element (concatenated objects like `}{`). The three L1 tools also return
  `usage_checked` (dead code, PDT costs) or `schema_checked` (schema drift) and, when that check
  did not run, a `hint` naming `STRATA_USAGE_FIXTURE` / `STRATA_SCHEMA_FIXTURE`: an empty list
  now says "not checked" instead of looking like a clean result. `strata_usage_summary` gains
  `usage_checked`, `schema_checked` and `hint` (from `analysis_coverage`); `has_l1` is
  deprecated (true on a schema-only build, where `dead_code_count: 0` is not a clean usage
  result) and kept for compatibility. CLI output is unchanged.
- MCP agent-facing descriptions: the server sends `instructions`, every tool parameter has a
  description (and examples where useful), tool descriptions state input format, failure modes
  and prerequisites, and `strata_find_field` takes `limit` (default 50, max 200) and requires a
  `query` of at least 2 characters.
- `strata check` is now a real CI gate. It used to fail any repo without dead code, PDT
  ledger rows and schema drift (a check on Strata's own playgrounds), so a clean repo failed
  and a dirty one passed. It now always fails (exit 1) on integrity: a missing repo or no
  `.lkml` files, an unresolved `extends` (missing target or cycle), or a verdict that breaks
  the evidence contract. Findings are counted and fail the gate only when named in the new
  `--fail-on dead-code,unused-pdt,zombie-pdt,drift|all|none` (default `none`); a category
  without its fixture is a usage error (exit 2). `--json` prints
  `{passed, failures: [{category, id, message}], counts}`. Compat: clean repos now pass, and
  repos with findings still pass by default; to keep failing on findings, add `--fail-on`.
  The playground scenario assertions moved to `tests/test_scenarios.py`; the weekly canary now
  checks out the playground submodules and runs the gate plus those assertions on every
  playground.
- CLI exits non-zero on not-found/invalid input; MCP tool errors now reach the client. Every
  anticipated failure raises one error type (`strata_lookml.errors`: `NotFound`, `InvalidInput`,
  each with a `code`, `message` and `hint`). The CLI prints `Error:` / `Hint:` on stderr and
  exits 1 (`strata query field v nope` and `strata query status --repo /nonexistent` used to
  exit 0); JSON commands also print `{"error", "code", "hint"}` on stdout, where `error` is
  still the message string. Over MCP these come back as `isError: true` with the message: under
  mcp 2.3 a bad `strata_validation_scope` input or `strata_render_chart` path used to reach the
  client only as "Error executing tool …", and an unknown field, explore, table or skill came
  back as a successful result carrying an `error` key or string. `strata_view_sources` now
  rejects an unknown `model` instead of returning no views, an empty repo (no `.lkml` files)
  is an error, and `strata auth status` without a token points at `strata auth login`. Requires
  `mcp>=2.3`.
- `strata dashboard`: the dependency graph is laid out left to right in layers (explores, views,
  PDTs and tables) with column headers. Labels show the short object name, hide when zoomed too far
  out to read, and always show for the hovered or selected node's neighbors. Node kinds have their
  own shapes, problem nodes get a halo, and the graph adds search, per-kind toggles, a "Needs
  attention" filter, zoom-to-selection and clickable upstream and downstream lists. A plain mouse
  wheel scrolls the page; pinch or Cmd/Ctrl+wheel zooms.
- Dashboard layout: section nav, a headline naming the costliest finding, KPI cards ordered by
  severity, sortable tables with sticky headers, one status-color palette shared by nodes, legend
  and chart, and a layout that works down to 390px wide.
- When usage or schema facts were not loaded, the dashboard headline, KPI cards and section empty
  states now say which checks did not run, instead of reporting a clean repo or a 0.
- `strata_usage_summary` (MCP) and the `usage_summary` artifact add `ir_explore_count` (every
  resolved explore), `dead_explore_count`, `dead_view_count` and `active_explore_count`
  (`null` when the usage checks did not run). `explore_count` is unchanged and counts explores
  with a usage row. The dashboard's active-explores KPI now uses `active_explore_count`; it
  previously subtracted dead explores from the usage-row count and could go negative.
- Dashboard graph: changing the search or the "Needs attention" filter clears a pinned
  selection, so the filter's results are what the graph highlights.
- `strata dashboard` serves `dashboard.html` at `/` instead of a directory listing. Artifact JSON
  stays at its own paths, and the `Host` check still applies.

### Fixed

- The dashboard's dependency graph no longer colours every explore green when no usage facts are
  loaded: explores render in a neutral "unknown" state (palette entry, legend swatch, note and
  UNKNOWN badge). With usage loaded, active/dead colouring is unchanged.
- `strata conductor status` and MCP `strata_conductor_status` share one parser; `active_slice` is null when absent instead of capturing prose.
- `strata validate --check-replay` no longer silently reads Strata's own fixture; without a replay file it fails with "pass --replay".

- A chart whose encoding names a column missing from the data (for example `strata chart line`
  on `month`/`revenue` data) used to render a blank chart and exit 0. `render_chart` now raises
  `InvalidInput` listing the missing and the available columns, so the CLI exits 1 and
  `strata_render_chart` returns `isError`. The column check covers single-view charts;
  layered, composite and transform specs are passed to Vega unchecked. Row-count channels
  (`aggregate: count`, field `*`) are skipped, and Vega field paths (`a.b`, `a[0]`, `a\.b`) are
  understood.

- `strata_list_orphans` / `strata query orphans` no longer accept `kind=explore|field`, which always
  returned an empty list (only orphan views are detected); `kind` is now `all|view` and other
  values are rejected with a clear error (#49).
- `strata validate`: the "Active slice file" check takes the first path token of the `Active slice:`
  line in `conductor/index.md`, so an annotated line (`path.md (review — PR open; ...)`) no longer
  fails as a missing file (#47).
- Test-only: the dashboard innerHTML escaping guardrail now scopes a `forEach`/`map` callback's index
  variable to that callback's body instead of the whole enclosing block, so an outer data-derived
  binding with the same name is no longer wrongly treated as safe (#31).

### Documentation

- `docs/reference.md` is now generated by `scripts/gen_reference.py [--check]` from the real CLI
  click tree and the MCP server's `list_tools()`; `tests/test_docs_consistency.py` fails when it
  is stale or when README tool counts disagree with introspection. The hand-kept command table in
  `docs/cli-guide.md` and the signature list in `src/strata_lookml/mcp/AGENTS.md` now link to it.

- Docs now match the code on four claims: `strata mcp` help and GOVERNANCE.md say 17 read-only
  tools plus `strata_render_chart` (writes HTML under `~/.strata/output/` or `/tmp/`), not "18
  read-only"; the Slack/Jira GitHub-secret rows are gone (delivery is not implemented, no workflow
  uses them); Conductor handoffs are described as a process convention, not an audit log; and
  `generate-schema` names the real prerequisite, `gcloud auth login` (the `bq` CLI uses gcloud's
  own credentials, not ADC). No behavior change.

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

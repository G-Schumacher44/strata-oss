# Changelog

All notable changes to `strata-lookml` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) (pre-1.0: minor versions may break).

## [Unreleased]

### Changed

- **BREAKING (Python importers only):** the import package is now `strata_lookml`; through 0.1.8
  it was `strata`. The unrelated PyPI projects `strata` and `strata-mcp` also ship a top-level
  `strata` package, so installing either beside `strata-lookml` overwrote files. Replace
  `import strata` / `from strata.x import y` with `strata_lookml`. The `strata`, `strata-mcp`
  and `strata-chart` commands, the MCP server name, and `~/.strata/` config are unchanged.
  No `strata` compatibility package ships, because it would recreate the collision.
  ([#45](https://github.com/G-Schumacher44/strata-oss/pull/45))
- Package metadata: SPDX `license = "Apache-2.0"` with `license-files` (PEP 639), keywords,
  more classifiers, and Documentation / Changelog project URLs.
- README: absolute links so it renders correctly on PyPI, Quick Start leads with
  `pipx install strata-lookml`, and a no-credentials path for your own LookML repo.

### Added

- Descriptions for the 8 MCP tools that reported an empty description in `tools/list`.
- `strata-mcp --help` / `-h` prints usage and exits instead of starting the stdio server.

### Fixed

- Dashboard: escape the remaining `innerHTML` sinks and harden the escaping guardrail
  ([#30](https://github.com/G-Schumacher44/strata-oss/pull/30)).
- Dashboard: evidence sentences, inlined L1 facts and deep links
  ([#28](https://github.com/G-Schumacher44/strata-oss/pull/28)); rich node detail, honest
  zombie vocabulary, live evidence links, graph layout and drift dedup
  ([#25](https://github.com/G-Schumacher44/strata-oss/pull/25)).
- An invalid `\]` escape in the dashboard HTML template (inside a JavaScript comment) raised a
  `SyntaxWarning` when the module was compiled, and a `SyntaxError` under `-W error`. The
  generated dashboard is byte-identical.
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

[Unreleased]: https://github.com/G-Schumacher44/strata-oss/compare/v0.1.8...HEAD
[0.1.8]: https://github.com/G-Schumacher44/strata-oss/compare/v0.1.7...v0.1.8
[0.1.7]: https://github.com/G-Schumacher44/strata-oss/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/G-Schumacher44/strata-oss/releases/tag/v0.1.6

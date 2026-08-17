# Strata MCP Bundle (.mcpb)

Source for the `.mcpb` bundle attached to each GitHub Release, for one-click
install into Claude Desktop. Built by the the `Build MCP Bundle (.mcpb)` step in `release.yml`'s `build-and-release` job step in
`.github/workflows/release.yml` using Anthropic's `mcpb` CLI
(`@anthropic-ai/mcpb`, spec: <https://github.com/modelcontextprotocol/mcpb>).

## Why a shim, not vendored source

The `.mcpb` spec's `uv` server type (v0.4+) requires a local `entry_point`
file — it does not support pointing directly at a published PyPI package name.
`src/server.py` is a two-line shim: `uv` installs `strata-lookml` from PyPI
per `pyproject.toml` in this directory, and the shim just calls its real
`main()` (`strata.mcp.server:main`, the same function backing the `strata-mcp`
console script). Nothing here duplicates package source.

## Verification status

This bundle's `manifest.json` was authored directly against the current
`modelcontextprotocol/mcpb` spec (fetched and diffed against
`examples/hello-world-uv` at authoring time). It has **not** been round-tripped
through `mcpb validate` / `mcpb pack` locally — the dispatch environment that
wrote this had no outbound network access to install the `mcpb` CLI from npm.
The the `Build MCP Bundle (.mcpb)` step in `release.yml`'s `build-and-release` job CI job installs the real CLI and runs `mcpb validate` before
`mcpb pack`, so a malformed manifest fails that job loudly rather than
shipping a broken bundle silently. First real release tag is the first true
end-to-end proof; spot-check the produced `.mcpb` against Claude Desktop once
before announcing this install path.

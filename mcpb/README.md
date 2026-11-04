# Strata MCP Bundle (.mcpb)

Source for the `.mcpb` bundle attached to each GitHub Release, for one-click
install into Claude Desktop. Built by the `Build MCP Bundle (.mcpb)` step of the `build` job in
`.github/workflows/release.yml` using Anthropic's `mcpb` CLI
(`@anthropic-ai/mcpb`, spec: <https://github.com/modelcontextprotocol/mcpb>).

## Why a shim, not vendored source

The `.mcpb` spec's `uv` server type (v0.4+) requires a local `entry_point`
file — it does not support pointing directly at a published PyPI package name.
`src/server.py` is a small shim: `uv` installs `strata-lookml` from PyPI
per `pyproject.toml` in this directory, and the shim runs that distribution's own
`strata-mcp` console-script entry point. It resolves the entry point rather than
importing a module path, so it works with any pin (the import package was `strata`
through 0.1.8 and is `strata_lookml` after). Nothing here duplicates package source.

## Verification status

The release workflow's `Build MCP Bundle (.mcpb)` step installs the real `mcpb` CLI and runs
`mcpb validate` before `mcpb pack`, so a malformed manifest fails that job instead of shipping a
broken bundle.

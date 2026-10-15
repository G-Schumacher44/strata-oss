# Handoff: feat/registry-readiness

Conductor Mode: patch. Context: research `2026-10-15-positioning-and-adoption.md` (registry + directory readiness). No tool behaviour changed; nothing published.

## What changed
- `README.md`: `mcp-name` token is now `<!-- mcp-name: io.github.G-Schumacher44/strata-oss -->` (was a visible, lower-cased `io.github.g-schumacher44/strata`; registry names are case-sensitive and must equal `server.json` `name`). The ~$45,000/month PDT figure is labelled as hand-authored `enterprise_mono` fixture data.
- `server.json` (new, unpublished): pypi package `strata-lookml` 0.1.8, stdio, `runtimeHint: uvx`.
- `pyproject.toml`: added console script `strata-lookml` (alias of `strata-mcp`) because the registry runs `uvx strata-lookml@<version>`, which needs an executable named after the distribution. Existing commands unchanged.
- `src/strata/mcp/server.py`: all 18 tools get `title` and `ToolAnnotations`. 17 read-only (`readOnlyHint=true`, `destructiveHint=false`, `openWorldHint=false`). `strata_render_chart` is `readOnlyHint=false, destructiveHint=true, idempotentHint=true`: it writes (and may overwrite) one HTML file under `~/.strata/output` or `/tmp`, and the README already calls it the one non-read-only tool. Deviation from "all readOnlyHint true": claiming read-only for a writer would be a false hint.
- Tests: `test_every_tool_has_title_and_explicit_read_only_stance` (allowlist over `list_tools()`, `WRITE_TOOLS` is the only exemption); `test_registry_manifest_matches_package_and_readme` (token matches `server.json` name, versions agree, identifier is a real script). `test_docs_consistency` regex widened for `@server.tool(...)`. Negative controls run: dropping a title, dropping the token each fail.

## Sources (primary)
- Registry PyPI verification, `mcp-name` token rules: modelcontextprotocol/registry `docs/modelcontextprotocol-io/package-types.mdx`
- server.json format and schema `2025-12-11`: `docs/reference/server-json/generic-server-json.md`, `static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`
- GitHub namespace `io.github.<user>/*`: modelcontextprotocol.io/registry/authentication
- Tool `title`, `ToolAnnotations`: MCP spec 2025-11-25 `server/tools` and `schema.ts`
- Claude directory: claude.com/docs/connectors/building/submission (title + readOnlyHint/destructiveHint on every tool; local servers only via a plugin; privacy section required for local connectors)

## Operator steps left (not done here)
1. After merge: bump version to 0.1.9 in `pyproject.toml`, `mcpb/manifest.json`, and `server.json` (both fields) and release to PyPI. The registry reads the README of the PUBLISHED version; 0.1.8 on PyPI carries the old token.
2. `mcp-publisher login github` then `mcp-publisher publish` from the repo root.
3. Claude directory: a plugin bundle (stdio is not accepted as a connector) plus a README "Privacy Policy" section. Not in this PR.
4. Other directories (Glama, Smithery, mcp.so, awesome-mcp-servers) per the research doc.

## Known, predates this PR
- Fresh clones need `git submodule update --init` or `test_pdt_ledger_unused_status_unaffected_by_zombie_detection` fails (fixtures are submodules).

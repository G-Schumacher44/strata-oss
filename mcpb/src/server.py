"""MCP Bundle entry point — launches the strata-lookml MCP server.

`uv` resolves `strata-lookml` from PyPI per mcpb/pyproject.toml at install
time; this shim exists only because the .mcpb `uv` runtime requires a local
entry_point file (see mcpb/README.md).
"""

from strata.mcp.server import main

if __name__ == "__main__":
    main()

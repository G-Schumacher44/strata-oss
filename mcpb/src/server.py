"""MCP Bundle entry point — launches the strata-lookml MCP server.

`uv` resolves `strata-lookml` from PyPI per mcpb/pyproject.toml at install
time; this shim exists only because the .mcpb `uv` runtime requires a local
entry_point file (see mcpb/README.md).

It runs the installed distribution's own `strata-mcp` console script instead
of importing a module path, so it works for any pinned version: through
0.1.8 the import package was `strata`, from 0.1.9 it is `strata_lookml`.
"""

from importlib.metadata import entry_points


def main() -> None:
    matches = [
        ep
        for ep in entry_points(group="console_scripts", name="strata-mcp")
        if ep.dist is not None and ep.dist.name.lower().replace("_", "-") == "strata-lookml"
    ]
    if len(matches) != 1:
        raise SystemExit(
            f"expected one strata-mcp entry point from strata-lookml, found {len(matches)}"
        )
    matches[0].load()()


if __name__ == "__main__":
    main()

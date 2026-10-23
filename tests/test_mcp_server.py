from importlib.metadata import version as pkg_version
from pathlib import Path

from strata_lookml.ir.resolver import build_resolved_graph
from strata_lookml.mcp.server import _server_version, create_server

FIXTURES = Path(__file__).parent / "fixtures"


def test_server_version_matches_installed_package():
    assert _server_version() == pkg_version("strata-lookml")


def test_every_registered_tool_has_a_description():
    # Over the real registry (list_tools), so a new tool without a docstring fails here:
    # an empty description gives the client model nothing to choose the tool by.
    import asyncio

    tools = asyncio.run(create_server(build_resolved_graph(FIXTURES)).list_tools())
    assert len(tools) >= 18
    missing = [tool.name for tool in tools if not (tool.description or "").strip()]
    assert not missing, f"tools without a description: {missing}"


def test_help_prints_usage_without_starting_the_server(tmp_path):
    import os
    import subprocess
    import sys

    env = {**os.environ, "STRATA_REPO_PATH": str(tmp_path / "no-such-repo")}
    for flag in ("--help", "-h"):
        result = subprocess.run(
            [sys.executable, "-m", "strata_lookml.mcp.server", flag],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith("usage: strata-mcp"), result.stdout
        assert "Starting Strata MCP server" not in result.stderr


def test_server_reports_package_version_not_sdk_version():
    graph = build_resolved_graph(FIXTURES)
    server = create_server(graph)

    installed = pkg_version("strata-lookml")
    sdk_version = pkg_version("mcp")

    # mcp 2.x exposes the version publicly (it's a first-class MCPServer kwarg) —
    # no more reaching into the 1.x private _mcp_server.
    assert server.version == installed
    assert server.version != sdk_version

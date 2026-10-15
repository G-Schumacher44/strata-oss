from importlib.metadata import version as pkg_version
from pathlib import Path

from strata.ir.resolver import build_resolved_graph
from strata.mcp.server import _server_version, create_server

FIXTURES = Path(__file__).parent / "fixtures"


def test_server_version_matches_installed_package():
    assert _server_version() == pkg_version("strata-lookml")


def test_server_reports_package_version_not_sdk_version():
    graph = build_resolved_graph(FIXTURES)
    server = create_server(graph)

    installed = pkg_version("strata-lookml")
    sdk_version = pkg_version("mcp")

    # mcp 2.x exposes the version publicly (it's a first-class MCPServer kwarg) —
    # no more reaching into the 1.x private _mcp_server.
    assert server.version == installed
    assert server.version != sdk_version


# --- Directory / registry readiness -------------------------------------------------------
# Allowlist invariants over the REAL registry (list_tools), so a newly added tool is
# rejected until it declares a title and a read-only stance. Sources: MCP spec 2025-11-25
# (Tool.title, ToolAnnotations.readOnlyHint); Claude directory submission requires every
# tool to carry a title plus readOnlyHint/destructiveHint.

# The only tool permitted to be non-read-only: writes one HTML file under ~/.strata/output
# or /tmp. Adding to this set is a deliberate review decision.
WRITE_TOOLS = {"strata_render_chart"}


def _registered_tools():
    import asyncio

    server = create_server(build_resolved_graph(FIXTURES))
    return asyncio.run(server.list_tools())


def test_every_tool_has_title_and_explicit_read_only_stance():
    tools = _registered_tools()
    assert len(tools) >= 18
    for tool in tools:
        assert tool.title and tool.title != tool.name, f"{tool.name}: missing human title"
        assert tool.annotations is not None, f"{tool.name}: missing annotations"
        assert tool.annotations.read_only_hint is not None, f"{tool.name}: readOnlyHint unset"
        expected_read_only = tool.name not in WRITE_TOOLS
        assert tool.annotations.read_only_hint is expected_read_only, tool.name
        assert tool.annotations.destructive_hint is not None, f"{tool.name}: destructiveHint"
        assert tool.annotations.destructive_hint is (not expected_read_only), tool.name


def test_registry_manifest_matches_package_and_readme():
    import json
    import re
    import tomllib

    root = FIXTURES.parents[1]
    manifest = json.loads((root / "server.json").read_text(encoding="utf-8"))
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    readme = (root / "README.md").read_text(encoding="utf-8")

    # PyPI ownership proof: the README that PyPI renders must carry the exact
    # `mcp-name: <server.json name>` token followed by a boundary (registry docs).
    assert re.search(rf"mcp-name: {re.escape(manifest['name'])}(?:\s|<|-->)", readme), (
        "README missing mcp-name token matching server.json name"
    )
    pkg = manifest["packages"][0]
    assert pkg["registryType"] == "pypi" and pkg["identifier"] == project["name"]
    mcpb = json.loads((root / "mcpb" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == pkg["version"] == project["version"] == mcpb["version"]
    # `uvx <identifier>` must resolve to an executable of that name.
    assert pkg["identifier"] in project["scripts"]
    assert len(manifest["description"]) <= 100

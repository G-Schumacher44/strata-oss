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

    assert server._mcp_server.version == installed
    assert server._mcp_server.version != sdk_version

"""Shared identifier resolution (identifiers.py): one answer for the CLI and the MCP tools."""

import json

import pytest
from click.testing import CliRunner

from strata_lookml.cli.main import strata_cli as cli
from strata_lookml.errors import InvalidInput, NotFound
from strata_lookml.identifiers import resolve_field
from strata_lookml.ir.resolver import build_resolved_graph
from strata_lookml.mcp.tools import (
    strata_explore_deps,
    strata_impact,
    strata_object,
    strata_query_field,
    strata_validation_scope,
    strata_view_sources,
)
from tests.test_mcp_tools import FIXTURES

_VIEW = """view: {name} {{
  sql_table_name: {table} ;;
  dimension: id {{
    type: number
    sql: ${{TABLE}}.id ;;
  }}
}}
"""
_MODEL = """connection: "c"
include: "*.view.lkml"
explore: orders {{
  from: {view}
}}
"""


@pytest.fixture(scope="module")
def ambiguous_repo(tmp_path_factory):
    """Two datasets with an `orders` table, and an `orders` explore in two models."""
    repo = tmp_path_factory.mktemp("ambiguous")
    (repo / "orders_a.view.lkml").write_text(_VIEW.format(name="orders_a", table="sales.orders"))
    (repo / "orders_b.view.lkml").write_text(_VIEW.format(name="orders_b", table="ops.orders"))
    (repo / "a.model.lkml").write_text(_MODEL.format(view="orders_a"))
    (repo / "b.model.lkml").write_text(_MODEL.format(view="orders_b"))
    return repo


@pytest.fixture(scope="module")
def graph():
    return build_resolved_graph(FIXTURES)


def test_short_table_resolves_and_echoes(graph):
    result = strata_impact(graph, "orders")

    assert result["physical_table"] == "analytics.orders"
    assert result["resolved_from"] == "orders"
    assert result["views"] == strata_impact(graph, "analytics.orders")["views"]
    assert strata_impact(graph, "analytics.orders")["resolved_from"] is None


def test_ambiguous_table_suffix_lists_candidates(ambiguous_repo):
    graph = build_resolved_graph(ambiguous_repo)

    with pytest.raises(InvalidInput, match=r"ambiguous.*ops\.orders, sales\.orders"):
        strata_impact(graph, "orders")
    assert strata_impact(graph, "ops.orders")["views"] == ["orders_b"]


def test_unknown_table_is_not_found(graph):
    with pytest.raises(NotFound):
        strata_impact(graph, "nope")


def test_explore_deps_without_model(graph):
    deps = strata_explore_deps(graph, "refined_customer")

    assert deps["model"] == "refined_explore"
    assert deps == strata_explore_deps(graph, "refined_customer", "refined_explore")
    assert deps == strata_explore_deps(graph, "refined_explore.refined_customer")


def test_explore_unknown_model_and_explore(graph):
    with pytest.raises(NotFound, match="model not found"):
        strata_explore_deps(graph, "customer", "nope")
    with pytest.raises(NotFound, match="explore not found"):
        strata_explore_deps(graph, "customer", "refined_explore")
    with pytest.raises(NotFound, match="explore not found"):
        strata_explore_deps(graph, "nope")


def test_field_as_one_argument(graph):
    assert strata_query_field(graph, "customer_extended.email") == strata_query_field(
        graph, "customer_extended", "email"
    )
    with pytest.raises(InvalidInput, match="view.field"):
        strata_query_field(graph, "customer_extended")


def test_field_on_a_dotted_view_resolves_by_the_longest_known_view(tmp_path):
    """G17: `view.field` splits after the longest view name it starts with, not the first dot."""
    (tmp_path / "v.view.lkml").write_text(
        'view: "sales.orders" { dimension: id { sql: 1 ;; } }\n'
        "view: sales { dimension: id { sql: 2 ;; } }\n"
    )
    (tmp_path / "m.model.lkml").write_text('connection: "c"\ninclude: "*.view.lkml"\n')
    g = build_resolved_graph(tmp_path)
    assert resolve_field("sales.orders.id", graph=g) == ("sales.orders", "id")
    assert resolve_field("sales.id", graph=g) == ("sales", "id")
    assert strata_query_field(g, "sales.orders.id")["sql"] == "1"
    assert strata_object(g, "field", "sales.orders.id")["id"] == "field:sales.orders.id"
    # Without the graph (or with no view as a prefix) it still splits at the first dot.
    assert resolve_field("sales.orders.id") == ("sales", "orders.id")
    assert resolve_field("nope.x", graph=g) == ("nope", "x")


def test_view_sources_unknown_model_is_not_found(graph):
    with pytest.raises(NotFound, match="model not found"):
        strata_view_sources(graph, "nope")


@pytest.mark.parametrize(
    "changed",
    [
        "customer_extended.view.lkml",
        "views/customer_extended.view.lkml",
        "view:customer_extended",
        "customer_extended",
        {"kind": "view", "name": "customer_extended"},
    ],
)
def test_validation_scope_accepts_every_form(graph, changed):
    scope = strata_validation_scope(graph, [changed])

    assert scope["unmatched"] == []
    assert scope["changed"] == [{"kind": "view", "name": "customer_extended"}]
    assert "refined_customer" in [e["explore"] for e in scope["explores"]]


def test_validation_scope_model_path_is_a_model():
    from strata_lookml.identifiers import parse_changed

    assert parse_changed("x/test_model.model.lkml") == ("model", "test_model")
    assert parse_changed("x/y.explore.lkml") == ("explore", "y")
    with pytest.raises(InvalidInput):
        parse_changed("view:")


def _cli(*args):
    result = CliRunner().invoke(cli, ["query", *args])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def _norm(value):
    return json.loads(json.dumps(value, default=str))


@pytest.mark.parametrize(
    ("command", "cli_args", "tool", "tool_args"),
    [
        ("impact", ["orders"], strata_impact, ("orders",)),
        ("explore", ["refined_customer"], strata_explore_deps, ("refined_customer",)),
        (
            "explore",
            ["refined_explore.refined_customer"],
            strata_explore_deps,
            ("refined_explore.refined_customer",),
        ),
        ("field", ["customer_extended.email"], strata_query_field, ("customer_extended.email",)),
        (
            "field",
            ["customer_extended", "email"],
            strata_query_field,
            ("customer_extended", "email"),
        ),
    ],
)
def test_cli_matches_mcp_tool(graph, command, cli_args, tool, tool_args):
    out = _cli(command, *cli_args, "--repo", str(FIXTURES))

    assert out == _norm(tool(graph, *tool_args))


@pytest.mark.parametrize(
    "files",
    [["views/customer_extended.view.lkml"], ["view:customer_extended"], ["customer_extended"]],
)
def test_cli_scope_matches_mcp_tool(graph, files):
    out = _cli("scope", *files, "--repo", str(FIXTURES))

    assert out == _norm(strata_validation_scope(graph, files))


def test_cli_ambiguous_exits_nonzero_with_candidates(ambiguous_repo):
    result = CliRunner().invoke(cli, ["query", "impact", "orders", "--repo", str(ambiguous_repo)])

    assert result.exit_code == 1
    assert "ops.orders" in result.output and "sales.orders" in result.output

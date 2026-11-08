"""Explores are keyed by model (N9): same-named explores in two models stay two explores."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from strata_lookml.cli.main import strata_cli
from strata_lookml.errors import InvalidInput
from strata_lookml.ir.resolver import build_resolved_graph
from strata_lookml.ir.store import describe_inputs, save_ir
from strata_lookml.l1.enrich import enrich_graph
from strata_lookml.l1.types import ContentReference, ExploreUsage
from strata_lookml.mcp.tools import strata_explore_deps
from strata_lookml.outputs.dashboard import _build_graph_data
from strata_lookml.pipeline import load_or_build

TWIN = Path(__file__).resolve().parent / "lookml" / "twin_models"


@pytest.fixture
def graph():
    return build_resolved_graph(TWIN)


def _explores(graph):
    return {
        node.id: (node.attrs["base_view"], [join["name"] for join in node.attrs["joins"]])
        for node in graph.nodes_by_kind("explore")
    }


def test_same_named_explores_in_two_models_are_two_nodes(graph):
    # Keyed by name, wholesale's `orders` became a refinement of retail's: one node with
    # wholesale's base view and join, and retail_orders reported as an orphan.
    assert _explores(graph) == {
        "explore:retail:orders": ("retail_orders", []),
        "explore:wholesale:orders": ("wholesale_orders", ["accounts"]),
    }
    assert graph.nodes["explore:wholesale:orders"].attrs["resolution_chain"] == [
        "orders",
        "+orders",
    ]
    assert graph.metadata["orphans"] == []
    assert graph.metadata["resolution_errors"] == []


def test_dead_code_and_usage_stay_per_model(graph):
    enrich_graph(
        graph,
        explore_usage=[ExploreUsage("retail", "orders", 40)],
        content_references=[ContentReference("1", "dashboard", "retail", "orders")],
    )
    dead = {(item["kind"], item["name"]) for item in graph.metadata["l1"]["dead_code"]}
    assert dead == {
        ("explore", "wholesale.orders"),
        ("view", "wholesale_orders"),
        ("view", "accounts"),
    }

    nodes = {n["data"]["id"]: n["data"] for n in _build_graph_data(graph)["nodes"]}
    retail, wholesale = nodes["explore:retail:orders"], nodes["explore:wholesale:orders"]
    assert (retail["label"], retail["status"], retail["query_count"]) == (
        "retail.orders",
        "active",
        40,
    )
    assert (wholesale["label"], wholesale["status"]) == ("wholesale.orders", "dead")
    assert nodes["view:accounts"]["label"] == "accounts"


def test_bare_name_is_ambiguous_and_the_model_resolves_it(graph):
    with pytest.raises(InvalidInput, match=r"ambiguous.*retail\.orders, wholesale\.orders"):
        strata_explore_deps(graph, "orders")
    assert strata_explore_deps(graph, "orders", "retail")["base_view"] == "retail_orders"
    assert strata_explore_deps(graph, "wholesale.orders")["base_view"] == "wholesale_orders"

    result = CliRunner().invoke(strata_cli, ["query", "explore", "orders", "--repo", str(TWIN)])
    assert result.exit_code == 1
    assert "retail.orders" in result.output and "wholesale.orders" in result.output


def test_shared_explore_file_is_a_fallback_for_every_model(tmp_path):
    # An explore outside a model file (an included .explore.lkml) is a base both models can
    # extend; each model's refinement of its own `orders` stays in that model.
    (tmp_path / "base.explore.lkml").write_text(
        "explore: orders_base {\n  extension: required\n  join: accounts {}\n}\n"
    )
    for model in ("a", "b"):
        (tmp_path / f"{model}.model.lkml").write_text(
            "explore: orders {\n  extends: [orders_base]\n}\n"
            f"explore: +orders {{\n  join: only_{model} {{}}\n}}\n"
        )
    graph = build_resolved_graph(tmp_path)

    assert _explores(graph) == {
        "explore::orders_base": ("orders_base", ["accounts"]),
        "explore:a:orders": ("orders", ["accounts", "only_a"]),
        "explore:b:orders": ("orders", ["accounts", "only_b"]),
    }
    assert graph.metadata["resolution_errors"] == []


def test_a_cache_from_the_name_keyed_resolver_is_rebuilt(tmp_path, monkeypatch):
    # The cache reuses a graph when its recorded inputs match; a cache written before IR_FORMAT
    # has the same .lkml fingerprint, so without the marker it would serve the merged graph.
    monkeypatch.setenv("HOME", str(tmp_path))
    cache = tmp_path / "ir.db"
    merged = build_resolved_graph(TWIN)
    del merged.nodes["explore:wholesale:orders"]
    old_inputs = {k: v for k, v in describe_inputs(TWIN).items() if k != "ir_format"}
    save_ir(merged, cache, old_inputs)

    graph = load_or_build(TWIN, None, None, cache, max_age_seconds=3600)

    assert set(_explores(graph)) == {"explore:retail:orders", "explore:wholesale:orders"}

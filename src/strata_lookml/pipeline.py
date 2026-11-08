"""Shared offline build pipeline for IR, L1 enrichment, synthesis, and outputs."""

from __future__ import annotations

from pathlib import Path

from strata_lookml.ir.parser import lkml_paths
from strata_lookml.ir.resolver import build_resolved_graph
from strata_lookml.ir.store import cache_is_fresh, describe_inputs, load_ir, save_ir
from strata_lookml.ir.types import IRGraph
from strata_lookml.l1.enrich import enrich_graph
from strata_lookml.l1.fixtures import load_usage_facts
from strata_lookml.l1.looker import LookerSystemActivityProvider
from strata_lookml.l1.provider import UsageFacts, UsageProvider
from strata_lookml.l1.schema import (
    SchemaFacts,
    SchemaProvider,
    enrich_schema_drift,
    load_schema_facts,
)

_REPO_HINT = "Pass --repo or set STRATA_REPO_PATH to the LookML project root."


def _repo_graph(repo_path: str | Path) -> IRGraph:
    """The resolved IR for a LookML repo; every pipeline entry point builds through here."""
    # Imported at raise time: errors.py subclasses the MCP SDK's ToolError, and importing the
    # SDK pulls httpx into the L0 import graph (test_l0_no_network_imports guards that).
    root = Path(repo_path)
    if not root.is_dir():
        from strata_lookml.errors import NotFound

        raise NotFound(f"LookML repo not found: {root}", hint=_REPO_HINT)
    if not lkml_paths(root):
        from strata_lookml.errors import InvalidInput

        raise InvalidInput(f"no .lkml files under {root}", hint=_REPO_HINT)
    return build_resolved_graph(root)


def build_graph(
    repo_path: str | Path,
    usage_fixture: str | Path | None = None,
    schema_fixture: str | Path | None = None,
) -> IRGraph:
    graph = _repo_graph(repo_path)
    if usage_fixture:
        facts = load_usage_facts(usage_fixture)
        graph = enrich_graph(graph, **facts)
    if schema_fixture:
        graph = enrich_schema_drift(graph, load_schema_facts(schema_fixture))
    return graph


def build_and_cache(
    repo_path: str | Path,
    usage_fixture: str | Path | None,
    schema_fixture: str | Path | None,
    cache_path: str | Path,
) -> IRGraph:
    """Build the graph and write it to the IR cache along with the inputs it was built from."""
    # Inputs (fixture mtimes) are read before the build: a fixture edited mid-build must not
    # be recorded as already loaded.
    inputs = describe_inputs(repo_path, usage_fixture, schema_fixture)
    graph = build_graph(repo_path, usage_fixture, schema_fixture)
    save_ir(graph, cache_path, inputs)
    return graph


def load_or_build(
    repo_path: str | Path,
    usage_fixture: str | Path | None,
    schema_fixture: str | Path | None,
    cache_path: str | Path,
    max_age_seconds: float,
) -> IRGraph:
    """Reuse the cache only if it was built from these exact inputs and is young enough."""
    inputs = describe_inputs(repo_path, usage_fixture, schema_fixture)
    if cache_is_fresh(cache_path, inputs, max_age_seconds):
        return load_ir(cache_path)
    return build_and_cache(repo_path, usage_fixture, schema_fixture, cache_path)


def build_graph_with_provider(repo_path: str | Path, provider: UsageProvider) -> IRGraph:
    graph = _repo_graph(repo_path)
    facts = UsageFacts.from_provider(provider)
    mapping = facts.to_mapping()
    return enrich_graph(
        graph,
        explore_usage=mapping.get("explore_usage"),
        content_references=mapping.get("content_references"),
        pdt_builds=mapping.get("pdt_builds"),
        period=mapping.get("period"),
    )


def build_graph_with_schema_provider(repo_path: str | Path, provider: SchemaProvider) -> IRGraph:
    graph = _repo_graph(repo_path)
    facts = SchemaFacts.from_provider(provider)
    return enrich_schema_drift(graph, facts)


def build_graph_from_looker(
    repo_path: str | Path,
    looker_url: str | None = None,
    days: int = 30,
    schema_fixture: str | Path | None = None,
) -> IRGraph:
    graph = build_graph_with_provider(
        repo_path, LookerSystemActivityProvider.from_config(looker_url, days=days)
    )
    if schema_fixture:
        graph = enrich_schema_drift(graph, load_schema_facts(schema_fixture))
    return graph

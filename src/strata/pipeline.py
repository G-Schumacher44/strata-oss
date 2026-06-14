"""Shared offline build pipeline for IR, L1 enrichment, synthesis, and outputs."""

from __future__ import annotations

from pathlib import Path

from strata.ir.resolver import build_resolved_graph
from strata.ir.types import IRGraph
from strata.l1.enrich import enrich_graph
from strata.l1.fixtures import load_usage_facts
from strata.l1.looker import LookerSystemActivityProvider
from strata.l1.provider import UsageFacts, UsageProvider
from strata.l1.schema import SchemaFacts, SchemaProvider, enrich_schema_drift, load_schema_facts


def build_graph(
    repo_path: str | Path,
    usage_fixture: str | Path | None = None,
    schema_fixture: str | Path | None = None,
) -> IRGraph:
    graph = build_resolved_graph(repo_path)
    if usage_fixture:
        facts = load_usage_facts(usage_fixture)
        graph = enrich_graph(graph, **facts)
    if schema_fixture:
        graph = enrich_schema_drift(graph, load_schema_facts(schema_fixture))
    return graph


def build_graph_with_provider(repo_path: str | Path, provider: UsageProvider) -> IRGraph:
    graph = build_resolved_graph(repo_path)
    facts = UsageFacts.from_provider(provider)
    mapping = facts.to_mapping()
    return enrich_graph(
        graph,
        explore_usage=mapping.get("explore_usage"),
        content_references=mapping.get("content_references"),
        pdt_builds=mapping.get("pdt_builds"),
    )


def build_graph_with_schema_provider(repo_path: str | Path, provider: SchemaProvider) -> IRGraph:
    graph = build_resolved_graph(repo_path)
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

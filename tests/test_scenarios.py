"""Scenario assertions: each bundled playground still exhibits the signals it was built to show.

These used to live inside `strata check`, which failed any repo without dead code, PDT
ledger rows and schema drift. They describe Strata's fixtures, not a user's repo, so they
are tests; `strata check` itself is the user-facing gate (`tests/test_cli.py`).
"""

from pathlib import Path

import pytest

from strata_lookml.cli.check import evaluate_gate
from strata_lookml.pipeline import build_graph

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"

# (repo, usage facts, schema facts, the finding categories it must produce)
PLAYGROUNDS = {
    "fixtures": (
        FIXTURES,
        "usage_facts.json",
        "schema_facts_drift.json",
        {"dead-code", "unused-pdt", "drift"},
    ),
    "gcs_analytics": (
        ROOT / "tests" / "lookml" / "gcs_analytics",
        "gcs_usage_facts.json",
        "gcs_schema_facts.json",
        {"dead-code", "unused-pdt", "drift"},
    ),
    "thelook": (
        ROOT / "tests" / "lookml" / "thelook",
        "playground_usage_facts.json",
        "playground_schema_facts.json",
        {"dead-code", "zombie-pdt", "drift"},
    ),
    "enterprise_mono": (
        ROOT / "tests" / "lookml" / "enterprise_mono",
        "enterprise_usage_facts.json",
        "enterprise_schema_facts.json",
        {"dead-code", "zombie-pdt", "drift"},
    ),
}


@pytest.mark.parametrize("name", sorted(PLAYGROUNDS))
def test_playground_scenario(name):
    repo, usage, schema, expected = PLAYGROUNDS[name]
    graph = build_graph(repo, FIXTURES / usage, FIXTURES / schema)
    result = evaluate_gate(graph, fail_on=set())

    assert result["passed"], result["failures"]
    assert graph.metadata["l1"]["pdt_ledger"], "expected at least one PDT ledger record"
    present = {category for category, count in result["counts"].items() if count}
    assert expected <= present, f"{name} lost a scenario signal: {expected - present}"

import json
import subprocess
import sys
from pathlib import Path

from strata.ir.resolver import build_resolved_graph
from strata.outputs import build_artifacts
from strata.validation import validation_scope

FIXTURES = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[1]


def test_changed_view_returns_only_impacted_explores():
    graph = build_resolved_graph(FIXTURES)

    scope = validation_scope(graph, [{"kind": "view", "name": "customer_extended"}])

    assert scope["unmatched"] == []
    assert scope["explores"] == [
        {
            "model": "refined_explore",
            "explore": "refined_customer",
            "impacted_views": ["customer_extended"],
            "changed_inputs": ["view:customer_extended"],
        },
        {
            "model": "test_model",
            "explore": "customer",
            "impacted_views": ["customer_extended"],
            "changed_inputs": ["view:customer_extended"],
        },
    ]


def test_changed_physical_table_includes_pdt_impacted_explore():
    graph = build_resolved_graph(FIXTURES)

    scope = validation_scope(graph, [{"kind": "physical_table", "name": "analytics.orders"}])

    assert scope["explores"] == [
        {
            "model": "pdt_validation",
            "explore": "pdt_scope",
            "impacted_views": ["pdt_scope_orders"],
            "changed_inputs": ["physical_table:analytics.orders"],
        }
    ]


def test_validation_scope_dedupes_and_reports_unmatched():
    graph = build_resolved_graph(FIXTURES)
    changed = json.loads((FIXTURES / "validation_scope_changed.json").read_text(encoding="utf-8"))[
        "changed"
    ]

    scope = validation_scope(graph, changed)

    assert [item["explore"] for item in scope["explores"]] == [
        "pdt_scope",
        "refined_customer",
        "customer",
    ]
    assert scope["explores"][1]["changed_inputs"] == ["view:customer_extended"]
    assert scope["unmatched"] == [{"kind": "physical_table", "name": "analytics.missing"}]


def test_validation_scope_surfaces_in_artifacts_and_cli(tmp_path):
    graph = build_resolved_graph(FIXTURES)
    graph.metadata["validation_scope_inputs"] = [{"kind": "view", "name": "customer_extended"}]

    assert (
        build_artifacts(graph)["validation_scope"]["explores"][0]["explore"] == "refined_customer"
    )

    out = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "strata.cli.main",
            "outputs",
            "--repo",
            str(FIXTURES),
            "--validation-scope-fixture",
            str(FIXTURES / "validation_scope_changed.json"),
            "--out",
            str(out),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    written = json.loads(result.stdout)
    payload = json.loads(Path(written["validation_scope"]).read_text(encoding="utf-8"))
    assert [item["explore"] for item in payload["explores"]] == [
        "pdt_scope",
        "refined_customer",
        "customer",
    ]

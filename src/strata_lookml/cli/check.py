"""strata check — the offline CI gate for a LookML repo."""

from __future__ import annotations

import json
from typing import Any

import click

from strata_lookml.cli._contract import JsonCommand
from strata_lookml.ir.types import IRGraph

INTEGRITY = "integrity"
# Opt-in finding categories, each with the fixture its signal is computed from.
FINDING_CATEGORIES: dict[str, str] = {
    "dead-code": "--usage-fixture",
    "unused-pdt": "--usage-fixture",
    "zombie-pdt": "--usage-fixture",
    "drift": "--schema-fixture",
}


def _parse_fail_on(value: str) -> set[str]:
    """`--fail-on` → the finding categories that fail the gate (integrity always does)."""
    names = {part.strip() for part in value.split(",") if part.strip()}
    if names == {"none"}:
        return set()
    if names == {"all"}:
        return set(FINDING_CATEGORIES)
    unknown = names - set(FINDING_CATEGORIES)
    if unknown or not names:
        allowed = ", ".join([*FINDING_CATEGORIES, "all", "none"])
        raise click.BadParameter(
            f"unknown category {', '.join(sorted(unknown)) or repr(value)} (choose from {allowed})",
            param_hint="--fail-on",
        )
    return names


def _integrity_failures(graph: IRGraph) -> list[dict[str, str]]:
    from strata_lookml.synthesis.slices import build_explore_slice
    from strata_lookml.synthesis.verdicts import deterministic_verdict, validate_verdict

    failures: list[dict[str, str]] = []
    for error in graph.metadata.get("resolution_errors", []):
        subject = error.get("name") or "→".join(error.get("chain", []))
        failures.append(
            {
                "category": INTEGRITY,
                "id": f"resolution:{error['kind']}:{error['type']}:{subject}",
                "message": f"{error['kind']} {error['type'].replace('_', ' ')}: {subject}",
            }
        )
    for node in graph.nodes_by_kind("explore"):
        explore_slice = build_explore_slice(graph, node.attrs["model"], node.name)
        verdict = deterministic_verdict(explore_slice)
        for message in validate_verdict(verdict, explore_slice["evidence_ids"]):
            failures.append({"category": INTEGRITY, "id": node.id, "message": message})
    return failures


def _findings(graph: IRGraph) -> dict[str, list[dict[str, str]] | None]:
    """Every finding category's records, or None where its fixture was not loaded."""
    l1 = graph.metadata.get("l1", {})
    findings: dict[str, list[dict[str, str]] | None] = dict.fromkeys(FINDING_CATEGORIES)
    if "dead_code" in l1:
        findings["dead-code"] = [
            {"category": "dead-code", "id": r["id"], "message": r["usage_reason"]}
            for r in l1["dead_code"]
        ]
        for status in ("unused", "zombie"):
            findings[f"{status}-pdt"] = [
                {
                    "category": f"{status}-pdt",
                    "id": f"pdt:{r['view']}",
                    "message": f"{status} PDT, {r['build_count']} builds",
                }
                for r in l1["pdt_ledger"]
                if r["status"] == status
            ]
    if "schema_drift" in l1:
        findings["drift"] = [
            {"category": "drift", "id": r["id"], "message": r["reason"]} for r in l1["schema_drift"]
        ]
    return findings


def evaluate_gate(graph: IRGraph, fail_on: set[str]) -> dict[str, Any]:
    """The gate result: `{passed, failures, counts}`.

    Integrity failures always fail; a finding category fails only when named in `fail_on`.
    `counts` has every category; a finding category whose fixture was not loaded is null.
    """
    integrity = _integrity_failures(graph)
    findings = _findings(graph)
    failures = integrity + [f for c in sorted(fail_on) for f in findings[c] or []]
    failures.sort(key=lambda f: (f["category"], f["id"], f["message"]))
    counts: dict[str, int | None] = {INTEGRITY: len(integrity)}
    counts.update({c: None if r is None else len(r) for c, r in findings.items()})
    return {"passed": not failures, "failures": failures, "counts": counts}


@click.command("check", cls=JsonCommand)
@click.option(
    "--repo",
    default=None,
    envvar="STRATA_REPO_PATH",
    show_envvar=True,
    help="Path to LookML repo (defaults to cwd)",
)
@click.option(
    "--usage-fixture",
    default=None,
    envvar="STRATA_USAGE_FIXTURE",
    show_envvar=True,
    help="Usage facts JSON — explore query counts and PDT build costs.",
)
@click.option(
    "--schema-fixture",
    default=None,
    envvar="STRATA_SCHEMA_FIXTURE",
    show_envvar=True,
    help="Schema facts JSON — warehouse column inventory for drift detection.",
)
@click.option(
    "--fail-on",
    "fail_on_raw",
    default="none",
    show_default=True,
    metavar="CATEGORIES",
    help=(
        "Comma-separated finding categories that also fail the gate: dead-code, unused-pdt, "
        "zombie-pdt, drift; or all / none. dead-code and the PDT categories need "
        "--usage-fixture; drift needs --schema-fixture."
    ),
)
@click.option("--json", "as_json", is_flag=True, help="Print {passed, failures, counts} as JSON")
def check(
    repo: str | None,
    usage_fixture: str | None,
    schema_fixture: str | None,
    fail_on_raw: str,
    as_json: bool,
) -> None:
    """Gate a LookML repo in CI: exit 0 pass, 1 gate failed, 2 usage error.

    Always fails on integrity: a missing repo or no .lkml files, unresolved extends
    (missing target, cycle), or a verdict that breaks the evidence contract. Findings
    (dead code, unused/zombie PDTs, schema drift) are reported but fail only the
    categories named in --fail-on.

    \b
    strata check --repo . --usage-fixture usage_facts.json
    strata check --repo . --schema-fixture schema_facts.json --fail-on drift
    """
    from pathlib import Path

    from strata_lookml.pipeline import build_graph

    fail_on = _parse_fail_on(fail_on_raw)
    loaded = {"--usage-fixture": usage_fixture, "--schema-fixture": schema_fixture}
    for category in sorted(fail_on):
        needed = FINDING_CATEGORIES[category]
        if not loaded[needed]:
            raise click.UsageError(f"--fail-on {category} needs {needed}")

    _repo = Path(repo).expanduser().resolve() if repo else Path.cwd()
    result = evaluate_gate(build_graph(str(_repo), usage_fixture, schema_fixture), fail_on)

    if as_json:
        click.echo(json.dumps(result, indent=2, sort_keys=True))
    else:
        for failure in result["failures"]:
            click.secho(
                f"FAIL [{failure['category']}] {failure['id']}: {failure['message']}",
                fg="red",
                err=True,
            )
        summary = ", ".join(
            f"{c} {'not checked' if n is None else n}" for c, n in result["counts"].items()
        )
        if result["passed"]:
            click.secho(f"Strata check passed ({summary}).", fg="green")
        else:
            click.secho(f"Strata check failed ({summary}).", fg="red", err=True)
    if not result["passed"]:
        raise SystemExit(1)

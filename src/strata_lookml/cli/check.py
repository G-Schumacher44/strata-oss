"""strata check — the offline CI gate for a LookML repo."""

from __future__ import annotations

import json

import click

from strata_lookml.cli._contract import JsonCommand
from strata_lookml.errors import InvalidInput
from strata_lookml.gate import (
    FINDING_CATEGORIES,
    BaselineError,
    evaluate_gate,
    load_baseline,
    write_baseline,
)


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
@click.option(
    "--baseline",
    "baseline_path",
    default=None,
    type=click.Path(dir_okay=False),
    help="Baseline file: known finding ids are ignored, so only NEW findings fail --fail-on.",
)
@click.option(
    "--write-baseline",
    "write_baseline_path",
    default=None,
    type=click.Path(dir_okay=False),
    help="Write the current findings' ids to this baseline file (sorted JSON), then gate.",
)
@click.option("--json", "as_json", is_flag=True, help="Print {passed, failures, counts} as JSON")
def check(
    repo: str | None,
    usage_fixture: str | None,
    schema_fixture: str | None,
    fail_on_raw: str,
    baseline_path: str | None,
    write_baseline_path: str | None,
    as_json: bool,
) -> None:
    """Gate a LookML repo in CI: exit 0 pass, 1 gate failed, 2 usage error.

    Always fails on integrity: a missing repo or no .lkml files, unresolved extends
    (missing target, cycle), or a verdict that breaks the evidence contract. Findings
    (dead code, unused/zombie PDTs, schema drift) are reported but fail only the
    categories named in --fail-on. On a legacy repo, record today's findings with
    --write-baseline FILE, commit it, then gate with --baseline FILE: only new findings fail.
    Integrity is never baselined; baseline ids no longer found are reported as stale.

    \b
    strata check --repo . --usage-fixture usage_facts.json
    strata check --repo . --schema-fixture schema_facts.json --fail-on drift
    strata check --repo . --usage-fixture usage_facts.json --write-baseline strata-baseline.json
    strata check --repo . --usage-fixture usage_facts.json --fail-on all --baseline strata-baseline.json
    """
    from pathlib import Path

    from strata_lookml.pipeline import build_graph

    fail_on = _parse_fail_on(fail_on_raw)
    loaded = {"usage": usage_fixture, "schema": schema_fixture}
    for category in sorted(fail_on):
        needed = FINDING_CATEGORIES[category]
        if not loaded[needed]:
            raise click.UsageError(f"--fail-on {category} needs --{needed}-fixture")

    if baseline_path and write_baseline_path:
        raise click.UsageError("--baseline and --write-baseline are mutually exclusive")
    baseline = None
    if baseline_path:
        try:
            baseline = load_baseline(Path(baseline_path))
        except BaselineError as exc:
            raise click.UsageError(str(exc)) from exc

    _repo = Path(repo).expanduser().resolve() if repo else Path.cwd()
    graph = build_graph(str(_repo), usage_fixture, schema_fixture)
    if write_baseline_path:
        try:
            written = write_baseline(graph, Path(write_baseline_path))
        except (BaselineError, InvalidInput) as exc:
            raise click.UsageError(str(exc)) from exc
        click.echo(f"Wrote {written} finding ids to {write_baseline_path}", err=True)
    result = evaluate_gate(graph, fail_on, baseline)

    if as_json:
        click.echo(json.dumps(result, indent=2, sort_keys=True))
    else:
        for failure in result["failures"]:
            click.secho(
                f"FAIL [{failure['category']}] {failure['id']}: {failure['message']}",
                fg="red",
                err=True,
            )
        for stale in result.get("stale_baseline_ids", []):
            click.secho(f"WARN stale baseline id (no longer found): {stale}", fg="yellow", err=True)
        summary = ", ".join(
            f"{c} {'not checked' if n is None else n}" for c, n in result["counts"].items()
        )
        if "baselined" in result:
            summary += f", {result['baselined']} baselined"
        if result["passed"]:
            click.secho(f"Strata check passed ({summary}).", fg="green")
        else:
            click.secho(f"Strata check failed ({summary}).", fg="red", err=True)
    if not result["passed"]:
        raise SystemExit(1)

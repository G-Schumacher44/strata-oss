"""strata findings / ack / unack — triage from the terminal (the CLI twin of the workbench list).

Thin over `strata_lookml.triage`: the rows, statuses, allowlist and concurrency all live there.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

from strata_lookml.gate import FINDING_CATEGORIES, INTEGRITY, BaselineError, load_baseline

if TYPE_CHECKING:
    from strata_lookml.ir.types import IRGraph
    from strata_lookml.triage import TriageRow, TriageStore

_STATUSES = ("new", "acknowledged", "baselined", "fixed", "not_checked")


def _repo_option(f):
    return click.option(
        "--repo",
        default=None,
        envvar="STRATA_REPO_PATH",
        show_envvar=True,
        help="Path to LookML repo (defaults to the configured repo, else cwd)",
    )(f)


def _fixture_options(f):
    f = click.option(
        "--schema-fixture",
        default=None,
        envvar="STRATA_SCHEMA_FIXTURE",
        show_envvar=True,
        help="Schema facts JSON — warehouse column inventory for drift detection.",
    )(f)
    return click.option(
        "--usage-fixture",
        default=None,
        envvar="STRATA_USAGE_FIXTURE",
        show_envvar=True,
        help="Usage facts JSON — explore query counts and PDT build costs.",
    )(f)


def _open(
    repo: str | None, usage_fixture: str | None, schema_fixture: str | None
) -> tuple[IRGraph, TriageStore]:
    """The graph the MCP server would load (same cache, same freshness) and its triage store."""
    from strata_lookml.config import load_cache_path, load_repo_path
    from strata_lookml.mcp.server import CACHE_MAX_AGE_SECONDS
    from strata_lookml.pipeline import load_or_build
    from strata_lookml.triage import TriageStore

    repo_path = Path(repo).expanduser().resolve() if repo else load_repo_path()
    graph = load_or_build(
        repo_path, usage_fixture, schema_fixture, load_cache_path(repo_path), CACHE_MAX_AGE_SECONDS
    )
    return graph, TriageStore.open(repo_path, graph)


def _flat(text: str) -> str:
    return " ".join(text.split())


def _line(row: TriageRow) -> str:
    """`file:line: [category] label — message (id)`; a row with no file is `-:0:`."""
    where = f"{row.source_file or '-'}:{row.source_line or 0}"
    return f"{where}: [{row.category}] {_flat(row.label)} — {_flat(row.message)} ({row.id})"


def _table(rows: list[TriageRow]) -> list[str]:
    cells = [
        (
            r.status,
            r.category,
            f"{r.source_file}:{r.source_line}" if r.source_file else "-",
            _flat(r.label),
        )
        for r in rows
    ]
    header = ("STATUS", "CATEGORY", "LOCATION", "FINDING")
    widths = [max(len(c[i]) for c in [header, *cells]) for i in range(3)]
    return [
        "  ".join(c[i].ljust(widths[i]) for i in range(3)) + "  " + c[3] for c in [header, *cells]
    ]


@click.command("findings")
@_repo_option
@_fixture_options
@click.option(
    "--baseline",
    "baseline_path",
    default=None,
    type=click.Path(dir_okay=False),
    help="Baseline file (as for `strata check`): its ids show as baselined.",
)
@click.option(
    "--status",
    type=click.Choice([*_STATUSES, "all"]),
    default="new",
    show_default=True,
    help="Only rows in this status.",
)
@click.option(
    "--category",
    type=click.Choice([INTEGRITY, *FINDING_CATEGORIES]),
    default=None,
    help="Only rows in this finding category.",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["table", "lines", "json"]),
    default="table",
    show_default=True,
    help="table for people; lines for fzf and vim quickfix; json for scripts.",
)
def findings(
    repo: str | None,
    usage_fixture: str | None,
    schema_fixture: str | None,
    baseline_path: str | None,
    status: str,
    category: str | None,
    fmt: str,
) -> None:
    """List findings with their triage status (new by default).

    The same rows the workbench shows. `lines` prints one finding per line as
    `file:line: [category] label — message (id)`: the shape fzf filters and vim's
    quickfix list parses (`%f:%l:%m`). A finding with no file (an integrity failure, a
    finding already fixed) prints `-:0:` instead. `json` is a list of row objects.

    \b
    $ strata findings --repo tests/lookml/enterprise_mono --usage-fixture usage.json --format lines
    models/em_legacy_v2.model.lkml:23: [dead-code] em_legacy_v2.dead_finance_v2 — zero queries ... (dead:explore:em_legacy_v2.dead_finance_v2)
    $ vim -q <(strata findings --format lines)
    """
    baseline = None
    if baseline_path:
        try:
            baseline = load_baseline(Path(baseline_path))
        except BaselineError as exc:
            raise click.UsageError(str(exc)) from exc
    from strata_lookml.triage import triage_rows

    graph, store = _open(repo, usage_fixture, schema_fixture)
    rows = [
        r
        for r in triage_rows(graph, baseline, store)
        if status in ("all", r.status) and category in (None, r.category)
    ]
    if fmt == "json":
        click.echo(json.dumps([dataclasses.asdict(r) for r in rows], indent=2))
    elif fmt == "lines":
        for r in rows:
            click.echo(_line(r))
    elif rows:
        click.echo("\n".join(_table(rows)))
        click.echo(f"{len(rows)} finding(s)", err=True)
    else:
        click.echo(f"No {'' if status == 'all' else status + ' '}findings.", err=True)


def _expand_ids(ids: tuple[str, ...]) -> list[str]:
    """`-` means one id per line from stdin; blank lines are skipped."""
    out: list[str] = []
    for token in ids:
        if token == "-":
            out.extend(s for line in sys.stdin if (s := line.strip()))
        else:
            out.append(token)
    if not out:
        raise click.UsageError("no finding ids given")
    return list(dict.fromkeys(out))


def _active(store: TriageStore) -> set[str]:
    return {i for i, e in store.snapshot()["ids"].items() if "unacked_at" not in e}


@click.command("ack")
@_repo_option
@_fixture_options
@click.option("--note", default=None, help="Why (stored with the acknowledgement; max 2000 chars).")
@click.argument("ids", nargs=-1, required=True)
def ack(
    repo: str | None,
    usage_fixture: str | None,
    schema_fixture: str | None,
    note: str | None,
    ids: tuple[str, ...],
) -> None:
    """Acknowledge findings by id (`-` reads ids from stdin, one per line).

    Only ids the current findings report are accepted; an unknown id fails and nothing is
    written. Acknowledgements live in ~/.strata/triage/, never in the repo, and never affect
    `strata check`. A baselined finding stays baselined.

    \b
    $ strata ack dead:view:legacy_order_detail --note "kept for the 2027 audit"
    $ strata findings --format lines | fzf -m | sed -E 's/.* \\((.*)\\)$/\\1/' | strata ack -
    """
    wanted = _expand_ids(ids)
    _, store = _open(repo, usage_fixture, schema_fixture)
    before = _active(store)
    store.acknowledge(wanted, note)
    for finding_id in wanted:
        verb = "already acknowledged" if finding_id in before and note is None else "acknowledged"
        click.echo(f"{verb}: {finding_id}")


@click.command("unack")
@_repo_option
@_fixture_options
@click.argument("ids", nargs=-1, required=True)
def unack(
    repo: str | None,
    usage_fixture: str | None,
    schema_fixture: str | None,
    ids: tuple[str, ...],
) -> None:
    """Withdraw acknowledgements by id (`-` reads ids from stdin, one per line).

    The id must be one this machine has acknowledged; an unknown id fails and nothing is
    written. The finding goes back to new (or baselined, if the baseline holds it).

    \b
    $ strata unack dead:view:legacy_order_detail
    """
    wanted = _expand_ids(ids)
    _, store = _open(repo, usage_fixture, schema_fixture)
    before = _active(store)
    store.unacknowledge(wanted)
    for finding_id in wanted:
        click.echo(
            f"{'unacknowledged' if finding_id in before else 'not acknowledged'}: {finding_id}"
        )

"""strata generate-schema — pull schema facts from BigQuery INFORMATION_SCHEMA."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

import click

# Table names come from LookML `sql_table_name` / derived-table SQL, i.e. repo-controlled text.
# Only the dataset path is interpolated into the query (BigQuery cannot parameterize an
# identifier); table names travel as a query parameter. Every part is still checked against a
# strict allowlist so a hostile name is skipped and reported, never sent to `bq`.
# Charsets: project IDs are lowercase letters, digits and hyphens; dataset names are letters,
# digits and underscores; table names are restricted here to ASCII letters, digits, underscores
# and hyphens (BigQuery allows more, but nothing outside this set reaches the CLI).
_PROJECT_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
_DATASET_RE = re.compile(r"[A-Za-z0-9_]{1,1024}")
_TABLE_RE = re.compile(r"[A-Za-z0-9_-]{1,1024}")

# `bq query` returns only 100 rows unless told otherwise; INFORMATION_SCHEMA.COLUMNS has one row
# per column, so the default silently truncates wide datasets.
BQ_MAX_ROWS = 1_000_000
# Metadata queries bill a small fixed minimum; 1 GB is a generous ceiling that still fails closed
# if the query is ever pointed at something larger.
BQ_MAXIMUM_BYTES_BILLED = 1_000_000_000

COLUMNS_SQL = (
    "SELECT table_name, column_name "
    "FROM `{dataset}.INFORMATION_SCHEMA.COLUMNS` "
    "WHERE table_name IN UNNEST(@names) "
    "ORDER BY table_name, ordinal_position"
)


def valid_dataset_path(dataset: str) -> bool:
    """True when `dataset` is exactly `project.dataset` with both parts in the allowlist."""
    parts = dataset.split(".")
    return (
        len(parts) == 2
        and _PROJECT_RE.fullmatch(parts[0]) is not None
        and _DATASET_RE.fullmatch(parts[1]) is not None
    )


def valid_table_name(name: str) -> bool:
    return _TABLE_RE.fullmatch(name) is not None


def _parse_table(name: str, bq_project: str | None) -> tuple[str, str] | None:
    parts = name.split(".")
    if len(parts) == 3:
        return f"{parts[0]}.{parts[1]}", parts[2]
    if len(parts) == 2:
        if bq_project:
            return f"{bq_project}.{parts[0]}", parts[1]
        return None
    return None


def _group_tables(
    table_names: list[str], bq_project: str | None
) -> tuple[dict[str, list[tuple[str, str]]], list[str], list[str]]:
    """Group tables by `project.dataset`.

    Returns (grouped, skipped, rejected): `skipped` names have no resolvable dataset (likely
    CTEs); `rejected` names resolve but contain characters outside the identifier allowlist and
    are never queried.
    """
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    skipped: list[str] = []
    rejected: list[str] = []
    for name in sorted(table_names):
        parsed = _parse_table(name, bq_project)
        if not parsed:
            skipped.append(name)
        elif valid_dataset_path(parsed[0]) and valid_table_name(parsed[1]):
            grouped[parsed[0]].append((name, parsed[1]))
        else:
            rejected.append(name)
    return dict(grouped), skipped, rejected


def build_columns_query(dataset: str, short_names: list[str]) -> list[str]:
    """The full `bq query` argv for one dataset; refuses any identifier outside the allowlist."""
    if not valid_dataset_path(dataset):
        raise ValueError(f"invalid BigQuery dataset path: {dataset!r}")
    bad = [n for n in short_names if not valid_table_name(n)]
    if bad:
        raise ValueError(f"invalid BigQuery table name(s): {bad!r}")
    return [
        "bq",
        "query",
        "--format=json",
        "--nouse_legacy_sql",
        f"--max_rows={BQ_MAX_ROWS}",
        f"--maximum_bytes_billed={BQ_MAXIMUM_BYTES_BILLED}",
        f"--parameter=names:ARRAY<STRING>:{json.dumps(short_names)}",
        COLUMNS_SQL.format(dataset=dataset),
    ]


def _bq_query(argv: list[str]) -> list[dict]:
    try:
        result = subprocess.run(argv, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        click.echo("ERROR: `bq` CLI not found. Install the Google Cloud CLI and run:", err=True)
        click.echo("  gcloud auth login", err=True)
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        click.echo(f"ERROR: bq query failed:\n{exc.stderr}", err=True)
        sys.exit(1)
    text = result.stdout.strip()
    return [] if not text or text == "[]" else json.loads(text)


def _pull_dataset(dataset: str, table_entries: list[tuple[str, str]]) -> dict[str, list[str]]:
    short_names = [short for _, short in table_entries]
    rows = _bq_query(build_columns_query(dataset, short_names))
    result: dict[str, list[str]] = {}
    for row in rows:
        full = next(
            (f for f, s in table_entries if s == row["table_name"]),
            f"{dataset}.{row['table_name']}",
        )
        result.setdefault(full, []).append(row["column_name"])
    return result


def describe_query(dataset: str, short_names: list[str]) -> list[str]:
    """Dry-run rendering of the query plan for one dataset (shared by the CLI and the script)."""
    return [
        "  SELECT table_name, column_name",
        f"  FROM `{dataset}.INFORMATION_SCHEMA.COLUMNS`",
        "  WHERE table_name IN UNNEST(@names)",
        f"  @names = {json.dumps(short_names)}",
    ]


def report_rejected(rejected: list[str], echo: Callable[[str], None]) -> None:
    if rejected:
        echo(f"  Rejected (invalid BigQuery identifier, not queried): {len(rejected)}")
        for name in rejected:
            echo(f"    {name!r}")


def _load_existing(path: Path) -> dict[str, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["name"]: list(item.get("columns", [])) for item in data.get("tables", [])}


def _diff(old: dict[str, list[str]], new: dict[str, list[str]]) -> dict[str, list[str]]:
    all_tables = set(old) | set(new)
    unchanged, updated, added, missing = [], [], [], []
    for t in sorted(all_tables):
        if t not in old:
            added.append(t)
        elif t not in new:
            missing.append(t)
        elif set(old[t]) != set(new[t]):
            updated.append(t)
        else:
            unchanged.append(t)
    return {"unchanged": unchanged, "updated": updated, "added": added, "missing": missing}


@click.command("generate-schema")
@click.option(
    "--repo",
    required=True,
    envvar="STRATA_REPO_PATH",
    show_envvar=True,
    help="Path to LookML repo root",
)
@click.option("--out", required=True, help="Output schema_facts.json path")
@click.option(
    "--bq-project", default=None, help="GCP project for 2-part table names (dataset.table)"
)
@click.option("--existing", default=None, help="Existing schema_facts.json to diff against")
@click.option("--dry-run", is_flag=True, help="Print query plan without hitting BQ")
def generate_schema(
    repo: str, out: str, bq_project: str | None, existing: str | None, dry_run: bool
) -> None:
    """Pull schema facts from BigQuery INFORMATION_SCHEMA.

    Extracts physical table names from the LookML IR, queries BigQuery
    INFORMATION_SCHEMA.COLUMNS for only the tables referenced in LookML,
    and writes schema_facts.json for use with strata check/outputs.

    Requires: the Google Cloud CLI in PATH, signed in with `gcloud auth login`
    (`bq` uses gcloud's own credentials, not Application Default Credentials).

    \b
    strata generate-schema --repo /path/to/lookml --out schema_facts.json --dry-run
    strata generate-schema --repo /path/to/lookml --out schema_facts.json
    strata generate-schema --repo . --out new.json --existing old.json
    """
    from strata_lookml.config import load_bq_project
    from strata_lookml.pipeline import build_graph

    repo_path = Path(repo).expanduser().resolve()
    if not bq_project:
        bq_project = load_bq_project()
    click.echo("=== Strata Schema Facts Generator ===")
    click.echo(f"Repo:  {repo_path}")
    if dry_run:
        click.echo("Mode:  dry-run")
    click.echo()

    graph = build_graph(str(repo_path))
    table_names = sorted({n.name for n in graph.nodes_by_kind("physical_table")})
    grouped, skipped, rejected = _group_tables(table_names, bq_project)

    total = sum(len(v) for v in grouped.values())
    click.echo(f"Physical tables in IR: {len(table_names)}")
    click.echo(f"  Queryable (have BQ dataset): {total}")
    if skipped:
        click.echo(f"  Skipped (no dataset prefix — likely CTEs): {len(skipped)}")
        for s in skipped:
            click.echo(f"    {s}")
    report_rejected(rejected, click.echo)
    click.echo()

    if grouped:
        click.echo(f"BQ datasets ({len(grouped)}):")
        for dataset, entries in sorted(grouped.items()):
            click.echo(f"  {dataset:<50s}  ({len(entries)} tables)")
        click.echo()

    if dry_run:
        click.echo(f"Queries that would run ({len(grouped)} datasets):")
        for dataset, entries in sorted(grouped.items()):
            for line in describe_query(dataset, [short for _, short in entries]):
                click.echo(line)
            click.echo()
        if existing and Path(existing).exists():
            old = _load_existing(Path(existing))
            queryable_names = {full for entries in grouped.values() for full, _ in entries}
            missing_from_ir = [k for k in old if k not in queryable_names]
            click.echo(f"Existing fixture: {existing}")
            click.echo(f"  Tables in fixture:     {len(old)}")
            click.echo(f"  Tables also in IR:     {len(old) - len(missing_from_ir)}")
            if missing_from_ir:
                click.echo(f"  In fixture but not IR: {len(missing_from_ir)} (may be stale)")
                for t in missing_from_ir[:5]:
                    click.echo(f"    {t}")
            click.echo()
        click.echo(
            "Run without --dry-run (signed in to gcloud) to execute and write schema_facts.json."
        )
        return

    if not grouped:
        click.echo("No queryable tables found. Nothing written.")
        return

    all_columns: dict[str, list[str]] = {}
    pulled = 0
    for dataset, entries in sorted(grouped.items()):
        click.echo(f"Querying {dataset}... ", nl=False)
        result = _pull_dataset(dataset, entries)
        all_columns.update(result)
        pulled += len(result)
        click.echo(f"{len(result)} / {len(entries)} tables")

    total_cols = sum(len(cols) for cols in all_columns.values())
    not_found = total - pulled

    out_path = Path(out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"tables": [{"name": n, "columns": c} for n, c in sorted(all_columns.items())]}
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    click.echo()
    click.echo("─" * 52)
    click.echo(f"Tables pulled:   {pulled} / {total}")
    click.echo(f"Columns indexed: {total_cols}")
    click.echo(f"Output:          {out_path}")
    if not_found:
        click.echo(f"Not found in BQ: {not_found}  ← flag for manual review")

    if existing and Path(existing).exists():
        old = _load_existing(Path(existing))
        delta = _diff(old, all_columns)
        click.echo()
        click.echo("Delta vs existing fixture:")
        click.echo(f"  {len(delta['unchanged']):>4}  unchanged")
        if delta["updated"]:
            click.echo(f"  {len(delta['updated']):>4}  updated   (column changes)")
            for t in delta["updated"]:
                removed = sorted(set(old[t]) - set(all_columns[t]))
                added_cols = sorted(set(all_columns[t]) - set(old[t]))
                if removed:
                    click.echo(
                        f"         removed: {', '.join(removed[:3])}{'...' if len(removed) > 3 else ''}"
                    )
                if added_cols:
                    click.echo(
                        f"         added:   {', '.join(added_cols[:3])}{'...' if len(added_cols) > 3 else ''}"
                    )
        if delta["added"]:
            click.echo(f"  {len(delta['added']):>4}  added     (new tables)")
        if delta["missing"]:
            click.echo(f"  {len(delta['missing']):>4}  missing   (not found in BQ — manual review)")
            for t in delta["missing"]:
                click.echo(f"         {t}")

    click.echo()
    click.echo(f"Run `strata check --schema-fixture {out_path}` to see full drift report.")

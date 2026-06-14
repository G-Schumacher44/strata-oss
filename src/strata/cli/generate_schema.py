"""strata generate-schema — pull schema facts from BigQuery INFORMATION_SCHEMA."""

from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import click


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
) -> tuple[dict[str, list[tuple[str, str]]], list[str]]:
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    skipped: list[str] = []
    for name in sorted(table_names):
        parsed = _parse_table(name, bq_project)
        if parsed:
            grouped[parsed[0]].append((name, parsed[1]))
        else:
            skipped.append(name)
    return dict(grouped), skipped


def _bq_query(sql: str) -> list[dict]:
    try:
        result = subprocess.run(
            ["bq", "query", "--format=json", "--nouse_legacy_sql", sql],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        click.echo("ERROR: `bq` CLI not found. Install Google Cloud SDK and run:", err=True)
        click.echo("  gcloud auth application-default login", err=True)
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        click.echo(f"ERROR: bq query failed:\n{exc.stderr}", err=True)
        sys.exit(1)
    text = result.stdout.strip()
    return [] if not text or text == "[]" else json.loads(text)


def _pull_dataset(dataset: str, table_entries: list[tuple[str, str]]) -> dict[str, list[str]]:
    short_names = [short for _, short in table_entries]
    names_sql = ", ".join(f"'{n}'" for n in short_names)
    sql = (
        f"SELECT table_name, column_name "
        f"FROM `{dataset}.INFORMATION_SCHEMA.COLUMNS` "
        f"WHERE table_name IN ({names_sql}) "
        f"ORDER BY table_name, ordinal_position"
    )
    rows = _bq_query(sql)
    result: dict[str, list[str]] = {}
    for row in rows:
        full = next(
            (f for f, s in table_entries if s == row["table_name"]),
            f"{dataset}.{row['table_name']}",
        )
        result.setdefault(full, []).append(row["column_name"])
    return result


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
@click.option("--repo", required=True, help="Path to LookML repo root")
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

    Requires: google-cloud-sdk in PATH + ADC configured.

    \b
    strata generate-schema --repo /path/to/lookml --out schema_facts.json --dry-run
    strata generate-schema --repo /path/to/lookml --out schema_facts.json
    strata generate-schema --repo . --out new.json --existing old.json
    """
    from strata.config import load_bq_project
    from strata.pipeline import build_graph

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
    grouped, skipped = _group_tables(table_names, bq_project)

    total = sum(len(v) for v in grouped.values())
    click.echo(f"Physical tables in IR: {len(table_names)}")
    click.echo(f"  Queryable (have BQ dataset): {total}")
    if skipped:
        click.echo(f"  Skipped (no dataset prefix — likely CTEs): {len(skipped)}")
        for s in skipped:
            click.echo(f"    {s}")
    click.echo()

    if grouped:
        click.echo(f"BQ datasets ({len(grouped)}):")
        for dataset, entries in sorted(grouped.items()):
            click.echo(f"  {dataset:<50s}  ({len(entries)} tables)")
        click.echo()

    if dry_run:
        click.echo(f"Queries that would run ({len(grouped)} datasets):")
        for dataset, entries in sorted(grouped.items()):
            names_sql = ", ".join(f"'{short}'" for _, short in entries)
            click.echo("  SELECT table_name, column_name")
            click.echo(f"  FROM `{dataset}.INFORMATION_SCHEMA.COLUMNS`")
            click.echo(f"  WHERE table_name IN ({names_sql})")
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
            "Run without --dry-run (with ADC configured) to execute and write schema_facts.json."
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

#!/usr/bin/env python3
"""Generate schema_facts.json by querying BigQuery INFORMATION_SCHEMA.

Extracts physical table names from the LookML IR, groups them by BQ dataset,
and runs targeted INFORMATION_SCHEMA.COLUMNS queries. Only tables actually
referenced in the LookML are queried — not entire BQ projects.

Raw column data is written to disk; stdout surfaces only a compact summary
safe for agent consumption (no context-window flooding).

Usage:
  python scripts/generate_schema_facts.py \\
    --repo /path/to/lookml \\
    --out schema_facts.json \\
    [--bq-project my-gcp-project] \\
    [--existing current_schema_facts.json] \\
    [--dry-run]

Requirements:
  google-cloud-sdk in PATH (for `bq` CLI) and ADC configured:
    gcloud auth application-default login
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from strata.pipeline import build_graph  # noqa: E402

HEADER = "=== Strata Schema Facts Generator ==="
SEP = "─" * 52


def _parse_table(name: str, bq_project: str | None) -> tuple[str, str] | None:
    """Return (dataset_key, table_short_name) or None if ungroupable."""
    parts = name.split(".")
    if len(parts) == 3:
        return f"{parts[0]}.{parts[1]}", parts[2]
    if len(parts) == 2:
        if bq_project:
            return f"{bq_project}.{parts[0]}", parts[1]
        return None  # can't resolve dataset without --bq-project
    return None  # single-part name — likely a CTE, not a real table


def _group_tables(
    table_names: list[str], bq_project: str | None
) -> tuple[dict[str, list[tuple[str, str]]], list[str]]:
    """Group tables by dataset. Returns (grouped, skipped)."""
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    skipped: list[str] = []
    for name in sorted(table_names):
        parsed = _parse_table(name, bq_project)
        if parsed:
            dataset, short = parsed
            grouped[dataset].append((name, short))
        else:
            skipped.append(name)
    return dict(grouped), skipped


def _bq_query(sql: str) -> list[dict]:
    """Run a bq CLI query and return parsed JSON rows."""
    try:
        result = subprocess.run(
            ["bq", "query", "--format=json", "--nouse_legacy_sql", sql],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        print("ERROR: `bq` CLI not found. Install Google Cloud SDK and run:", file=sys.stderr)
        print("  gcloud auth application-default login", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: bq query failed:\n{exc.stderr}", file=sys.stderr)
        sys.exit(1)
    text = result.stdout.strip()
    if not text or text == "[]":
        return []
    return json.loads(text)


def _pull_dataset(dataset: str, table_entries: list[tuple[str, str]]) -> dict[str, list[str]]:
    """Query INFORMATION_SCHEMA for a dataset, return {full_table_name: [columns]}."""
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
        tbl = row["table_name"]
        col = row["column_name"]
        # Reconstruct full name by looking up in table_entries
        full = next((full for full, short in table_entries if short == tbl), f"{dataset}.{tbl}")
        result.setdefault(full, []).append(col)
    return result


def _load_existing(path: Path) -> dict[str, list[str]]:
    """Load existing schema_facts.json → {table_name: [columns]}."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["name"]: list(item.get("columns", [])) for item in data.get("tables", [])}


def _diff(old: dict[str, list[str]], new: dict[str, list[str]]) -> dict[str, list[str]]:
    """Compute delta between old and new column inventories."""
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo", required=True, help="Path to LookML repo root")
    parser.add_argument("--out", required=True, help="Output schema_facts.json path")
    parser.add_argument("--bq-project", help="GCP project for 2-part table names (dataset.table)")
    parser.add_argument("--existing", help="Existing schema_facts.json to diff against")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print query plan without hitting BQ"
    )
    args = parser.parse_args()

    print(HEADER)
    print(f"Repo:  {args.repo}")
    if args.dry_run:
        print("Mode:  dry-run")
    print()

    graph = build_graph(args.repo)
    table_names = sorted({n.name for n in graph.nodes_by_kind("physical_table")})
    grouped, skipped = _group_tables(table_names, args.bq_project)

    total = sum(len(v) for v in grouped.values())
    print(f"Physical tables in IR: {len(table_names)}")
    print(f"  Queryable (have BQ dataset): {total}")
    if skipped:
        print(f"  Skipped (no dataset prefix — likely CTEs): {len(skipped)}")
        for s in skipped:
            print(f"    {s}")
    print()

    if grouped:
        print(f"BQ datasets ({len(grouped)}):")
        for dataset, entries in sorted(grouped.items()):
            print(f"  {dataset:<50s}  ({len(entries)} tables)")
        print()

    if args.dry_run:
        print(f"Queries that would run ({len(grouped)} datasets):")
        for dataset, entries in sorted(grouped.items()):
            names_sql = ", ".join(f"'{short}'" for _, short in entries)
            print("  SELECT table_name, column_name")
            print(f"  FROM `{dataset}.INFORMATION_SCHEMA.COLUMNS`")
            print(f"  WHERE table_name IN ({names_sql})")
            print()
        if args.existing and Path(args.existing).exists():
            old = _load_existing(Path(args.existing))
            queryable_names = {full for entries in grouped.values() for full, _ in entries}
            old_queryable = {k: v for k, v in old.items() if k in queryable_names}
            missing_from_ir = [
                k for k in old if k not in {n for entries in grouped.values() for n, _ in entries}
            ]
            print(f"Existing fixture: {args.existing}")
            print(f"  Tables in fixture:        {len(old)}")
            print(f"  Tables also in IR:        {len(old_queryable)}")
            if missing_from_ir:
                print(f"  In fixture but not IR:    {len(missing_from_ir)} (may be stale)")
                for t in missing_from_ir[:5]:
                    print(f"    {t}")
            print()
        print("Run without --dry-run (with ADC) to execute and write schema_facts.json.")
        return 0

    # Live mode — pull from BQ
    if not grouped:
        print("No queryable tables found. Nothing written.")
        return 0

    all_columns: dict[str, list[str]] = {}
    pulled = 0
    for dataset, entries in sorted(grouped.items()):
        print(f"Querying {dataset}... ", end="", flush=True)
        result = _pull_dataset(dataset, entries)
        all_columns.update(result)
        pulled += len(result)
        print(f"{len(result)} / {len(entries)} tables")

    total_cols = sum(len(cols) for cols in all_columns.values())
    not_found = total - pulled

    # Write output
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tables": [{"name": name, "columns": cols} for name, cols in sorted(all_columns.items())]
    }
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print()
    print(SEP)
    print(f"Tables pulled:   {pulled} / {total}")
    print(f"Columns indexed: {total_cols}")
    print(f"Output:          {out_path}")
    if not_found:
        print(f"Not found in BQ: {not_found}  ← flag for manual review")

    if args.existing and Path(args.existing).exists():
        old = _load_existing(Path(args.existing))
        delta = _diff(old, all_columns)
        print()
        print("Delta vs existing fixture:")
        print(f"  {len(delta['unchanged']):>4}  unchanged")
        if delta["updated"]:
            print(f"  {len(delta['updated']):>4}  updated   (column changes)")
            for t in delta["updated"]:
                removed = sorted(set(old[t]) - set(all_columns[t]))
                added = sorted(set(all_columns[t]) - set(old[t]))
                if removed:
                    print(
                        f"         removed: {', '.join(removed[:3])}{'...' if len(removed) > 3 else ''}"
                    )
                if added:
                    print(
                        f"         added:   {', '.join(added[:3])}{'...' if len(added) > 3 else ''}"
                    )
        if delta["added"]:
            print(f"  {len(delta['added']):>4}  added     (new tables)")
        if delta["missing"]:
            print(f"  {len(delta['missing']):>4}  missing   (not found in BQ — manual review)")
            for t in delta["missing"]:
                print(f"         {t}")

    print()
    print(f"Run `make ci SCHEMA={out_path}` to see full drift report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

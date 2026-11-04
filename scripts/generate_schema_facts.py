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
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Query construction and identifier validation live in one place — the `strata generate-schema`
# CLI module — so this script cannot drift from it.
from strata_lookml.cli.generate_schema import (  # noqa: E402
    _diff,
    _group_tables,
    _load_existing,
    _pull_dataset,
    describe_query,
    report_rejected,
)
from strata_lookml.pipeline import build_graph  # noqa: E402

HEADER = "=== Strata Schema Facts Generator ==="
SEP = "─" * 52


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
    grouped, skipped, rejected = _group_tables(table_names, args.bq_project)

    total = sum(len(v) for v in grouped.values())
    print(f"Physical tables in IR: {len(table_names)}")
    print(f"  Queryable (have BQ dataset): {total}")
    if skipped:
        print(f"  Skipped (no dataset prefix — likely CTEs): {len(skipped)}")
        for s in skipped:
            print(f"    {s}")
    report_rejected(rejected, print)
    print()

    if grouped:
        print(f"BQ datasets ({len(grouped)}):")
        for dataset, entries in sorted(grouped.items()):
            print(f"  {dataset:<50s}  ({len(entries)} tables)")
        print()

    if args.dry_run:
        print(f"Queries that would run ({len(grouped)} datasets):")
        for dataset, entries in sorted(grouped.items()):
            for line in describe_query(dataset, [short for _, short in entries]):
                print(line)
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

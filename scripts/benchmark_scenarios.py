#!/usr/bin/env python3
"""
Strata Benchmark Runner
Automates deterministic checks against the three playgrounds to establish a ground truth.
"""

import json
import os
import subprocess
import time
from pathlib import Path

PLAYGROUNDS = [
    {
        "name": "thelook",
        "repo": "tests/lookml/thelook",
        "usage": "tests/fixtures/playground_usage_facts.json",
        "schema": "tests/fixtures/playground_schema_facts.json",  # Note: thelook has no schema fixture by design
        "expected_dead": 6,
        "expected_drift": 1,
    },
    {
        "name": "gcs_analytics",
        "repo": "tests/lookml/gcs_analytics",
        "usage": "tests/fixtures/gcs_usage_facts.json",
        "schema": "tests/fixtures/gcs_schema_facts.json",
        "expected_dead": 6,
        "expected_drift": 1,
    },
    {
        "name": "enterprise_mono",
        "repo": "tests/lookml/enterprise_mono",
        "usage": "tests/fixtures/enterprise_usage_facts.json",
        "schema": "tests/fixtures/enterprise_schema_facts.json",
        "expected_dead": 11,  # 6 dead explores + 5 zombie views
        "expected_drift": 14,
    },
]


def run_command(cmd):
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.time() - start_time
    return result, duration


def main():
    print("Strata Benchmark — Deterministic Ground Truth Verification")
    print("=" * 60)

    results = []

    for p in PLAYGROUNDS:
        print(f"\nScenario: {p['name']}")
        print("Running strata check...")

        cmd = [".venv/bin/strata", "check", "--repo", p["repo"], "--usage-fixture", p["usage"]]

        # thelook doesn't use schema fixture in the docs, but check if we should add it
        if os.path.exists(p["schema"]):
            cmd.extend(["--schema-fixture", p["schema"]])

        res, duration = run_command(cmd)

        # For simplicity, we parse the stdout for counts if available,
        # but strata check might just exit 0.
        # We can also run 'strata outputs' and parse the JSON.

        print(f"Duration: {duration:.2f}s")
        if res.returncode == 0:
            print("✓ Gate passed")
        else:
            print(f"✗ Gate failed (Exit {res.returncode})")
            print(res.stderr)

        # Verify findings by running outputs
        out_dir = Path(f"output/benchmarks/{p['name']}")
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd_out = [
            ".venv/bin/strata",
            "outputs",
            "--repo",
            p["repo"],
            "--usage-fixture",
            p["usage"],
            "--out",
            str(out_dir),
        ]
        if os.path.exists(p["schema"]):
            cmd_out.extend(["--schema-fixture", p["schema"]])

        res_out, _ = run_command(cmd_out)

        dead_count = 0
        drift_count = 0

        if res_out.returncode == 0:
            # Parse dead_code_register.json
            dead_code_file = out_dir / "dead_code_register.json"
            drift_file = out_dir / "schema_drift.json"

            with open(dead_code_file) as f:
                dead_code = json.load(f)
            with open(drift_file) as f:
                drift = json.load(f)

            dead_count = len(dead_code)
            drift_count = len(drift)

            print(f"Findings: {dead_count} dead items, {drift_count} drift hits")

            status = (
                "PASS"
                if dead_count == p["expected_dead"] and drift_count == p["expected_drift"]
                else "FAIL"
            )
            if status == "FAIL":
                print(f"  !! Expected: {p['expected_dead']} dead, {p['expected_drift']} drift")
        else:
            print("✗ Failed to generate outputs")
            status = "ERROR"

        results.append(
            {
                "playground": p["name"],
                "duration": duration,
                "dead_count": dead_count if status != "ERROR" else 0,
                "drift_count": drift_count if status != "ERROR" else 0,
                "status": status,
            }
        )

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    for r in results:
        print(
            f"{r['playground']:16} | {r['status']:5} | {r['duration']:5.2f}s | Dead: {r['dead_count']:2} | Drift: {r['drift_count']:2}"
        )


if __name__ == "__main__":
    main()

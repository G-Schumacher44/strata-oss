"""Synthetic LookML at scale: `copies` renamed copies of enterprise_mono in one repo.

Spec §6b Q4 sizes the static export against real repos: "large" = 20 copies (~400 views and
~3.9k fields, about the p95 of public LookML repos) and "very large" = 50 copies (~1,000 views
and ~10k fields). Each copy prefixes every model, explore, view and warehouse-table name
(`s7_orders`), in the LookML and in the usage and schema facts alike, so the copies never share
a node and every finding repeats per copy. Written under a temp dir by the tests; never
committed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from strata_lookml.pipeline import build_graph

ROOT = Path(__file__).resolve().parent
BASE = ROOT / "lookml" / "enterprise_mono"
USAGE = ROOT / "fixtures" / "enterprise_usage_facts.json"
SCHEMA = ROOT / "fixtures" / "enterprise_schema_facts.json"


def _names() -> list[str]:
    """Every model, explore, view and table-name segment in the base repo, longest first."""
    graph = build_graph(BASE)
    names: set[str] = set()
    for node in graph.nodes.values():
        if node.kind in ("model", "explore", "view", "pdt"):
            names.add(node.name)
        elif node.kind == "physical_table":
            names.add(node.name.rsplit(".", 1)[-1])
    names |= {p.name.removesuffix(".model.lkml") for p in BASE.rglob("*.model.lkml")}
    return sorted(names, key=lambda n: (-len(n), n))


def generate(root: Path, copies: int) -> tuple[Path, Path, Path]:
    """Write `copies` copies under `root`; returns (repo, usage facts, schema facts)."""
    names = _names()
    token = re.compile(r"(?<![\w-])(" + "|".join(re.escape(n) for n in names) + r")(?![\w-])")
    repo = root / "repo"
    sources = sorted(BASE.rglob("*.lkml"))
    usage = json.loads(USAGE.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    scaled_usage: dict[str, object] = {"period": usage["period"]}
    scaled_schema: dict[str, list[object]] = {"tables": []}
    for i in range(copies):

        def rename(text: str, i: int = i) -> str:
            return token.sub(lambda m: f"s{i}_{m.group(1)}", text)

        def relocate(text: str, i: int = i) -> str:  # includes are repo-absolute
            return rename(text).replace('include: "/', f'include: "/s{i}/')

        for source in sources:
            relative = source.relative_to(BASE)
            target = repo / f"s{i}" / relative.parent / rename(relative.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(relocate(source.read_text(encoding="utf-8")), encoding="utf-8")
        copy_usage = json.loads(rename(json.dumps(usage)))
        for key, value in copy_usage.items():
            if isinstance(value, list):
                scaled_usage.setdefault(key, []).extend(value)  # type: ignore[union-attr]
        scaled_schema["tables"].extend(json.loads(rename(json.dumps(schema)))["tables"])
    usage_path, schema_path = root / "usage.json", root / "schema.json"
    usage_path.write_text(json.dumps(scaled_usage), encoding="utf-8")
    schema_path.write_text(json.dumps(scaled_schema), encoding="utf-8")
    return repo, usage_path, schema_path

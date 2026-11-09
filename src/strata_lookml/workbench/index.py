"""The workbench's one in-memory index, built once at startup from the cached IR.

Every page reads this object; nothing re-reads `output/*.json` or rebuilds the graph per
request. The graph comes from `pipeline.load_or_build` (the same cache the MCP server uses), so
a second start on unchanged inputs is a cache hit. `Staleness` re-fingerprints the inputs at
most every `STALE_CHECK_SECONDS` and only raises a banner flag: there is no reload endpoint.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from strata_lookml.config import load_cache_path
from strata_lookml.gate import finding_records, findings_by_node
from strata_lookml.ir.store import describe_inputs
from strata_lookml.ir.types import IRGraph
from strata_lookml.l1.enrich import analysis_coverage
from strata_lookml.pipeline import CACHE_MAX_AGE_SECONDS, load_or_build

STALE_CHECK_SECONDS = 10.0


@dataclass(frozen=True)
class Workbench:
    """What every page reads: the graph plus the indexes derived from it once.

    `findings_by_id` holds 1..n records per id (two fields of one name can miss the same
    column); `findings_by_node` is `gate.findings_by_node`. `inputs` is the cache input
    fingerprint the graph was built from, which `Staleness` compares against.
    """

    repo: Path
    graph: IRGraph
    usage_fixture: str | None
    schema_fixture: str | None
    inputs: Mapping[str, Any]
    records: tuple[Mapping[str, Any], ...]
    findings_by_id: Mapping[str, tuple[Mapping[str, Any], ...]]
    findings_by_node: Mapping[str, tuple[str, ...]]
    coverage: Mapping[str, bool]
    source: Mapping[str, Any] | None
    baseline: Mapping[str, frozenset[str]] | None
    baseline_path: str | None
    base_url: str | None

    def fingerprint(self) -> dict[str, Any]:
        """The cache inputs as they are on disk now."""
        return describe_inputs(self.repo, self.usage_fixture, self.schema_fixture)


def load_graph(
    repo: Path, usage_fixture: str | None, schema_fixture: str | None
) -> tuple[IRGraph, dict[str, Any]]:
    """The graph from the IR cache (rebuilt and cached on a miss) and the inputs it was built from.

    The inputs are read before the build, so an edit made during it reads as stale, never as
    already loaded.
    """
    inputs = describe_inputs(repo, usage_fixture, schema_fixture)
    graph = load_or_build(
        repo, usage_fixture, schema_fixture, load_cache_path(repo), CACHE_MAX_AGE_SECONDS
    )
    return graph, inputs


def index_graph(
    graph: IRGraph,
    *,
    repo: Path,
    usage_fixture: str | None,
    schema_fixture: str | None,
    inputs: Mapping[str, Any],
    baseline: Mapping[str, set[str]] | None = None,
    baseline_path: str | None = None,
    base_url: str | None = None,
) -> Workbench:
    records = tuple(MappingProxyType(dict(r)) for r in finding_records(graph))
    by_id: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        by_id.setdefault(record["id"], []).append(record)
    source = graph.metadata.get("source")
    return Workbench(
        repo=repo,
        graph=graph,
        usage_fixture=usage_fixture,
        schema_fixture=schema_fixture,
        inputs=MappingProxyType(dict(inputs)),
        records=records,
        findings_by_id=MappingProxyType({k: tuple(v) for k, v in by_id.items()}),
        findings_by_node=MappingProxyType(
            {k: tuple(v) for k, v in findings_by_node([dict(r) for r in records]).items()}
        ),
        coverage=MappingProxyType(analysis_coverage(graph)),
        source=MappingProxyType(dict(source)) if isinstance(source, dict) else None,
        baseline=None
        if baseline is None
        else MappingProxyType({k: frozenset(v) for k, v in baseline.items()}),
        baseline_path=baseline_path,
        base_url=base_url,
    )


class Staleness:
    """Whether the inputs changed since startup, re-checked at most every `interval` seconds.

    Once stale it stays stale: the graph in memory does not change until a restart.
    """

    def __init__(
        self,
        loaded: Mapping[str, Any],
        fingerprint: Callable[[], Mapping[str, Any]],
        interval: float = STALE_CHECK_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._loaded = dict(loaded)
        self._fingerprint = fingerprint
        self._interval = interval
        self._clock = clock
        self._checked_at = clock()
        self._stale = False
        self._lock = threading.Lock()

    def stale(self) -> bool:
        with self._lock:
            now = self._clock()
            if not self._stale and now - self._checked_at >= self._interval:
                self._checked_at = now
                self._stale = dict(self._fingerprint()) != self._loaded
            return self._stale

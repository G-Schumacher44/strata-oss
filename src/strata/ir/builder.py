"""Build the initial IR graph from parsed LookML files."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from strata.ir.parser import ParsedFile, parse_repo
from strata.ir.types import IRGraph, IRNode


def build_raw_graph(parsed_files: list[ParsedFile], repo_path: str | Path) -> IRGraph:
    """Create a raw graph that preserves parser output for deterministic resolution."""

    graph = IRGraph(
        repo_path=str(Path(repo_path)),
        built_at=datetime.now(UTC).isoformat(),
        metadata={"parsed_files": [asdict(parsed) for parsed in parsed_files]},
    )
    for parsed in parsed_files:
        graph.add_node(
            IRNode(
                id=f"file:{parsed.path}",
                kind="lookml_file",
                name=Path(parsed.path).name,
                source_file=parsed.path,
                attrs={"file_type": parsed.file_type},
            )
        )
    return graph


def build_repo_graph(repo_path: str | Path) -> IRGraph:
    """Parse a repo and return the unresolved graph."""

    parsed = parse_repo(repo_path)
    return build_raw_graph(parsed, repo_path)

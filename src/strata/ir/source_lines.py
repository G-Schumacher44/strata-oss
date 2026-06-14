"""Build-time capture of definition line numbers for IR nodes.

The LookML parser does not preserve source positions, so we scan each source file
once at build time and record the 1-based definition line in `node.attrs["source_line"]`.

Doing this at build time (here, in the IR layer) keeps the MCP layer's contract intact:
MCP tools answer from the resolved/cached IR and never read raw LookML during a live
request. Line numbers travel with the cache like any other node attribute.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from strata.ir.types import IRGraph

_FIELD_KW = "dimension|dimension_group|measure|filter|parameter"


def attach_source_lines(graph: IRGraph) -> None:
    """Populate `node.attrs['source_line']` for view / field / explore nodes (in place)."""
    repo_path = graph.repo_path
    for node_id, node in graph.nodes.items():
        if not node.source_file:
            continue
        if node_id.startswith("view:"):
            kind, name = "view", node.name
        elif node_id.startswith("explore:"):
            kind, name = "explore", node.name
        elif node_id.startswith("field:"):
            kind, name = "field", node.attrs.get("field_name", node.name.split(".")[-1])
        else:
            continue
        line = _definition_line(repo_path, node.source_file, kind, name)
        if line is not None:
            node.attrs["source_line"] = line


def _definition_line(repo_path: str, source_file: str, kind: str, name: str) -> int | None:
    if kind == "view":
        pattern = rf"^\s*view:\s*{re.escape(name)}\s*\{{"
    elif kind == "explore":
        pattern = rf"^\s*explore:\s*{re.escape(name)}\s*\{{"
    else:
        pattern = rf"^\s*(?:{_FIELD_KW}):\s*{re.escape(name)}\s*\{{"
    return _scan_file(_resolve(repo_path, source_file), pattern)


def _resolve(repo_path: str, source_file: str) -> str:
    p = Path(source_file)
    if p.is_absolute() or p.exists():
        return str(p)
    return str(Path(repo_path) / source_file)


@lru_cache(maxsize=512)
def _scan_file(path: str, pattern: str) -> int | None:
    try:
        with open(path, encoding="utf-8") as fh:
            for i, line in enumerate(fh, start=1):
                if re.search(pattern, line):
                    return i
    except OSError:
        return None
    return None

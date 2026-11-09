"""One place that turns what a caller typed into an IR identifier.

Both surfaces (`mcp/tools.py` and `cli/query.py`) resolve through here, so the same input gives
the same answer in an AI client and in a terminal. Every form is additive: the original
positional forms (`explore` + `model`, `view` + `field`, `kind:name`) still resolve.

- tables: exact name, else a unique dot-boundary suffix (`orders` -> `analytics.orders`)
- explores: `model` optional; `model.explore` accepted as one argument
- fields: `view.field` accepted as one argument
- changed objects: `kind:name`, `{kind, name}`, `.lkml` paths, or a bare name (= a view)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from strata_lookml.errors import InvalidInput, NotFound
from strata_lookml.ir.types import IRGraph, explore_id, explore_key

_CHANGED_HINT = 'Pass "<kind>:<name>" (e.g. "view:orders"), {"kind", "name"}, a .lkml path, or a bare view name.'
_MAX_CANDIDATES = 10


def _candidates(names: list[str]) -> str:
    shown = ", ".join(sorted(names)[:_MAX_CANDIDATES])
    return shown + (", ..." if len(names) > _MAX_CANDIDATES else "")


def table_matches(graph: IRGraph, name: str) -> list[str]:
    """The tables `name` can mean: the exact name alone, else every table ending in `.name`."""
    wanted = name.strip().strip("`")
    tables = [node.name for node in graph.nodes_by_kind("physical_table")]
    if wanted in tables:
        return [wanted]
    return [t for t in tables if t.endswith(f".{wanted}")] if wanted else []


def resolve_table(graph: IRGraph, name: str) -> str:
    """Return the IR's physical table name for `name`: exact, else the one table ending in
    `.name`. Ambiguous -> InvalidInput listing candidates; none -> NotFound."""
    matches = table_matches(graph, name)
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise InvalidInput(
            f"table name is ambiguous: {name!r} matches {_candidates(matches)}.",
            hint="Pass more of the name, e.g. dataset.table.",
        )
    raise NotFound(
        f"physical_table not found in IR: {name}",
        hint="Pass the table as written in sql_table_name, or a unique dataset.table / table "
        "suffix; strata_view_sources lists every view's table.",
    )


def _explore_pairs(graph: IRGraph) -> list[tuple[str, str]]:
    return [(str(node.attrs.get("model")), node.name) for node in graph.nodes_by_kind("explore")]


def explores_by_key(graph: IRGraph, key: str) -> list[tuple[str, str]]:
    """The (model, explore) pairs whose canonical `model.explore` key is exactly `key` (the form
    `links.object_path` publishes). Unlike `explore_matches` it never splits at a guessed dot,
    so a dotted model name resolves; more than one pair only when dots in the model and explore
    names make two keys spell the same string."""
    return [p for p in _explore_pairs(graph) if explore_key(*p) == key]


def explore_matches(graph: IRGraph, explore: str) -> list[tuple[str, str]]:
    """The (model, explore) pairs a model-less `explore` can mean: every explore of that name,
    else the one `model.explore` it spells."""
    pairs = _explore_pairs(graph)
    matches = [p for p in pairs if p[1] == explore]
    if not matches and "." in explore:
        # A lone `model.explore` argument; an explore whose own name has a dot matched above.
        model_part, _, explore_part = explore.partition(".")
        matches = [p for p in pairs if p == (model_part, explore_part)]
    return matches


def resolve_explore(graph: IRGraph, explore: str, model: str | None = None) -> tuple[str, str]:
    """Return (model, explore). `model` may be omitted if the explore name is unique, or the
    explore may be given as `model.explore`."""
    if model:
        if graph.get_node(f"model:{model}") is None:
            models = sorted(node.name for node in graph.nodes_by_kind("model"))
            raise NotFound(f"model not found: {model}", hint=f"Known models: {', '.join(models)}.")
        if graph.get_node(explore_id(model, explore)) is None:
            raise NotFound(
                f"explore not found: {explore_key(model, explore)}",
                hint="strata_navigate finds an explore by name.",
            )
        return model, explore

    matches = explore_matches(graph, explore)
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise InvalidInput(
            f"explore name is ambiguous: {explore!r} exists in "
            f"{_candidates([f'{m}.{e}' for m, e in matches])}.",
            hint="Pass the model too: model.explore, or the model argument.",
        )
    raise NotFound(
        f"explore not found: {explore}",
        hint="strata_navigate finds an explore by name; pass model.explore or a model to be exact.",
    )


def resolve_field(view: str, field: str | None = None) -> tuple[str, str]:
    """Return (view, field). `field` may be omitted when `view` is `view.field`."""
    if field:
        return view, field
    view_part, dot, field_part = view.partition(".")
    if not dot or not view_part or not field_part:
        raise InvalidInput(
            f"field must be given as view.field or as a view and a field. Got: {view!r}",
            hint="Example: orders.total_revenue. strata_find_field locates a field by fragment.",
        )
    return view_part, field_part


def parse_changed(value: Any) -> tuple[str, str]:
    """Normalise one changed object to (kind, name): `kind:name`, `{kind, name}`, a `.lkml`
    path (kind from the file name), or a bare name (a view)."""
    if isinstance(value, dict):
        if "kind" not in value or "name" not in value:
            raise InvalidInput(
                f"changed object must have 'kind' and 'name'. Got: {value!r}", hint=_CHANGED_HINT
            )
        return str(value["kind"]), str(value["name"])
    if not isinstance(value, str) or not value.strip():
        raise InvalidInput(
            f"changed object must be a string or object. Got: {value!r}", hint=_CHANGED_HINT
        )
    text = value.strip()
    if text.endswith(".lkml"):
        return _from_lkml_path(text)
    if ":" in text:
        kind, _, name = text.partition(":")
        if not kind or not name:
            raise InvalidInput(
                f"changed object must use '<kind>:<name>'. Got: {value!r}", hint=_CHANGED_HINT
            )
        return kind, name
    return "view", text


def _from_lkml_path(path: str) -> tuple[str, str]:
    file_name = Path(path).name
    for kind in ("view", "model", "explore"):
        marker = f".{kind}."
        if marker in file_name:
            return kind, file_name.split(marker)[0]
    return "view", file_name.removesuffix(".lkml")

"""Read-only MCP tool implementations over a resolved IRGraph."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from strata_lookml.errors import InvalidInput, NotFound
from strata_lookml.identifiers import resolve_explore, resolve_field, resolve_table
from strata_lookml.ir.types import IRGraph, explore_id, explore_key
from strata_lookml.l1.enrich import (
    analysis_coverage,
    direct_view_consumers,
    evidence_facts,
    view_consumer_map,
)
from strata_lookml.validation import validation_scope

FIND_FIELD_DEFAULT_LIMIT = 50
FIND_FIELD_MAX_LIMIT = 200
OBJECT_KINDS = ("explore", "view", "pdt", "table", "field")

_FIXTURE_ENV = {"usage": "STRATA_USAGE_FIXTURE", "schema": "STRATA_SCHEMA_FIXTURE"}


def _unchecked_hint(missing: list[str]) -> str:
    envs = " and ".join(_FIXTURE_ENV[name] for name in missing)
    return (
        f"The {' and '.join(missing)} checks did not run, so empty results mean 'not checked', "
        f"not 'nothing found'. Set {envs} in the MCP server env (see `strata mcp config`) "
        "and restart the server."
    )


def list_envelope(items: Sequence[Any], **extra: Any) -> dict[str, Any]:
    """The one shape every list tool returns: {"items": [...], "count": N} as a single JSON
    object (a bare list is split by the SDK into one content block per element)."""
    return {"items": list(items), "count": len(items), **extra}


def l1_list_envelope(graph: IRGraph, items: Sequence[Any], check: str) -> dict[str, Any]:
    """list_envelope for a tool whose result needs an L1 check (`usage` or `schema`): adds the
    coverage flag and, when that check did not run, a hint naming the fixture env var."""
    checked = analysis_coverage(graph)[check]
    extra: dict[str, Any] = {f"{check}_checked": checked}
    if not checked:
        extra["hint"] = _unchecked_hint([check])
    return list_envelope(items, **extra)


def strata_query_field(graph: IRGraph, view: str, field: str | None = None) -> dict[str, Any]:
    view, field = resolve_field(view, field)
    node = graph.get_node(f"field:{view}.{field}")
    if node is None:
        raise NotFound(
            f"field not found: {view}.{field}",
            hint="Search field names with strata_find_field (CLI: strata query find-field).",
        )
    return {
        "sql": node.attrs.get("sql"),
        "type": node.attrs.get("type"),
        "tags": node.attrs.get("tags", []),
        "source_file": node.source_file,
        "resolution_chain": node.attrs.get("resolution_chain", []),
    }


def strata_list_orphans(graph: IRGraph, kind: str = "all") -> list[dict[str, Any]]:
    if kind not in {"all", "view"}:
        raise InvalidInput(
            "kind must be one of: all, view (only orphan views are detected; "
            f"explore/field orphans are not supported). Got: {kind!r}"
        )
    orphans = graph.metadata.get("orphans", [])
    if kind == "all":
        return list(orphans)
    return [orphan for orphan in orphans if orphan.get("kind") == kind]


def strata_explore_deps(graph: IRGraph, explore: str, model: str | None = None) -> dict[str, Any]:
    model, explore = resolve_explore(graph, explore, model)
    node = graph.nodes[explore_id(model, explore)]
    joins = [
        {
            "name": join["name"],
            "view": join.get("from") or join["name"],
            "type": join.get("type"),
        }
        for join in node.attrs.get("joins", [])
    ]
    view_names = [node.attrs.get("base_view")] + [join["view"] for join in joins]
    field_count = sum(
        _field_count_for_view(graph, view_name) for view_name in view_names if view_name
    )
    return {
        "model": model,
        "explore": explore,
        "base_view": node.attrs.get("base_view"),
        "joins": joins,
        "resolution_chain": node.attrs.get("resolution_chain", []),
        "field_count": field_count,
    }


def strata_ir_status(graph: IRGraph) -> dict[str, Any]:
    return {
        "repo_path": graph.repo_path,
        "built_at": graph.built_at,
        "node_counts": graph.node_counts(),
        "edge_count": len(graph.edges),
        "cache_path": graph.cache_path,
    }


def strata_usage_summary(graph: IRGraph) -> dict[str, Any]:
    l1 = graph.metadata.get("l1", {})
    usage = l1.get("explore_usage", {})
    total_queries = sum(item.get("query_count", 0) for item in usage.values())
    dead_code = l1.get("dead_code", [])
    # Active/dead counts share ONE population: every resolved explore in the IR, which is what
    # _dead_code() checks. `explore_count` (usage rows only) misses unqueried explores, so
    # subtracting dead explores from it undercounts and can go negative.
    ir_explore_count = sum(1 for node in graph.nodes.values() if node.kind == "explore")
    dead_explore_count = sum(1 for item in dead_code if item.get("kind") == "explore")
    coverage = analysis_coverage(graph)
    usage_checked = coverage["usage"]
    not_run = [name for name in ("usage", "schema") if not coverage[name]]
    return {
        # usage_checked / schema_checked say which L1 checks ran; a 0 count means "nothing found"
        # only when its check ran. has_l1 is DEPRECATED: it is true when ANY L1 data exists, so a
        # schema-only build reports true with dead_code_count 0. Kept for compatibility.
        "usage_checked": usage_checked,
        "schema_checked": coverage["schema"],
        "has_l1": bool(l1),
        "hint": _unchecked_hint(not_run) if not_run else None,
        "period": l1.get("period"),
        # Explores with a usage row (kept for compatibility); not the resolved-explore total.
        "explore_count": len(usage),
        "ir_explore_count": ir_explore_count,
        "dead_explore_count": dead_explore_count,
        "dead_view_count": sum(1 for item in dead_code if item.get("kind") == "view"),
        # None when the usage checks did not run: no dead-code verdict exists to subtract.
        "active_explore_count": (ir_explore_count - dead_explore_count) if usage_checked else None,
        "total_queries": total_queries,
        "dead_code_count": len(dead_code),
        "pdt_count": len(l1.get("pdt_ledger", [])),
        "unused_pdt_count": sum(
            1 for item in l1.get("pdt_ledger", []) if item.get("status") == "unused"
        ),
        "zombie_pdt_count": sum(
            1 for item in l1.get("pdt_ledger", []) if item.get("status") == "zombie"
        ),
        "schema_drift_count": len(l1.get("schema_drift", [])),
    }


def strata_dead_code_register(graph: IRGraph) -> list[dict[str, Any]]:
    return list(graph.metadata.get("l1", {}).get("dead_code", []))


def strata_pdt_costs(graph: IRGraph) -> list[dict[str, Any]]:
    return list(graph.metadata.get("l1", {}).get("pdt_ledger", []))


def strata_schema_drift(graph: IRGraph) -> list[dict[str, Any]]:
    return list(graph.metadata.get("l1", {}).get("schema_drift", []))


def strata_validation_scope(
    graph: IRGraph, changed: Sequence[str | dict[str, Any]]
) -> dict[str, Any]:
    return validation_scope(graph, list(changed))


def strata_impact(graph: IRGraph, physical_table: str) -> dict[str, Any]:
    requested = physical_table
    physical_table = resolve_table(graph, requested)
    table_id = f"physical_table:{physical_table}"

    # Build reverse adjacency index once — O(E) — so inner loops are O(degree) not O(E)
    edges_by_target: dict[str, list] = {}
    for edge in graph.edges:
        edges_by_target.setdefault(edge.target, []).append(edge)

    views: set[str] = set()
    for edge in edges_by_target.get(table_id, []):
        if edge.relation == "view→physical_table":
            views.add(edge.source.removeprefix("view:"))
        elif edge.relation == "pdt→upstream":
            pdt = graph.get_node(edge.source)
            if pdt:
                views.add(pdt.name)

    explores: set[str] = set()
    fields: set[str] = set()
    for view in views:
        for edge in edges_by_target.get(f"view:{view}", []):
            if edge.relation in {"explore→base_view", "explore→joined_view"}:
                node = graph.get_node(edge.source)
                if node:
                    explores.add(explore_key(node.attrs.get("model", ""), node.name))
        prefix = f"field:{view}."
        fields.update(
            node_id.removeprefix("field:") for node_id in graph.nodes if node_id.startswith(prefix)
        )
    return {
        "physical_table": physical_table,
        "resolved_from": requested if requested != physical_table else None,
        "views": sorted(views),
        "explores": sorted(explores),
        "fields": sorted(fields),
    }


def strata_find_field(
    graph: IRGraph, query: str, kind: str = "all", limit: int = FIND_FIELD_DEFAULT_LIMIT
) -> dict[str, Any]:
    """Search all views for fields matching a name fragment, SQL substring, or tag.

    Returns up to `limit` matches (default 50, max 200). The `count` field is the number of
    returned matches, not the total; `truncated` is true when more existed. Narrow the query
    or raise `limit` for exhaustive output.
    """
    if not 1 <= limit <= FIND_FIELD_MAX_LIMIT:
        raise InvalidInput(f"limit must be between 1 and {FIND_FIELD_MAX_LIMIT}. Got: {limit}")
    valid_kinds = {"all", "dimension", "measure", "filter", "parameter"}
    if kind not in valid_kinds:
        raise InvalidInput(f"kind must be one of: {', '.join(sorted(valid_kinds))}. Got: {kind!r}")

    query_lower = query.lower()
    matches: list[dict[str, Any]] = []
    total = 0
    for node_id, node in graph.nodes.items():
        if not node_id.startswith("field:"):
            continue
        field_kind = node.attrs.get("field_kind", node.attrs.get("type", ""))
        if kind != "all" and field_kind != kind:
            continue
        name_hit = query_lower in node.name.lower()
        sql_hit = query_lower in str(node.attrs.get("sql", "")).lower()
        tag_hit = any(query_lower in str(t).lower() for t in node.attrs.get("tags", []))
        label_hit = query_lower in str(node.attrs.get("label", "")).lower()
        desc_hit = query_lower in str(node.attrs.get("description", "")).lower()
        group_hit = query_lower in str(node.attrs.get("group_label", "")).lower()
        if name_hit or sql_hit or tag_hit or label_hit or desc_hit or group_hit:
            total += 1
            if len(matches) < limit:
                matches.append(
                    {
                        "view": node.attrs.get("view", node_id.split(":")[1].split(".")[0]),
                        "field": node.attrs.get("field_name", node.name.split(".")[-1]),
                        "type": field_kind,
                        "sql": node.attrs.get("sql"),
                        "label": node.attrs.get("label"),
                        "description": node.attrs.get("description"),
                        "source_file": node.source_file,
                        "source_line": node.attrs.get("source_line"),
                    }
                )

    return {
        "query": query,
        "kind": kind,
        "matches": matches,
        "count": len(matches),
        "truncated": total > limit,
    }


def strata_view_sources(graph: IRGraph, model: str | None = None) -> dict[str, Any]:
    """List all views with their physical BQ table backing and field counts.

    Pass model= to restrict to views reachable from a specific model's explores.
    """
    # If model filter requested, collect views reachable from that model's explores
    scoped_views: set[str] | None = None
    if model:
        if graph.get_node(f"model:{model}") is None:
            models = sorted(node.name for node in graph.nodes_by_kind("model"))
            raise NotFound(f"model not found: {model}", hint=f"Known models: {', '.join(models)}.")
        scoped_views = set()
        for node_id, node in graph.nodes.items():
            if node_id.startswith("explore:") and node.attrs.get("model") == model:
                base = node.attrs.get("base_view")
                if base:
                    scoped_views.add(base)
                for join in node.attrs.get("joins", []):
                    scoped_views.add(join.get("from") or join["name"])

    # Build forward edge index for view→physical_table lookups
    edges_by_source: dict[str, list] = {}
    for edge in graph.edges:
        edges_by_source.setdefault(edge.source, []).append(edge)

    views = []
    for node_id, node in graph.nodes.items():
        if not node_id.startswith("view:"):
            continue
        view_name = node.name
        if scoped_views is not None and view_name not in scoped_views:
            continue

        # Prefer edge-derived physical table; fall back to sql_table_name in body
        physical_table: str | None = None
        for edge in edges_by_source.get(node_id, []):
            if edge.relation == "view→physical_table":
                physical_table = edge.target.removeprefix("physical_table:")
                break
        if physical_table is None:
            body = node.attrs.get("body", {})
            physical_table = body.get("sql_table_name")

        views.append(
            {
                "name": view_name,
                "physical_table": physical_table,
                "field_count": _field_count_for_view(graph, view_name),
                "source_file": node.source_file,
                "source_line": node.attrs.get("source_line"),
                "orphan": node.attrs.get("orphan", False),
            }
        )

    views.sort(key=lambda v: v["name"])
    return {"model_filter": model, "views": views, "count": len(views)}


def chart_output_dir() -> Path:
    """The canonical chart output root (allowed by strata_render_chart's path guard)."""
    return (Path.home() / ".strata" / "output").resolve()


def strata_render_chart(spec_yaml: str, data_json: str, out_path: str) -> dict[str, str]:
    """Render a Vega-Lite spec (YAML or JSON string) + JSON data rows to an HTML file."""
    import json as _json

    # Resolve the directory only: resolving the final component would follow a symlink there and
    # defeat both this guard and render_chart's O_NOFOLLOW check.
    requested = Path(out_path).expanduser()
    resolved = requested.parent.resolve() / requested.name
    if resolved.is_symlink():
        # Refuse here too, not only in render_chart: O_NOFOLLOW is absent on some platforms.
        raise InvalidInput(f"out_path must not be a symlink. Got: {out_path!r}")
    allowed_roots = [
        chart_output_dir(),
        Path("/tmp").resolve(),
    ]
    if not any(resolved.is_relative_to(r) for r in allowed_roots):
        raise InvalidInput(
            f"out_path must be within ~/.strata/output/ or /tmp/. Got: {out_path!r}",
            hint=f"Write under {chart_output_dir()}/.",
        )
    if resolved.suffix.lower() != ".html":
        raise InvalidInput(f"out_path must end in .html. Got: {out_path!r}")

    import yaml as _yaml

    try:
        spec = _yaml.safe_load(spec_yaml)
    except _yaml.YAMLError as exc:
        raise InvalidInput(f"spec_yaml is not valid YAML or JSON: {exc}") from exc
    try:
        rows = _json.loads(data_json)
    except ValueError as exc:
        raise InvalidInput(f"data_json is not valid JSON: {exc}") from exc
    from strata_lookml.viz.render import render_chart

    path = render_chart(spec, rows, resolved)
    return {"path": str(path), "status": "ok"}


def strata_chart_templates(charts_dir: str | Path) -> list[dict[str, str]]:
    """List available chart templates with mark type."""
    charts_dir = Path(charts_dir)
    templates = []
    for f in sorted(charts_dir.glob("*.yml")):
        content = f.read_text(encoding="utf-8")
        mark_m = re.search(r"^mark:\s*(\w+)", content, re.MULTILINE)
        templates.append(
            {
                "name": f.stem,
                "mark": mark_m.group(1) if mark_m else "?",
            }
        )
    return templates


def strata_list_skills(skills_dir: str | Path) -> list[dict[str, str]]:
    """List available skills with compact metadata — name, domain, mode, trigger only."""
    skills_dir = Path(skills_dir)
    skills = []
    for skill_file in sorted(skills_dir.rglob("SKILL.md")):
        content = skill_file.read_text(encoding="utf-8")
        meta = _parse_skill_meta(content)
        meta["name"] = skill_file.parent.name
        skills.append(meta)
    return skills


def strata_skill(skills_dir: str | Path, name: str) -> str:
    """Return full SKILL.md content for a given skill name. Pull-on-demand."""
    skills_dir = Path(skills_dir)
    for skill_file in skills_dir.rglob("SKILL.md"):
        if skill_file.parent.name == name:
            return skill_file.read_text(encoding="utf-8")
    names = sorted(skill_file.parent.name for skill_file in skills_dir.rglob("SKILL.md"))
    raise NotFound(f"skill not found: {name}", hint=f"Available skills: {', '.join(names)}.")


def strata_conductor_status(conductor_dir: str | Path) -> dict[str, Any]:
    """Return active slice, mode, and next steps. Capped for small context windows."""
    from strata_lookml.conductor_state import read_status

    return read_status(conductor_dir)


def _parse_skill_meta(content: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for key in ("domain", "mode", "complexity", "version"):
        m = re.search(rf"^{key}:\s*(.+)$", content, re.MULTILINE | re.IGNORECASE)
        if m:
            meta[key] = m.group(1).strip()
    trigger_m = re.search(r"## Trigger\s*\n+([\s\S]+?)(?:\n\n---|\n##|$)", content)
    if trigger_m:
        bullets = re.findall(r"^[-*]\s+(.+)$", trigger_m.group(1), re.MULTILINE)
        if bullets:
            meta["trigger"] = bullets[0]
    return meta


def _field_count_for_view(graph: IRGraph, view: str) -> int:
    prefix = f"field:{view}."
    return sum(1 for node_id in graph.nodes if node_id.startswith(prefix))


def _edge_targets(graph: IRGraph, source: str, relation: str, prefix: str) -> list[str]:
    return sorted(
        {
            edge.target.removeprefix(prefix)
            for edge in graph.edges
            if edge.source == source and edge.relation == relation
        }
    )


def _view_ancestors(chain: Sequence[str], own_name: str) -> list[str]:
    """Ancestors from a view's resolution chain: `+` refinement markers stripped, the view
    itself dropped (a refined view's chain ends in its own `+name`), duplicates removed in order."""
    ancestors: dict[str, None] = {}
    for entry in chain:
        entry = entry.lstrip("+")
        if entry != own_name:
            ancestors.setdefault(entry)
    return list(ancestors)


def _node_finding_ids(graph: IRGraph, kind: str, node_id: str, name: str) -> list[str]:
    """Ids of the findings on one node, taken from `findings_by_category` (the same records
    `strata check` gates on), matched by each category's own subject."""
    # Deferred: gate -> synthesis.slices imports this module.
    from strata_lookml.gate import findings_by_category

    l1 = graph.metadata.get("l1", {})
    ids: set[str] = set()
    if kind == "explore":
        ids.add(f"dead:explore:{name}")
    elif kind == "view":
        ids.add(f"dead:view:{name}")
    elif kind == "pdt":
        ids.add(node_id)
    elif kind == "table":
        ids.update(r["id"] for r in l1.get("schema_drift", []) if r.get("table") == name)
    elif kind == "field":
        ids.update(r["id"] for r in l1.get("schema_drift", []) if r.get("field") == name)
    present = {f["id"] for records in findings_by_category(graph).values() for f in records or []}
    return sorted(ids & present)


def _explore_content(graph: IRGraph, key: str) -> dict[str, Any] | None:
    """Content that references this explore, from the L1 usage facts; None when usage was not
    checked (never 0). The window is the usage period the facts were pulled for, not all time."""
    l1 = graph.metadata.get("l1", {})
    if not analysis_coverage(graph)["usage"]:
        return None
    items = sorted(
        (
            {"content_id": r["content_id"], "content_type": r["content_type"], "title": r["title"]}
            for r in l1.get("content_references", [])
            if explore_key(r["model"], r["explore"]) == key
        ),
        key=lambda r: (r["content_type"], r["content_id"]),
    )
    by_type: dict[str, int] = {}
    for item in items:
        by_type[item["content_type"]] = by_type.get(item["content_type"], 0) + 1
    period = l1.get("period")
    days = period.get("days") if isinstance(period, dict) else None
    return {
        "reference_count": evidence_facts(graph)["content_reference_counts"].get(key, 0),
        "by_type": by_type,
        "items": items,
        "window": period,
        "window_label": f"viewed in {days}d"
        if days
        else "viewed in the usage window (length not recorded)",
    }


def strata_object(graph: IRGraph, kind: str, name: str) -> dict[str, Any]:
    """One read for an object's definition site, lineage, findings, coverage and usage.

    kind is explore | view | pdt | table | field. Upstream/downstream reuse
    strata_explore_deps / strata_impact / the consumer maps, grouped by relation.
    `content` (explores only) counts content viewed in the usage window; it is None, never 0,
    when usage was not checked or the kind has no content.
    """
    if kind not in OBJECT_KINDS:
        raise InvalidInput(f"kind must be one of: {', '.join(OBJECT_KINDS)}. Got: {kind!r}")
    coverage = analysis_coverage(graph)
    upstream: dict[str, list[str]] = {}
    downstream: dict[str, list[Any]] = {}
    content: dict[str, Any] | None = None
    details: dict[str, Any] = {}

    if kind == "explore":
        model, explore = resolve_explore(graph, name)
        node = graph.nodes[explore_id(model, explore)]
        label = explore_key(model, explore)
        deps = strata_explore_deps(graph, explore, model)
        upstream = {
            "base_view": [deps["base_view"]] if deps["base_view"] else [],
            "joined_view": sorted({j["view"] for j in deps["joins"]}),
        }
        content = _explore_content(graph, label)
        if content is not None:
            downstream = {"content": content["items"]}
        details = {"model": model, "joins": deps["joins"], "field_count": deps["field_count"]}
    elif kind == "table":
        table = resolve_table(graph, name)
        node = graph.nodes[f"physical_table:{table}"]
        label = table
        impact = strata_impact(graph, table)
        downstream = {k: impact[k] for k in ("views", "explores", "fields")}
    elif kind == "field":
        view, field = resolve_field(name)
        found = graph.get_node(f"field:{view}.{field}")
        if found is None:
            raise NotFound(
                f"field not found: {view}.{field}",
                hint="Search field names with strata_find_field (CLI: strata query find-field).",
            )
        node = found
        label = node.name
        upstream = {
            "view": [view],
            "physical_table": _edge_targets(
                graph, f"view:{view}", "view→physical_table", "physical_table:"
            ),
        }
        downstream = {"explore": view_consumer_map(graph).get(view, [])}
        details = strata_query_field(graph, view, field)
    else:  # view | pdt
        found = graph.get_node(f"{kind}:{name}")
        if found is None:
            raise NotFound(
                f"{kind} not found: {name}",
                hint="strata_view_sources lists every view; strata_pdt_costs lists PDTs.",
            )
        node = found
        label = node.name
        if kind == "view":
            upstream = {
                "physical_table": _edge_targets(
                    graph, node.id, "view→physical_table", "physical_table:"
                ),
                "pdt": _edge_targets(graph, node.id, "view→pdt", "pdt:"),
                "extends": _view_ancestors(node.attrs.get("resolution_chain", []), node.name),
            }
            downstream = {"explore": view_consumer_map(graph).get(name, [])}
            details = {"field_count": _field_count_for_view(graph, name)}
        else:
            upstream = {
                "physical_table": _edge_targets(graph, node.id, "pdt→upstream", "physical_table:")
            }
            downstream = {"explore": direct_view_consumers(graph).get(name, [])}
            ledger = graph.metadata.get("l1", {}).get("pdt_ledger", [])
            details = {"ledger": next((r for r in ledger if r.get("view") == name), None)}

    return {
        "kind": kind,
        "id": node.id,
        "name": label,
        "source_file": node.source_file,
        "source_line": node.attrs.get("source_line"),
        "upstream": upstream,
        "downstream": downstream,
        "findings": _node_finding_ids(graph, kind, node.id, label),
        "coverage": {"usage_checked": coverage["usage"], "schema_checked": coverage["schema"]},
        "content": content,
        "details": details,
    }

"""The one place a workbench URL is built from an IR node id or a finding id.

Paths follow the workbench URL scheme: `/explore/<model>.<explore>`, `/view/<v>`, `/pdt/<v>`,
`/table/<dataset.table>`, `/field/<view>.<field>`, `/finding/<id>`. `link` joins a path to the
configured base; with no base there is no link (a guessed port would be wrong). Plain Python:
check, PR reports, MCP, the workbench and the TUI all link through here.
"""

from __future__ import annotations

from urllib.parse import quote

from strata_lookml.ir.types import explore_key

# IR node kind -> the workbench page for it. Explores are handled apart: their id carries the
# model (`explore:<model>:<name>`), their page key is `explore_key(model, name)`.
_PAGES = {"view": "view", "pdt": "pdt", "physical_table": "table", "field": "field"}


def _segment(value: str) -> str:
    return quote(value, safe="")


def object_path(node_id: str) -> str | None:
    """The workbench path of an IR node, or None for a kind with no page (model, include, ...)."""
    kind, _, rest = node_id.partition(":")
    if not rest:
        return None
    if kind == "explore":
        model, _, name = rest.partition(":")
        return f"/explore/{_segment(explore_key(model, name))}" if model and name else None
    page = _PAGES.get(kind)
    return f"/{page}/{_segment(rest)}" if page else None


def finding_path(finding_id: str) -> str:
    """The workbench path of a finding: its id quoted whole (`/` and `:` included)."""
    return f"/finding/{_segment(finding_id)}"


def link(base: str | None, path: str | None) -> str | None:
    """`path` under the workbench `base`, or None without a base (or a path).

    A static export (`base` ending `.html` or containing `#`) links by hash: `<base>#/<path>`,
    replacing any fragment already on the base. Otherwise the path form `<base>/<path>`.
    """
    if not base or not path:
        return None
    relative = path.lstrip("/")
    if base.endswith(".html") or "#" in base:
        return f"{base.split('#', 1)[0]}#/{relative}"
    return f"{base.rstrip('/')}/{relative}"

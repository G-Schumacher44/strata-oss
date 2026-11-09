"""The one Jinja environment the workbench renders through.

Escaping model: autoescape is on for every template, whatever its extension. Templates never
mark values safe (`|safe`, `{% autoescape false %}` and `Markup(` are banned by
tests/test_workbench_render.py). The single sanctioned way to emit raw HTML is `safe_svg()`
below, the only place in the package allowed to construct `markupsafe.Markup`.
"""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape
from markupsafe import Markup

_ENV: Environment | None = None


def make_environment() -> Environment:
    """Build a fresh environment: autoescape always on, strict undefined, no extensions."""
    return Environment(
        loader=PackageLoader("strata_lookml.workbench", "templates"),
        # default=True: an unknown or missing extension (.txt, .svg, string templates) escapes.
        autoescape=select_autoescape(default_for_string=True, default=True),
        undefined=StrictUndefined,
        extensions=[],
        keep_trailing_newline=True,
    )


def get_environment() -> Environment:
    global _ENV
    if _ENV is None:
        _ENV = make_environment()
    return _ENV


def render(template_name: str, **context: Any) -> str:
    """Render a packaged template. Every value in `context` is escaped on output."""
    return get_environment().get_template(template_name).render(**context)


def safe_svg(svg: str) -> Markup:
    """Mark server-built inline SVG as raw HTML.

    Reviewed single entry point for intentional raw markup. The caller must have built `svg`
    from escaped parts (never from request or LookML text interpolated unescaped).
    """
    return Markup(svg)  # the one sanctioned construction site

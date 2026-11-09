"""The one Jinja environment the workbench renders through.

Escaping model: autoescape is on for every template, whatever its extension. Templates never
mark values safe (`|safe`, `{% autoescape false %}` and `Markup(` are banned by
tests/test_workbench_render.py). Raw HTML enters a page only through the helpers below, which
all construct `markupsafe.Markup` in `_raw` (the only place in the package allowed to): server-
built SVG (`safe_svg`), and for the static export (`export.py`) a packaged script or stylesheet
(`inline_script`, `inline_style`), a JSON payload (`json_script`) and a rendered page body
(`page_fragment`). Each refuses text that could close the element it is placed in.
"""

from __future__ import annotations

import json
import re
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


def embed_json(obj: Any) -> str:
    """json.dumps for a JSON response or a `<script>` payload, with every `<` as `\\u003c`.

    json.dumps leaves `<` intact, so a value holding `</script>` would end the surrounding
    script element and hand the rest to the HTML parser as markup (the classic breakout).
    `\\u003c` is `<` again after JSON parsing, so no consumer sees a difference.
    """
    return json.dumps(obj).replace("<", "\\u003c")


def _raw(text: str) -> Markup:
    """The one construction site of `Markup`: callers below have checked `text` first."""
    return Markup(text)


def safe_svg(svg: str) -> Markup:
    """Mark server-built inline SVG as raw HTML.

    The caller must have built `svg` from escaped parts (never from request or LookML text
    interpolated unescaped).
    """
    return _raw(svg)


def _refuse(text: str, closer: str, what: str) -> str:
    if re.search(re.escape(closer), text, re.IGNORECASE):
        raise ValueError(f"{what} contains {closer!r}: it would close its element early")
    return text


def inline_script(source: str) -> Markup:
    """A packaged script's source for an inline `<script>` (the export has no /static/)."""
    # `<!--` puts a script element into its escaped state, where a later `<script` nests.
    return _raw(_refuse(_refuse(source, "</script", "script"), "<!--", "script"))


def inline_style(source: str) -> Markup:
    """A packaged stylesheet for an inline `<style>`."""
    return _raw(_refuse(source, "</style", "stylesheet"))


def json_script(obj: Any) -> Markup:
    """`obj` as the body of a `<script type="application/json">`: `embed_json` has no `<`."""
    return _raw(embed_json(obj))


def page_fragment(html: str) -> Markup:
    """A page body the workbench rendered (autoescaped), for an export `<template>`."""
    return _raw(_refuse(html, "</template", "page body"))

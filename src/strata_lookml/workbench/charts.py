"""Inline SVG bars for the workbench, built from numbers only.

`bar()` takes numbers and returns an SVG string whose every attribute value is a number or a
fixed literal. No label, name or other text ever enters it, so a hostile LookML name cannot
reach SVG markup. The caller passes the result through `render.safe_svg`, the one sanctioned
raw-HTML site. Colour comes from CSS on the surrounding element, not from the SVG.
"""

from __future__ import annotations

import math


def _number(value: float, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"bar() {what} must be a number, got {type(value).__name__}")
    if not math.isfinite(value):
        raise ValueError(f"bar() {what} must be finite")
    return float(value)


def bar(value: float, total: float, width: int = 120, height: int = 8) -> str:
    """A horizontal bar: `value` out of `total`, drawn `width` x `height` pixels.

    A non-positive `total` or `value` draws the empty track only; a positive `value` always
    fills at least one pixel so a small share stays visible. The fill is clamped to the track.
    """
    v, t = _number(value, "value"), _number(total, "total")
    w, h = int(_number(width, "width")), int(_number(height, "height"))
    if w < 1 or h < 1:
        raise ValueError("bar() width and height must be positive")
    fill = 0 if t <= 0 or v <= 0 else min(w, max(1, round(w * v / t)))
    parts = [
        f'<svg class="bar" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        'role="img" aria-hidden="true" focusable="false">',
        f'<rect class="track" x="0" y="0" width="{w}" height="{h}" rx="2"/>',
    ]
    if fill:
        parts.append(f'<rect class="fill" x="0" y="0" width="{fill}" height="{h}" rx="2"/>')
    parts.append("</svg>")
    return "".join(parts)

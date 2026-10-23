"""Strata viz renderer — Vega-Lite YAML/JSON spec + data → interactive HTML."""

from __future__ import annotations

import argparse
import csv
import html as _html_module
import json
import os
import webbrowser
from pathlib import Path
from typing import Any


def _resolve_charts_dir() -> Path:
    env = os.environ.get("STRATA_CHARTS_PATH")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent / "charts"


def _read_js(filename: str) -> str:
    js_dir = Path(__file__).resolve().parent.parent / "assets" / "js"
    return (js_dir / filename).read_text(encoding="utf-8")


_CHARTS_DIR = _resolve_charts_dir()

_HTML = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  {scripts}
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, sans-serif;
      margin: 40px;
      background: #f5f5f5;
    }}
    #chart {{
      background: white;
      padding: 24px;
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.12);
      display: inline-block;
    }}
  </style>
</head>
<body>
  <div id="chart"></div>
  <script>
    vegaEmbed('#chart', {spec_json}, {{renderer: 'svg', actions: true}}).catch(console.error);
  </script>
</body>
</html>
"""


def render_chart(
    spec: dict[str, Any],
    rows: list[dict],
    out_path: Path | str,
    open_browser: bool = False,
) -> Path:
    """Render a Vega-Lite spec dict + data rows to an HTML file. Returns the output path."""
    spec = _strip_empty_channels(spec)
    spec = _apply_auto_labels(spec)
    spec = _apply_show_labels(spec)
    spec["data"] = {"values": rows}
    spec.setdefault("$schema", "https://vega.github.io/schema/vega-lite/v5.json")
    spec.setdefault("width", 640)
    spec.setdefault("height", 400)

    mark = spec.get("mark", {})
    if isinstance(mark, str):
        spec["mark"] = {"type": mark, "tooltip": True}
    elif isinstance(mark, dict):
        mark.setdefault("tooltip", True)

    title = _html_module.escape(str(spec.get("title", "Strata Chart")))
    scripts = "\n  ".join(
        f"<script>{_read_js(f)}</script>"
        for f in ("vega.min.js", "vega-lite.min.js", "vega-embed.min.js")
    )
    html = _HTML.format(title=title, scripts=scripts, spec_json=json.dumps(spec, indent=2))

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(out_path)

    if open_browser:
        webbrowser.open(out_path.as_uri())

    return out_path


def _strip_empty_channels(spec: dict[str, Any]) -> dict[str, Any]:
    """Remove encoding channels where field is None/empty — template placeholders."""
    encoding = spec.get("encoding", {})
    spec["encoding"] = {
        ch: enc for ch, enc in encoding.items() if not isinstance(enc, dict) or enc.get("field")
    }
    return spec


def _apply_auto_labels(spec: dict[str, Any]) -> dict[str, Any]:
    """Set axis title from field name (snake_case → Title Case) when no title provided."""
    for enc in spec.get("encoding", {}).values():
        if isinstance(enc, dict) and enc.get("field") and "title" not in enc:
            enc["title"] = enc["field"].replace("_", " ").title()
    return spec


def _apply_show_labels(spec: dict[str, Any]) -> dict[str, Any]:
    """Add text mark layer for value labels when show_labels: true."""
    if not spec.pop("show_labels", False):
        return spec

    mark = spec.get("mark", "")
    mark_type = mark if isinstance(mark, str) else mark.get("type", "")
    if mark_type not in ("bar", "point"):
        return spec

    encoding = spec.get("encoding", {})
    y_enc = encoding.get("y", {})
    x_enc = encoding.get("x", {})
    text_layer = {
        "mark": {"type": "text", "dy": -8, "fontSize": 11, "color": "#555"},
        "encoding": {
            "x": x_enc,
            "y": y_enc,
            "text": {"field": y_enc.get("field"), "format": ".2s"},
        },
    }

    top: dict[str, Any] = {k: v for k, v in spec.items() if k not in ("mark", "encoding")}
    top["layer"] = [{"mark": spec["mark"], "encoding": encoding}, text_layer]
    return top


def _load_spec(path: Path) -> dict[str, Any]:
    if path.suffix in (".yml", ".yaml"):
        try:
            import yaml
        except ImportError:
            raise SystemExit("pyyaml required for YAML specs: pip install pyyaml") from None
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    return json.loads(path.read_text(encoding="utf-8"))


def _load_data(path: Path) -> list[dict]:
    if path.suffix == ".csv":
        with path.open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    return json.loads(path.read_text(encoding="utf-8"))


def _list_templates() -> None:
    if not _CHARTS_DIR.exists():
        print("No chart templates found.")
        return
    for t in sorted(_CHARTS_DIR.glob("*.yml")):
        print(t.stem)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="strata-chart",
        description="Render a Vega-Lite chart to interactive HTML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
        "  strata-chart list\n"
        "  strata-chart bar data.json --open\n"
        "  strata-chart line data.csv --title 'Revenue trend' --out /tmp/trend.html\n"
        "  strata-chart --spec custom.yml data.json",
    )
    parser.add_argument(
        "type_or_spec",
        nargs="?",
        metavar="TYPE",
        help="Chart type (bar|line|scatter|heatmap), 'list', or use --spec",
    )
    parser.add_argument("data", nargs="?", metavar="DATA", help="Data file (.json or .csv)")
    parser.add_argument("--spec", metavar="FILE", help="Path to a custom spec file (YAML or JSON)")
    parser.add_argument(
        "--out",
        default="/tmp/strata_chart.html",
        metavar="FILE",
        help="Output HTML path (default: /tmp/strata_chart.html)",
    )
    parser.add_argument("--title", metavar="TEXT", help="Override chart title from spec")
    parser.add_argument("--open", action="store_true", help="Open in browser after rendering")

    args = parser.parse_args()

    if args.type_or_spec == "list" or (args.type_or_spec is None and args.spec is None):
        _list_templates()
        return

    if args.spec:
        spec_path = Path(args.spec)
        data_arg = args.type_or_spec  # positional is data when --spec provided
    else:
        chart_type = args.type_or_spec
        spec_path = _CHARTS_DIR / f"{chart_type}.yml"
        if not spec_path.exists():
            raise SystemExit(
                f"Unknown chart type '{chart_type}'. "
                f"Run 'strata-chart list' to see available types."
            )
        data_arg = args.data

    if not data_arg:
        raise SystemExit("Data file required. Example: strata-chart bar data.json")

    spec = _load_spec(spec_path)
    rows = _load_data(Path(data_arg))

    if args.title:
        spec["title"] = args.title

    render_chart(spec, rows, Path(args.out), open_browser=args.open)

"""Guard tests for the workbench rendering foundation (escaping by construction)."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import zipfile
from importlib import resources
from pathlib import Path

import pytest
from jinja2 import Environment, UndefinedError

from strata_lookml.workbench import render as wb

SRC = Path(wb.__file__).resolve().parents[1]  # src/strata_lookml
TEMPLATES = Path(wb.__file__).resolve().parent / "templates"

HOSTILE = [
    "</script>",
    '"',
    "'",
    "<img src=x onerror=alert(1)>",
    "javascript:alert(1)",
    "{{7*7}}",
    "%2F..",
]
# Characters that must never survive unescaped into HTML text/attribute positions.
RAW_FORBIDDEN = ["<", ">", '"', "'"]


@pytest.mark.parametrize("s", HOSTILE)
def test_hostile_strings_escaped_in_text_and_attributes(s):
    out = wb.render("_smoke.html", title=s, text=s)
    # No raw payload markup anywhere in the page.
    assert "<img src=x" not in out
    assert "</script>" not in out
    # Body of the page carries no raw metacharacters from the value: strip the static shell by
    # comparing against a benign render and checking the delta only contains escaped forms.
    benign = wb.render("_smoke.html", title="t", text="t")
    assert out.count("<") == benign.count("<")
    assert out.count(">") == benign.count(">")
    # Attribute positions: quotes from the value cannot close the attribute.
    assert out.count('"') == benign.count('"')
    assert out.count("'") == benign.count("'")
    # No expression evaluation of the payload.
    if s == "{{7*7}}":
        assert "49" not in out


def test_strict_undefined_raises_on_missing_variable():
    with pytest.raises(UndefinedError):
        wb.render("_smoke.html", title="x")  # `text` missing


def test_autoescape_on_for_txt_and_unknown_extensions():
    env = wb.make_environment()
    assert env.autoescape is not False
    assert env.get_template("_smoke.txt").render(text="<b>&") == "&lt;b&gt;&amp;\n"
    assert env.from_string("{{ x }}").render(x="<b>") == "&lt;b&gt;"
    assert env.autoescape("whatever.unknownext") is True  # type: ignore[operator]
    assert env.autoescape(None) is True  # type: ignore[operator]


def test_environment_has_no_extensions_and_is_strict():
    from jinja2 import StrictUndefined

    env = wb.make_environment()
    assert env.undefined is StrictUndefined
    assert len(env.extensions) == 0


def test_safe_svg_is_the_raw_html_door():
    env: Environment = wb.make_environment()
    out = env.from_string("{{ s }}").render(s=wb.safe_svg("<svg/>"))
    assert out == "<svg/>"


# --- static scans -------------------------------------------------------------------------

_BANNED_TEMPLATE = re.compile(
    r"\|\s*safe\b|\{%-?\s*autoescape\s+(false|False)|Markup\s*\(|\|\s*forceescape\s*\}\}\s*\{\{"
)


def scan_templates(root: Path) -> list[str]:
    bad = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and _BANNED_TEMPLATE.search(p.read_text(encoding="utf-8")):
            bad.append(str(p))
    return bad


def _is_markup_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    return (isinstance(f, ast.Name) and f.id == "Markup") or (
        isinstance(f, ast.Attribute) and f.attr == "Markup"
    )


def scan_markup_calls(root: Path, allowed: tuple[str, str]) -> list[str]:
    """`Markup(...)` calls anywhere under root except inside function `allowed[1]` of file
    `allowed[0]` (path relative to root)."""
    bad = []
    for p in sorted(root.rglob("*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        rel = p.relative_to(root).as_posix()
        permitted: set[int] = set()
        if rel == allowed[0]:
            for fn in ast.walk(tree):
                if isinstance(fn, ast.FunctionDef) and fn.name == allowed[1]:
                    permitted |= {id(n) for n in ast.walk(fn)}
        for n in ast.walk(tree):
            if _is_markup_call(n) and id(n) not in permitted:
                bad.append(f"{rel}:{n.lineno}")  # type: ignore[attr-defined]
    return bad


ALLOWED = ("workbench/render.py", "safe_svg")


def test_templates_ban_safe_autoescape_off_and_markup():
    assert scan_templates(TEMPLATES) == []


def test_markup_constructed_only_in_the_one_helper():
    assert scan_markup_calls(SRC, ALLOWED) == []


def test_negative_control_template_scan_catches_planted_violations(tmp_path):
    for i, bad in enumerate(
        [
            "{{ x|safe }}",
            "{{ x | safe }}",
            "{% autoescape false %}{{ x }}{% endautoescape %}",
            "{{ Markup(x) }}",
        ]
    ):
        d = tmp_path / str(i)
        d.mkdir()
        (d / "t.html").write_text(bad)
        assert scan_templates(d) != [], bad
    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "t.html").write_text("{{ x }}")
    assert scan_templates(clean) == []


def test_negative_control_markup_scan_catches_planted_violations(tmp_path):
    (tmp_path / "workbench").mkdir()
    (tmp_path / "workbench" / "render.py").write_text(
        "from markupsafe import Markup\n"
        "def safe_svg(s):\n    return Markup(s)\n"
        "def other(s):\n    return Markup(s)\n"
    )
    (tmp_path / "evil.py").write_text("import markupsafe\nx = markupsafe.Markup('<b>')\n")
    bad = scan_markup_calls(tmp_path, ALLOWED)
    assert sorted(bad) == ["evil.py:2", "workbench/render.py:5"]


# --- packaging ----------------------------------------------------------------------------


def test_templates_are_package_data():
    root = resources.files("strata_lookml.workbench") / "templates"
    for name in ("_base.html", "_smoke.html"):
        assert (root / name).is_file()


def test_templates_ship_in_the_built_wheel(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "-w",
            str(tmp_path),
            str(repo),
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0 and "hatchling" in r.stderr + r.stdout:
        pytest.skip("hatchling not installed for an offline wheel build")
    assert r.returncode == 0, r.stdout + r.stderr
    wheel = next(tmp_path.glob("strata_lookml-*.whl"))
    names = zipfile.ZipFile(wheel).namelist()
    for f in sorted(TEMPLATES.iterdir()):
        assert f"strata_lookml/workbench/templates/{f.name}" in names
    meta = next(n for n in names if n.endswith("METADATA"))
    assert "Requires-Dist: jinja2" in zipfile.ZipFile(wheel).read(meta).decode()

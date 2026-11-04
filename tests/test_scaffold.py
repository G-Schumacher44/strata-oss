"""Smoke test — confirms the package installs and core deps import correctly."""

import importlib


def test_strata_importable():
    assert importlib.import_module("strata_lookml") is not None


def test_networkx_importable():
    import networkx as nx

    assert nx.__version__ >= "3.0"


def test_mcp_importable():
    import mcp

    assert mcp is not None


def test_package_source_compiles_without_syntax_warnings():
    """Invalid string escapes warn at compile time (DeprecationWarning on 3.11, SyntaxWarning
    from 3.12) and become a SyntaxError under -W error. Promote both to errors."""
    import warnings
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src" / "strata_lookml"
    with warnings.catch_warnings():
        warnings.simplefilter("error", SyntaxWarning)
        warnings.simplefilter("error", DeprecationWarning)
        for path in sorted(src.rglob("*.py")):
            compile(path.read_text(encoding="utf-8"), str(path), "exec")

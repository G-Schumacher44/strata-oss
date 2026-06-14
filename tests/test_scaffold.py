"""Smoke test — confirms the package installs and core deps import correctly."""

import importlib


def test_strata_importable():
    assert importlib.import_module("strata") is not None


def test_networkx_importable():
    import networkx as nx

    assert nx.__version__ >= "3.0"


def test_mcp_importable():
    import mcp

    assert mcp is not None

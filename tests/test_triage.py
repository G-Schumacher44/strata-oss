"""Workbench S4b: the triage store, `triage_rows` statuses, the link builder, and the import
graph that keeps the core free of HTTP, rendering and TUI code."""

import ast
import copy
import hashlib
import json
import os
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner

from strata_lookml import triage
from strata_lookml.config import triage_path
from strata_lookml.errors import InvalidInput, StrataError
from strata_lookml.links import finding_path, link, object_path
from strata_lookml.pipeline import build_graph
from strata_lookml.triage import ABSENT_TTL, TriageStore, triage_rows

FIXTURES = Path(__file__).parent / "fixtures"
REPO = Path(__file__).parent / "lookml" / "enterprise_mono"
SRC = Path(__file__).resolve().parents[1] / "src"
T0 = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


@pytest.fixture(scope="module")
def graph():
    return build_graph(
        REPO, FIXTURES / "enterprise_usage_facts.json", FIXTURES / "enterprise_schema_facts.json"
    )


@pytest.fixture(scope="module")
def ids(graph):
    l1 = graph.metadata["l1"]
    dead = sorted(r["id"] for r in l1["dead_code"])
    drift = sorted({r["id"] for r in l1["schema_drift"]})
    return {"d1": dead[0], "d2": dead[1], "s1": drift[0], "s2": drift[1]}


def _without(graph, *finding_ids):
    """The graph after those findings were fixed (their L1 rows gone, checks still run)."""
    fixed = copy.deepcopy(graph)
    l1 = fixed.metadata["l1"]
    for key in ("dead_code", "schema_drift"):
        l1[key] = [r for r in l1[key] if r["id"] not in finding_ids]
    return fixed


class Clock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now


def _store(graph, clock=None):
    return TriageStore.open(REPO, graph, clock=clock)


def _statuses(graph, baseline=None, clock=None):
    return {r.id: r for r in triage_rows(graph, baseline, _store(graph, clock))}


# --- status table (D4, M6, M8) --------------------------------------------------------------


def test_status_table_new_acknowledged_baselined_fixed(graph, ids):
    _store(graph).acknowledge([ids["d1"], ids["s1"]], note="owned by data eng")
    baseline = {"dead-code": {ids["d2"]}, "drift": {ids["s1"], ids["s2"]}}

    rows = _statuses(graph, baseline)
    assert rows[ids["d1"]].status == "acknowledged"
    assert rows[ids["d1"]].note == "owned by data eng"
    assert rows[ids["d2"]].status == "baselined"
    # M6: baselined wins over acknowledged; the ack record is kept and still shown.
    assert rows[ids["s1"]].status == "baselined"
    assert rows[ids["s1"]].acked_at is not None
    assert {r.status for r in rows.values()} == {"new", "acknowledged", "baselined"}
    assert sum(r.id == ids["s1"] for r in triage_rows(graph, baseline, _store(graph))) == 1

    # Out of the baseline, the kept ack takes effect again.
    assert _statuses(graph, {"drift": {ids["s2"]}})[ids["s1"]].status == "acknowledged"

    fixed = _statuses(_without(graph, ids["d1"], ids["s2"]), baseline)
    assert fixed[ids["d1"]].status == "fixed"  # acked, absent, usage checked
    assert fixed[ids["s2"]].status == "fixed"  # baselined, absent, schema checked
    assert fixed[ids["d1"]].subject_id is None and fixed[ids["d1"]].label == ids["d1"]


def test_unchecked_category_is_not_checked_never_fixed(graph, ids):
    _store(graph).acknowledge([ids["s1"], ids["d1"]])
    no_schema = build_graph(REPO, FIXTURES / "enterprise_usage_facts.json", None)

    rows = _statuses(no_schema, {"drift": {ids["s2"]}})
    assert rows[ids["s1"]].status == "not_checked"  # acked, drift not run
    assert rows[ids["s2"]].status == "not_checked"  # baselined, drift not run
    assert rows[ids["d1"]].status == "acknowledged"
    assert "fixed" not in {r.status for r in rows.values()}
    # Unknown is never absent: no first_absent_at for the unchecked category.
    assert "first_absent_at" not in _store(no_schema).snapshot()["ids"][ids["s1"]]


def test_rows_need_the_graph_the_store_was_opened_on(graph, ids):
    with pytest.raises(ValueError, match="different graph"):
        triage_rows(_without(graph, ids["d1"]), None, _store(graph))


# --- append-only store (M8) -----------------------------------------------------------------


def test_unack_keeps_the_entry_and_reack_clears_unacked_at(graph, ids):
    clock = Clock()
    store = _store(graph, clock)
    store.acknowledge([ids["d1"]], note="n")
    clock.now = T0 + timedelta(hours=1)
    store.unacknowledge([ids["d1"]])

    entry = store.snapshot()["ids"][ids["d1"]]
    assert entry["unacked_at"] == "2026-11-08T13:00:00+00:00"
    assert entry["acked_at"] == "2026-11-08T12:00:00+00:00" and entry["note"] == "n"
    assert _statuses(graph)[ids["d1"]].status == "new"

    store.acknowledge([ids["d1"]])
    assert "unacked_at" not in store.snapshot()["ids"][ids["d1"]]
    with pytest.raises(InvalidInput):
        store.unacknowledge([ids["d2"]])  # never stored


def test_first_absent_at_stamps_clears_and_ttl_prunes(graph, ids):
    clock = Clock()
    _store(graph, clock).acknowledge([ids["d1"]])
    fixed = _without(graph, ids["d1"])

    clock.now = T0 + timedelta(days=1)
    _statuses(fixed, clock=clock)
    stamped = _store(fixed).snapshot()["ids"][ids["d1"]]["first_absent_at"]
    assert stamped == "2026-11-09T12:00:00+00:00"

    # It reappears: the stamp clears.
    _statuses(graph, clock=clock)
    assert "first_absent_at" not in _store(graph).snapshot()["ids"][ids["d1"]]

    # Absent again: kept until ABSENT_TTL past first absence, then pruned.
    _statuses(fixed, clock=clock)
    clock.now += ABSENT_TTL - timedelta(seconds=1)
    assert _statuses(fixed, clock=clock)[ids["d1"]].status == "fixed"
    clock.now += timedelta(seconds=1)
    assert ids["d1"] not in _statuses(fixed, clock=clock)
    assert ids["d1"] not in _store(fixed).snapshot()["ids"]


def test_reads_write_nothing_when_nothing_changed(graph):
    _statuses(graph)
    assert not triage_path(REPO).exists()


# --- allowlist ------------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [["no:such:finding"], "a-string", [""], [None], [{}]])
def test_acknowledge_refuses_ids_outside_the_allowlist(graph, ids, bad):
    with pytest.raises(InvalidInput):
        _store(graph).acknowledge(bad if isinstance(bad, str) else [ids["d1"], *bad])
    assert not triage_path(REPO).exists()


def test_a_stored_id_stays_acknowledgeable_after_it_is_gone(graph, ids):
    _store(graph).acknowledge([ids["d1"]])
    before = _store(graph).snapshot()["rev"]

    _store(_without(graph, ids["d1"])).acknowledge([ids["d1"]], note="later")
    assert _store(graph).snapshot()["rev"] == before + 1


# --- optimistic concurrency -----------------------------------------------------------------


def _interleave(monkeypatch, other, other_id, times):
    """Make `other` acknowledge just before each of the next `times` pre-replace rev checks."""
    real = triage._current_rev
    left = [times]

    def current_rev(path):
        if left[0]:
            left[0] -= 1
            monkeypatch.setattr(triage, "_current_rev", real)
            other.acknowledge([other_id])
            monkeypatch.setattr(triage, "_current_rev", current_rev)
        return real(path)

    monkeypatch.setattr(triage, "_current_rev", current_rev)


def test_interleaved_writers_both_land(graph, ids, monkeypatch):
    first, second = _store(graph), _store(graph)
    _interleave(monkeypatch, second, ids["d2"], times=1)

    first.acknowledge([ids["d1"]])
    stored = first.snapshot()
    assert set(stored["ids"]) == {ids["d1"], ids["d2"]}
    assert stored["rev"] == 2


def test_a_store_that_keeps_changing_fails_after_three_tries(graph, ids, monkeypatch):
    first, second = _store(graph), _store(graph)
    _interleave(monkeypatch, second, ids["d2"], times=3)

    with pytest.raises(StrataError, match="changed concurrently") as caught:
        first.acknowledge([ids["d1"]])
    assert caught.value.hint == "retry"
    stored = first.snapshot()
    assert set(stored["ids"]) == {ids["d2"]} and stored["rev"] == 3


# --- the file on disk -----------------------------------------------------------------------


@pytest.mark.skipif(os.name != "posix", reason="POSIX modes")
def test_store_file_is_0600_in_a_0700_dir(graph, ids):
    _store(graph).acknowledge([ids["d1"]])
    path = triage_path(REPO)
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert path.parent == Path(os.environ["HOME"]) / ".strata" / "triage"


def test_symlink_destination_is_refused(graph, ids, tmp_path):
    victim = tmp_path / "victim.json"
    victim.write_text("keep", encoding="utf-8")
    path = triage_path(REPO)
    path.parent.mkdir(parents=True)
    path.symlink_to(victim)

    with pytest.raises(InvalidInput, match="through a symlink"):
        _store(graph).acknowledge([ids["d1"]])
    with pytest.raises(InvalidInput, match="through a symlink"):
        _store(graph).snapshot()  # nor read through one
    assert victim.read_text(encoding="utf-8") == "keep"


def test_a_foreign_file_is_never_overwritten(graph, ids):
    path = triage_path(REPO)
    path.parent.mkdir(parents=True)
    path.write_text('{"not": "a store"}', encoding="utf-8")

    with pytest.raises(InvalidInput, match="not a version 1 Strata triage store"):
        _store(graph).acknowledge([ids["d1"]])
    assert path.read_text(encoding="utf-8") == '{"not": "a store"}'


def test_interrupted_write_keeps_the_previous_store(graph, ids, monkeypatch):
    _store(graph).acknowledge([ids["d1"]])
    path = triage_path(REPO)
    before = path.read_bytes()

    def crash(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(triage.os, "replace", crash)
    with pytest.raises(OSError, match="disk full"):
        _store(graph).acknowledge([ids["d2"]])
    assert path.read_bytes() == before
    assert sorted(p.name for p in path.parent.iterdir()) == [path.name]


def _tree_digest(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_triage_never_touches_the_repo_tree(graph, ids):
    before = _tree_digest(REPO)
    store = _store(graph)
    store.acknowledge([ids["d1"], ids["s1"]], note="n")
    store.unacknowledge([ids["s1"]])
    triage_rows(graph, None, store)
    assert _tree_digest(REPO) == before
    assert not triage_path(REPO).is_relative_to(REPO.resolve())


# --- the gate stays on the committed baseline -----------------------------------------------


def test_strata_check_ignores_acknowledgements(graph, ids, monkeypatch):
    from strata_lookml.cli.main import strata_cli

    _store(graph).acknowledge([ids["s1"]])

    def forbidden(*args, **kwargs):
        raise AssertionError("strata check read the triage store")

    monkeypatch.setattr(triage, "_read_document", forbidden)
    monkeypatch.setattr(TriageStore, "open", forbidden)
    args = ["check", "--repo", str(REPO), "--schema-fixture"]
    args += [str(FIXTURES / "enterprise_schema_facts.json"), "--fail-on", "drift", "--json"]
    result = CliRunner().invoke(strata_cli, args)

    assert result.exit_code == 1 and isinstance(result.exception, SystemExit), result.output
    failed = {f["id"] for f in json.loads(result.output)["failures"]}
    assert ids["s1"] in failed


# --- links (D3) -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("node_id", "path"),
    [
        ("explore:sales:orders", "/explore/sales.orders"),
        ("view:orders", "/view/orders"),
        ("pdt:pdt_funnel", "/pdt/pdt_funnel"),
        ("physical_table:acme-analytics.silver.t", "/table/acme-analytics.silver.t"),
        ("field:orders.amount", "/field/orders.amount"),
        ("model:sales", None),
        ("explore:sales", None),
        ("view:", None),
        ("orders", None),
    ],
)
def test_object_path(node_id, path):
    assert object_path(node_id) == path


def test_finding_path_quotes_the_whole_id():
    assert finding_path("schema:missing_column:a.t/x c:v.f") == (
        "/finding/schema%3Amissing_column%3Aa.t%2Fx%20c%3Av.f"
    )


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        (None, None),
        ("", None),
        ("http://127.0.0.1:8800", "http://127.0.0.1:8800/view/orders"),
        ("http://127.0.0.1:8800//", "http://127.0.0.1:8800/view/orders"),
        ("https://wb.example/strata/", "https://wb.example/strata/view/orders"),
        ("file:///ci/dashboard.html", "file:///ci/dashboard.html#/view/orders"),
        ("https://pages.example/wb/#", "https://pages.example/wb/#/view/orders"),
        ("https://pages.example/x.html#/old", "https://pages.example/x.html#/view/orders"),
    ],
)
def test_link_forms(base, expected):
    assert link(base, "/view/orders") == expected
    assert link(base, "view/orders") == expected


def test_link_without_a_path_is_none():
    assert link("http://127.0.0.1:8800", object_path("model:sales")) is None


# --- import graph (D2) ----------------------------------------------------------------------

CORE = (
    "strata_lookml.triage",
    "strata_lookml.links",
    "strata_lookml.gate",
    "strata_lookml.mcp.tools",
)
BANNED = ("http", "textual", "jinja2", "strata_lookml.workbench", "strata_lookml.tui")


def _module_file(src, name):
    base = src.joinpath(*name.split("."))
    for candidate in (base / "__init__.py", base.with_suffix(".py")):
        if candidate.is_file():
            return candidate
    return None


def _imported(tree, module, is_package):
    package = module if is_package else module.rsplit(".", 1)[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                stem = ".".join(parts[: len(parts) - node.level + 1])
                name = f"{stem}.{node.module}" if node.module else stem
            else:
                name = node.module or ""
            yield name
            yield from (f"{name}.{alias.name}" for alias in node.names)


def _banned_imports(src, roots, banned):
    """`module imports name` for every banned name reachable from `roots` through strata_lookml's
    own modules (every import statement, function-level included; third-party not followed)."""
    found, seen, stack = [], set(), list(roots)
    while stack:
        module = stack.pop()
        path = _module_file(src, module)
        if module in seen or path is None:
            continue
        seen.add(module)
        parts = module.split(".")
        stack.extend(".".join(parts[:i]) for i in range(1, len(parts)))
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name in _imported(tree, module, path.name == "__init__.py"):
            if any(name == b or name.startswith(f"{b}.") for b in banned):
                found.append(f"{module} imports {name}")
            elif name.startswith("strata_lookml"):
                stack.append(name)
    return sorted(set(found))


def test_core_never_imports_http_rendering_or_tui():
    assert _banned_imports(SRC, CORE, BANNED) == []


def test_the_gate_never_reaches_the_triage_store():
    assert _banned_imports(SRC, ["strata_lookml.gate"], ["strata_lookml.triage"]) == []


@pytest.mark.parametrize(
    "planted",
    [
        "import http.server",
        "from http import server",
        "import textual",
        "import jinja2",
        "from strata_lookml.workbench import render",
        "from strata_lookml import tui",
    ],
)
def test_import_guard_catches_a_planted_import(tmp_path, planted):
    """Negative control: the guard fails once a banned import is planted, even one level down
    (the plant goes in safe_paths, which triage imports) and inside a function."""
    shutil.copytree(SRC / "strata_lookml", tmp_path / "strata_lookml")
    target = tmp_path / "strata_lookml" / "safe_paths.py"
    target.write_text(
        target.read_text(encoding="utf-8") + f"\n\ndef _planted():\n    {planted}\n",
        encoding="utf-8",
    )

    found = _banned_imports(tmp_path, ["strata_lookml.triage"], BANNED)
    assert found and all(f.startswith("strata_lookml.safe_paths imports") for f in found)

"""IR cache location + identity (S7): one resolver, ~/.strata/cache default, input-keyed reuse."""

import asyncio
import json
import os
import shutil
import sqlite3
import stat
import time
from pathlib import Path

import pytest
from click.testing import CliRunner
from mcp import Client

from strata_lookml.cli.main import strata_cli
from strata_lookml.config import default_cache_path
from strata_lookml.mcp.server import create_server

ROOT = Path(__file__).resolve().parents[1]
GCS = ROOT / "tests" / "lookml" / "gcs_analytics"
USAGE = ROOT / "tests" / "fixtures" / "gcs_usage_facts.json"


@pytest.fixture
def env(tmp_path, monkeypatch):
    """HOME in tmp (never the real ~/.strata), no cache/repo/fixture env, a scratch repo copy."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for var in (
        "STRATA_CACHE_PATH",
        "STRATA_REPO_PATH",
        "STRATA_USAGE_FIXTURE",
        "STRATA_SCHEMA_FIXTURE",
    ):
        monkeypatch.delenv(var, raising=False)
    repo = tmp_path / "gcs_analytics"
    shutil.copytree(GCS, repo, ignore=shutil.ignore_patterns(".git"))
    monkeypatch.chdir(tmp_path)
    return home, repo


def _strata(*args):
    result = CliRunner().invoke(strata_cli, list(args))
    assert result.exit_code == 0, result.output
    return result


def _files(root):
    return sorted(p.relative_to(root) for p in root.rglob("*"))


def test_server_with_fixtures_rebuilds_a_cache_built_without_them(env, monkeypatch):
    # N1: the server reused any cache younger than 300s, so `strata build` without fixtures
    # followed by a server start with STRATA_USAGE_FIXTURE served an L1-less graph.
    _, repo = env
    _strata("build", "--repo", str(repo))
    monkeypatch.setenv("STRATA_REPO_PATH", str(repo))
    monkeypatch.setenv("STRATA_USAGE_FIXTURE", str(USAGE))

    async def summary():
        async with Client(create_server()) as client:
            return await client.call_tool("strata_usage_summary", {})

    data = json.loads(asyncio.run(summary()).content[0].text)
    assert data["usage_checked"] is True


def test_server_rebuilds_after_a_lkml_edit_within_the_reuse_window(env, monkeypatch):
    # The cache keyed on the repo path alone served a stale IR for up to the max age after a
    # .lkml edit; the .lkml fingerprint in the inputs forces the rebuild.
    from strata_lookml.mcp.server import load_configured_graph

    _, repo = env
    built = json.loads(_strata("build", "--repo", str(repo), "--json").output)
    view_file = next(repo.glob("*.view.lkml"))
    with view_file.open("a", encoding="utf-8") as handle:
        handle.write("\nview: s7_probe {\n  dimension: id {\n    sql: 1 ;;\n  }\n}\n")
    monkeypatch.setenv("STRATA_REPO_PATH", str(repo))
    graph = load_configured_graph()
    assert graph.node_counts()["view"] == built["node_counts"]["view"] + 1


def test_build_default_cache_lands_private_under_strata_home(env):
    home, repo = env
    out = json.loads(_strata("build", "--repo", str(repo), "--json").output)
    cache = Path(out["cache_path"])
    assert cache == default_cache_path(repo)
    assert cache.parent == home / ".strata" / "cache"
    assert cache.name.startswith("gcs_analytics-") and cache.is_file()
    if os.name == "posix":
        assert stat.S_IMODE(cache.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(cache.stat().st_mode) == 0o600


def test_build_writes_nothing_inside_the_repo(env):
    _, repo = env
    before = _files(repo)
    _strata("build", "--repo", str(repo), "--usage-fixture", str(USAGE))
    assert _files(repo) == before


def test_same_named_repos_get_separate_cache_entries(tmp_path):
    assert default_cache_path(tmp_path / "a" / "repo") != default_cache_path(
        tmp_path / "b" / "repo"
    )


def test_cache_env_wins_and_every_consumer_agrees(env, monkeypatch, tmp_path):
    _, repo = env
    custom = tmp_path / "elsewhere" / "ir.db"
    monkeypatch.setenv("STRATA_CACHE_PATH", str(custom))
    monkeypatch.setenv("STRATA_REPO_PATH", str(repo))
    built = json.loads(_strata("build", "--json").output)
    shown = json.loads(_strata("mcp", "config").output)
    assert built["cache_path"] == shown["cache_path"] == str(custom.resolve())
    assert custom.is_file()
    flag = tmp_path / "flag.db"
    assert json.loads(_strata("build", "--cache", str(flag), "--json").output)["cache_path"] == (
        str(flag.resolve())
    )


def test_clean_repo_removes_new_entry_and_legacy_in_repo_cache(env):
    _, repo = env
    _strata("build", "--repo", str(repo))
    entry = default_cache_path(repo)
    legacy = repo / "strata_ir.db"
    legacy.write_bytes(b"old")
    assert entry.exists()
    _strata("clean", "--repo", str(repo))
    assert not entry.exists() and not legacy.exists()


def test_clean_repo_honours_strata_repo_path(env, monkeypatch):
    home, repo = env
    legacy = repo / "strata_ir.db"
    legacy.write_bytes(b"old")
    monkeypatch.setenv("STRATA_REPO_PATH", str(repo))
    monkeypatch.chdir(home)  # a cwd that does not contain the repo
    _strata("clean")
    assert not legacy.exists()


class _FailOnInsert(sqlite3.Connection):
    def execute(self, sql, *args):
        if sql.lstrip().upper().startswith("INSERT"):
            raise sqlite3.OperationalError("simulated crash mid-write")
        return super().execute(sql, *args)


def test_interrupted_cache_write_leaves_the_previous_cache_whole(env, monkeypatch):
    # The old write dropped the table in autocommit before re-creating it, so a crash (or a
    # concurrent reader) in between saw no ir_cache table at all.
    from strata_lookml.ir.store import cache_age_seconds, load_ir, save_ir

    home, repo = env
    _strata("build", "--repo", str(repo))
    cache = default_cache_path(repo)
    views = load_ir(cache).node_counts()["view"]
    real_connect = sqlite3.connect
    monkeypatch.setattr(
        sqlite3, "connect", lambda *a, **k: real_connect(*a, **{**k, "factory": _FailOnInsert})
    )
    with pytest.raises(sqlite3.OperationalError, match="simulated"):
        save_ir(load_ir(cache), cache, {})
    monkeypatch.setattr(sqlite3, "connect", real_connect)
    assert cache_age_seconds(cache) is not None
    assert load_ir(cache).node_counts()["view"] == views
    assert sorted(p.name for p in cache.parent.iterdir()) == [cache.name]  # no temp left


@pytest.mark.parametrize("damage", ["drop_table", "not_a_database"])
def test_server_rebuilds_a_damaged_cache_instead_of_failing(env, monkeypatch, damage):
    from strata_lookml.ir.store import cache_age_seconds
    from strata_lookml.mcp.server import load_configured_graph

    _, repo = env
    _strata("build", "--repo", str(repo))
    cache = default_cache_path(repo)
    if damage == "drop_table":
        with sqlite3.connect(cache) as conn:
            conn.execute("DROP TABLE ir_cache")
    else:
        cache.write_bytes(b"this is not a sqlite database" * 20)
    monkeypatch.setenv("STRATA_REPO_PATH", str(repo))
    assert load_configured_graph().node_counts()["view"] > 0
    assert cache_age_seconds(cache) is not None  # rebuilt in place


def test_cache_swap_failure_keeps_old_cache_and_still_serves_the_new_graph(env, monkeypatch):
    # Windows refuses to replace a file another process has open (PermissionError). The cache
    # is an optimisation: the swap failing must not fail the server start.
    from strata_lookml.ir import store
    from strata_lookml.mcp.server import load_configured_graph

    _, repo = env
    _strata("build", "--repo", str(repo))
    cache = default_cache_path(repo)
    old_views = store.load_ir(cache).node_counts()["view"]
    view_file = next(repo.glob("*.view.lkml"))
    with view_file.open("a", encoding="utf-8") as handle:
        handle.write("\nview: s7_swap {\n  dimension: id {\n    sql: 1 ;;\n  }\n}\n")

    def sharing_violation(src, dst):
        raise PermissionError(32, "The process cannot access the file", str(dst))

    real_replace = os.replace
    monkeypatch.setattr(os, "replace", sharing_violation)
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    monkeypatch.setenv("STRATA_REPO_PATH", str(repo))
    with pytest.warns(RuntimeWarning, match="IR cache not updated"):
        graph = load_configured_graph()
    monkeypatch.setattr(os, "replace", real_replace)
    assert graph.node_counts()["view"] == old_views + 1
    assert store.load_ir(cache).node_counts()["view"] == old_views  # old cache intact
    assert sorted(p.name for p in cache.parent.iterdir()) == [cache.name]  # temp removed


def test_load_ir_closes_its_connection(env, monkeypatch):
    # sqlite3's context manager ends the transaction but not the connection; an open reader
    # handle blocks the next cache replace on Windows.
    from strata_lookml.ir.store import load_ir

    _, repo = env
    _strata("build", "--repo", str(repo))
    opened = []

    class Tracking(sqlite3.Connection):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            opened.append(self)

    real_connect = sqlite3.connect
    monkeypatch.setattr(
        sqlite3, "connect", lambda *a, **k: real_connect(*a, **{**k, "factory": Tracking})
    )
    load_ir(default_cache_path(repo))
    assert opened
    for conn in opened:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            conn.execute("SELECT 1")


def _build_with_cache(repo, cache):
    return CliRunner().invoke(strata_cli, ["build", "--repo", str(repo), "--cache", str(cache)])


def test_build_refuses_a_lkml_cache_destination(env):
    # The atomic replace would have swapped a mistyped --cache .lkml for a SQLite database.
    _, repo = env
    source = next(repo.glob("*.view.lkml"))
    before = source.read_bytes()
    result = _build_with_cache(repo, source)
    assert result.exit_code == 1 and "LookML" in result.output
    assert source.read_bytes() == before


def test_build_refuses_a_symlink_cache_destination(env, tmp_path):
    _, repo = env
    target = tmp_path / "real.db"
    _strata("build", "--repo", str(repo), "--cache", str(target))
    link = tmp_path / "link.db"
    link.symlink_to(target)
    result = _build_with_cache(repo, link)
    assert result.exit_code == 1 and "symlink" in result.output
    assert link.is_symlink()


def test_build_refuses_to_overwrite_a_non_sqlite_file(env, tmp_path):
    _, repo = env
    other = tmp_path / "notes.txt"
    other.write_text("keep me\n", encoding="utf-8")
    result = _build_with_cache(repo, other)
    assert result.exit_code == 1 and "not a previous Strata IR cache" in result.output
    assert other.read_text(encoding="utf-8") == "keep me\n"


def test_build_replaces_an_existing_strata_cache_at_a_custom_path(env, tmp_path):
    from strata_lookml.ir.store import cache_inputs

    _, repo = env
    cache = tmp_path / "custom.db"
    _strata("build", "--repo", str(repo), "--cache", str(cache))
    _strata("build", "--repo", str(repo), "--cache", str(cache), "--usage-fixture", str(USAGE))
    assert cache_inputs(cache)["usage_fixture"]["path"] == str(USAGE.resolve())


def test_build_refuses_to_overwrite_an_unrelated_sqlite_database(env, tmp_path):
    # Any SQLite file used to count as "ours", so --cache at a user's own database replaced it.
    _, repo = env
    other = tmp_path / "app.db"
    with sqlite3.connect(other) as conn:
        conn.execute("CREATE TABLE users (name TEXT)")
        conn.execute("INSERT INTO users VALUES ('ada')")
    conn.close()
    result = _build_with_cache(repo, other)
    assert result.exit_code == 1 and "not a previous Strata IR cache" in result.output
    with sqlite3.connect(other) as conn:
        assert conn.execute("SELECT name FROM users").fetchall() == [("ada",)]
    conn.close()

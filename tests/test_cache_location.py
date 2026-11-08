"""IR cache location + identity (S7): one resolver, ~/.strata/cache default, input-keyed reuse."""

import asyncio
import json
import os
import shutil
import stat
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

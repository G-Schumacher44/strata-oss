"""`strata diff` and run provenance: findings a branch introduces or fixes, read-only."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
ENTERPRISE = Path(__file__).parent / "lookml" / "enterprise_mono"
USAGE = FIXTURES / "enterprise_usage_facts.json"
CLI = [sys.executable, "-m", "strata_lookml.cli.main"]

LEGACY_MODEL = "models/em_legacy_v1.model.lkml"
NEW_EXPLORE = "dead:explore:em_legacy_v1.brand_new_dead"
FIXED_IDS = {
    "dead:explore:em_legacy_v1.legacy_inventory",
    "dead:view:legacy_inventory_snapshot",
}


def git(repo, *args):
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
    }
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True, env=env
    ).stdout


def strata(*args, cwd=None, home=None):
    env = {**os.environ, "HOME": str(home)} if home else os.environ
    return subprocess.run(
        [*CLI, *args], cwd=cwd or REPO_ROOT, capture_output=True, text=True, check=False, env=env
    )


@pytest.fixture
def lookml_repo(tmp_path):
    """A throwaway git repo: `main` = enterprise_mono, `feature` adds a dead explore and removes
    a dead explore plus its view."""
    repo = tmp_path / "lookml"
    shutil.copytree(ENTERPRISE, repo)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "checkout", "-q", "-b", "feature")
    model = repo / LEGACY_MODEL
    text = model.read_text()
    text = re.sub(r"explore: legacy_inventory \{.*?\n\}\n", "", text, flags=re.S)
    model.write_text(text + "\nexplore: brand_new_dead {\n  from: legacy_order_detail\n}\n")
    (repo / "views/legacy/legacy_inventory_snapshot.view.lkml").unlink()
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "B")
    git(repo, "checkout", "-q", "main")
    return repo


def snapshot(repo):
    """Everything diff must leave alone: refs, worktrees, the working tree's bytes."""
    tree = {
        str(p.relative_to(repo)): p.read_bytes()
        for p in sorted(repo.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(repo).parts
    }
    return {
        "refs": git(repo, "for-each-ref"),
        "worktrees": git(repo, "worktree", "list"),
        "head": git(repo, "rev-parse", "HEAD"),
        "status": git(repo, "status", "--porcelain"),
        "git_dir": sorted(
            str(p.relative_to(repo / ".git")) for p in (repo / ".git").rglob("*") if p.is_file()
        ),
        "tree": tree,
    }


def diff_json(repo, *extra, tmp_path):
    result = strata(
        "diff", "main", "feature", "--repo", str(repo), "--usage-fixture", str(USAGE), "--json",
        *extra, home=tmp_path / "home",
    )  # fmt: skip
    return result, json.loads(result.stdout)


def test_diff_reports_new_and_fixed_ids_exactly(lookml_repo, tmp_path):
    result, out = diff_json(lookml_repo, tmp_path=tmp_path)

    assert result.returncode == 0, result.stderr
    assert [r["id"] for r in out["new"]] == [NEW_EXPLORE]
    assert {r["id"] for r in out["fixed"]} == FIXED_IDS
    assert out["unchanged_count"] == 13 - len(FIXED_IDS)
    assert out["base"] == {"ref": "main", "commit": git(lookml_repo, "rev-parse", "main").strip()}
    assert out["head"]["commit"] == git(lookml_repo, "rev-parse", "feature").strip()
    # records are the full finding records, with repo-relative paths (never the temp export dir)
    assert out["new"][0]["source_file"] == LEGACY_MODEL


def test_fail_on_new_exits_1_only_when_a_finding_is_new(lookml_repo, tmp_path):
    new_side, _ = diff_json(lookml_repo, "--fail-on-new", tmp_path=tmp_path)
    assert new_side.returncode == 1

    # a ref against itself introduces nothing
    same = strata(
        "diff", "main", "main", "--repo", str(lookml_repo), "--usage-fixture", str(USAGE),
        "--fail-on-new", home=tmp_path / "home",
    )  # fmt: skip
    assert same.returncode == 0, same.stderr
    assert "0 new, 0 fixed" in same.stdout

    text = strata(
        "diff", "main", "feature", "--repo", str(lookml_repo), "--usage-fixture", str(USAGE),
        home=tmp_path / "home",
    )  # fmt: skip
    assert text.returncode == 0
    assert "+ [dead-code]" in text.stdout and NEW_EXPLORE in text.stdout
    assert "1 new, 2 fixed" in text.stdout


def test_head_defaults_to_the_working_tree(lookml_repo, tmp_path):
    git(lookml_repo, "checkout", "-q", "feature")
    (lookml_repo / LEGACY_MODEL).write_text(
        (lookml_repo / LEGACY_MODEL).read_text() + "\nexplore: uncommitted_dead {\n"
        "  from: legacy_order_detail\n}\n"
    )
    result = strata(
        "diff", "feature", "--repo", str(lookml_repo), "--usage-fixture", str(USAGE), "--json",
        home=tmp_path / "home",
    )  # fmt: skip
    out = json.loads(result.stdout)
    assert [r["id"] for r in out["new"]] == ["dead:explore:em_legacy_v1.uncommitted_dead"]
    assert out["head"]["ref"] == "working tree" and out["head"]["dirty"] is True


def test_unknown_ref_is_invalid_input(lookml_repo, tmp_path):
    result = strata(
        "diff", "nope", "--repo", str(lookml_repo), "--usage-fixture", str(USAGE), "--json",
        home=tmp_path / "home",
    )  # fmt: skip
    assert result.returncode == 1
    err = json.loads(result.stdout)
    assert err["code"] == "invalid_input" and "nope" in err["error"] and err["hint"]


def test_option_shaped_ref_never_reaches_git(lookml_repo, tmp_path):
    result = strata(
        "diff", "--repo", str(lookml_repo), "--", "--output=evil", home=tmp_path / "home"
    )
    assert result.returncode == 1
    assert "unknown git ref" in result.stderr
    assert not (lookml_repo / "evil").exists() and not Path("evil").exists()


def test_diff_leaves_the_users_repo_untouched(lookml_repo, tmp_path):
    before = snapshot(lookml_repo)
    diff_json(lookml_repo, tmp_path=tmp_path)
    strata(
        "diff", "main", "--repo", str(lookml_repo), "--usage-fixture", str(USAGE),
        home=tmp_path / "home",
    )  # fmt: skip
    assert snapshot(lookml_repo) == before
    assert len(before["worktrees"].splitlines()) == 1


def test_diff_works_from_a_project_subdirectory(lookml_repo, tmp_path):
    """The LookML project need not sit at the checkout root."""
    outer = tmp_path / "outer"
    shutil.copytree(lookml_repo, outer / "looker", ignore=shutil.ignore_patterns(".git"))
    git(outer, "init", "-q", "-b", "main")
    git(outer, "add", "-A")
    git(outer, "commit", "-q", "-m", "A")
    result = strata(
        "diff", "main", "--repo", str(outer / "looker"), "--usage-fixture", str(USAGE), "--json",
        home=tmp_path / "home",
    )  # fmt: skip
    out = json.loads(result.stdout)
    assert result.returncode == 0 and out["new"] == [] and out["fixed"] == []


# -- provenance ----------------------------------------------------------------------------


def check_json(repo, tmp_path):
    result = strata("check", "--repo", str(repo), "--json", home=tmp_path / "home")
    return json.loads(result.stdout)


def test_check_json_carries_source_for_a_git_repo(lookml_repo, tmp_path):
    out = check_json(lookml_repo, tmp_path)
    assert out["source"] == {
        "commit": git(lookml_repo, "rev-parse", "HEAD").strip(),
        "branch": "main",
        "dirty": False,
    }

    (lookml_repo / "views/untracked.view.lkml").write_text("view: untracked_v {}\n")
    assert check_json(lookml_repo, tmp_path)["source"]["dirty"] is True

    git(lookml_repo, "checkout", "-q", "--detach")
    assert check_json(lookml_repo, tmp_path)["source"]["branch"] == "detached"


def test_source_is_omitted_outside_git(tmp_path):
    plain = tmp_path / "plain"
    shutil.copytree(ENTERPRISE, plain)
    assert "source" not in check_json(plain, tmp_path)


def test_build_output_and_graph_metadata_carry_source(lookml_repo, tmp_path):
    result = strata(
        "build", "--repo", str(lookml_repo), "--cache", str(tmp_path / "c.db"), "--json",
        home=tmp_path / "home",
    )  # fmt: skip
    out = json.loads(result.stdout)
    head = git(lookml_repo, "rev-parse", "HEAD").strip()
    assert out["source"]["commit"] == head

    from strata_lookml.ir.store import load_ir

    assert load_ir(tmp_path / "c.db").metadata["source"]["commit"] == head


# -- read-only guarantees and the API --------------------------------------------------------


def index_state(repo):
    index = repo / ".git" / "index"
    return index.read_bytes(), index.stat().st_mtime_ns


def test_provenance_and_diff_never_rewrite_the_git_index(lookml_repo, tmp_path):
    """A touched file (stat change only) makes a plain `git status` refresh and rewrite .git/index."""
    touched = lookml_repo / LEGACY_MODEL
    os.utime(touched, (1_000_000_000, 1_000_000_000))
    before = index_state(lookml_repo)

    from strata_lookml.provenance import git_source

    assert git_source(lookml_repo)["dirty"] is False  # content unchanged: stat noise is not dirty
    assert index_state(lookml_repo) == before
    check_json(lookml_repo, tmp_path)
    strata(
        "diff", "main", "--repo", str(lookml_repo), "--usage-fixture", str(USAGE),
        home=tmp_path / "home",
    )  # fmt: skip
    assert index_state(lookml_repo) == before


def test_diff_findings_api(lookml_repo):
    from strata_lookml.diff import diff_findings

    result = diff_findings(lookml_repo, "main", "feature", usage_fixture=USAGE)

    assert [r["id"] for r in result.new] == [NEW_EXPLORE]
    assert {r["id"] for r in result.fixed} == FIXED_IDS
    assert result.to_dict()["unchanged_count"] == result.unchanged_count
    assert result.head["commit"] == git(lookml_repo, "rev-parse", "feature").strip()

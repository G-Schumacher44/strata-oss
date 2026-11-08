import importlib.util
import re
from pathlib import Path

from strata_lookml.cli.main import strata_cli

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
SERVER = REPO_ROOT / "src" / "strata_lookml" / "mcp" / "server.py"
SKILLS_DIR = REPO_ROOT / "src" / "strata_lookml" / "skills"
REFERENCE = REPO_ROOT / "docs" / "reference.md"


def _load_gen_reference():
    spec = importlib.util.spec_from_file_location(
        "gen_reference", REPO_ROOT / "scripts" / "gen_reference.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_readme_tool_table_matches_registered_mcp_tools():
    server_text = SERVER.read_text(encoding="utf-8")
    registered = {
        match.group(1)
        for match in re.finditer(r"@server\.tool\([^\n]*\)\s+def\s+(strata_[a-z_]+)\(", server_text)
    }

    readme_text = README.read_text(encoding="utf-8")
    documented = {
        match.group(1)
        for match in re.finditer(r"^\| `(strata_[a-z_]+)` \|", readme_text, re.MULTILINE)
    }

    assert documented == registered


def test_readme_lists_all_bundled_skills():
    readme_text = README.read_text(encoding="utf-8")
    skill_names = {path.parent.name for path in SKILLS_DIR.rglob("SKILL.md")}

    missing = sorted(name for name in skill_names if name not in readme_text)

    assert len(skill_names) == 15
    assert missing == []


def test_readme_domain_skills_count_matches_filesystem():
    readme_text = README.read_text(encoding="utf-8")
    skill_count = len({path.parent.name for path in SKILLS_DIR.rglob("SKILL.md")})

    mentions = re.findall(r"(\d+)\s+domain skills", readme_text)
    assert mentions, "expected at least one 'N domain skills' phrase in README"
    stale = [n for n in mentions if int(n) != skill_count]
    assert stale == [], (
        f"README says {stale} domain skills but the filesystem has {skill_count} "
        f"(src/strata_lookml/skills/**/SKILL.md)"
    )


def test_readme_cli_table_matches_top_level_commands():
    readme_text = README.read_text(encoding="utf-8")
    cli_section = readme_text.split("## CLI", 1)[1].split("\n---", 1)[0]
    documented = {
        match.group(1)
        for match in re.finditer(r"^\| `strata ([a-z-]+)` \|", cli_section, re.MULTILINE)
    }

    # Hidden commands (e.g. internal helpers) are intentionally undocumented.
    visible = {name for name, cmd in strata_cli.commands.items() if not cmd.hidden}
    assert documented == visible


def test_reference_is_current():
    generated = _load_gen_reference().render()
    assert REFERENCE.read_text(encoding="utf-8") == generated, (
        "docs/reference.md is stale: run `python scripts/gen_reference.py` and commit the result"
    )


def test_readme_counts_match_introspection():
    counts = _load_gen_reference().counts()
    readme_text = README.read_text(encoding="utf-8")

    tool_mentions = re.findall(r"(\d+) (?:(?:MCP|analysis) )?tools", readme_text)
    read_only_mentions = re.findall(r"(\d+) read-only", readme_text)
    assert tool_mentions, "expected at least one 'N tools' phrase in README"
    assert read_only_mentions, "expected at least one 'N read-only' phrase in README"
    assert [n for n in tool_mentions if int(n) != counts["tools"]] == []
    assert [n for n in read_only_mentions if int(n) != counts["read_only"]] == []


def test_agent_facing_docs_do_not_contain_stale_counts():
    checked = [
        README,
        REPO_ROOT / "tests" / "README.md",
        REPO_ROOT / "src" / "strata_lookml" / "skills" / "governance" / "strata_workflow.md",
    ]
    stale_phrases = [
        "skills: 13 found",
        "skills: 14 found",
        "All 13 skills",
        "All 14 skills",
        "All 15 MCP tools",
        "All 10 tools",
        "13 commands",
        "14 commands",
    ]

    hits = []
    for path in checked:
        text = path.read_text(encoding="utf-8")
        hits.extend(
            f"{path.relative_to(REPO_ROOT)}: {phrase}" for phrase in stale_phrases if phrase in text
        )

    assert hits == []

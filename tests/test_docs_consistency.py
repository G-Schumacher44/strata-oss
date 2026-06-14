import re
from pathlib import Path

from strata.cli.main import strata_cli

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
SERVER = REPO_ROOT / "src" / "strata" / "mcp" / "server.py"
SKILLS_DIR = REPO_ROOT / "src" / "strata" / "skills"


def test_readme_tool_table_matches_registered_mcp_tools():
    server_text = SERVER.read_text(encoding="utf-8")
    registered = {
        match.group(1)
        for match in re.finditer(r"@server\.tool\(\)\s+def\s+(strata_[a-z_]+)\(", server_text)
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


def test_readme_cli_table_matches_top_level_commands():
    readme_text = README.read_text(encoding="utf-8")
    cli_section = readme_text.split("## CLI", 1)[1].split("\n---", 1)[0]
    documented = {
        match.group(1)
        for match in re.finditer(r"^\| `strata ([a-z-]+)` \|", cli_section, re.MULTILINE)
    }

    assert documented == set(strata_cli.commands)


def test_agent_facing_docs_do_not_contain_stale_counts():
    checked = [
        README,
        REPO_ROOT / "tests" / "README.md",
        REPO_ROOT / "src" / "strata" / "skills" / "governance" / "strata_workflow.md",
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

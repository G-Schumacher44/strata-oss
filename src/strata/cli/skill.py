"""strata skill — read the bundled skill catalog from the terminal.

CLI twin of the MCP `strata_list_skills` / `strata_skill` tools, so an agent that
prefers the shell (or has no MCP transport) can still discover and load skill
procedures instead of guessing at non-existent commands.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click

from strata.mcp.tools import strata_list_skills, strata_skill


def _skills_dir() -> Path:
    # Mirrors strata.mcp.server._skills_dir so the CLI and MCP resolve the same catalog.
    env = os.environ.get("STRATA_SKILLS_PATH")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent.parent / "skills"


@click.command("skill")
@click.argument("name", required=False)
def skill(name: str | None) -> None:
    """List bundled skills, or print one skill's full procedure.

    Same skills the MCP server exposes (`strata_list_skills` / `strata_skill`),
    available from the shell for agents and humans.

    \b
    Examples:
      strata skill                          # list all skills
      strata skill list                     # list all skills
      strata skill lookml_ticket_navigator  # print one skill's SKILL.md
    """
    skills_dir = _skills_dir()

    if name is None or name == "list":
        skills = strata_list_skills(skills_dir)
        click.echo(json.dumps(skills, indent=2))
        return

    content = strata_skill(skills_dir, name)
    if content.startswith("error:"):
        click.secho(content, fg="red", err=True)
        sys.exit(1)
    click.echo(content)

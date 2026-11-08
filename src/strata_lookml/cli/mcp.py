"""strata mcp — MCP server controls."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click

from strata_lookml.config import _read_config, load_cache_path, load_repo_path


@click.group()
def mcp() -> None:
    """Local MCP server for AI clients (Claude, Cursor, Gemini).

    Exposes 18 LookML analysis tools over stdio: 17 read-only, plus
    strata_render_chart, which writes one HTML file under ~/.strata/output/
    or /tmp/. Configure your AI client to launch `strata-mcp` via .mcp.json,
    then ask it to audit dead code, PDT costs, schema drift, or explore
    dependencies.
    """


@mcp.command("run")
def mcp_run() -> None:
    """Start the MCP server (used by .mcp.json / AI client configs).

    Runs in the foreground over stdio. Normally launched by your AI client
    automatically — you don't need to run this manually unless debugging.
    Set STRATA_REPO_PATH to point at your LookML repo.
    """
    from strata_lookml.mcp.server import main

    main()


@mcp.command("validate")
@click.option("--json", "as_json", is_flag=True, help="Emit {ready, checks, counts} as JSON.")
def mcp_validate(as_json: bool) -> None:
    """Check the repo parses and the server has what it needs to start.

    Builds the IR graph from your LookML, so "ready" means it parsed. Each check is
    pass (✓), advisory (~, never changes the exit code) or fail (✗, exit 1). Run it
    after `strata bootstrap`, before opening your AI client.

    \b
    $ STRATA_REPO_PATH=tests/lookml/enterprise_mono strata mcp validate
      repo:  tests/lookml/enterprise_mono  (from STRATA_REPO_PATH env)
      ✓ repo path: exists
      ✓ LookML parse: 41 nodes (3 models, 9 views, 12 explores, 17 fields)
      ~ IR cache: not built yet
        The server builds it on start; `strata build` pre-warms it.
      ✓ skills: 15 found
      ✓ chart templates: 4 found
      ~ usage facts: STRATA_USAGE_FIXTURE not set
        L1 tools will report usage_checked=false.
      ~ Looker token: missing
        Only needed for --looker-url; `strata auth login` creates it.
      MCP server is ready.
    """
    checks: list[dict[str, str | None]] = []
    counts: dict[str, int] = {}

    def add(name: str, status: str, message: str, hint: str | None = None) -> None:
        checks.append({"name": name, "status": status, "message": message, "hint": hint})

    repo = _repo_path()
    if os.environ.get("STRATA_REPO_PATH"):
        source = "STRATA_REPO_PATH env"
    elif _read_config().get("repo_path"):
        source = "~/.strata/config.json"
    else:
        source = "cwd default"

    graph = None
    if not repo.is_dir():
        if source == "STRATA_REPO_PATH env":
            hint = "unset or fix STRATA_REPO_PATH (it overrides ~/.strata/config.json)"
        elif source == "~/.strata/config.json":
            hint = "fix repo_path in ~/.strata/config.json or run `strata bootstrap`"
        else:
            hint = "set STRATA_REPO_PATH, add repo_path to ~/.strata/config.json, or run `strata bootstrap`"
        add("repo path", "fail", "repo path does not exist", hint)
    else:
        add("repo path", "pass", "exists")
        from strata_lookml.errors import StrataError
        from strata_lookml.pipeline import build_graph

        try:
            graph = build_graph(repo)
        except StrataError as exc:
            add("LookML parse", "fail", exc.message, exc.hint)
        except Exception as exc:  # parser/resolver crash on malformed LookML: report, don't trace
            add("LookML parse", "fail", f"{type(exc).__name__}: {exc}")
    if graph is not None:
        for node in graph.nodes.values():
            counts[node.kind] = counts.get(node.kind, 0) + 1
        by_kind = ", ".join(f"{n} {k}s" for k, n in sorted(counts.items()))
        counts = {"nodes": len(graph.nodes), "edges": len(graph.edges), **counts}
        add("LookML parse", "pass", f"{len(graph.nodes)} nodes ({by_kind})")

    # IR cache (the one resolver: honours --cache / STRATA_CACHE_PATH)
    from strata_lookml.ir.store import cache_age_seconds

    age = cache_age_seconds(load_cache_path(repo))
    if age is not None:
        add("IR cache", "pass", f"found (age: {int(age)}s)")
    else:
        add(
            "IR cache",
            "warn",
            "not built yet",
            "The server builds it on start; `strata build` pre-warms it.",
        )

    # Skills / chart templates (bundled)
    try:
        skills_dir = Path(__file__).resolve().parent.parent / "skills"
        add("skills", "pass", f"{len(list(skills_dir.rglob('SKILL.md')))} found")
    except OSError as e:
        add("skills", "fail", f"not found: {e}")
    try:
        charts_dir = Path(__file__).resolve().parent.parent / "viz" / "charts"
        add("chart templates", "pass", f"{len(list(charts_dir.glob('*.yml')))} found")
    except OSError as e:
        add("chart templates", "fail", f"not found: {e}")

    # Fixtures: unset is advisory; configured-but-broken is a hard failure
    from strata_lookml.l1.fixtures import load_usage_facts
    from strata_lookml.l1.schema import load_schema_facts

    for label, env_name, loader, flag in (
        ("usage facts", "STRATA_USAGE_FIXTURE", load_usage_facts, "usage_checked"),
        ("schema facts", "STRATA_SCHEMA_FIXTURE", load_schema_facts, "schema_checked"),
    ):
        configured = os.environ.get(env_name)
        if not configured:
            add(label, "warn", f"{env_name} not set", f"L1 tools will report {flag}=false.")
            continue
        fixture = Path(configured).expanduser()
        if not fixture.is_file():
            add(
                label,
                "fail",
                f"{env_name} points at a missing file: {fixture}",
                f"fix or unset {env_name}",
            )
            continue
        try:
            loader(fixture)
        except Exception as exc:  # any parse/shape failure means the server would not load it
            add(label, "fail", f"{fixture} is not valid {label}: {type(exc).__name__}: {exc}")
        else:
            add(label, "pass", str(fixture))

    # BQ project
    from strata_lookml.config import load_bq_project

    bq_project = load_bq_project()
    if bq_project:
        add("BQ project", "pass", bq_project)
    else:
        add(
            "BQ project",
            "warn",
            "not set (gcloud default will be used)",
            "set bq_project in ~/.strata/config.json for 2-part table names",
        )

    # Looker token
    from strata_lookml.l1.looker import DEFAULT_TOKEN_PATH

    if DEFAULT_TOKEN_PATH.exists():
        add("Looker token", "pass", "present")
    else:
        add(
            "Looker token",
            "warn",
            "missing",
            "Only needed for --looker-url; `strata auth login` creates it.",
        )

    ready = not any(c["status"] == "fail" for c in checks)
    if as_json:
        click.echo(json.dumps({"ready": ready, "checks": checks, "counts": counts}, indent=2))
    else:
        click.echo(f"  repo:       {repo}  (from {source})")
        glyph = {"pass": ("✓", "green"), "warn": ("~", "yellow"), "fail": ("✗", "red")}
        for c in checks:
            mark, color = glyph[str(c["status"])]
            click.secho(f"  {mark} {c['name']}: {c['message']}", fg=color)
            if c["hint"]:
                click.secho(f"    {c['hint']}", fg="yellow")
        click.echo()
        if ready:
            click.secho("MCP server is ready.", fg="green", bold=True)
        else:
            click.secho("Issues found — see above.", fg="red", bold=True)
    if not ready:
        sys.exit(1)


@mcp.command("config")
@click.option(
    "--client",
    type=click.Choice(["claude", "cursor"]),
    default=None,
    help="Print the MCP client config (.mcp.json / .cursor/mcp.json) instead of resolved paths",
)
@click.option(
    "--repo",
    "repo_arg",
    default=None,
    envvar="STRATA_REPO_PATH",
    show_envvar=True,
    help="With --client: LookML repo path (default: resolved)",
)
@click.option(
    "--usage-fixture",
    default=None,
    envvar="STRATA_USAGE_FIXTURE",
    show_envvar=True,
    help="With --client: usage_facts.json",
)
@click.option(
    "--schema-fixture",
    default=None,
    envvar="STRATA_SCHEMA_FIXTURE",
    show_envvar=True,
    help="With --client: schema_facts.json",
)
def mcp_config(
    client: str | None, repo_arg: str | None, usage_fixture: str | None, schema_fixture: str | None
) -> None:
    """Show resolved paths and env vars the MCP server will use.

    Outputs JSON — useful for debugging path resolution or confirming which
    repo, skills dir, and BQ project the server will pick up.

    \b
    $ STRATA_REPO_PATH=tests/lookml/enterprise_mono strata mcp config
    {
      "repo_path": "tests/lookml/enterprise_mono",
      "skills_path": "(bundled)",
      "charts_path": "(bundled)",
      "bq_project": "(not set — gcloud default used)",
      "cost_threshold_gb": 100.0
    }

    With --client, prints the exact file `strata bootstrap` writes, so you can
    wire an AI client without running bootstrap:

    \b
    $ strata mcp config --client claude > .mcp.json
    """
    from strata_lookml.config import load_bq_project, load_cost_threshold_gb

    if client:
        from strata_lookml.bootstrap.plan import render_mcp_client_config, resolve_fixture

        click.echo(
            render_mcp_client_config(
                Path(repo_arg).expanduser().resolve() if repo_arg else _repo_path(),
                resolve_fixture(usage_fixture),
                resolve_fixture(schema_fixture),
                client,
            ),
            nl=False,
        )
        return

    repo = _repo_path()
    config = {
        "repo_path": str(repo),
        "skills_path": os.environ.get("STRATA_SKILLS_PATH", "(bundled)"),
        "charts_path": os.environ.get("STRATA_CHARTS_PATH", "(bundled)"),
        "conductor_path": os.environ.get("STRATA_CONDUCTOR_PATH", str(repo / "conductor")),
        "cache_path": str(load_cache_path(repo)),
        "usage_fixture": os.environ.get("STRATA_USAGE_FIXTURE", "(none)"),
        "schema_fixture": os.environ.get("STRATA_SCHEMA_FIXTURE", "(none)"),
        "bq_project": load_bq_project() or "(not set — gcloud default used)",
        "cost_threshold_gb": load_cost_threshold_gb(),
    }
    click.echo(json.dumps(config, indent=2))


def _repo_path() -> Path:
    return load_repo_path()

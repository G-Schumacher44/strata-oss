"""strata workbench (alias: strata dashboard) — serve the local triage workbench."""

from __future__ import annotations

import threading
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit

import click

from strata_lookml.cli import dashboard as dash


def _url_port(url: str | None) -> int | None:
    """The explicit port of a path-form workbench URL, else None (no URL, no port, or a file)."""
    if not url:
        return None
    try:
        return urlsplit(url).port
    except ValueError:
        return None


@click.command("workbench")
@click.option(
    "--repo", required=True, envvar="STRATA_REPO_PATH", show_envvar=True, help="Path to LookML repo"
)
@click.option(
    "--usage-fixture",
    default=None,
    envvar="STRATA_USAGE_FIXTURE",
    show_envvar=True,
    help="Usage facts JSON",
)
@click.option(
    "--schema-fixture",
    default=None,
    envvar="STRATA_SCHEMA_FIXTURE",
    show_envvar=True,
    help="Schema facts JSON",
)
@click.option(
    "--looker-url",
    default=None,
    help="Looker API host URL for live L1 enrichment — the URL the `strata auth login` token was issued for (usually the instance URL)",
)
@click.option("--days", default=30, show_default=True, help="Looker usage window in days")
@click.option(
    "--baseline",
    "baseline_path",
    default=None,
    type=click.Path(dir_okay=False),
    help="Baseline file (from `strata check --write-baseline`): its ids show as baselined. Read only.",
)
@click.option(
    "--workbench-url",
    default=None,
    help="Workbench base URL that check, PR reports and MCP results link to (else "
    "STRATA_WORKBENCH_URL / config workbench_url); warned about when it names another port",
)
@click.option(
    "--out",
    default=None,
    help="Instead of the workbench: write the JSON artifacts and the static dashboard.html to "
    "this directory and serve it",
)
@click.option(
    "--port",
    default=dash.DEFAULT_PORT,
    show_default=True,
    help="Local server port (without --port, the next free port is used if the default is busy)",
)
@click.option("--no-browser", is_flag=True, help="Skip opening the browser")
def workbench(
    repo: str,
    usage_fixture: str | None,
    schema_fixture: str | None,
    looker_url: str | None,
    days: int,
    baseline_path: str | None,
    workbench_url: str | None,
    out: str | None,
    port: int,
    no_browser: bool,
) -> None:
    """Serve the triage workbench on 127.0.0.1: findings, overview and a page per object.

    Loads the IR from the cache (`strata build` / the MCP server write the same one) or builds
    and caches it, then serves until Ctrl+C. Opens the browser automatically — use
    --no-browser for headless environments. If the repo or a fixture changes while it runs, the
    pages show a "restart to reload" banner. `--out DIR` writes the static dashboard instead.

    \b
    strata workbench \\
      --repo tests/lookml/enterprise_mono \\
      --usage-fixture tests/fixtures/enterprise_usage_facts.json \\
      --schema-fixture tests/fixtures/enterprise_schema_facts.json
    """
    explicit = (
        click.get_current_context().get_parameter_source("port")
        is not click.core.ParameterSource.DEFAULT
    )
    if out:
        if baseline_path or workbench_url:
            raise click.UsageError(
                "--baseline and --workbench-url apply to the workbench, not --out"
            )
        dash.export_and_serve(
            repo, usage_fixture, schema_fixture, looker_url, days, out, port, explicit, no_browser
        )
        return

    from strata_lookml.config import load_workbench_url
    from strata_lookml.gate import BaselineError, load_baseline
    from strata_lookml.ir.store import describe_inputs
    from strata_lookml.workbench.app import App
    from strata_lookml.workbench.index import Staleness, index_graph, load_graph
    from strata_lookml.workbench.server import make_handler, new_token

    _repo = Path(repo).expanduser().resolve()
    base_url = load_workbench_url(workbench_url)
    baseline = None
    if baseline_path:
        try:
            baseline = load_baseline(Path(baseline_path))
        except BaselineError as exc:
            raise click.UsageError(str(exc)) from exc

    click.echo(f"Loading IR for {_repo.name}...")
    if looker_url:
        from strata_lookml.cli.outputs import live_looker_graph

        # Live usage is not cached; staleness still watches the repo and the schema fixture.
        usage_fixture = None
        inputs = describe_inputs(_repo, None, schema_fixture)
        graph = live_looker_graph(str(_repo), looker_url, days, schema_fixture)
    else:
        graph, inputs = load_graph(_repo, usage_fixture, schema_fixture)
    index = index_graph(
        graph,
        repo=_repo,
        usage_fixture=usage_fixture,
        schema_fixture=schema_fixture,
        inputs=inputs,
        baseline=baseline,
        baseline_path=baseline_path,
        base_url=base_url,
    )
    token = new_token()
    staleness = Staleness(index.inputs, index.fingerprint)

    server = dash.bind_server(
        port if explicit else dash.DEFAULT_PORT,
        explicit,
        handler_factory=lambda p: make_handler(App(index, dash.allowed_hosts(p), token, staleness)),
    )
    bound = server.server_address[1]
    url = f"http://127.0.0.1:{bound}/findings"
    if bound != dash.DEFAULT_PORT and not explicit:
        click.echo(f"Port {dash.DEFAULT_PORT} is busy; using {bound}.")
    linked = _url_port(base_url)
    if linked is not None and linked != bound:
        click.secho(
            f"Warning: the workbench URL {base_url} names port {linked}, but the workbench is "
            f"on {bound}; links built from it will not reach this server.",
            fg="yellow",
            err=True,
        )
    click.echo(f"\nServing at {url}  (Ctrl+C to stop)\n")

    if not no_browser:
        threading.Timer(0.4, webbrowser.open, args=[url]).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        click.echo("\nStopped.")
    finally:
        server.server_close()


dashboard = click.Command(
    "dashboard",
    params=workbench.params,
    callback=workbench.callback,
    help="Alias of `strata workbench` (same options).\n\n"
    "`--out DIR` keeps the static dashboard export: JSON artifacts plus a self-contained "
    "dashboard.html written to DIR and served from it.",
)

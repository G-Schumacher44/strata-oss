"""strata dashboard — build artifacts and serve observability dashboard."""

from __future__ import annotations

import http.server
import json
import socketserver
import threading
import webbrowser
from pathlib import Path
from typing import Any

import click


@click.command("dashboard")
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
@click.option("--looker-url", default=None, help="Looker URL for live enrichment")
@click.option("--days", default=30, show_default=True, help="Looker usage window in days")
@click.option("--out", default=None, help="Output directory (default: output/<repo-name>)")
@click.option("--port", default=8765, show_default=True, help="Local server port")
@click.option("--no-browser", is_flag=True, help="Skip opening the browser")
def dashboard(
    repo: str,
    usage_fixture: str | None,
    schema_fixture: str | None,
    looker_url: str | None,
    days: int,
    out: str | None,
    port: int,
    no_browser: bool,
) -> None:
    """Build all artifacts and open an interactive observability dashboard.

    Writes JSON artifacts to OUT/ (dead code, PDT costs, schema drift, etc.),
    generates a self-contained dashboard.html, and serves it locally. Opens
    the browser automatically — use --no-browser for headless environments.

    \b
    strata dashboard \\
      --repo tests/lookml/enterprise_mono \\
      --usage-fixture tests/fixtures/enterprise_usage_facts.json \\
      --schema-fixture tests/fixtures/enterprise_schema_facts.json
    """
    from strata.outputs import write_artifacts
    from strata.outputs.dashboard import build_dashboard_html
    from strata.pipeline import build_graph, build_graph_from_looker

    _repo = Path(repo).expanduser().resolve()
    out_dir = Path(out).expanduser().resolve() if out else Path.cwd() / "output" / _repo.name
    out_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"Building IR for {_repo.name}...")
    if looker_url:
        graph = build_graph_from_looker(str(_repo), looker_url, days, schema_fixture)
    else:
        graph = build_graph(str(_repo), usage_fixture, schema_fixture)

    click.echo("Writing artifacts...")
    artifacts = write_artifacts(graph, str(out_dir))

    click.echo("Generating dashboard...")
    artifact_data = {
        name: json.loads(Path(path).read_text(encoding="utf-8")) for name, path in artifacts.items()
    }
    html = build_dashboard_html(artifact_data, graph)
    dashboard_path = out_dir / "dashboard.html"
    dashboard_path.write_text(html, encoding="utf-8")
    click.secho(f"Dashboard: {dashboard_path}", fg="green")

    url = f"http://localhost:{port}/dashboard.html"
    click.echo(f"\nServing at {url}  (Ctrl+C to stop)\n")

    import os

    os.chdir(out_dir)

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

    socketserver.TCPServer.allow_reuse_address = True
    server = http.server.HTTPServer(("localhost", port), QuietHandler)

    if not no_browser:
        threading.Timer(0.4, webbrowser.open, args=[url]).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        click.echo("\nStopped.")

"""strata dashboard — build artifacts and serve observability dashboard."""

from __future__ import annotations

import errno
import http.server
import json
import socketserver
import threading
import webbrowser
from pathlib import Path
from typing import Any

import click

from strata_lookml.errors import StrataError

DEFAULT_PORT = 8765
# Tried in order when the default port is busy and `--port` was not passed.
FALLBACK_PORTS = range(8766, 8786)


def allowed_hosts(port: int) -> frozenset[str]:
    """Host header values accepted for a loopback server bound to ``port`` (lowercase)."""
    hosts = ("127.0.0.1", "localhost", "[::1]")
    permitted = {f"{h}:{port}" for h in hosts}
    if port == 80:  # browsers omit the default port from Host
        permitted.update(hosts)
    return frozenset(permitted)


def make_handler(port: int) -> type[http.server.SimpleHTTPRequestHandler]:
    """Static-file handler that serves only requests whose Host header is a permitted loopback form.

    Guards against DNS rebinding: a foreign page can point its own hostname at 127.0.0.1, but
    the browser then sends that hostname in Host, which is not on the allowlist.
    """
    permitted = allowed_hosts(port)

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

        def send_head(self) -> Any:  # GET and HEAD both route through here
            if (self.headers.get("Host") or "").strip().lower() not in permitted:
                self.send_error(403, "Forbidden")
                return None
            # `/` opens the dashboard rather than a raw directory listing; every artifact
            # stays reachable at its own path, and the Host check above still runs first.
            path, sep, query = self.path.partition("?")
            if path == "/" and (Path(self.directory) / "dashboard.html").is_file():
                self.path = "/dashboard.html" + sep + query
            return super().send_head()

    return QuietHandler


def bind_server(
    port: int, explicit: bool, fallback_ports: range | None = None
) -> http.server.HTTPServer:
    """Bind the loopback server, with the Host allow-list built from the port actually bound.

    An explicit ``--port`` that is busy fails; the default port falls back through the range.
    """
    fallback = FALLBACK_PORTS if fallback_ports is None else fallback_ports
    candidates = [port] if explicit else [port, *fallback]
    for candidate in candidates:
        try:
            # Loopback only, by IP literal: "localhost" can resolve to other interfaces on some hosts.
            return http.server.HTTPServer(("127.0.0.1", candidate), make_handler(candidate))
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE:
                raise
    if explicit:
        raise StrataError(
            f"Port {port} is already in use.",
            hint="Pass a different --port, or omit --port to use the first free port from "
            f"{port} up.",
        )
    tried = f"{port} and {candidates[1]}-{candidates[-1]}" if len(candidates) > 1 else str(port)
    raise StrataError(
        f"No free port for the dashboard (tried {tried}).",
        hint="Free a port, or pass --port with one that is open.",
    )


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
@click.option(
    "--looker-url",
    default=None,
    help="Looker API host URL for live L1 enrichment — the URL the `strata auth login` token was issued for (usually the instance URL)",
)
@click.option("--days", default=30, show_default=True, help="Looker usage window in days")
@click.option("--out", default=None, help="Output directory (default: output/<repo-name>)")
@click.option(
    "--port",
    default=DEFAULT_PORT,
    show_default=True,
    help="Local server port (without --port, the next free port is used if the default is busy)",
)
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
    from strata_lookml.cli.outputs import live_looker_graph
    from strata_lookml.outputs import write_artifacts
    from strata_lookml.outputs.dashboard import build_dashboard_html
    from strata_lookml.pipeline import build_graph

    _repo = Path(repo).expanduser().resolve()
    out_dir = Path(out).expanduser().resolve() if out else Path.cwd() / "output" / _repo.name
    out_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"Building IR for {_repo.name}...")
    if looker_url:
        graph = live_looker_graph(str(_repo), looker_url, days, schema_fixture)
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

    explicit = (
        click.get_current_context().get_parameter_source("port")
        is not click.core.ParameterSource.DEFAULT
    )
    import os

    os.chdir(out_dir)

    socketserver.TCPServer.allow_reuse_address = True
    server = bind_server(port if explicit else DEFAULT_PORT, explicit)
    bound = server.server_address[1]
    url = f"http://127.0.0.1:{bound}/dashboard.html"
    if bound != DEFAULT_PORT and not explicit:
        click.echo(f"Port {DEFAULT_PORT} is busy; using {bound}.")
    click.echo(f"\nServing at {url}  (Ctrl+C to stop)\n")

    if not no_browser:
        threading.Timer(0.4, webbrowser.open, args=[url]).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        click.echo("\nStopped.")

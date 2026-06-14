"""strata auth — Looker OAuth token management."""

from __future__ import annotations

import json
import webbrowser

import click

from strata.l1.looker import (
    DEFAULT_CLIENT_GUID,
    DEFAULT_REDIRECT_URI,
    DEFAULT_TOKEN_PATH,
    auth_url,
    exchange_code,
    load_token,
    save_token,
)


@click.group()
def auth() -> None:
    """Authenticate with Looker and manage your local OAuth token.

    Required for `strata dashboard --looker-url` and live `strata generate-schema`.
    Offline commands (check, outputs, query) don't need a token.

    \b
    strata auth login --looker-url https://your-instance.looker.com
    strata auth status
    strata auth logout
    """


@auth.command("login")
@click.option("--looker-url", required=True, envvar="LOOKER_URL", help="Looker instance URL")
@click.option("--code", default=None, help="Authorization code from the redirect URL")
@click.option("--client-guid", default=DEFAULT_CLIENT_GUID, show_default=True)
@click.option("--redirect-uri", default=DEFAULT_REDIRECT_URI, show_default=True)
@click.option("--token-path", default=str(DEFAULT_TOKEN_PATH), show_default=True)
@click.option("--no-browser", is_flag=True, help="Print auth URL without opening browser")
def auth_login(
    looker_url: str,
    code: str | None,
    client_guid: str,
    redirect_uri: str,
    token_path: str,
    no_browser: bool,
) -> None:
    """Start Looker OAuth flow or exchange an authorization code for a token."""
    url = auth_url(looker_url, client_guid, redirect_uri)
    click.echo(f"Auth URL:\n{url}\n")
    if not no_browser:
        webbrowser.open(url)
    if not code:
        click.echo(
            "Authorize Strata in the browser, then re-run with --code from the redirect URL."
        )
        return
    token = exchange_code(looker_url, code, client_guid, redirect_uri)
    save_token(token, token_path)
    click.secho("Token saved.", fg="green")
    click.echo(json.dumps(token.redacted(), indent=2, sort_keys=True))


@auth.command("status")
@click.option("--token-path", default=str(DEFAULT_TOKEN_PATH), show_default=True)
def auth_status(token_path: str) -> None:
    """Show redacted local token status."""
    token = load_token(token_path)
    click.echo(json.dumps(token.redacted(), indent=2, sort_keys=True))


@auth.command("logout")
@click.option("--token-path", default=str(DEFAULT_TOKEN_PATH), show_default=True)
def auth_logout(token_path: str) -> None:
    """Delete the local Looker token."""
    from pathlib import Path

    path = Path(token_path).expanduser()
    if path.exists():
        path.unlink()
        click.secho(f"Token removed: {path}", fg="green")
    else:
        click.echo("No token found.")

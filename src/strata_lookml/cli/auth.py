"""strata auth — Looker OAuth token management."""

from __future__ import annotations

import json
import webbrowser
from pathlib import Path

import click

from strata_lookml.l1.looker import (
    DEFAULT_CLIENT_ID,
    DEFAULT_REDIRECT_URI,
    DEFAULT_TOKEN_PATH,
    LiveLookerNotConfigured,
    LookerAPIError,
    auth_url,
    exchange_code,
    load_token,
    save_token,
)
from strata_lookml.l1.oauth import (
    LoopbackReceiver,
    OAuthCallbackError,
    code_from_callback,
    new_pkce_pair,
    new_state,
)


@click.group()
def auth() -> None:
    """Authenticate with Looker and manage your local OAuth token.

    Needed only for live Looker enrichment (`strata outputs --looker-url`,
    `strata dashboard --looker-url`). Offline commands (check, outputs, query, the MCP
    server) never read the token; `strata generate-schema` uses the `bq` CLI and your gcloud
    credentials, not this token.

    \b
    strata auth login --looker-url https://your-instance.looker.com
    strata auth status
    strata auth logout
    """


@auth.command("login")
@click.option("--looker-url", required=True, envvar="LOOKER_URL", help="Looker UI host URL")
@click.option(
    "--api-url",
    default=None,
    envvar="LOOKER_API_URL",
    help="Looker API host URL, if it differs from the UI host (token is bound to this host)",
)
@click.option(
    "--client-id",
    "--client-guid",
    "client_id",
    default=DEFAULT_CLIENT_ID,
    show_default=True,
    help="client_guid of the OAuth client app registered in Looker",
)
@click.option(
    "--redirect-uri",
    default=DEFAULT_REDIRECT_URI,
    show_default=True,
    help="Redirect URI registered on the OAuth client app (must match exactly)",
)
@click.option("--token-path", default=str(DEFAULT_TOKEN_PATH), show_default=True)
@click.option(
    "--no-browser",
    is_flag=True,
    help="Don't open a browser or listen locally; paste the redirect URL on stdin instead",
)
@click.option("--timeout", default=300, show_default=True, help="Seconds to wait for the redirect")
def auth_login(
    looker_url: str,
    api_url: str | None,
    client_id: str,
    redirect_uri: str,
    token_path: str,
    no_browser: bool,
    timeout: int,
) -> None:
    """Sign in to Looker with OAuth (PKCE + state) and store the access token locally.

    By default Strata listens once on the loopback redirect URI, opens the browser, and
    captures the code itself. With --no-browser, open the printed URL anywhere, then paste
    the full redirect URL when prompted (read from stdin, never from the command line).
    """
    verifier, challenge = new_pkce_pair()
    state = new_state()
    url = auth_url(looker_url, state, challenge, client_id, redirect_uri)
    try:
        if no_browser:
            click.echo(f"Open this URL to authorize Strata:\n{url}\n")
            pasted = click.prompt(
                "Paste the full redirect URL", hide_input=True, err=True, prompt_suffix=": "
            )
            code = code_from_callback(pasted, state)
        else:
            try:
                receiver = LoopbackReceiver(redirect_uri)
            except OSError as exc:
                raise click.ClickException(
                    f"could not listen on {redirect_uri} ({exc.strerror}); free the port, "
                    "register a different loopback redirect URI, or use --no-browser"
                ) from exc
            click.echo(f"Opening your browser to authorize Strata:\n{url}\n")
            click.echo(f"Waiting for the redirect on {redirect_uri} ...")
            webbrowser.open(url)
            code = receiver.wait(state, timeout=timeout)
        token = exchange_code(api_url or looker_url, code, verifier, client_id, redirect_uri)
    except (OAuthCallbackError, LookerAPIError, LiveLookerNotConfigured) as exc:
        raise click.ClickException(str(exc)) from exc
    save_token(token, token_path)
    click.secho("Token saved.", fg="green")
    click.echo(json.dumps(token.redacted(), indent=2, sort_keys=True))


@auth.command("status")
@click.option("--token-path", default=str(DEFAULT_TOKEN_PATH), show_default=True)
def auth_status(token_path: str) -> None:
    """Show redacted local token status."""
    try:
        token = load_token(token_path)
    except LiveLookerNotConfigured as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(token.redacted(), indent=2, sort_keys=True))


@auth.command("logout")
@click.option("--token-path", default=str(DEFAULT_TOKEN_PATH), show_default=True)
def auth_logout(token_path: str) -> None:
    """Delete the local Looker token.

    This is local only: the token stays valid at Looker until it expires or a Looker admin
    revokes it.
    """
    path = Path(token_path).expanduser()
    if path.exists():
        path.unlink()
        click.secho(f"Token removed: {path}", fg="green")
    else:
        click.echo("No token found.")
    click.echo(
        "Note: this only deletes the local copy. The token stays valid at Looker until it "
        "expires or a Looker admin revokes it."
    )

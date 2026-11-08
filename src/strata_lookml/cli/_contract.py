"""The CLI side of the error contract (see `strata_lookml.errors`).

Exit codes: 0 success, 1 failure (any `StrataError` or other `ClickException`), 2 usage error
(click's own). Commands raise `StrataError` and never catch it themselves; this module is the
only place it turns into output.
"""

from __future__ import annotations

import json
from typing import IO, Any

import click

from strata_lookml.errors import StrataError


class _StrataClickError(click.ClickException):
    exit_code = 1

    def __init__(self, error: StrataError) -> None:
        super().__init__(error.message)
        self.error = error

    def show(self, file: IO[Any] | None = None) -> None:
        click.echo(f"Error: {self.error.message}", err=True)
        if self.error.hint:
            click.echo(f"Hint: {self.error.hint}", err=True)


class StrataGroup(click.Group):
    """Root group: a `StrataError` from any subcommand → stderr `Error:`/`Hint:`, exit 1."""

    def invoke(self, ctx: click.Context) -> Any:
        try:
            return super().invoke(ctx)
        except StrataError as exc:
            raise _StrataClickError(exc) from exc


class JsonCommand(click.Command):
    """A command whose stdout is JSON: a `StrataError` also prints its envelope there.

    The envelope is `{"error": <message>, "code": <code>, "hint": <hint>}`; `error` stays a
    string so `.error` checks written against the old soft-error output keep working. A
    command with an `as_json` flag (`--json`) emits it only when the flag is set.
    """

    def invoke(self, ctx: click.Context) -> Any:
        try:
            return super().invoke(ctx)
        except StrataError as exc:
            if ctx.params.get("as_json", True):
                click.echo(json.dumps(exc.to_dict(), indent=2))
            raise

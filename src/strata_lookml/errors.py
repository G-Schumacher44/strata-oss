"""Strata's one error contract, shared by the MCP server and the CLI.

Every anticipated domain failure (unknown object, bad input, missing repo) raises a
`StrataError`. The type is the seam on both surfaces:

- MCP: `StrataError` subclasses the SDK's `ToolError`, so the server returns `isError: true`
  with the message for the client model to read. Anything else stays a crash, and the SDK
  keeps its text on the server.
- CLI: `cli._contract.StrataGroup` prints `Error:` / `Hint:` on stderr and exits 1;
  `cli._contract.JsonCommand` also prints `{"error", "code", "hint"}` on stdout.
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver.exceptions import ToolError


class StrataError(ToolError):
    """An anticipated failure: a stable `code`, a `message`, and an optional next-step `hint`."""

    code = "error"

    def __init__(self, message: str, hint: str | None = None) -> None:
        self.message = message
        self.hint = hint
        super().__init__(message)

    def __str__(self) -> str:
        return f"{self.message} Hint: {self.hint}" if self.hint else self.message

    def to_dict(self) -> dict[str, Any]:
        return {"error": self.message, "code": self.code, "hint": self.hint}


class NotFound(StrataError):
    """The named object (field, explore, table, model, skill, repo) does not exist."""

    code = "not_found"


class InvalidInput(StrataError):
    """The input is malformed or outside what the tool accepts."""

    code = "invalid_input"

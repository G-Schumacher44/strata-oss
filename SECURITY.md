# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x (latest) | Yes |
| < 0.1 | No |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Email **me@garrettschumacher.com** with the subject line `[strata-oss] Security vulnerability`. Include:

- A description of the vulnerability and its potential impact
- Steps to reproduce or a proof of concept
- Affected Strata versions
- Any suggested mitigations

You will receive a response within **5 business days**. If the issue is confirmed, we will work on a fix and coordinate a disclosure timeline with you before any public disclosure.

## Security surface areas

Strata is a local analysis tool with an offline-first design. Primary security surface areas:

| Area | Notes |
|---|---|
| **Credential handling** | `strata auth login` stores tokens at `~/.strata/tokens.json` (0600 permissions, 0700 parent directory). Path-traversal or permission-escalation issues are in scope. |
| **MCP server** | stdio transport only — no HTTP server exposed. Injection via malicious LookML content or fixture JSON is in scope. |
| **LookML parsing** | Parsing attacker-controlled `.lkml` files from untrusted repos. Path traversal or code execution during IR build is in scope. |
| **CLI input handling** | Shell injection via command arguments is in scope. |

Out of scope: vulnerabilities in third-party dependencies (report upstream), theoretical issues with no realistic attack path.

## Security design

See [`docs/security-hardening.md`](docs/security-hardening.md) for the full security model — read-only enforcement, HTTPS enforcement, token permission checks, and MCP security posture.

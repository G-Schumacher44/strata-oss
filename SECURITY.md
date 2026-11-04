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

Strata is a local analysis tool with an offline-first design. In scope:

| Area | Notes |
|---|---|
| **Credential handling** | `strata auth login` stores a Looker access token at `~/.strata/tokens.json` (file 0600, directory 0700 on POSIX; a group/world-accessible file is refused on read). The token is sent only to the Looker origin it was issued for. Token leakage, path-traversal, or permission issues are in scope. |
| **OAuth flow** | Authorization code + PKCE (S256) + `state`, with a one-shot loopback receiver on `127.0.0.1`. Code interception, `state` bypass, or redirect handling issues are in scope. |
| **MCP server** | stdio transport only. It writes one file, the IR cache (`strata_ir.db` in the LookML repo root, or `STRATA_CACHE_PATH`), and `strata_render_chart` writes `.html` files under `~/.strata/output/` or `/tmp/`. Injection via malicious LookML content or fixture JSON is in scope. |
| **Local HTTP servers** | `strata dashboard` serves its output directory on `127.0.0.1` (default port 8765) until stopped; `strata auth login` listens on the loopback redirect port for a single request. Exposure beyond loopback is in scope. |
| **LookML parsing** | Parsing attacker-controlled `.lkml` files from untrusted repos. Path traversal (including symlinks), or code execution during IR build, is in scope. |
| **Command and query construction** | Shell injection via command arguments, and SQL injection into the BigQuery queries `strata generate-schema` builds from repo-controlled table names, are in scope. |

Out of scope: vulnerabilities in third-party dependencies (report upstream), theoretical issues
with no realistic attack path, and prompt injection that relies on an agent acting on LookML or
skill text (Strata returns that text as data and executes none of it; see
[`docs/security-hardening.md`](docs/security-hardening.md#prompt-injection)).

## Security design

See [`docs/security-hardening.md`](docs/security-hardening.md) for the full security model — what Strata reads and writes, HTTPS enforcement, OAuth and token handling, and MCP security posture.

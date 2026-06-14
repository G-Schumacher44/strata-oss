# CLI Layer

**Entry point:** `strata_cli` group in `main.py`, exposed as `strata` via pyproject.toml

---

## What this layer is

User-facing CLI built with Click. Every command is a thin wrapper that calls into the
Python API (`pipeline.py`, `mcp/tools.py`, `outputs/`). No business logic lives here.

## Conventions

**Env var support.** Every `--repo`, `--usage-fixture`, and `--schema-fixture` option
must declare `envvar=` and `show_envvar=True` so users can set once and run short:

```python
@click.option("--repo", envvar="STRATA_REPO_PATH", show_envvar=True, ...)
```

Env vars: `STRATA_REPO_PATH`, `STRATA_USAGE_FIXTURE`, `STRATA_SCHEMA_FIXTURE`.

**Help strings.** Every command needs a docstring. Non-trivial commands get a `\b` literal
block showing a real example with actual output — not pseudocode:

```python
def my_command(...):
    """One-line summary.

    \b
    $ strata my-command --repo tests/lookml/enterprise_mono
    { "result": "..." }
    """
```

**Output.** Commands that return data print JSON via `click.echo(json.dumps(..., indent=2))`.
Commands that report status use `click.secho(..., fg="green"|"red"|"yellow")`.

**Exit codes.** Exit 0 on success, 1 on hard failure (`sys.exit(1)` or `raise click.ClickException`).

## Files

| File | Command(s) |
|---|---|
| `main.py` | `strata` group + `clean` |
| `check.py` | `strata check` |
| `outputs.py` | `strata outputs` |
| `query.py` | `strata query` group (field, explore, orphans, impact, scope, status, find-field, view-sources, navigate) |
| `skill.py` | `strata skill [name]` — list skills or print one (CLI twin of `strata_list_skills`/`strata_skill`) |
| `mcp.py` | `strata mcp` group (run, validate, config) |
| `build_ir.py` | `strata build` |
| `dashboard.py` | `strata dashboard` |
| `generate_schema.py` | `strata generate-schema` |
| `bootstrap.py` | `strata bootstrap` |
| `validate.py` | `strata validate` |
| `auth.py` | `strata auth` group (login, status, logout) |
| `chart.py` | `strata chart` group (bar, line, scatter, heatmap, render, list) |
| `conductor.py` | `strata conductor` group (init, new-slice, status) |

## Adding a command

1. Create `src/strata/cli/mycommand.py` with a Click function
2. Import and register in `main.py` via `strata_cli.add_command(...)`
3. Add env vars for any repo/fixture path options
4. Add a CLI smoke test in `tests/test_cli.py` using the `run(*args)` helper
5. Update `docs/cli-guide.md` command table

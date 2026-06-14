# Contributing to Strata

Thanks for your interest. Strata is a deterministic LookML governance engine — preserving the deterministic core is the primary constraint on all contributions.

## Quick start

```bash
git clone https://github.com/G-Schumacher44/strata-oss.git
cd strata-oss
pip install -e ".[dev]"
pre-commit install
```

## Core constraints

These are non-negotiable:

- **L0 and L1 must remain free of LLM/model calls.** The IR builder and enrichment pipeline are pure deterministic Python — no model calls, no external network calls.
- **CI must pass without live credentials.** Tests run against bundled fixture JSON. No live Looker, BigQuery, Slack, or Jira access required.
- **New verdicts or reports need evidence-backed tests.** If you add a new analysis result, add a test fixture that proves it fires correctly.
- **No secrets, generated outputs, or local token files in commits.** `~/.strata/tokens.json`, `output/`, `strata_ir.db`, and `.mcp.json` are all gitignored — keep it that way.

## Development workflow

### Linting and type checking

```bash
strata lint                   # ruff check + mypy
strata lint --fix --format    # auto-fix safe violations + format
```

### Running tests

```bash
pytest
```

### Running the full offline gate

Run both of these before opening a PR — both must exit 0:

```bash
strata check \
  --repo tests/lookml/gcs_analytics \
  --usage-fixture tests/fixtures/gcs_usage_facts.json \
  --schema-fixture tests/fixtures/gcs_schema_facts.json

strata check \
  --repo tests/lookml/enterprise_mono \
  --usage-fixture tests/fixtures/enterprise_usage_facts.json \
  --schema-fixture tests/fixtures/enterprise_schema_facts.json
```

### Pre-commit hooks

`pre-commit install` wires ruff and mypy to run on every commit automatically.

## PR process

1. Fork the repo and create a branch from `main`.
2. Make your changes, following the constraints above.
3. Run `strata lint`, `pytest`, and both `strata check` invocations.
4. Open a PR and fill out the pull request template.
5. A maintainer will review. CI must be green before merge.

## Code style

- Ruff enforces formatting (line length 100) and a curated rule set — see `[tool.ruff]` in `pyproject.toml`.
- Mypy runs with `check_untyped_defs = true` — type new code.
- Write comments only when the *why* is non-obvious. No docstring walls.

## Testing with the bundled playgrounds

Three LookML repos with matching fixture JSON ship in `tests/`:

| Playground | Description |
|---|---|
| `enterprise_mono` | 19 models, 34 explores, cross-model extends, 3 legacy clusters |
| `gcs_analytics` | Gold/silver BQ layer, mixed active and legacy |
| `thelook` | Looker's public demo repo — structural baseline |

Fixture JSON in `tests/fixtures/` simulates Looker System Activity API responses so the full analysis stack runs offline.

## Questions

Open a [Discussion](https://github.com/G-Schumacher44/strata-oss/discussions) for how-to questions or design ideas. Open an [Issue](https://github.com/G-Schumacher44/strata-oss/issues) for bugs or feature requests.

---

[← README](README.md) · [Docs index](docs/README.md) · [Original contributing notes](docs/CONTRIBUTING.md)

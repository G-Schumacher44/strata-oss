# tests/

Run fully offline — no Looker instance, no BigQuery credentials.

```bash
python -m pytest          # full suite
python -m pytest -k cli   # one file
python -m pytest -x       # stop on first failure
```

## Test files

| File | What it covers |
|---|---|
| `test_scaffold.py` | Package importable, networkx and mcp deps present |
| `test_ir_parser.py` | LookML parser: views, models, explores, joins, blocks, lists |
| `test_ir_resolver.py` | Extends/refinement chain resolution, orphan detection, IR cache round-trip |
| `test_l1_providers.py` | Usage providers: replay, fixture, graph enrichment contract |
| `test_l1_synthesis_outputs.py` | Dead code, PDT ledger, zombie views, verdict validation, artifact determinism |
| `test_schema_drift.py` | Schema drift detection: missing tables, missing columns, evidence IDs |
| `test_schema_refresh.py` | `generate-schema` dry-run across all 3 playgrounds |
| `test_validation_scope.py` | Changed file → impacted explore resolution, artifact output |
| `test_mcp_tools.py` | MCP tools against fixture IR: shape, types, error paths |
| `test_docs_consistency.py` | README and agent-facing docs stay aligned with registered tools and bundled skills |
| `test_cli.py` | CLI smoke tests: every `strata` subcommand returns expected output |
| `test_looker_provider.py` | Looker OAuth, token save/load/redact, HTTPS enforcement |
| `test_notifications.py` | Slack/Jira payload structure, notify.py dry-run |
| `test_security.py` | HTTPS enforcement, L0 import guard, MCP error paths, chart path escape |

## Fixtures

`tests/fixtures/` contains two kinds of fixture:

**Synthetic LookML** — minimal `.lkml` files designed to exercise specific resolver behaviors
(extends chains, refinements, orphans, PDTs). Not realistic repos — deliberate edge cases.

**JSON fact fixtures** — usage, schema, and replay facts for the synthetic fixtures and all
3 playgrounds (`enterprise_mono`, `gcs_analytics`, `thelook`):

| File | Contents |
|---|---|
| `usage_facts.json` | Explore query counts for synthetic fixtures |
| `replay_facts.json` | Raw Looker System Activity rows for replay provider tests |
| `schema_facts_clean.json` | Schema with no drift (baseline) |
| `schema_facts_drift.json` | Schema with deliberate drift (missing tables + columns) |
| `validation_scope_changed.json` | Changed objects input for scope tests |
| `enterprise_usage_facts.json` | Usage + PDT facts for enterprise_mono playground |
| `enterprise_schema_facts.json` | Schema facts for enterprise_mono playground |
| `gcs_usage_facts.json` | Usage facts for gcs_analytics playground |
| `gcs_schema_facts.json` | Schema facts for gcs_analytics playground |
| `playground_usage_facts.json` | Usage facts for thelook playground |
| `playground_schema_facts.json` | Schema facts for thelook playground |

**LookML playgrounds** live in `tests/lookml/` (git submodules):
- `enterprise_mono` — 19 models, 34 explores, cross-model extends, 3 legacy clusters
- `gcs_analytics` — gold/silver BQ layer, mixed active and legacy
- `thelook` — Looker's public demo repo, structural baseline

## Adding tests

- Use `tests/fixtures/` for all fixture paths — no hardcoded absolute paths
- Use real parsed fixtures, not mocked graphs
- CLI tests go in `test_cli.py` using the `run(*args)` helper
- MCP tool tests go in `test_mcp_tools.py` — call the Python function directly, not the server
- New fixture LookML files belong in `tests/fixtures/`, not in a playground submodule

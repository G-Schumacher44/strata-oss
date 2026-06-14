## Summary

<!-- What does this PR change and why? One to three sentences. -->

## Type of change

- [ ] Bug fix
- [ ] New feature / enhancement
- [ ] Refactor (no behavior change)
- [ ] Documentation
- [ ] CI / tooling

## Strata area(s) affected

- [ ] LookML IR / parser
- [ ] Dead code detection
- [ ] PDT ledger / cost
- [ ] Schema drift
- [ ] MCP server tools
- [ ] CLI
- [ ] Dashboard / charts
- [ ] Conductor / handoffs
- [ ] Skills
- [ ] BigQuery enrichment
- [ ] Looker auth
- [ ] CI / workflow

## Pre-merge checklist

- [ ] `strata lint` passes (ruff + mypy)
- [ ] `pytest` passes locally
- [ ] `strata check` passes on `gcs_analytics` and `enterprise_mono` playgrounds
- [ ] L0 and L1 layers remain free of LLM/model calls
- [ ] No secrets, token files, or org-specific fixtures committed
- [ ] New verdicts/reports have evidence-backed tests

## Testing done

<!-- Describe how you tested this. Which playground(s)? Offline fixtures or live enrichment? -->

## Related issues

<!-- Closes #NNN -->

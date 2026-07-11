# Capped xfail inventory

> Maintainer/internal documentation. This page is intentionally omitted from
> public navigation and is enforced by the release-hygiene policy.

Only failures listed here may be quarantined. The cap is deliberately small so
the nightly suite remains an honest signal rather than a parking lot.

Maximum active xfails: 1

| Test | Reason | Clearing phase |
| --- | --- | --- |
| tests/integration/phase9/test_phase9_metadata_rules.py::test_docstring_extraction_with_rules | GATES-1: phase-9 docstring metadata baseline | COREFIX |

## mypy type-debt baseline (GATES)

Strict mypy carries **1241 pre-existing error signatures** (~2244 raw errors across ~214
files) surfaced when GATES removed the CI `::warning::` downgrade. CI runs
`scripts/mypy_gate.py`, a **baseline-relative** gate: it fails only on error signatures
NOT in `docs/development/mypy-baseline.txt`, so new type errors are blocked immediately
while the tracked debt is paid down by shrinking the baseline.

- Clearing owner: a dedicated type-debt phase (post-remediation), which reduces the
  baseline in bounded batches and re-runs `scripts/mypy_gate.py --update`.
- Do NOT add to the baseline to silence a new error — fix the error instead.

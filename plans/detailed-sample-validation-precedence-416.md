---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Preserve validation failure through sample classification

## Task and research

Resolve treesitter-chunker#416 separately from accepted treesitter-chunker#406.
On accepted main, an actual missing-grammar validation error plus one valid and
one malformed Python sample produces LIMITED with score0 and retained errors.
The sample stage unconditionally assigns LIMITED for success rates[0.5,0.8),
weakening an independently established INCOMPATIBLE result.
Read access to own verification artifacts is allowlisted at /tmp/chunker-416-*.

## Changes

- chunker/grammar_management/compatibility.py: prevent only the partial-success
  sample branch from replacing INCOMPATIBLE. Preserve actual sample execution,
  counts/errors, existing score multiplication and every other classification.
- tests/test_grammar_compatibility_contract.py: add one parameterized behavior
  cluster using checked-in service.py and malformed variants with real parsers,
  real isolated GrammarManager/GrammarValidator and an actual missing artifact.
  Cover validation failure versus no failure, metadata timing0/3/6seconds,
  and sample success rates0,1/3,1/2,2/3,4/5,1. Require independent failure stays
  INCOMPATIBLE/zero while sample-only levels and score multipliers are unchanged.
  Assert all counts, actual parse errors, retained validation issues and warnings.
- docs/grammar_management.md: replace the deferred sample-stage warning with
  the bounded precedence contract, retaining independent timing semantics.
- CHANGELOG.md: describe retained incompatibility without claiming native safety.
- This plan and its typed plans/manifest.json row are owned control paths.

## Dependencies and order

Start from main containing accepted treesitter-chunker#417. Register the plan
before tests/code. Reproduce the six partial-success/validation-failure cases,
apply the guard, then kill promote_invalid_validation_with_partial_samples by
restoring unconditional LIMITED. Exact restoration must pass the full focused
cluster and record production/test hashes. No parser/validator/checker mocks.
File separately discovered defects; no native admission or deadline changes.
At most three substantive manual four-seat review rounds on immutable candidates.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_grammar_compatibility_contract.py tests/test_grammar_compatibility_cleanup_contract.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py

Matching-source Windows focused/standing preflight, exact-head hosted jobs and
the original six/refresh/full tests plus spec_tests are required before closeout.
No coverage percentage or pinned plan outputs; assertions target real behavior.

## Acceptance criteria

- [ ] Actual missing-artifact validation plus partial sample success retains
  INCOMPATIBLE, zero score and exact validation errors at all three timing values.
- [ ] Actual sample-only classification, complete counts/errors and existing
  threshold multipliers remain, including success boundaries0.5 and0.8.
  The named unconditional-LIMITED mutation fails six intended cases and exact
  restoration passes all focused contracts.
- [ ] Original six checks, locked refresh/full tests/spec_tests, matching-source
  Windows, exact hosted CI and bounded manual reviews accept only this repair.
  No native, parser pin, consumer lock or whole COMPAT/IF acceptance.

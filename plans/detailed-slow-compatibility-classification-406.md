---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_grammar_compatibility_contract.py tests/test_grammar_compatibility_cleanup_contract.py -q"
---

# Detailed plan: Reach very-slow classification without losing incompatibility

## Task and research

Resolve treesitter-chunker#406 as an independently landable EC-COMPAT-1 subset.
CompatibilityChecker._perform_detailed_compatibility_check checks >2 seconds
before elif >5 seconds, so the declared very-slow score multiplier and DEGRADED
classification are unreachable. The method receives performance metadata and
parses actual caller samples through its validator. Timing inputs are metadata,
not a new measured wall-clock correctness gate. Existing validation errors must
remain INCOMPATIBLE within the timing adjustment when this formerly unreachable
branch becomes active. The later sample-stage precedence defect is independently
tracked as treesitter-chunker#416 and remains outside this timing repair.

## Changes

- chunker/grammar_management/compatibility.py: put the existing >5 threshold
  before >2. Very-slow metadata halves the score and degrades otherwise compatible
  validation, preserving INCOMPATIBLE within that timing branch if independent
  validation errors exist.
  Preserve moderate 0.8 multiplier and existing slow warning, exact threshold
  strictness, validation errors/warnings and subsequent actual sample outcomes.
  No timing-source, baseline arithmetic, missing-sample classification, database
  or native-admission changes.
- tests/test_grammar_compatibility_contract.py: actual installed Python parsing
  of checked-in service fixture and real isolated manager/validator feed the
  actual checker. Parameterize metadata 0,2,2.01,5,5.01,6 seconds. Require exact
  compatible/degraded classification, score and warning at every boundary plus
  actual successful sample counts. Additional validation-error and malformed
  sample cases at six seconds must prove that the timing branch retains
  validation incompatibility and that actual sample failures still produce
  their existing independent observations. Mixed validation errors with partial
  sample success remain treesitter-chunker#416. No parser/validator/checker/time mocks.
- Named mutations broad_threshold_first and overwrite_incompatible_level must
  fail the very-slow and independent-validation contracts respectively. Restore
  exact production bytes and pass the focused batch after every mutation.
- docs/grammar_management.md and CHANGELOG.md: clarify metadata threshold
  classification and timing-stage precedence of independent incompatibility; no performance
  SLA or new wall-clock gate. Own this detailed plan and typed manifest.

## Dependencies and order

The accepted nullable history repair treesitter-chunker#408 is already in the
base. Register before tests/source edits. Record failing threshold regressions,
apply the bounded repair, kill/restore both mutations, then collect a complete
manual tool-enabled Opus/Gemini/Astra/Sol code round before fixes (maximum three
substantive rounds). Serialize original full runners and accepted-main merges.
Require matching-source Windows focused/standing checks and exact hosted CI.
The existing Linux native fixture may skip explicitly on Windows; all new
threshold cases must execute. Publish through the supported adapter. Separate
treesitter-chunker#133 and treesitter-chunker#149 remain outside this repair.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_grammar_compatibility_contract.py tests/test_grammar_compatibility_cleanup_contract.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py

## Acceptance criteria

- [ ] EC-COMPAT-1 threshold subset: focused actual parsing/checker tests prove
  existing strict boundaries, moderate/very-slow scores and warning observations,
  with timing-stage validation precedence and actual sample-failure observations.
- [ ] Both named actual production mutations fail intended contracts; each exact
  restoration passes the focused batch without time-budget correctness gates.
- [ ] Valid original six checks/refresh/full tests/spec_tests, matching-source
  Windows, exact hosted platforms and bounded manual review support this repair
  only. No native/pin/consumer-lock or whole COMPAT/IF acceptance.

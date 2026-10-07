---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Normalize diagnostic locations without changing messages

## Task and research

Resolve treesitter-chunker#431 after accepted treesitter-chunker#430. The
existing _signature applies numeric-colon substitutions and backslash changes
to the entire complete mypy diagnostic, so distinct Literal values can become
the same debt signature. Real checker reproduction is preserved in
/tmp/chunker-426-literal-normalization-repro.json. Own execution evidence is
allowlisted at /tmp/chunker-431-*.

## Changes

- scripts/mypy_gate.py: match only the leading file/line/optional-column
  location before the error message. Remove its coordinates and normalize
  separators only in the captured path. Preserve the complete error message
  and code byte-for-byte; retain outer line stripping. Unmatched input retains
  its stripped original text. Keep checker options, failure/stderr boundaries,
  baseline comparison and intentional update semantics unchanged.
- tests/test_mypy_gate.py: add two actual external-mypy fixture contracts for
  colon-number literals and escaped-backslash versus slash literals. Seed each
  private baseline using its original actual diagnostic, accept unchanged
  messages and unrelated line shifts, reject the changed literal message and
  retain baseline bytes. Require complete messages and assignment code. Use
  real private fixtures/config/checker cache, not mocked checker execution or
  signature logic. Existing actual wrapped-message and boundary tests remain.
  Assert coordinate/optional-column/path separator normalization against
  location variants of the real captured diagnostic, while preserving its
  message. Force width80 in the checker fixture environment for deterministic
  mutation checks, including the existing wrapped-message preconditions.
- docs/development/mypy-baseline.txt: if normalization changes its format,
  migrate only the complete diagnostics captured on unchanged accepted
  e131493a before implementation. Preserve old gate pass, raw errors, old/new
  signatures, digests and reconciliation. If bytes remain identical, leave the
  file unchanged and record that evidence. Never update from candidate errors.
- CONTRIBUTING.md and CHANGELOG.md: document location-only normalization and
  preserved literal message values; no universal checker completeness claim.
- This plan and its typed plans/manifest.json lifecycle row are owned paths.
  The existing platform selection already runs all tests/test_mypy_gate.py.

## Dependencies and order

Register and commit the plan before tests/code. Capture the unchanged accepted
base's original gate output and raw complete checker diagnostics first, then
derive proposed signatures in a separate evidence script without modifying
the gate. Write the two actual regressions and record their failure before
repairing _signature. Apply only a justified unchanged-base format migration.
The named mutation normalize_message_body restores the original global
substitution: both new literal tests must fail, then exact restoration must
pass and bind source/test hashes. Preserve all failed diagnostic attempts.
Collect four manual tool-enabled reviews, maximum three substantive rounds.

## Documentation impact

Contributor guidance explains the meaningful message boundary. This is a
quality-gate repair; runtime chunking, public commands and parser pins remain.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_mypy_gate.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py

Original six/locked refresh/full tests/spec_tests, matching-source Windows
focused/standing checks, exact hosted jobs and bounded review remain required.
No coverage-percentage gate, pin, native, consumer-lock or broker-state change.

## Acceptance criteria

- [ ] Actual changed colon/backslash Literal diagnostics cannot reuse old debt;
  real gate tests reject them without changing private baselines. Unrelated
  line/column shifts and path separator changes preserve matching diagnostics,
  while literal message bytes and assignment codes remain intact.
- [ ] Any baseline format migration comes only from measured unchanged accepted
  source, with old gate pass/raw output/digest reconciliation. The named global
  message-body mutation fails both new tests and restoration passes.
- [ ] Original checks, locked refresh/full tests/spec_tests, matching-source
  Windows, hosted jobs and four bounded reviewers accept only this quality work.
  No product typing repair or candidate debt is silently admitted.

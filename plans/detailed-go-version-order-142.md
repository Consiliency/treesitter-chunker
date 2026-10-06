---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_go_version_hints_contract.py -q"
---

# Detailed plan: Order detected Go build versions numerically

## Task and research

Resolve treesitter-chunker#142, the Go numeric-order subset of EC-COMPAT-2.
GoVersionDetector.detect_from_build_constraints uses string max for both
modern and legacy positive constraints. Separate lines requiring1.9 and1.10
incorrectly select1.9. Existing tests parse the checked-in Go service fixture
and verify module-over-source precedence through the public detection API.

## Changes

- chunker/languages/version_detection/go_detector.py: compare the captured
  major/minor components numerically when selecting the highest detected
  positive version in each of the two existing branches. Preserve returned
  strings and modern-over-legacy branch priority. Do not introduce Boolean
  expression evaluation, negated-constraint semantics or Go language support.
- tests/test_go_version_hints_contract.py: parameterize modern/legacy separate
  constraint lines and both orders across1.9/1.10 and1.99/2.0. Prefix the actual
  checked-in Go service source, parse it using the real installed Go parser,
  write/read a private source fixture and verify detector/primary results.
  Retain the existing go.mod precedence/export control. No mocks or timings.
- CHANGELOG.md: describe numeric comparison for detected Go build-version hints.
- This plan and its typed plans/manifest.json entry are owned control paths.

## Dependencies and order

Independent detector slice; no compatibility DB/native ownership. Register
before tests or source edits. Reproduce, make the minimal numeric fix, kill and
restore lexicographic_build_version_max in both branches. Use an isolated
private worktree, supported publication, original runner and exact hosted CI.
Maximum three substantive manual tool-enabled review rounds. No silent repair
of separately discovered defects or whole COMPAT/IF claim.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_go_version_hints_contract.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py

Record mutation failure and exact restoration hashes. Actual Windows focused
checks/standing preflight and hosted Linux/macOS/Windows remain required;
external panel records supplement the runner without formal IF acceptance.

## Acceptance criteria

- [ ] EC-COMPAT-2 Go subset: both positive constraint formats select1.10 over1.9
  and2.0 over1.99 regardless of line order, using real parsed source fixtures.
- [ ] Existing module-over-source precedence remains; restoring string max in
  the named actual production mutation fails numeric-order cases and restores.
- [ ] Original six checks, locked refresh/full tests/spec_tests, Windows, exact
  hosted checks and bounded manual reviews accept this detector-only contract.

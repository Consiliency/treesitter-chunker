---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_grammar_compatibility_contract.py -q"
---

# Detailed plan: Preserve findings without a positive timing baseline

## Task and research

Resolve treesitter-chunker#345 as the arithmetic portion of EC-COMPAT-1.
CompatibilityChecker.detect_breaking_changes appends incompatibility findings,
then divides by an old average_parse_time of zero. Its outer exception handler
discards those findings and returns analysis_error. Existing tests already store
results derived from real fixture parses and reopen the actual SQLite database.

## Changes

- chunker/grammar_management/compatibility.py: in detect_breaking_changes,
  treat missing/None average timing as unavailable (zero); calculate a percentage
  regression only with a positive old timing baseline. Retain the existing 50%
  threshold when a positive baseline is available. Preserve independently found
  incompatibility and parse-success/structure regressions; do not fabricate a
  numerical percentage or a performance finding without that baseline.
- tests/test_grammar_compatibility_contract.py: parse the checked-in Python
  service fixture and actual malformed Python source with the real parser.
  Persist results derived from those outcomes, with legacy timing records at
  zero, missing, None and negative baseline; reopen SQLite through a new actual
  checker. Require incompatibility and success regression findings without
  analysis_error or a fabricated performance percentage. Existing positive
  0.02->0.04 test must retain its 100% regression. No production/parser/DB mocks.
- docs/grammar_management.md and CHANGELOG.md: explain that percentage timing
  comparisons require a positive available baseline, while independent findings
  remain. This plan and its own typed manifest entry are control paths.

## Dependencies and order

Accepted treesitter-chunker#394 connection-lifetime and treesitter-chunker#401
helper-cache propagation are incorporated. Register before source changes,
reproduce the real persisted-result failure, fix the arithmetic, then kill and
restore divide_without_positive_baseline. Serialize shared compatibility source
ownership and mutation runs. Integrate final accepted main before the original
full runner; publication is through the supported adapter. Maximum three manual
tool-enabled substantive review rounds. No native admission, DB migration,
duplicate/NULL history repair (treesitter-chunker#135), pin or consumer lock edits.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_grammar_compatibility_contract.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --all-extras pytest -q

Restoring unconditional ratio calculation must fail the zero-baseline real DB
case and restoring bytes must pass the whole focused module. Changed-source
Windows and hosted Linux/macOS/Windows are required; external panel/platform
records supplement the original runner without formal IF acceptance.

## Acceptance criteria

- [ ] Zero/unavailable/nonpositive old timing does not erase real independent
  incompatibility and parse-success regressions or claim a numerical slowdown.
- [ ] The existing positive-baseline real fixture case retains its expected
  performance finding, and the named mutant fails then fully restores.
- [ ] Original runner, Windows, exact hosted checks and bounded reviewers accept
  the focused arithmetic change with accurate docs and no whole COMPAT claim.

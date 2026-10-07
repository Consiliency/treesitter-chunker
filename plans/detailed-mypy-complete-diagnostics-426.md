---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Compare complete type diagnostics

## Task and research

Resolve treesitter-chunker#426. Existing pyproject pretty output wraps mypy
messages, but scripts/mypy_gate.py retains only header lines containing error:.
The committed baseline consequently contains truncated messages such as
Incompatible or Argument. Distinct new errors can inherit an existing prefix.
Read access to own evidence is allowlisted at /tmp/chunker-426-*.

## Changes

- scripts/mypy_gate.py: request non-pretty output and explicit error codes from
  the actual checker, retaining complete one-line diagnostic messages. Keep
  current-interpreter launch, checker failure/stderr rejection, path/line
  normalization and ordinary baseline-relative exit behavior.
- docs/development/mypy-baseline.txt: deliberately migrate the baseline format
  using complete real diagnostics measured on this unchanged accepted base
  before implementation edits. Preserve raw old/complete output, base commit,
  baseline digest and counts. Validate the old gate passes on that base, explain
  the expanded distinct-signature count and cleared old debt. Never regenerate
  from the changed candidate or admit candidate type errors silently.
- tests/test_mypy_gate.py: add actual mypy-process contracts on a valid Python
  fixture with deliberately long expected type names and forced pretty wrapping.
  Prove different complete messages sharing the same old header prefix fail
  against the first baseline, and unrelated line shifts pass. Assert error
  codes survive and a rejected candidate leaves the baseline bytes unchanged.
  Configure the external checker target and private baseline at the boundary;
  do not mock checker subprocesses or the gate functions in these new tests.
  Existing crash/stderr checks remain intact.
- scripts/run_platform_core.py: add the actual gate contracts to the common
  platform selection, retaining every accepted main selection.
- CONTRIBUTING.md: explain complete-message/code comparison and intentional
  baseline format migration from unchanged accepted code; no blanket update.
- CHANGELOG.md: document the improved quality gate without changing runtime.
- This plan and its typed plans/manifest.json row are owned control paths.

## Dependencies and order

Register this plan before tests/code. Measure and preserve the actual unchanged
accepted-base checker outputs before implementation, then verify an executable
regression with real wrapped output. Add non-pretty/coded output and migrate
only that base's measured diagnostics. Kill truncate_pretty_diagnostics by
restoring pretty output; the real distinct-message tests must fail, then exact
restoration must pass and record source/test hashes. Separately file any newly
exposed product defects. Four manual reviews, maximum three substantive rounds.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_mypy_gate.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py

Original six checks, locked refresh/full tests plus spec_tests, real Windows
focused/standing checks and exact hosted jobs are required before closeout.
Record intentional migration separately from later candidate checks. No
coverage percentage gate or implementation-output count assertion.

## Acceptance criteria

- [ ] Actual complete messages/error codes distinguish a new diagnostic from
  existing debt even when their pretty first lines match; rejection retains
  the baseline. Line/path normalization remains independent of source lines.
- [ ] Baseline migration comes solely from measured unchanged accepted code,
  with old gate pass and raw-output/digest reconciliation. The named pretty
  mutation fails the new real-checker contract; exact restoration passes.
- [ ] Original six/refresh/full tests/spec_tests, matching-source Windows,
  hosted gates and bounded reviews accept this quality-only slice. No hidden
  product fixes, parser pins, native admission, consumer lock or full GATES/IF.

---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Separate large-file correctness from controlled timing

## Task and research

Resolve treesitter-chunker#195, the large-file subset of EC-GATES-1/2.
The existing test already parses and JSON-exports 5000 real Python functions in
an isolated child. Its chunk-time assertion can still stop later checks.
Fresh main d56cdf62 measurements found normal chunking0.30-0.52seconds and
explicit covered chunking5.65-10.03seconds; all5000 chunk identities and JSON
exports survive. Initial measurements had high host CPU use; these are
diagnostic, not certified benchmark results. Actual covered pytest passed once.

Read access to owned diagnostic artifacts is allowlisted at
/home/viperjuice/workspace/evidence/treesitter-chunker/large-file-profile-195/d56cdf62/**
and /tmp/chunker-195-*. Raw measurement/history remain unchanged.

## Changes

- tests/test_performance_advanced.py: retain the existing isolated5000-function
  source, actual chunk_file/JSONExporter calls and measured post-chunk RSS.
  Independently read the actual exported JSON; require every generated function
  content in order,5000 distinct nonempty IDs, correct kinds and file attribution.
  Check the existing500MiB RSS limit and complete export before any timing gate.
  Record all measured values for diagnostics. Default correctness does not fail
  solely for chunk/export wall time. CHUNKER_CONTROLLED_PERFORMANCE=1 explicitly
  enables the unchanged10second chunking/five-second export limits, evaluating
  both before reporting failure. This is a development-test option, not an API.
- scripts/run_platform_core.py: select this real large-file correctness contract
  on all hosted platforms, without opting shared CI into controlled wall time.
- docs/performance-guide.md: distinguish default correctness/resource checking
  from the explicit noninstrumented controlled command; preserve historical
  limits, require prefetched grammars and quiet host conditions, and describe
  post-chunk RSS truthfully rather than peak memory.
- CHANGELOG.md: document the test-gate separation without a speed guarantee.
- This plan and its typed plans/manifest.json entry are owned control paths.
- Temporary verification only: actual JSONExporter.export in
  chunker/export/json_export.py is allowlisted for two killed/restored mutations;
  no permanent production change is allowed.

## Documentation impact

Performance guide names the exact development command and retained budgets.
README, AGENTS, CLI options, runtime behavior and consumer requirements remain.

## Dependencies and order

Independent test repair after measurement; no parser/analyzer deadline repair.
Register before source/test edits. Verify baseline and new functional assertions.
Kill truncate_large_json_export by omitting the last actual exported chunk.
Kill delay_real_json_export using an actual5.05second delay in the exporter:
default correctness must still pass and controlled timing must fail the export
budget, then exact restoration must pass both modes. Real parsing/exporting
remain active; no parser/exporter/time mocks. Record source/test hashes.
Use private worktree and at most three substantive manual code-review rounds.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_performance_advanced.py::TestScalabilityLimits::test_very_large_file_handling -q
- CHUNKER_CONTROLLED_PERFORMANCE=1 uv run --locked --all-extras pytest tests/test_performance_advanced.py::TestScalabilityLimits::test_very_large_file_handling --no-cov -q -s
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py

The original runner includes the controlled command as a seventh machine-checked
command in addition to the usual six, then locked refresh and full tests/spec_tests.
Windows focused/standing checks and all exact-head hosted jobs are required.
Controlled evidence is recorded with its command, host conditions and coverage
disabled; it does not certify throughput on every host. No coverage percentage
or plan-output pin. File separate product defects instead of fixing them here.

## Acceptance criteria

- [ ] EC-GATES-1 large-file subset: real5000-function parsing preserves all
  contents/IDs/kinds/attribution in actual JSON and checks existing RSS budget
  before timing; default remains correct under real export delay. Focused test
  and truncate_large_json_export establish observable outcomes.
- [ ] EC-GATES-2 large-file subset: explicit controlled command preserves both
  original wall-time limits; delay_real_json_export fails its export limit.
  Exact restoration passes both modes and recorded hashes match final bytes.
- [ ] Seven original checks, locked refresh/full tests/spec_tests, actual
  Windows and exact hosted jobs plus bounded manual review accept this slice.
  No native, parser pin, consumer lock or whole GATES/IF acceptance.

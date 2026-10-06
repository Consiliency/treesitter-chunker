---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_config_advanced_scenarios.py -q"
---

# Detailed plan: Replace a simulated configuration timing gate

## Task

Resolve treesitter-chunker#397 independently of treesitter-chunker#396. Two
Python 3.11 hosted runs fail the unchanged synthetic parser's 50 ms overhead
gate. This supplies one bounded GATES correctness repair; it does not establish
a performance budget or complete EC-RUNTIME-2/EC-GATES acceptance.

## Research summary

The failing test implements its own MockParser and dotted-dictionary lookup,
then asserts scheduler-sensitive timing. It never invokes production parsing
or configuration. ChunkerConfig loads actual per-language/default settings and
returns disabled settings for excluded languages; PluginManager.chunk_file
accepts those settings explicitly. The checked-in Python service fixture has
both class and function definitions. The existing platform selection already
includes this test module on every platform.

## Changes

- tests/test_config_advanced_scenarios.py: replace only the failing simulated
  parser/timing test with actual temporary JSON configuration loading, repeated
  production configuration lookups and real PluginManager parsing of the checked-in
  service fixture. Assert a Python function-only override, class-only default,
  disabled-language selection, stable values after repeated lookups and nonempty
  source-matching output. Rename the replaced test to describe this contract.
  Leave unrelated existing tests and production code unchanged.
- This detailed plan and its own typed plans/manifest.json entry are owned.

## Documentation impact

No product surface changes. No timing/performance guarantee is introduced or
claimed; the acceptance record explains retirement of the synthetic gate.

## Dependencies and order

Start from current main. Register the plan before test edits. Keep this repair
in its own PR and merge it before integrating its accepted history into
treesitter-chunker#396 and the helper-cache repair. No repeated failed-job retry
until the test change is accepted. Do not change thresholds, parser pins,
consumer locks or admitted ledgers/checkpoints. Cap manual substantive review
at three rounds; tools remain enabled with compact file pointers.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_config_advanced_scenarios.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --all-extras pytest -q

Named mutation return_default_plugin_config makes the production per-language
lookup return its default even when a Python override exists. The new real
configuration/parse assertions must fail; restore production bytes exactly and
require the entire focused module to pass. Require the original sealed runner,
exact-head hosted Linux/macOS/Windows and manual tool-enabled code review.
The standing Windows preflight applies; its availability is reported honestly.

## Acceptance criteria

- [ ] Actual JSON-backed production lookups retain overrides, defaults and
  disabled-language settings across repeated lookups, proven by the new test.
- [ ] Actual parsing of the checked-in fixture produces the selected function
  or class definitions, nonempty exact source content and no disabled chunks;
  no simulated parser or timing threshold is used in this replacement test.
- [ ] The named production-lookup mutation fails and restores; original runner,
  exact-head hosted platforms and bounded manual code review accept the repair.

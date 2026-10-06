---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_config_advanced_scenarios.py tests/test_config.py -q"
---

# Detailed plan: Verify concurrent configuration reads with real parsing

## Task and research summary

Resolve treesitter-chunker#200 as an independently landable EC-GATES-1 subset.
The existing contention test implements its own RLock-backed fake config store,
simulates parsing with sleeps, and fails on absolute wait/scaling thresholds.
Two unchanged-head macOS failures are recorded on the issue. Its result/error
queues and total access counts are never asserted. The adjacent real lookup
test already uses ChunkerConfig, PluginManager/PythonPlugin and service.py.
Production ChunkerConfig has no contention counter or concurrent-write contract.

## Changes

- tests/test_config_advanced_scenarios.py: replace only the simulated contention
  test with parameterized 1/2/4/8/16-thread actual config reads and real parsing.
  Load private JSON once with environment overrides disabled, share the actual
  config and registered plugin manager, and synchronize worker start with a
  Barrier. Each worker repeatedly observes the Python override, default Rust
  settings and disabled JavaScript; parse the checked-in Python service with
  actual selected function and class configurations. Every expected worker
  result and iteration must exist and match actual fixture content, types and
  counts. Future exceptions propagate; no error queue can hide them. The
  generous barrier timeout diagnoses readiness failure. Completion timeouts
  are not a termination guarantee: executor shutdown can still wait on a hung
  worker, with the original runner/CI providing the outer process bound. No
  performance threshold or lock-contention measurement. Remove the unused
  queue import. No mock
  config store, parser, plugin or timing instrumentation.
- Temporarily mutate the existing ChunkerConfig.get_plugin_config return in
  chunker/chunker_config.py to ignore_language_override. The concurrent fixture
  cases must fail; restore exact production bytes and pass the focused batch.
  This file has no permanent change. The old test's synthetic contention/count
  observations are retired, not represented as actual product instrumentation.
- CONTRIBUTING.md and CHANGELOG.md: record that concurrent configuration quality
  checks use real fixture results; wall-clock observations are not correctness
  gates. No production latency/scaling guarantee or new release blocker.
- This plan and its typed plans/manifest.json row are owned control paths.

## Documentation impact

Verification guidance changes; public config/CLI/runtime behavior is unchanged.
The contract covers concurrent reads of a preloaded configuration, not reload
or concurrent writes. Other simulated cache tests remain outside this repair.

## Dependencies and order

Register the plan before tests/mutations. Use the locked environment. Retain
historical failure evidence, run the unchanged narrow test, then real fixture
tests and the named mutation. Integrate accepted main before the original full
runner. Maximum three substantive manual tool-enabled code review rounds;
collect a whole round before fixes. Require actual changed Windows/preflight,
documented Linux platform-core/full tier and all exact-head hosted platforms.
External reviews/platform records are supplementary, without phase IF claims.
Publish through the supported adapter. No parser pins, native admission,
consumer locks, ledgers, checkpoints or broad configuration refactor.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_config_advanced_scenarios.py tests/test_config.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py

## Acceptance criteria

- [ ] EC-GATES-1 concurrent-read subset: actual worker results preserve every
  override/default/disabled observation and nonempty parsed fixture result for
  every thread count. Proven by the focused batch; no whole GATES acceptance.
- [ ] ignore_language_override fails the concurrent cases, restored production
  bytes pass the full focused batch, and correctness has no speed/wait ratio gate.
- [ ] Original checks/full tier, actual Windows and exact hosted platforms plus
  bounded independent reviews support the test repair and accurate guidance.

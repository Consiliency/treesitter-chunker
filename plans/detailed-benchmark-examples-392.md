---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_benchmark_examples.py -q"
---

# Detailed plan: Make legacy cache examples executable and truthful

## Task and research summary

Resolve treesitter-chunker#392 independently of accepted treesitter-chunker#379.
Both example modules import an unexported parallel-directory helper from chunker,
then pass obsolete use_cache keywords to direct chunk_file. Neither direct call
queries or populates SQLite. The comprehensive cache example also clears the
global cache. Existing supported ASTCache methods permit explicit isolated
lookup/store behavior without changing the production cache or its identity.

## Changes

- benchmarks/comprehensive_suite.py and benchmarks/example_benchmark.py:
  import chunk_directory_parallel from chunker.parallel. Retain other supported
  exports; remove the obsolete keyword only within the declared cache examples.
- ComprehensiveBenchmarkSuite._benchmark_cache: use a private disposable cache
  by default, with context['cache_dir'] as an optional explicit root. Clear only
  the selected input before each cold iteration, query actual SQLite, parse with
  supported chunk_file, and populate it. Warm iterations use actual lookups,
  recording misses/hits and chunk counts rather than assuming a hit. Existing
  modified-input phase queries file-hash/mtime validation, reparses/stores on
  misses and reports observed counts. Preserve timings as observations, no
  speed or percentage gate and no global invalidation. Existing scenario input
  modification remains; caller inputs must be disposable copies.
- demo_cached_chunking: retain no-argument usage, accept optional test_file and
  cache_dir for real consumer fixtures, use an isolated disposable cache by
  default, explicit cold parse/store and actual warm lookup. Return observed
  chunk/hit/file counts while retaining informational console timings. Clean
  only generated demo inputs; caller fixture/root are not removed.
- tests/test_benchmark_examples.py: import both actual modules, copy and parse
  checked-in Python service fixture, then run both real cache paths without
  production/parser/file/cache mocks. Inspect reopened SQLite chunk equality,
  content-hash identity and actual reported counts. A second real input entry
  in the supplied private cache must survive the comprehensive cold loops.
  Private HOME/USERPROFILE must acquire no default cache. Default demo and
  comprehensive roots are disposable, explicit roots remain reopenable.
- Kill import_unexported_parallel_helper and omit_example_cache_population,
  the latter separately in both modules. Intended tests must fail; restore exact
  bytes and pass the focused batch after each mutation.
- scripts/run_platform_core.py: select the new module on all hosted platforms
  after accepted treesitter-chunker#342 to preserve its shared runner changes.
- docs/performance-guide.md and CHANGELOG.md: describe explicit isolated example
  cache hits/misses, disposable inputs and informational timings. This plan and
  typed plans/manifest.json are owned control paths.

## Documentation impact

Examples now run supported APIs and return actual observations. Production
cache identity remains treesitter-chunker#358; no speedup promise or default
parallel cache policy is changed.

## Dependencies and order

Register before edits; reproduce both real imports. Execute the independent
example/tests first. Serialize shared platform runner modification after
treesitter-chunker#342 merges, then integrate accepted main and run all original
gates. Require actual Windows focused/preflight and exact hosted platforms.
Four manual tool-enabled reviewers, maximum three substantive rounds, collect
each complete round before fixes. External records supplement original gates
without IF claims. Supported publication only; no pins/native/consumer locks or
broker state edits. File independent defects rather than silently expanding.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_benchmark_examples.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py

## Acceptance criteria

- [ ] EC-GATES-2 example subset: both actual modules import and execute the cache
  examples on real fixture copies using supported APIs; proven by focused tests.
- [ ] Cold/warm/modified counts reflect actual isolated SQLite observations,
  nonempty fixture output and unchanged unrelated entries; named mutations fail
  and exact restoration passes. No performance correctness gate.
- [ ] Original six checks/full tier, Windows, hosted platforms and bounded
  reviews support the examples and their consumer guidance; no whole-phase claim.

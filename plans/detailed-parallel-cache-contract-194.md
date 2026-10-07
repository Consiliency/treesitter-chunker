---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_parallel.py::TestWorkerPoolSizing::test_io_bound_sizing -q"
---

# Detailed plan: Verify parallel cache reuse without a one-second gate

## Task and research

Resolve treesitter-chunker#194, the cached parallel portion of EC-GATES-2.
The current full suite on treesitter-chunker#413 returned equal result counts
but failed cached_duration<1.0 at1.0749 seconds. This is the same previously
reproduced load-sensitive bound, not a database-upsert regression. ParallelChunker
uses a real ASTCache instance on its cache attribute and returns cached CodeChunks
before parsing. Existing tests already replace that attribute with private SQLite.

## Changes

- tests/test_parallel.py: replace only TestWorkerPoolSizing.test_io_bound_sizing
  with a bounded real-fixture cache contract using two copies of checked-in
  Python service source and explicit small worker counts. Construct with cache
  disabled to avoid touching the home cache, then assign actual private ASTCache
  and enable caching. Cold results must equal eager actual parsing and persisted
  reopened SQLite chunks. Add an annotation to copies of actual parsed chunk
  metadata and store them through the real cache API. Warm multiprocessing must
  return these exact annotated payloads, proving actual cache reuse rather than
  just equal counts. Preserve source bytes/spans and all unannotated fields.
  No mocks of parsers/workers/cache, or one-second/throughput assertion.
- scripts/run_platform_core.py: select this focused contract on all platforms.
- CONTRIBUTING.md and CHANGELOG.md: distinguish cached result correctness from
  controlled informational performance measurements. Do not change other timing
  tests or production cache identity/worker behavior.
- This plan and its typed plans/manifest.json entry are owned control paths.

## Dependencies and order

Accepted treesitter-chunker#342 supplies the shared runner baseline. Register
before test edits. Existing exact-head failure is the unchanged reproducer;
preserve its complete original runner as excluded acceptance evidence. Implement
the test-only contract, kill/restore bypass_parallel_cache_lookup on actual
production source temporarily, then require actual Windows and original six
checks/full tests/spec_tests plus hosted platforms and four manual tool-enabled
reviews. Maximum three substantive rounds. Source permanently unchanged.
After acceptance, integrate into pending candidates and rerun their originally
specified checks; never reuse a failed full-suite verdict or rewrite its seal.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_parallel.py::TestWorkerPoolSizing::test_io_bound_sizing -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py

The actual lookup-bypass mutation must lose the cached annotation and fail the
intended warm assertion; restore exact source bytes and pass the focused batch.
Windows focused/standing checks must run the real multiprocessing/SQLite path.
No performance, native, cache identity or whole GATES/IF acceptance claim.

## Acceptance criteria

- [ ] EC-GATES-2 parallel-cache subset: real cold parsing persists exact chunks;
  actual warm multiprocessing returns distinguishable cached metadata intact.
- [ ] Private cache/input isolation and the lookup-bypass mutation prove reuse
  without mocks or wall-clock correctness limits; exact restoration passes.
- [ ] Original six checks/refresh/full tests/spec_tests, actual Windows, hosted
  exact-head checks and bounded manual reviews support this test-only repair.

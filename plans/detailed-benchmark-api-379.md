---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_streaming.py -q"
---

# Detailed plan: Run truthful benchmarks through current APIs

## Task

Resolve treesitter-chunker#379. Published 5.2.0 remains usable; benchmark timing is
informational, not a correctness or release threshold.

## Research summary

PerformanceBenchmark passes the removed use_cache keyword to sequential
chunk_file calls. Parallel calls still support that option. Its cached benchmark
creates ASTCache but never explicitly populates or reads it for chunking, although
the guide correctly states chunk_file does not consult SQLite automatically.

## Changes

- benchmarks/benchmark.py: remove the obsolete keyword only from sequential
  parsing. Inside benchmark_cached_chunking, use real get_cached_chunks,
  chunk_file and cache_chunks operations for cold and warm passes. Count a cache
  hit only when the measured operation actually returns cached chunks. Preserve
  result names, supported parallel flags and logical file/chunk counts.
- tests/test_streaming.py: exercise the actual run_all_benchmarks entrypoint
  on two distinct paths containing a real checked-in Python fixture. Assert
  nonempty eager references, seven real benchmark results, truthful per-result
  counts and actual SQLite contents/hits. Isolate Path.home only while creating
  the benchmark cache; restore it before real parser/process-pool execution.
  Do not mock production parsing, cache or parallel methods.
- docs/performance-guide.md and CHANGELOG.md: document explicit cached benchmark
  work, real hit observations and the limits of informational timings. This plan
  and its typed plans/manifest.json entry are owned controls.
- scripts/run_platform_core.py: include the full-entrypoint real-fixture test in
  the shared Linux/macOS/Windows selection.

## Dependencies and order

Use current main. Register the plan before edits, reproduce the full-run failure,
repair sequential/cache operations and verify. Keep grammar/runtime/extraction
cache-identity debt in treesitter-chunker#358 and native/cache transaction holds
separate. Do not introduce a public cache option or change consumer locks/pins.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_streaming.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ benchmarks/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/ benchmarks/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --all-extras pytest -q

Kill obsolete_sequential_cache_keyword by restoring the removed basic-call
keyword; the actual full runner test must fail with its TypeError. Kill
skip_benchmark_cache_population by removing the real write; hit/content assertions
must fail. Restore and rerun the streaming module after each. Require changed-source
Windows full-entrypoint test, exact-head hosted platforms and manual tool-enabled
code review before merge. No timing or coverage-percentage threshold.

## Acceptance criteria

- [ ] The actual full entrypoint completes seven benchmarks on real fixtures;
  all nonempty counts match their logical file and chunk observations.
- [ ] Cached passes use real SQLite records and measured hit flags; no fabricated
  hits or speedup guarantee. Both named mutations fail and restore.
- [ ] Original runner checks, changed-source/hosted platforms and code review
  accept; docs preserve the distinction between streaming and core extraction.

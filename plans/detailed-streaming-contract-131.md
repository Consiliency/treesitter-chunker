# Detailed plan: Correctness gate for repeated streaming

## Task

Resolve treesitter-chunker#131 independently of native admission and the held
cache transaction. The latest full suite for treesitter-chunker#373 reproduced
the unchanged absolute timing-variance failure (0.06035 against 0.05). Timing
observations belong in the existing benchmark, not a shared-host correctness gate.
This small repair produces no whole-phase GATES acceptance.

## Changes

Owned paths: tests/test_streaming.py, benchmarks/benchmark.py,
docs/performance-guide.md, scripts/run_platform_core.py, CHANGELOG.md, this plan
and plans/manifest.json.

- Replace only the variance assertion with a repeated-output contract using
  the checked-in Python service.py fixture. Parse with the real parser, require
  nonempty eager reference chunks, and compare ordered streaming content,
  node types and line bounds over fresh repeated calls. No timing threshold,
  mock streamer, percentage gate or wider performance-test rewrite.
- Record repeated streaming timings and their variance as informational
  metadata in the existing streaming benchmark. Keep logical file/chunk counts;
  duration sums the per-file means for one logical pass. No CI pass/fail threshold.
- Coupled prerequisite treesitter-chunker#377 was reproduced separately: this
  existing benchmark imports removed chunker.cache. Use the current exported
  ASTCache and preserve the existing chunker.parallel helper import so
  the timing observation can actually run. No other benchmark repair is owned.
- Document that distinction in the existing performance guide/changelog.
- Include the focused repeated-output contract in the platform-core selection
  so the changed behavior runs on Linux, macOS and Windows.
- Kill drop_streamed_chunks at the production streaming yield. The new test
  must reject missing output relative to eager parsing. Restore and rerun.
- File additional timing defects separately; do not change unrelated tests.

## Verification

- uv sync --locked --all-extras
- Locked targeted repeated-output test, then the existing streaming suite.
- Exercise the actual benchmark on the same checked-in fixture; inspect
  recorded samples and variance without asserting a performance target.
- Ruff/Black/mypy baseline, CI smoke, full suite and strict temporary-site docs.
- Standing Windows main preflight; changed-head Linux/macOS/Windows checks.
- Manual tool-enabled Opus 5.5 TUI/Gemini 3.8 Flash/Astra/Sol review, at most
  three substantive rounds, reconcile blockers before merge.

## Acceptance criteria

Repeated streaming preserves the eager fixture's ordered content/type/line
contracts and rejects dropped chunks under the named mutation. Timing variance
is reported in benchmark metadata and cannot fail correctness CI. Required
verification and exact-head review pass; close treesitter-chunker#131 with
evidence after merge and prune the clean worktree.

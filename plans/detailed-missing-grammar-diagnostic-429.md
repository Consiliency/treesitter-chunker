---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Preserve actionable invalid-path validation diagnostics

## Task and research

Resolve treesitter-chunker#429 independently of the sample precedence repair.
GrammarValidator.validate_grammar currently computes a stat-based cache key
before _validate_basic can report a missing path. Missing paths consequently
return a generic OS error instead of the existing actionable message.
The existing basic validator already rejects directories before ABI checks;
the public entrypoint must reach that rejection before cache lookup as well.
Own execution evidence is allowlisted at /tmp/chunker-429-*.

## Changes

- chunker/grammar_management/core.py: before cache-key computation, route paths
  that are not regular files through the existing _validate_basic rejection.
  Preserve the caller's requested level on the returned invalid result. Return
  before reading or writing an invalid-path cache entry. Retain existing cache
  keys, freshness, validation dispatch and native behavior for regular files.
- tests/test_public_grammar_validator.py: exercise actual missing paths and
  actual directories at all three validation levels through the public API.
  Parse the checked-in Python service fixture using the real installed parser
  as a control. Assert exact existing actionable path message, invalidity,
  requested level, empty metrics/metadata and no created validation cache.
  Existing actual regular-file parsing/cache replacement tests remain controls.
- docs/grammar_management.md: document invalid-path diagnostics and requested
  level preservation without claiming native admission or race protection.
- CHANGELOG.md: record the user-visible diagnostic repair.
- This plan and its typed plans/manifest.json lifecycle row are owned paths.

## Dependencies and order

Register and commit the plan before tests or code. Measure the six actual
invalid-path cases on unchanged accepted main before changing the entrypoint.
Then add the early rejection. The named mutation cache_key_before_path_check
restores a real cache-key stat before the guard: missing-path tests must fail,
and exact restoration must pass. Preserve raw logs and source/test hashes.
Collect four manual tool-enabled reviews before editing their findings, with
at most three substantive rounds. Integration retains canonical manifest rows.

## Documentation impact

The validation guide and changelog explain the improved diagnostics. No new
public API, cache format, source-loading policy or package pin is introduced.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_public_grammar_validator.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py

The original six checks, locked refresh, full tests/spec_tests, matching-source
Windows focused/standing verification and exact hosted jobs remain required.
No percentage or timing gate is added. No manually edited verification seal,
broker state, admitted branch, ledger, checkpoint or consumer lock is allowed.

## Acceptance criteria

- [ ] Real missing paths and directories yield their existing actionable
  messages, invalid results and requested levels across BASIC/STANDARD/EXTENSIVE;
  the focused actual-parser contracts prove this without mocking the validator.
- [ ] Invalid paths do not create cache records; regular-file parsing and cache
  replacement remain covered. The named cache-before-path mutation fails the
  missing-path contracts and exact restoration passes with final-byte binding.
- [ ] Original local checks, locked refresh/full tests/spec_tests, matching-source
  Windows, hosted jobs and bounded reviews accept only this diagnostic repair.
  Native admission, TOCTOU protection and writer coordination remain separate.

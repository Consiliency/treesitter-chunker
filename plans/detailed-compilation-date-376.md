# Detailed plan: Truthful legacy compilation metadata

## Task

Resolve treesitter-chunker#376 as an independently landable precursor to native
admission. File modification time is not authenticated compilation metadata.
This repair does not secure native loading or produce a SAFELOAD acceptance gate.

## Research summary

SmartGrammarManager.get_grammar_compatibility currently converts an artifact's
mtime into compilation_date. GrammarCompatibility already defaults that field
to None and accepts explicit caller-provided values. The existing manager tests
and grammar guide are the appropriate contract surfaces.

## Changes

Owned paths: chunker/_internal/grammar_management.py,
tests/test_grammar_management.py, scripts/run_platform_core.py,
docs/grammar_management.md, CHANGELOG.md,
this plan and plans/manifest.json.

- Remove the mtime-derived compilation_date block. Retain the existing optional
  field and explicit dataclass values; do not invent a replacement date source.
  Remove the now-unreachable date bonus from manager-derived scores.
- Add a real Python parser fixture contract: parse the checked-in service.py,
  copy the parser provider's actual compiled Python grammar into two isolated
  manager roots, vary only mtimes, require identical bytes and None dates.
  Each manager is fresh so its metadata cache cannot hide an invented date.
- Retain the existing explicit-date dataclass test. Document unknown dates and
  the absence of a timestamp bonus in compatibility scores.
- Select the focused real-artifact regression in the platform-core batch so
  Linux, macOS and Windows actually exercise this contract.
- Kill infer_compilation_date_from_mtime by restoring the removed block; the
  new contract must fail. Restore the repair and rerun the same test.
- File unrelated metadata or native defects separately.

## Documentation impact

The grammar guide and Unreleased changelog describe None when no authentic
compilation metadata exists. No parser pin, consumer lock or golden changes.

## Dependencies & order

Base is current main after treesitter-chunker#366 and treesitter-chunker#374.
Land independently before updating the native admission branch. No dependency
on the held cache transaction.

## Verification

- `uv sync --locked --all-extras`
- `uv run --locked --all-extras pytest tests/test_grammar_management.py -q`
- Named mutation and restored targeted contract.
- Repository Ruff, Black, mypy baseline, CI smoke and full suite.
- Strict MkDocs temporary-site build.
- Changed-head Linux/macOS/Windows matrix and standing Windows main preflight.
- Manual tool-enabled Opus 5.5 TUI, Gemini 3.8 Flash, Astra and Sol review;
  maximum three substantive rounds, collect all findings before fixing.
- Fresh runner-owned verification before acceptance.

## Acceptance criteria

- Identical actual parser artifacts at different mtimes never acquire a date;
  proven by the new real-fixture manager contract and killed named mutation.
- Explicit caller-provided dates remain intact, proven by existing dataclass tests.
- Required verification and review pass before merging and closing
  treesitter-chunker#376. No whole-phase acceptance is claimed.

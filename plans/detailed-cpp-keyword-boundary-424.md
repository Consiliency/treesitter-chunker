---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Keep constexpr keyword detection out of identifiers

## Task and research

Resolve treesitter-chunker#424 independently of C++ chronology in
treesitter-chunker#146. detect_cxx_standard's constexpr pattern currently matches
the suffix of __cpp_if_constexpr. That creates a false direct C++11 hint which
precedes the genuine C++17 feature-macro result. The real widget.cpp fixture
parses this reproducer successfully. Own evidence: /tmp/chunker-424-*.

## Changes

- chunker/languages/version_detection/cpp_detector.py: add the leading word
  boundary to the existing constexpr-plus-whitespace keyword pattern only.
  Preserve actual standalone constexpr and if constexpr detection, feature
  macro extraction/mapping and existing declared-standard priority. Do not
  broaden this into comment/string lexing or repair unrelated feature patterns.
- tests/test_cpp_version_hints_contract.py: parse the actual widget fixture
  prefixed with __cpp_if_constexpr's genuine preprocessor test; assert no false
  direct standard, macro C++17 and public primary C++17. Parse valid identifier
  controls ending in constexpr without manufacturing a C++11 hint. Parse real
  standalone constexpr declarations and if constexpr constructs, asserting
  genuine C++11/C++17 and retaining explicit C++20 priority over macro hints.
  Preserve every chronology test from treesitter-chunker#146. No mocked parser
  or detector, timing or coverage-percentage gate.
- CHANGELOG.md: describe identifier-safe constexpr matching, without claiming
  complete lexical or compiler-standard inference. Own plan and typed manifest
  entry are control paths; the whole test module is already platform-selected.

## Dependencies and order

Register this plan before test/source edits. Wait for treesitter-chunker#146
to merge, integrate accepted main, then write tests and record actual baseline
failure. Repair the single pattern. Named mutation constexpr_suffix_match
restores the missing leading boundary: the macro/identifier contracts must fail
and exact restoration pass with final source/test hashes. Four manual
tool-enabled reviewers, maximum three complete substantive rounds. Serialize
original full runners and use supported publication; no proxy acceptance.

## Documentation impact

Changelog only: existing inference becomes more precise; no new option or API.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_cpp_version_hints_contract.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py

Original six/locked refresh/full tests/spec_tests, actual matching-source Windows
and every exact hosted platform are mandatory merge gates. Preserve admitted
branches, broker, ledger, checkpoints, parser pins and consumer locks.

## Acceptance criteria

- [ ] Actual parsed macro/identifier fixtures do not invent direct C++11;
  feature-macro primary inference and genuine constexpr/if constexpr remain.
- [ ] Existing declared-standard and chronology contracts remain; real
  constexpr_suffix_match fails intended cases and exact restoration passes.
- [ ] Original/full, Windows, hosted and four bounded reviewer gates accept
  only this keyword-boundary change; no general lexical/native/IF claim.

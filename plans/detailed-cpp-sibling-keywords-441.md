---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Keep six C++ keyword hints out of identifiers

## Task and research

Resolve treesitter-chunker#441 as a separate small test-plus-code-review slice
after treesitter-chunker#440 resolves treesitter-chunker#424. The actual parser
reproduction in `/tmp/chunker-424-sibling-keyword-reproduction.json` shows that
six existing indicators match keyword fragments in identifiers. The originating
source is a6d998c4b8149a3c0e980b162e9d3ccb68d79ce2; these six patterns are unchanged
from accepted main. This is extracted-hint quality work, not compiler certification.

The existing `CppVersionDetector.detect_cxx_standard` indicator table and
`tests/test_cpp_version_hints_contract.py` provide the bounded implementation
and real parsed `tests/fixtures/boundary_ir/repos/cpp/widget.cpp` controls.
The adjacent constexpr correction and release chronology stay independently
accepted prerequisites. No new protocol vocabulary, API or export field is needed.

## Changes

- `chunker/languages/version_detection/cpp_detector.py`: modify only the six
  indicator patterns for nullptr, override, final, static_assert, concept and
  co_yield. Require complete keyword boundaries. Use `\bnullptr\b`,
  `\boverride\b`, `\bfinal\b`, `\bstatic_assert\s*\(`,
  `\bconcept\s+\w+\s*=` and `\bco_yield\b`. Existing whitespace/punctuation,
  inferred standards, chronological maximum, feature macros and primary-hint
  priority remain unchanged. Other indicators stay outside this slice.
- `tests/test_cpp_version_hints_contract.py`: extend the existing fixture tests,
  without mocking the parser or detector. Write each real snippet plus widget.cpp
  to a private file, parse through `get_parser("cpp")` without errors, then assert
  direct/public/primary hint fields. Include all six reproduced prefixes:
  is_final, my_override, my_nullptr, my_static_assert called as a function,
  my_co_yield and the my_concept alias. Assert no manufactured keyword hint;
  the alias control concerns false concept/C++20 recognition, not whether the
  alias itself uses another C++ feature. Add trailing-identifier controls for
  these names as valid C++ snippets. Add the reported controls with an explicit
  C++98 marker: fragment names must not promote that declared detector hint.
- In the same test module, independently exercise each genuine keyword in real
  parsed snippets: null pointer initialization; overriding a base virtual method;
  a final class; static_assert; a template concept definition; and a coroutine
  yield. Assert the existing C++11/C++20 hint and public primary result. Place
  each genuine token both after a newline and after ordinary same-line content
  so a mistaken beginning-of-line anchor is caught. Preserve the accepted
  chronology, feature-macro and constexpr/if-constexpr cases unchanged.
- `CHANGELOG.md`: document only that these six keyword fragments no longer
  manufacture hints. This plan and its typed `plans/manifest.json` row are owned.
  No guide update: the supported API and existing source-hint limits do not change.

## Dependencies and order

Commit this plan before source/test edits. Do not implement until
treesitter-chunker#440 is accepted and merged. Integrate its accepted main,
preserving every canonical manifest row, then mark only this row executing
through the supported typed lifecycle API before implementation.

First add the real regression/control cases and preserve actual failures on
the accepted unchanged patterns. Apply only the six specified boundaries.
The named mutation `keyword_fragment_matching` restores all six former patterns:
each of the six reproduced identifier families must fail. Independently run
`line_start_keywords`, replacing the six leading boundaries with beginning-of-line
anchors: each same-line genuine keyword control must fail. Exact restoration
must pass the full focused module after each mutation, with source/test hashes
captured before and verified after. This prevents fixing fragments by suppressing
genuine keywords. Do not use a coverage percentage or required total test count.

File any additional defects separately before considering their repair. In
particular, comment/string lexing, the other coroutine indicators, full C++
syntax/semantic inference and compiler validity are outside this contract.
Collect complete four-seat manual tool-enabled rounds before making changes;
maximum three substantive rounds. Opus5.5 uses the TUI adapter, Gemini3.8Flash
uses file tools, Astra and Sol complete the panel. The requested Astra president
adjudicates their actual outputs and completed evidence. Serialize supported
publication and original full runners; later machine checks cannot be waived
by a reviewer agreement. No admitted ledger/checkpoint/pin/consumer-lock edits.

## Verification

- `uv sync --locked --all-extras`
- `uv run --locked --all-extras pytest tests/test_cpp_version_hints_contract.py -q`
- `uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site`
- `uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/`
- `uv run --locked --all-extras python scripts/mypy_gate.py`
- `uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py`
- `uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux`
- `uv run --locked --with toml --all-extras python scripts/run_full_suite.py`

Preserve original six commands, locked refresh and full tests/spec_tests in the
sealed runner artifact. Run focused and standing Windows checks on the exact
source/test bytes and preserve platform head/digests. All exact-head hosted
Linux/macOS/Windows jobs, four final agreements and the manual chair ruling
remain mandatory. Archive raw evidence before qualified exact-head merge and
clean merged-worktree pruning. No whole SIGNATURES phase or IF gate is claimed.

## Acceptance criteria

- [ ] The focused command proves all six real parsed identifier families and
  trailing controls do not manufacture keyword hints, including beside an
  explicit C++98 marker. The actual `keyword_fragment_matching` mutation fails
  every reported family, and exact restoration passes the focused module.
- [ ] The focused command proves each genuine keyword still has its existing
  direct/public/primary hint at both placements; `line_start_keywords` fails
  every same-line family. Both restorations bind final source/test bytes; all
  accepted chronology, feature-macro and constexpr cases remain unchanged.
- [ ] Original six checks, locked refresh/full tests/spec_tests, matching-source
  Windows, exact hosted jobs, four bounded reviews and Astra chair accept only
  this source-hint contract. Newly found defects are separate issues, with no
  compiler/lexical completeness, native admission or whole-phase assertion.

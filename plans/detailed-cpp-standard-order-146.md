---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_cpp_version_hints_contract.py -q"
---

# Detailed plan: Select the newest detected C++ standard chronologically

## Task and research

Resolve treesitter-chunker#146, the C++ chronology subset of EC-COMPAT-2.
Both CppVersionDetector.detect_cxx_standard and map_features_to_standard use
string max, so 98 outranks newer standards. The existing cpp_standard_map
already provides release years for every admitted standard. Existing tests
parse the checked-in widget fixture and verify public detector precedence.

## Changes

- chunker/languages/version_detection/cpp_detector.py: select maxima in the
  two affected methods with the existing standard-map year as the key.
  Preserve strings, recognized standards/macros, extraction and primary
  precedence. Do not change C standard inference or compiler semantics.
  Use runtime-neutral typing.cast for the existing integer year and string
  macro-standard values in heterogeneous lookup dictionaries so the locked
  mypy gate can check the comparison. Do not change its debt baseline.
- tests/test_cpp_version_hints_contract.py: parse actual checked-in widget
  bytes with mixed C++98/newer comments in both orders for each recognized
  newer standard, and exercise the original __cplusplus98/newer20 case.
  Parse real preprocessor feature-macro cases pairing C++98 and C++11/14/17/20
  macros in both orders; verify detection, mapping and primary results.
  Retain single-standard, unknown/empty and declared-over-feature controls.
  No mocks of the parser or detector and no compiler-support claim.
- CHANGELOG.md: describe correct release chronology for C++ version hints.
- This plan and its typed plans/manifest.json entry are owned control paths.

## Documentation impact

Changelog records this user-visible inference repair. Existing API and source
hint precedence stay unchanged; no new user configuration is introduced.

During test writing, the existing constexpr pattern also matched the suffix
of __cpp_if_constexpr and weakened primary inference. This independent defect
is reproduced on unchanged main and filed as treesitter-chunker#424. Use the
structured-bindings macro for the isolated C++17 chronology case; preserve the
initial failure/restoration logs as excluded evidence. No keyword fix here.

## Dependencies and order

Independent detector slice. Register this plan before tests/source edits,
reproduce the mixed-standard failures, then modify only the two maxima.
Kill and restore the named string_order_cpp_standards mutation in both
methods. Use a private worktree and supported draft publication. Allow at
most three substantive manual tool-enabled code-review rounds.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_cpp_version_hints_contract.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py

Record actual intended mutation failures, restoration results and source/test
hashes. Actual Windows focused tests/standing preflight and all exact-head
hosted platform jobs are required before merge. Existing platform-core already
selects this test module. External review is supplemental code evidence; no
runner seal or operational authority is edited.

## Acceptance criteria

- [ ] EC-COMPAT-2 C++ subset: real parsed fixture hints choose every recognized
  newer standard over C++98 regardless of order, including the reported direct
  macro and feature-mapping paths; empty/unknown/single and precedence controls
  retain their results, proven by the focused module.
- [ ] string_order_cpp_standards fails the intended mixed cases in both
  methods; exact restoration passes the focused module with matching hashes.
- [ ] Original six checks, locked refresh/full tests/spec_tests, Windows,
  exact hosted jobs and bounded manual reviews accept this isolated repair.
  No native, parser pin, consumer lock or whole COMPAT/IF claim.

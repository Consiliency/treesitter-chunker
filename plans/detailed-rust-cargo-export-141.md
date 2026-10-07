---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_rust_version_hints_contract.py -q"
---

# Detailed plan: Export the explicit Cargo Rust requirement

## Task and research

Resolve treesitter-chunker#141, the Cargo export subset of EC-COMPAT-2.
RustVersionDetector already selects explicit Cargo rust-version ahead of source
rustc comments, but RustVersionInfo has no field that can retain it. Existing
tests parse real checked-in Rust source and read a valid private Cargo.toml.
No production callers construct this container in the repository; its public
four positional arguments and default export shape should remain compatible.

## Changes

- chunker/languages/version_detection/rust_detector.py: append an optional
  keyword-only rust_version argument to RustVersionInfo, retaining the existing
  four positional arguments and rustc_version meaning. Store it separately and
  include rust_version in to_dict only when provided, keeping legacy exports
  unchanged. Include the explicit requirement in string/repr output when present
  so diagnostics do not imply that the lower rustc hint was selected instead.
  Do not change detector extraction, selection priority or infer provenance.
- tests/test_rust_version_hints_contract.py: extend the actual parsed Rust/Cargo
  fixture contract to construct/export selected Cargo rust_version while
  retaining the distinct source rustc hint, edition, features and Cargo source.
  Add legacy four-positional-argument controls with/without version hints,
  verifying unchanged export keys and rendering. No parser/detector mocks.
- CHANGELOG.md: document optional Cargo requirement export beside rustc hints.
- This plan and its typed plans/manifest.json entry are owned control paths.

## Dependencies and order

Independent detector-container slice. Register before test/source changes,
reproduce missing result field, implement the additive optional contract, and
kill/restore omit_exported_cargo_requirement. File distinct defects separately.
Serialize original full runners; use supported publication and four manual
tool-enabled reviewers, maximum three substantive rounds. No native, pin,
consumer lock or whole COMPAT/IF acceptance.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_rust_version_hints_contract.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py

The named actual production mutation must fail Cargo export assertions and
exact restoration must pass the focused module. Actual Windows focused/standing
checks and exact hosted platforms supplement the original six/full runner;
external reviews do not confer formal IF acceptance.

## Acceptance criteria

- [ ] EC-COMPAT-2 Cargo subset: exported information retains selected explicit
  Cargo requirement and its caller-attributed source beside the older rustc hint.
- [ ] Legacy positional construction/export/rendering remains, and the actual
  omitted-export mutation fails then fully restores real fixture contracts.
- [ ] Original six checks/refresh/full tests/spec_tests, Windows, exact hosted
  checks and bounded manual reviews accept the additive container contract.

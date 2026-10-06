---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_cli.py tests/test_baml_language.py tests/test_iface_cli_detection.py -q"
---

# Detailed plan: Detect BAML through the canonical extension map

## Task

Resolve treesitter-chunker#402 independently of treesitter-chunker#359. The
installed companion already parses this fixture; main CLI detection skips it.

## Research summary

ZeroConfigAPI._detect_by_extension has a companion-aware BAML special case, but
the public EXTENSION_MAP lacks .baml. cli/main.py process_file reads that map
directly. RepoProcessor has its own companion-aware map. The existing optional
companion guards must retain their behavior: implicit ZeroConfigAPI falls back
to text when absent, explicit BAML raises installation guidance, and registry
never substitutes an ambient BAML grammar or downloads it.

## Changes

- chunker/auto.py: add .baml -> baml to EXTENSION_MAP, retaining the earlier
  companion-aware _detect_by_extension guard. Filter absent companions out of
  list_supported_extensions rather than advertising a missing parser. No
  parser/backend or pin change.
- chunker/symbol_graph.py and chunker/boundary/adapter.py: retain missing/wrong
  companion skipping in automatic repository scans and implicit file detection.
  Explicit language requests receive the existing BAML installation guidance
  instead of being hidden by the old map omission. With the extra,
  actual Boundary IR parsing of the fixture must produce14 source-backed nodes
  and no diagnostics; no addition to the pack census or twelve-language golden
  contract. SemanticQuery uses the same guarded collector.
- tests/test_cli.py: actual installed entrypoint on checked-in declarations.baml
  copied to private temporary input, file and batch JSON with no language option.
  Compare nonempty structural chunks with explicit --lang baml on identical
  inputs, requiring no warning and matching actual fixture contents.
  Missing/wrong external companion metadata must yield status1, installation
  guidance on stderr and an empty parseable JSON payload without --lang.
- tests/test_baml_language.py: actual UniversalLanguageRegistry with private
  metadata root, inactive None discovery/download services as in the existing
  BAML registry test, and actual ZeroConfigAPI parsing. Canonical map and detected
  language agree; implicit and explicit outputs agree and are not fallback.
  Retain all existing missing/wrong companion tests and real span/fixture cases.
- Add absent and wrong-version cases by changing only external distribution
  metadata, not the production detection/parser functions. An actual registry
  and API must omit BAML from supported extensions and fall back on file input;
  automatic symbol/Boundary directory scans skip it and parse a real Python
  control without errors. Implicit direct symbol/Boundary file detection also
  skips BAML; explicit requests retain installation errors.
- docs/cli-reference.md, README.md, docs/language-coverage.md and CHANGELOG.md:
  describe automatic .baml selection
  with the optional installed companion. Main CLI without it reports actionable
  installation failure; implicit ZeroConfigAPI retains its documented fallback.
- This plan and its typed plans/manifest.json row are owned control paths.

## Dependencies and order

Register before source edits. Integrate accepted treesitter-chunker#359 first so
new main CLI companion failures have the accepted nonzero/stderr semantics.
Reproduce current skip versus 14 real explicit chunks. Add tests, fix only the
map, kill and restore omit_canonical_baml_mapping, then original checks plus
dependency refresh/full suite. Require changed Windows tests/standing preflight,
hosted platforms and manual tool-enabled review, at most three substantive rounds.
No native admission, implicit network download, consumer lock or broker edits.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_cli.py tests/test_baml_language.py tests/test_iface_cli_detection.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py

Removing the mapping must fail both real installed CLI detection tests; restore
exact source and the full focused batch. The existing test_cli platform selection
covers both new subprocess cases. Also kill advertise_absent_baml_companion
(omit the list-supported guard) and ignore_scan_companion_gate (omit the
automatic symbol collector gate); missing/wrong companion cases must fail and
the entire focused batch must restore after each. Manual platform/review records supplement the
original runner without inventing a runner-stamped amendment or IF acceptance.

## Acceptance criteria

- [ ] Actual file and batch CLI without a language option return nonempty BAML
  chunks equal to explicit parsing, with no skip warning, and kill the mutation.
- [ ] Actual API detection/parsing agrees with the canonical map and preserves
  existing absent/wrong-companion and unknown-extension contracts.
- [ ] Original runner, current source/test Windows evidence, exact hosted checks
  and bounded reviews accept the repair with matching consumer documentation.

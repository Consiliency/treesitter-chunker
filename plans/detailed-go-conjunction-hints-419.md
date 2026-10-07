---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Preserve every release tag in a positive Go conjunction

## Task and research

Resolve treesitter-chunker#419 after the accepted numeric ordering repair in
treesitter-chunker#142. The modern line regex greedily retains only the last
release tag. The existing numeric maximum cannot recover discarded tags.
The checked-in service.go fixture and real parser already exercise detection.
Go's standard constraint package documents conjunction and separate full Boolean
evaluation: https://pkg.go.dev/go/build/constraint. This slice does not implement
that evaluator. Own evidence is allowlisted at /tmp/chunker-419-*.

## Changes

- chunker/languages/version_detection/go_detector.py: supplement the existing
  modern matches with every tag from a complete, unparenthesized conjunction
  consisting solely of positive go<major>.<minor> tags joined by &&. Anchor the
  directive to a complete line and accept horizontal whitespace/CRLF. Feed all
  captured pairs into the existing numeric maximum. Preserve single tags,
  existing modern-before-legacy and module precedence, and all fallback branches.
  Do not reinterpret OR, negation, parentheses, platform tags or legacy syntax.
- tests/test_go_version_hints_contract.py: extend real fixture parsing with
  one modern directive and a blank line before the package. Cover both reported
  orders, whitespace/CRLF, repeated tags and a three-tag conjunction with its
  maximum first/middle/last. Assert public build_constraints and primary hints.
  Retain the existing numeric ordering and module-priority contracts; add a
  modern conjunction beside a higher legacy hint to prove modern priority.
  No mocked parser or detector, external compiler dependency or timing gate.
- CHANGELOG.md: describe this precise conjunction extraction repair, without
  claiming general build-expression evaluation. This plan and typed manifest
  row are owned paths; the platform selector already runs the whole module.

## Dependencies and order

Register and commit before test/source edits. Reproduce actual missing earlier
tag on unchanged accepted source, then add bounded extraction. The named
mutation last_tag_only removes the supplementary conjunction extraction and
must fail cases whose maximum is not last. Exact restoration must pass with
source/test digest bindings. Collect complete manual four-seat reviews, maximum
three substantive rounds. Serialize original full runners and Git publication.

## Documentation impact

Changelog only: this repairs existing extracted hints without adding an API or
claiming complete compiler build-selection semantics.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_go_version_hints_contract.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py

Original six/locked refresh/full tests/spec_tests, actual matching-source Windows
and every exact hosted platform remain independent merge gates. No native, pin,
consumer lock, broker, ledger or checkpoint edits; no percentage or IF claim.

## Acceptance criteria

- [ ] Real parsed positive release-only conjunctions retain all tags and select
  the numeric maximum regardless of order, proven by the focused module.
- [ ] Existing single/separate-line numeric and modern/module precedence remain;
  last_tag_only fails earlier-maximum cases and exact restoration passes.
- [ ] Original checks/full tier, Windows/hosted platforms and four bounded
  reviews accept only the declared extraction contract, without Boolean claims.

---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_boundary_ir_schema.py tests/test_boundary_ir_golden_snapshots.py tests/test_boundary_ir_determinism.py -q"
---

# Detailed plan: Align the published Boundary IR contract with emitted records

## Task and research

Resolve treesitter-chunker#412 and separately filed documentation defect
treesitter-chunker#414 in one bounded published-contract repair. The adapter
already emits skipped unmapped files with language/parser null, while fileRecord
requires strings. The guide calls itself canonical but describes 1.0/1.1;
live types and JSON Schema require 2.0/2.1 following the existing canonical
identity break in chunker 3.0.0. No emitter change or new protocol is proposed.

Frozen vocabulary from docs/interface-boundary-spec.md: "The Phase 0 top-level
Boundary IR object keys are frozen as" schema_version, source, files, nodes,
edges, diagnostics, metrics, run. Identity sources remain definition_id,
module + qualified_name, node_id. Existing status vocabulary remains parsed,
skipped, error. Preserve these keys, values, identity and canonical ordering.

## Changes

- chunker/boundary/boundary_ir.schema.json: permit string/null language and
  parser for status skipped only, using a conditional that keeps string types
  for parsed/error records. Preserve existing required fields; do not globally
  relax parser/language, permit arbitrary types, or alter node language.
- tests/test_boundary_ir_schema.py: use the real installed parser and checked-in
  Python fixture to produce a parsed control and an unmapped-extension file
  copy. Require skipped status, null metadata, no nodes/parse failures and
  successful validation of the actual emitted skipped document. Validate the
  parsed control and explicitly reject null language and parser on copies of
  that real parsed output. Reject invalid non-string/non-null skipped metadata.
  Explicit empty semantic resolver tuple must produce actual 2.1 output that
  validates; default output must use 2.0. Validate the guide's JSON example with
  the same schema. No production/parser/validator mocks.
- Named mutations restore_skip_metadata_mismatch (restore string-only base
  metadata properties) and allow_null_parsed_metadata (remove the conditional)
  must fail their respective real-output/negative-contract cases. Restore exact
  schema bytes and pass the focused batch after each mutation.
- docs/interface-boundary-spec.md: describe current 2.0/2.1 constants and the
  existing 1.x re-extract/re-index migration, not a newly introduced version.
  Explain skipped unknown metadata and parsed/error string requirements. Replace
  the obsolete minimal JSON with a schema-valid actual no-declaration Python
  file example, with volatile paths labeled as illustrative. Preserve frozen
  keys/identity/canonical policy. Label the original
  Phase 0 checklist as historical instead of rewriting its acceptance events.
- CHANGELOG.md: record conditional skipped-file schema validation and corrected
  existing-version documentation. Own this detailed plan and typed manifest.

## Dependencies and order

Register before tests/schema changes. Record the actual schema mismatch before
fixing, run focused real-output and negative tests, kill/restore both mutations,
then bounded manual tool-enabled Opus/Gemini/Astra/Sol code review (at most three
substantive rounds, complete round before fixes). Integrate accepted main after
treesitter-chunker#411, with no BAML product changes owned here. Serialize original
six checks/full tests/spec_tests; require actual Windows focused/standing checks,
exact hosted platforms and strict docs build. Publish through the supported
adapter. No native admission, consumer locks or whole SEMANTICS/IF acceptance.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_boundary_ir_schema.py tests/test_boundary_ir_golden_snapshots.py tests/test_boundary_ir_determinism.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py
- uv run --locked --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict --site-dir <private temporary directory>

No emitter, golden or parser pin changes are needed. Existing real golden and
determinism tests must pass with unchanged tracked snapshots. No hand editing.

## Acceptance criteria

- [ ] Actual skipped output validates, parsed/error metadata remains constrained
  and arbitrary skipped types are rejected; focused schema/real-parsing tests
  and both killed/restored named mutations prove the conditional contract.
- [ ] Real syntax/semantic documents and the guide example validate at existing
  2.0/2.1 versions; strict documentation build and unchanged goldens confirm
  current contract documentation without a new version or historical rewrite.
- [ ] Original six checks, full tests/spec_tests, matching-source Windows, exact
  hosted platforms and bounded code review support this published-contract
  repair only. No coverage percentage or whole SEMANTICS/IF acceptance.

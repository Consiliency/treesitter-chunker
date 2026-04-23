# CONFORMANCE: Golden Conformance And Determinism Gate

## Context

Roadmap source: `specs/phase-plans-v1.md`, Phase 3. The roadmap is currently staged as a new file (`A  specs/phase-plans-v1.md`), so it is not an untracked `git clean -fd` risk.

Phase 0 through Phase 2 artifacts are present in this working tree. `docs/interface-boundary-spec.md` defines the Boundary IR schema and canonical JSON rules, `chunker.boundary.extract_boundary_ir()` emits canonical dictionaries with strict Boundary IR resolution by default, and `extract_symbol_graph()` additively exposes `resolution`, `candidates`, and `resolution_mode`. Current tests use temporary inline fixtures; there is no reusable `tests/fixtures/` corpus, no checked golden snapshot set, and `scripts/run_ci_smoke.py` does not yet include a Boundary IR determinism gate.

This phase freezes conformance coverage for the P0 language matrix: `python`, `javascript`, `typescript`, and `go`. JavaScript and TypeScript are treated as one language family for roadmap wording, but each language ID gets its own fixture and assertions because the repository exposes distinct extractors and grammar selection. Go fixtures must exist even when the local grammar is unavailable; Go extraction tests should skip only at runtime using the existing `list_languages()` pattern.

## Interface Freeze Gates

- [x] IF-0-CONFORMANCE-4 -- Golden fixture and double-run determinism test contract is frozen for Python, JavaScript/TypeScript, and Go.
- [x] IF-0-CONFORMANCE-4A -- The P0 conformance language IDs are exactly `python`, `javascript`, `typescript`, and `go`.
- [x] IF-0-CONFORMANCE-4B -- Fixture source roots live under `tests/fixtures/boundary_ir/repos/<language>/` and golden snapshots live under `tests/fixtures/boundary_ir/golden/<language>.json`.
- [x] IF-0-CONFORMANCE-4C -- Golden comparison uses `dumps_boundary_ir()` canonical JSON, with only `run.tool_version` normalized to a sentinel before snapshot comparison; `files`, `nodes`, `edges`, `diagnostics`, `metrics`, `run.options`, and `created_at` are not normalized.
- [x] IF-0-CONFORMANCE-4D -- Double-run determinism asserts byte-identical `dumps_boundary_ir(extract_boundary_ir(...))` output for the same fixture input and language in one process, with no normalization.
- [x] IF-0-CONFORMANCE-4E -- Required-field validation covers top-level fields, file records, node records, edge records, diagnostic records, metrics, and run metadata.
- [x] IF-0-CONFORMANCE-4F -- Per-language parity assertions cover node `kind`, `qualified_name`, `signature`, metadata `imports` and `dependencies`, `calls` edges, and `resolved`, `ambiguous`, and `unresolved` resolution states where syntax-derived extraction can produce them.
- [x] IF-0-CONFORMANCE-4G -- `scripts/run_ci_smoke.py` includes the deterministic Boundary IR conformance gate in the fast local CI-equivalent smoke batch.

## Lane Index & Dependencies

- SL-0 -- Conformance helper contract; Depends on: (none); Blocks: SL-1, SL-2, SL-3, SL-4, SL-5; Parallel-safe: no
- SL-1 -- P0 fixture repository corpus; Depends on: SL-0; Blocks: SL-2, SL-3, SL-4, SL-5; Parallel-safe: yes
- SL-2 -- Required-field and double-run harness; Depends on: SL-0, SL-1; Blocks: SL-3, SL-4, SL-5; Parallel-safe: yes
- SL-3 -- Language parity closure; Depends on: SL-0, SL-1, SL-2; Blocks: SL-4, SL-5; Parallel-safe: mixed
- SL-4 -- Golden snapshots and smoke gate; Depends on: SL-0, SL-1, SL-2, SL-3; Blocks: SL-5; Parallel-safe: no
- SL-5 -- Documentation and contract synthesis; Depends on: SL-0, SL-1, SL-2, SL-3, SL-4; Blocks: (none); Parallel-safe: no

## Lanes

### SL-0 -- Conformance Helper Contract

- **Scope**: Add reusable conformance helpers and constants before fixture, harness, and language-fix work depend on them.
- **Owned files**: `tests/boundary_ir_conformance.py`, `tests/test_boundary_ir_conformance_helpers.py`
- **Interfaces provided**: `P0_BOUNDARY_LANGUAGES`, `FIXTURE_ROOT`, `GOLDEN_ROOT`, `fixture_path(language)`, `extract_fixture_ir(language)`, `fixture_boundary_json_bytes(language)`, `normalize_ir_for_golden(ir)`, `assert_required_fields(ir)`
- **Interfaces consumed**: `chunker.boundary.extract_boundary_ir`, `chunker.boundary.dumps_boundary_ir`, `chunker.boundary.types.TOP_LEVEL_KEYS`, `METRIC_KEYS`, `RESOLUTION_STATUSES`, `RESOLUTION_MODES`
- **Parallel-safe**: no
- **Tasks**:
  - test: add helper tests proving the P0 language tuple is exact, fixture paths are relative repo paths, `normalize_ir_for_golden()` changes only `run.tool_version`, and `assert_required_fields()` validates a synthetic diagnostic record shape.
  - impl: implement helper functions without reading or writing golden files during import.
  - impl: keep extraction calls deterministic by passing relative fixture paths from the repo root and relying on default `created_at=None`.
  - impl: make the Go helper expose a grammar-availability skip predicate using `chunker.parser.list_languages()` instead of hiding missing fixture files.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_conformance_helpers.py -q`

### SL-1 -- P0 Fixture Repository Corpus

- **Scope**: Add compact source fixture repositories and an expectation manifest for all P0 languages.
- **Owned files**: `tests/fixtures/boundary_ir/repos/**`, `tests/fixtures/boundary_ir/manifest.json`, `tests/test_boundary_ir_fixture_inventory.py`
- **Interfaces provided**: fixture roots for `python`, `javascript`, `typescript`, and `go`; manifest fields for expected symbols, kinds, signatures, imports, dependencies, calls, and resolution statuses
- **Interfaces consumed**: `P0_BOUNDARY_LANGUAGES`, `fixture_path(language)` from SL-0
- **Parallel-safe**: yes
- **Tasks**:
  - test: add fixture inventory tests asserting each P0 language has a repo directory, UTF-8 source files, and manifest entries for nested definitions, imports, calls, duplicate names, and unresolved references.
  - impl: create minimal realistic fixtures: Python package modules, JavaScript ES module files, TypeScript typed module files, and Go package files.
  - impl: include duplicate local symbol names in each fixture where the syntax extractor can surface ambiguity, plus one unresolved reference per language where parser support allows it.
  - impl: keep fixture files small and deterministic; avoid generated timestamps, lockfiles, vendored directories, or dependency installs.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_fixture_inventory.py -q`

### SL-2 -- Required-Field And Double-Run Harness

- **Scope**: Add generic Boundary IR conformance tests for required fields and byte-identical double-run output.
- **Owned files**: `tests/test_boundary_ir_required_fields.py`, `tests/test_boundary_ir_determinism.py`
- **Interfaces provided**: failing/contract tests for IF-0-CONFORMANCE-4D and IF-0-CONFORMANCE-4E
- **Interfaces consumed**: helpers from SL-0; fixtures and manifest from SL-1; Boundary IR schema constants from `chunker.boundary.types`
- **Parallel-safe**: yes
- **Tasks**:
  - test: add parametrized required-field tests for all P0 languages, skipping Go extraction only when `go` is absent from `list_languages()`.
  - test: assert top-level keys, file keys, node keys, edge keys, metrics keys, run keys, and diagnostic keys through `assert_required_fields()`.
  - test: add parametrized double-run tests that compare raw canonical JSON bytes from two consecutive fixture extractions.
  - impl: keep tests independent of golden snapshots so they can identify determinism failures before snapshot regeneration.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_required_fields.py tests/test_boundary_ir_determinism.py -q`

### SL-3 -- Language Parity Closure

- **Scope**: Close metadata and relationship gaps exposed by the P0 fixtures without changing the frozen Boundary IR public surface.
- **Owned files**: `tests/test_boundary_ir_language_parity.py`, `chunker/boundary/adapter.py`, `chunker/symbol_graph.py`, `chunker/metadata/languages/python.py`, `chunker/metadata/languages/javascript.py`, `chunker/metadata/languages/typescript.py`, `chunker/metadata/languages/go.py`
- **Interfaces provided**: consistent P0 field parity for `kind`, `qualified_name`, `signature`, imports, dependencies, calls, and resolution states
- **Interfaces consumed**: manifest expectations from SL-1; generic conformance tests from SL-2; existing `extract_boundary_ir(..., resolution_mode="strict")`; existing `extract_symbol_graph(..., resolution_mode=...)`
- **Parallel-safe**: mixed
- **Tasks**:
  - test: add manifest-driven parity assertions that each language emits expected node kinds, qualified names, nonempty signatures for callable definitions, import/dependency metadata, call edges, and expected resolution statuses.
  - test: include strict-mode checks that ambiguous and unresolved edges keep `target == reference` and do not gain guessed node identities.
  - impl: fix only inconsistencies revealed by the new tests, preferring existing metadata extractors and adapter normalization over new abstractions.
  - impl: preserve existing `chunk_file()`, `extract_symbol_graph()`, boundary CLI, and legacy exporter compatibility tests.
  - impl: if a language cannot produce one parity dimension from syntax-only extraction, encode that limitation explicitly in the manifest and document the reason in the test assertion message rather than weakening other languages.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_language_parity.py tests/test_boundary_ir_required_fields.py tests/test_boundary_ir_determinism.py -q`

### SL-4 -- Golden Snapshots And Smoke Gate

- **Scope**: Write final golden snapshots from the settled P0 output and add the deterministic Boundary IR gate to the fast smoke runner.
- **Owned files**: `tests/fixtures/boundary_ir/golden/**`, `tests/test_boundary_ir_golden_snapshots.py`, `scripts/run_ci_smoke.py`
- **Interfaces provided**: checked golden snapshots; snapshot comparison test; CI smoke inclusion for IF-0-CONFORMANCE-4G
- **Interfaces consumed**: helpers from SL-0; fixtures and manifest from SL-1; required-field/determinism tests from SL-2; final parity behavior from SL-3
- **Parallel-safe**: no
- **Tasks**:
  - test: add golden snapshot tests that normalize only `run.tool_version`, compare canonical JSON structures against `tests/fixtures/boundary_ir/golden/<language>.json`, and fail with a clear regeneration/update message.
  - test: add or update smoke-runner coverage proving `scripts/run_ci_smoke.py` includes the Boundary IR conformance test file exactly once.
  - impl: generate or hand-update golden JSON after SL-3 passes, using `dumps_boundary_ir()` output with the frozen normalization rule from IF-0-CONFORMANCE-4C.
  - impl: add the narrowest deterministic Boundary IR test file to `CI_SMOKE_TESTS`, favoring the golden/determinism gate over broad language test modules.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_golden_snapshots.py tests/test_boundary_ir_determinism.py tests/test_cicd_pipeline.py -q`
  - verify: `uv run --with toml --all-extras python scripts/run_ci_smoke.py`

### SL-5 -- Documentation And Contract Synthesis

- **Scope**: Record the finalized conformance contract and documentation impact after all producer lanes settle.
- **Owned files**: `docs/interface-boundary-spec.md`, `docs/interface-boundary-roadmap.md`
- **Interfaces provided**: documented IF-0-CONFORMANCE-4 fixture paths, P0 language matrix, normalization rule, double-run rule, and smoke command
- **Interfaces consumed**: all helpers, fixtures, tests, snapshots, parity findings, and smoke-runner changes from SL-0 through SL-4
- **Parallel-safe**: no
- **Tasks**:
  - test: review SL-0 through SL-4 tests against docs and add no docs-only tests unless a documented conformance rule lacks executable coverage.
  - impl: add a concise conformance section to `docs/interface-boundary-spec.md` covering fixture paths, canonical snapshot normalization, required-field checks, language parity dimensions, and double-run byte equality.
  - impl: update `docs/interface-boundary-roadmap.md` only if the current roadmap status convention calls for marking the conformance gate as implemented or in progress.
  - impl: do not broaden docs into observability, incremental recomputation, semantic enrichment, or policy enforcement.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_conformance_helpers.py tests/test_boundary_ir_fixture_inventory.py tests/test_boundary_ir_required_fields.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_language_parity.py tests/test_boundary_ir_golden_snapshots.py -q`
  - verify: `uv run --with toml --all-extras mkdocs build --strict`

## Verification

Lane-specific verification is listed in each lane. After all lanes are integrated, run:

```bash
uv run --with toml --all-extras pytest tests/test_boundary_ir_conformance_helpers.py tests/test_boundary_ir_fixture_inventory.py tests/test_boundary_ir_required_fields.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_language_parity.py tests/test_boundary_ir_golden_snapshots.py tests/test_boundary_ir_adapter.py tests/test_boundary_ir_resolution_modes.py tests/test_symbol_graph_resolution.py -q
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
```

Because this phase touches fixtures, paths, extraction, and export formatting, run the standing Windows preflight before pushing:

```bash
ssh leno 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
```

## Acceptance Criteria

- [x] Golden fixture repositories exist under `tests/fixtures/boundary_ir/repos/` for Python, JavaScript, TypeScript, and Go.
- [x] Golden snapshots exist under `tests/fixtures/boundary_ir/golden/` and compare through canonical JSON with only `run.tool_version` normalized.
- [x] Same-input double-run tests assert byte-identical Boundary IR output for every available P0 language fixture.
- [x] Required fields are validated for nodes, edges, files, diagnostics, metrics, source, and run metadata.
- [x] Per-language conformance checks cover `kind`, `qualified_name`, signatures, imports, dependencies, calls, and resolution states.
- [x] Strict-mode ambiguous and unresolved edges do not emit guessed target node identities.
- [x] Go conformance fixtures are present, and Go extraction tests skip only when the local Go grammar is unavailable.
- [x] `scripts/run_ci_smoke.py` includes the deterministic Boundary IR conformance gate.
- [x] Existing Boundary IR adapter, resolution-mode, CLI, symbol graph, and metadata tests continue to pass.
- [x] Phase 3 does not add performance optimization, broad language expansion, semantic resolver correctness, observability metrics, incremental recomputation, or ownership policy enforcement.

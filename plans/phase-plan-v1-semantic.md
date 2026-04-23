# SEMANTIC: Optional Semantic Enrichment Hooks

## Context

Roadmap source: `specs/phase-plans-v1.md`, Phase 6. The roadmap file is tracked and clean, so it is not an untracked `git clean -fd` risk.

Phase 1 through Phase 5 Boundary IR artifacts are present in this working tree. `chunker.boundary.extract_boundary_ir()` already emits syntax-derived Boundary IR with strict/permissive resolution, deterministic diagnostics, opt-in timings, and an incremental cache path. Edge provenance currently records syntax extraction through `provenance.source = "syntax"` and `provenance.resolver = "extract_symbol_graph"`.

The Phase 6 work should be additive and opt-in. Default syntax-only output must remain byte-identical for existing Boundary IR fixtures and CLI/export consumers. Semantic enrichment should introduce a resolver hook contract and supplemental semantic edges, not mandatory LSP/type-checker dependencies, ownership-policy decisions, or rewrites of syntax-first node identity.

The current worktree also contains in-progress Phase 5 files (`chunker/boundary/cache.py`, `chunker/boundary/impact.py`, incremental tests, and related docs). Phase 6 execution should preserve that work and re-check adapter signatures before editing `chunker/boundary/adapter.py`.

## Interface Freeze Gates

- [x] IF-0-SEMANTIC-7 -- Optional semantic enrichment plugin interface, provenance, confidence, and schema migration contract are frozen.
- [x] IF-0-SEMANTIC-7A -- Semantic resolver API version is `1.0`; the public contract exposes `SemanticResolver`, `SemanticResolverContext`, and `SemanticEdge` from `chunker.boundary`.
- [x] IF-0-SEMANTIC-7B -- `SemanticResolver` requires stable `resolver_id`, `resolver_version`, `supported_languages`, and `enrich(context) -> Iterable[SemanticEdge]`; no resolver package is imported unless a caller or plugin explicitly provides one.
- [x] IF-0-SEMANTIC-7C -- `extract_boundary_ir(..., semantic_resolvers=None, semantic_min_confidence=0.0)` is the additive public API; `semantic_resolvers=None` preserves the exact syntax-only execution path and output.
- [x] IF-0-SEMANTIC-7D -- Semantic edges are supplemental edge records with `provenance.source == "semantic"`, `provenance.resolver`, `provenance.resolver_version`, `provenance.resolver_api_version`, and `provenance.confidence` in the inclusive range `[0.0, 1.0]`.
- [x] IF-0-SEMANTIC-7E -- Semantic enrichment never rewrites or deletes syntax edges, syntax edge IDs, syntax node IDs, or syntax-first ordering; duplicate semantic results are deduplicated deterministically by resolver ID, source, target, type, and reference, keeping the highest confidence.
- [x] IF-0-SEMANTIC-7F -- Resolver errors emit deterministic `boundary.semantic_resolver_error` diagnostics when `fail_fast=False` and raise when `fail_fast=True`, while preserving baseline syntax edges in non-fail-fast runs.
- [x] IF-0-SEMANTIC-7G -- Syntax-only output keeps `schema_version == "1.0"`; enriched output uses an additive semantic schema version and migration notes that tell consumers how to ignore or trust `provenance.source == "semantic"` edges.
- [x] IF-0-SEMANTIC-7H -- Semantic confidence is data only; this repository does not turn confidence into ownership, authorization, or enforcement policy.

## Lane Index & Dependencies

- SL-0 -- Semantic resolver contract preamble; Depends on: (none); Blocks: SL-1, SL-2, SL-3; Parallel-safe: no
- SL-1 -- Language plugin semantic hook discovery; Depends on: SL-0; Blocks: SL-3; Parallel-safe: yes
- SL-2 -- Boundary IR semantic edge enrichment; Depends on: SL-0; Blocks: SL-3; Parallel-safe: yes
- SL-3 -- Documentation and migration synthesis; Depends on: SL-0, SL-1, SL-2; Blocks: (none); Parallel-safe: no

## Lanes

### SL-0 -- Semantic Resolver Contract Preamble

- **Scope**: Freeze the semantic resolver API, provenance vocabulary, and exported constants before plugin discovery and adapter merge work branch from it.
- **Owned files**: `chunker/boundary/semantic.py`, `chunker/boundary/types.py`, `chunker/boundary/__init__.py`, `tests/test_boundary_ir_semantic_contract.py`
- **Interfaces provided**: `SEMANTIC_RESOLVER_API_VERSION`, `BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION`, `SemanticEdgeSource`, `SEMANTIC_EDGE_SOURCES`, `SemanticResolverContext`, `SemanticEdge`, `SemanticResolver`
- **Interfaces consumed**: existing `BoundaryIR`, `BoundaryRecord`, `ResolutionMode`, `ResolutionStatus`, `RESOLUTION_MODES`, `RESOLUTION_STATUSES`, `DIAGNOSTIC_STAGES`
- **Parallel-safe**: no
- **Tasks**:
  - test: add contract tests proving semantic constants are exact and exported from `chunker.boundary`.
  - test: assert `SemanticEdge` requires source node ID, target/reference, relationship type, resolution status, candidates, confidence, resolver identity, and deterministic metadata.
  - test: assert semantic confidence validation accepts `0.0` and `1.0`, rejects values outside `[0.0, 1.0]`, and sorts candidate IDs deterministically.
  - impl: add `chunker/boundary/semantic.py` with dataclasses or protocols for resolver context, resolver output, and resolver interface.
  - impl: add semantic schema/API constants and `semantic` to diagnostic stage vocabulary without changing default Boundary IR output.
  - impl: export the semantic resolver contract from `chunker/boundary/__init__.py`.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_semantic_contract.py tests/test_boundary_ir_contract.py -q`

### SL-1 -- Language Plugin Semantic Hook Discovery

- **Scope**: Let language plugins expose semantic resolvers without requiring built-in plugins or baseline chunking to load external semantic tools.
- **Owned files**: `chunker/languages/plugin_base.py`, `chunker/plugin_manager.py`, `tests/test_boundary_ir_semantic_plugin_hooks.py`
- **Interfaces provided**: `LanguagePlugin.semantic_resolvers()`, `PluginRegistry.get_semantic_resolvers(language: str | None = None)`, deterministic resolver ordering by `(resolver_id, resolver_version)`
- **Interfaces consumed**: `SemanticResolver`, `SEMANTIC_RESOLVER_API_VERSION`, existing `PluginRegistry.register()`, `PluginRegistry.get_plugin()`, `PluginManager.load_plugins_from_directory()`
- **Parallel-safe**: yes
- **Tasks**:
  - test: add a dummy language plugin that returns a semantic resolver and prove registry discovery returns it only after explicit plugin registration.
  - test: prove built-in plugins that do not override `semantic_resolvers()` return an empty sequence and do not import optional semantic dependencies.
  - test: prove resolver ordering is stable across registration order and repeated calls.
  - impl: add a default `semantic_resolvers()` method to `LanguagePlugin` returning an empty tuple.
  - impl: add registry discovery for semantic resolvers with optional language filtering and stable ordering.
  - impl: keep plugin validation non-fatal for plugins with no semantic hooks and avoid changing chunking plugin behavior.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_semantic_plugin_hooks.py tests/test_plugin_system.py tests/test_plugin_custom_directory_scanning.py -q`

### SL-2 -- Boundary IR Semantic Edge Enrichment

- **Scope**: Merge opt-in semantic resolver output into Boundary IR as deterministic supplemental edges while preserving syntax-only baselines.
- **Owned files**: `chunker/boundary/adapter.py`, `tests/test_boundary_ir_semantic_enrichment.py`, `tests/test_boundary_ir_semantic_determinism.py`
- **Interfaces provided**: `extract_boundary_ir(..., semantic_resolvers=None, semantic_min_confidence=0.0)`, semantic edge construction, semantic resolver diagnostics, enriched-output schema selection
- **Interfaces consumed**: semantic contract from SL-0; existing `_edge_record()`, `_diagnostic()`, `_assemble_boundary_ir()`, `canonicalize_boundary_ir()`, `extract_symbol_graph()`, incremental cache key payloads
- **Parallel-safe**: yes
- **Tasks**:
  - test: assert `dumps_boundary_ir(extract_boundary_ir(...))` remains byte-identical for P0 fixtures when `semantic_resolvers=None`.
  - test: add a deterministic fake resolver that turns a syntax-unresolved call into a supplemental semantic `calls` edge with provenance source, resolver ID/version/API version, and confidence.
  - test: prove syntax edges remain present and unchanged in enriched output, including IDs, targets, resolution, candidates, and syntax provenance.
  - test: prove semantic resolver results below `semantic_min_confidence` are filtered without mutating syntax output.
  - test: prove resolver exceptions produce `boundary.semantic_resolver_error` diagnostics with deterministic IDs when `fail_fast=False` and raise when `fail_fast=True`.
  - test: prove enriched output is byte-identical across double runs with resolver ordering, semantic edge deduplication, and highest-confidence tie handling.
  - test: prove incremental extraction uses semantic schema/resolver fingerprints in cache-key payloads when semantic resolvers are supplied, and does not reuse syntax-only records for enriched output.
  - impl: thread `semantic_resolvers` and `semantic_min_confidence` through non-incremental and incremental extraction paths after existing Phase 5 options.
  - impl: build resolver contexts from canonical baseline nodes, syntax edges, files, source root, language, and resolution mode.
  - impl: merge semantic edges after syntax edge assembly, dedupe deterministically, and keep syntax `relationships` lists stable except for adding semantic edge IDs in enriched output.
  - impl: use the semantic schema version only when semantic enrichment is actually requested; leave syntax-only `schema_version`, `run.options`, cache keys, and canonical JSON unchanged.
  - impl: treat confidence as provenance data only and do not add `enforcement_grade` to semantic edges.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_semantic_enrichment.py tests/test_boundary_ir_semantic_determinism.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_incremental_runtime.py -q`

### SL-3 -- Documentation And Migration Synthesis

- **Scope**: Document the finalized semantic hook and migration behavior after the contract, plugin, and adapter lanes settle.
- **Owned files**: `docs/interface-boundary-spec.md`, `docs/interface-boundary-roadmap.md`, `docs/agent-interface-readiness.md`, `docs/plugin-development.md`, `docs/grammar_management.md`
- **Interfaces provided**: documented IF-0-SEMANTIC-7 resolver API, opt-in API behavior, semantic provenance, confidence semantics, schema migration notes, plugin author guidance
- **Interfaces consumed**: semantic contract from SL-0; plugin discovery behavior from SL-1; enriched Boundary IR behavior and tests from SL-2
- **Parallel-safe**: no
- **Tasks**:
  - test: review executable coverage from SL-0 through SL-2 and add no docs-only tests unless a documented semantic rule lacks focused coverage.
  - impl: update `docs/interface-boundary-spec.md` with semantic enrichment versioning, resolver input/output shapes, edge provenance keys, confidence range, diagnostics, and syntax-only baseline guarantees.
  - impl: add migration notes explaining that syntax-only output remains schema `1.0`, enriched output uses the additive semantic schema version, and consumers can ignore `provenance.source == "semantic"` edges if unsupported.
  - impl: update roadmap/readiness docs to mark optional semantic hooks as planned or implemented according to the existing status style.
  - impl: update plugin development and grammar-management docs with guidance for exposing semantic resolvers from language plugins without adding mandatory LSP/type-checker dependencies.
  - impl: explicitly preserve non-goals: no built-in full-language LSP integrations, no mandatory semantic resolver, no ownership policy, and no confidence-to-authorization decision in this repository.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_semantic_contract.py tests/test_boundary_ir_semantic_plugin_hooks.py tests/test_boundary_ir_semantic_enrichment.py tests/test_boundary_ir_semantic_determinism.py -q`
  - verify: `uv run --with toml --all-extras mkdocs build --strict`

## Verification

Lane-specific verification is listed in each lane. After all lanes are integrated, run:

```bash
uv run --with toml --all-extras pytest tests/test_boundary_ir_semantic_contract.py tests/test_boundary_ir_semantic_plugin_hooks.py tests/test_boundary_ir_semantic_enrichment.py tests/test_boundary_ir_semantic_determinism.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_golden_snapshots.py tests/test_boundary_ir_required_fields.py tests/test_boundary_ir_incremental_runtime.py tests/test_plugin_system.py -q
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
```

Because this phase touches extraction, cache-key behavior when semantic resolvers are supplied, plugin discovery, and export formatting, run the standing Windows preflight before pushing:

```bash
ssh leno 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
```

## Acceptance Criteria

- [x] Semantic resolver API version, resolver context, resolver output, and resolver identity requirements are frozen and exported from `chunker.boundary`.
- [x] Baseline syntax-only `extract_boundary_ir()` output remains byte-identical with `semantic_resolvers=None`, including `schema_version == "1.0"` and unchanged golden snapshots.
- [x] Semantic enrichment is opt-in through explicit resolver objects, including resolver objects obtained from explicitly registered plugins; no LSP/type-checker package is imported for baseline extraction.
- [x] Enriched output contains supplemental semantic edges with `provenance.source == "semantic"`, resolver identity, resolver API version, and confidence in `[0.0, 1.0]`.
- [x] Syntax edges, syntax node IDs, syntax edge IDs, and syntax provenance are not rewritten by semantic enrichment.
- [x] Semantic edge ordering, resolver ordering, candidate ordering, diagnostics, and enriched canonical JSON are deterministic across repeated runs.
- [x] Resolver failures respect `fail_fast` and otherwise emit deterministic `boundary.semantic_resolver_error` diagnostics without dropping syntax results.
- [x] Incremental extraction does not reuse syntax-only cache records for enriched output and includes semantic schema/resolver fingerprints in relevant cache-key payloads.
- [x] Documentation covers resolver authoring, plugin exposure, schema migration, provenance, confidence semantics, and baseline compatibility.
- [x] Phase 6 does not add built-in full-language LSP integrations, make semantic enrichment mandatory, relax canonical serialization, or implement ownership/authorization policy.

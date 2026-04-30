---
phase_loop_plan_version: 1
phase: SEMANTIC
roadmap: specs/phase-plans-v1.md
roadmap_sha256: 8e02fa7e008f0a7df7dd7b28c36c2c2eb2ab79b5ebdc52cb8e3fd611efee277c
---

# SEMANTIC: Optional Semantic Enrichment Hooks

## Context

Roadmap source: `specs/phase-plans-v1.md`, Phase 6 (`SEMANTIC`). Canonical
`.phase-loop/state.json` marks `SCHEMA` through `INCREMENTAL` complete and
`SEMANTIC` unplanned, so this write promotes the requested uppercase artifact
into the execution-ready Phase 6 plan. The roadmap hash matches the required
`8e02fa7e008f0a7df7dd7b28c36c2c2eb2ab79b5ebdc52cb8e3fd611efee277c`.

This checkout is materially ahead of the original Phase 6 baseline. The live
repo already contains semantic contracts in `chunker/boundary/semantic.py`,
semantic constants and exports in `chunker/boundary/types.py` and
`chunker/boundary/__init__.py`, plugin hook surfaces in
`chunker/languages/plugin_base.py` and `chunker/plugin_manager.py`, adapter and
incremental-cache wiring in `chunker/boundary/adapter.py`, focused tests in
`tests/test_boundary_ir_semantic_contract.py`,
`tests/test_boundary_ir_semantic_plugin_hooks.py`,
`tests/test_boundary_ir_semantic_enrichment.py`,
`tests/test_boundary_ir_semantic_determinism.py`, and semantic-facing docs in
`docs/interface-boundary-spec.md`, `docs/interface-boundary-roadmap.md`,
`docs/agent-interface-readiness.md`, `docs/plugin-development.md`,
`docs/grammar_management.md`, and `docs/user-guide.md`.

SEMANTIC execution should therefore audit and harden the already-landed
additive implementation instead of rebuilding Phase 6 from scratch. The job is
to reconcile the roadmap exit criteria with the live resolver API, explicit
plugin discovery, syntax-only byte stability, semantic diagnostics,
incremental-cache segregation, and migration docs while preserving the Phase 0
through Phase 5 contracts. The older lowercase artifact
`plans/phase-plan-v1-semantic.md` remains historical planning context only.
Phase-loop execution for this run should use this uppercase
`plans/phase-plan-v1-SEMANTIC.md` artifact.

## Interface Freeze Gates

- [ ] IF-0-SEMANTIC-7 - Optional semantic enrichment plugin interface,
  provenance, confidence, and schema migration contract are frozen.
- [ ] IF-0-SEMANTIC-7A - `chunker.boundary` exports the live public semantic
  surface without widening the baseline syntax contract:
  `SEMANTIC_RESOLVER_API_VERSION == "1.0"`,
  `BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION == "1.1"`,
  `SEMANTIC_EDGE_SOURCES == ("semantic",)`, `SemanticResolverContext`,
  `SemanticEdge`, and `SemanticResolver`.
- [ ] IF-0-SEMANTIC-7B - `LanguagePlugin.semantic_resolvers()` defaults to an
  empty tuple, and `PluginRegistry.get_semantic_resolvers(language=None)`
  discovers resolvers only from explicitly registered plugins with stable
  ordering by `(resolver_id, resolver_version)`.
- [ ] IF-0-SEMANTIC-7C - `extract_boundary_ir(path, language=None, *,
  canonical=True, created_at=None, resolution_mode="strict", fail_fast=False,
  include_timings=False, incremental=False, cache_dir=None,
  force_rebuild=False, semantic_resolvers=None,
  semantic_min_confidence=0.0)` remains additive-compatible;
  `semantic_resolvers=None` preserves the exact syntax-only execution path and
  output.
- [ ] IF-0-SEMANTIC-7D - Semantic enrichment adds only supplemental edge
  records with `provenance.source == "semantic"`, `provenance.resolver`,
  `provenance.resolver_version`, `provenance.resolver_api_version`, and
  `provenance.confidence` in the inclusive range `[0.0, 1.0]`; syntax nodes,
  syntax edges, syntax IDs, and syntax ordering are never rewritten.
- [ ] IF-0-SEMANTIC-7E - Resolver exceptions emit deterministic
  `boundary.semantic_resolver_error` diagnostics with `stage == "semantic"`
  when `fail_fast=False`, and raise immediately when `fail_fast=True`, without
  dropping baseline syntax results in non-fail-fast runs.
- [ ] IF-0-SEMANTIC-7F - Syntax-only output keeps
  `schema_version == "1.0"` and the Phase 4 `run.options` baseline, while
  enriched output uses `schema_version == "1.1"` and adds only
  semantic-specific `run.options` fields when resolvers are explicitly
  requested.
- [ ] IF-0-SEMANTIC-7G - Incremental semantic runs use distinct cache-key
  payload fields for `semantic_schema_version`, `semantic_resolvers`, and
  `semantic_min_confidence`, and syntax-only cache records are not reused for
  enriched output.
- [ ] IF-0-SEMANTIC-7H - Semantic confidence remains data only; this repo does
  not turn confidence into ownership, authorization, or enforcement policy.

## Lane Index & Dependencies

- SL-0 - Semantic contract audit and additive-surface freeze; Depends on:
  (none); Blocks: SL-1, SL-2, SL-3; Parallel-safe: no
- SL-1 - Plugin hook discovery and lazy registration contract; Depends on:
  SL-0; Blocks: SL-2, SL-3; Parallel-safe: yes
- SL-2 - Adapter merge, diagnostics, and semantic cache segregation; Depends
  on: SL-0, SL-1; Blocks: SL-3; Parallel-safe: no
- SL-3 - Documentation and migration synthesis; Depends on: SL-0, SL-1, SL-2;
  Blocks: (none); Parallel-safe: no

## Lanes

### SL-0 - Semantic Contract Audit And Additive-Surface Freeze

- **Scope**: Freeze the live resolver datatypes, exported constants, and public
  Boundary IR semantic vocabulary before plugin discovery or adapter behavior
  depends on them.
- **Owned files**: `chunker/boundary/semantic.py`, `chunker/boundary/types.py`, `chunker/boundary/__init__.py`, `tests/test_boundary_ir_semantic_contract.py`
- **Interfaces provided**: `SEMANTIC_RESOLVER_API_VERSION`,
  `BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION`, `SEMANTIC_EDGE_SOURCES`,
  `SemanticResolverContext`, `SemanticEdge`, `SemanticResolver`,
  semantic-stage diagnostic vocabulary exported through `chunker.boundary`
- **Interfaces consumed**: existing `BOUNDARY_IR_SCHEMA_VERSION`,
  `DIAGNOSTIC_STAGES`, `ResolutionMode`, `ResolutionStatus`,
  canonical Boundary IR type aliases
- **Parallel-safe**: no
- **Tasks**:
  - test: keep contract tests explicit about the exact semantic constants and
    exported `chunker.boundary` surface.
  - test: prove `SemanticResolverContext` exposes the read-only Boundary IR
    inputs execution depends on.
  - test: prove `SemanticEdge` requires identity fields, rejects confidence
    values outside `[0.0, 1.0]`, and deterministically normalizes candidates.
  - impl: fix only concrete drift between the live semantic module, exported
    constants, and the Phase 6 contract.
  - impl: do not widen this lane into plugin discovery, adapter merge logic,
    cache invalidation, or docs-only wording.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_semantic_contract.py tests/test_boundary_ir_contract.py -q`

### SL-1 - Plugin Hook Discovery And Lazy Registration Contract

- **Scope**: Keep semantic resolver discovery explicit, lazy, and stable so
  optional plugins can surface semantic work without changing baseline chunking
  or built-in plugin behavior.
- **Owned files**: `chunker/languages/plugin_base.py`, `chunker/plugin_manager.py`, `tests/test_boundary_ir_semantic_plugin_hooks.py`
- **Interfaces provided**: `LanguagePlugin.semantic_resolvers()`,
  `PluginRegistry.get_semantic_resolvers(language: str | None = None)`,
  deterministic resolver ordering by `(resolver_id, resolver_version)`
- **Interfaces consumed**: SL-0 `SemanticResolver`; existing plugin
  registration, instance reuse, and directory discovery behavior
- **Parallel-safe**: yes
- **Tasks**:
  - test: keep hook tests explicit that unregistered plugins expose no
    resolvers and explicitly registered plugins do.
  - test: prove built-in plugins that do not override `semantic_resolvers()`
    still return `()`.
  - test: prove resolver ordering is stable across registration order and
    repeated calls.
  - impl: fix only concrete drift in default hook exposure, filtering, or
    ordering; keep heavy optional dependencies lazy and out of module import
    time.
  - impl: do not widen this lane into adapter behavior, semantic edge merging,
    or grammar-management policy changes beyond the hook contract.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_semantic_plugin_hooks.py tests/test_plugin_system.py tests/test_plugin_custom_directory_scanning.py -q`

### SL-2 - Adapter Merge, Diagnostics, And Semantic Cache Segregation

- **Scope**: Reconcile semantic resolver execution, supplemental edge merge,
  additive `run.options`, deterministic ordering, and incremental semantic
  cache separation without regressing syntax-only Boundary IR behavior.
- **Owned files**: `chunker/boundary/adapter.py`, `tests/test_boundary_ir_semantic_enrichment.py`, `tests/test_boundary_ir_semantic_determinism.py`, `tests/test_boundary_ir_observability_contract.py`
- **Interfaces provided**: `extract_boundary_ir(..., semantic_resolvers=None, semantic_min_confidence=0.0)`, semantic edge construction and deduplication, semantic resolver diagnostics, semantic cache-key payload separation, additive semantic `run.options`
- **Interfaces consumed**: SL-0 semantic contract; SL-1 resolver discovery
  contract; existing `canonicalize_boundary_ir()`, `build_boundary_cache_key`,
  Phase 4 diagnostics and `fail_fast` behavior, Phase 5 incremental cache
  runtime
- **Parallel-safe**: no
- **Tasks**:
  - test: keep syntax-only tests explicit that default output and explicit
    `semantic_resolvers=None` remain byte-identical.
  - test: prove supplemental semantic edges record the frozen provenance keys
    and do not rewrite syntax edges, syntax IDs, or syntax ordering.
  - test: prove `semantic_min_confidence` filters semantic additions without
    mutating syntax output.
  - test: prove resolver failures emit deterministic
    `boundary.semantic_resolver_error` diagnostics when `fail_fast=False` and
    raise when `fail_fast=True`.
  - test: prove enriched output is deterministic across resolver ordering and
    duplicate results, keeping the highest-confidence equivalent semantic edge.
  - test: prove semantic runs add only semantic-specific `run.options` keys,
    flip to the additive semantic schema version, and keep syntax-only
    `run.options` unchanged.
  - test: prove incremental semantic runs carry semantic resolver fingerprints
    in cache-key payloads and do not reuse syntax-only cache records.
  - impl: fix only concrete drift exposed by the focused tests; preserve the
    syntax-first baseline, canonical serialization, and existing Phase 4/5
    behaviors outside the additive semantic surface.
  - impl: do not widen this lane into built-in LSP integrations, performance
    tuning, ownership policy, or non-semantic cache redesign.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_semantic_enrichment.py tests/test_boundary_ir_semantic_determinism.py tests/test_boundary_ir_observability_contract.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_incremental_runtime.py -q`

### SL-3 - Documentation And Migration Synthesis

- **Scope**: Reduce the settled semantic implementation into accurate migration
  and authoring docs after the producer lanes finish.
- **Owned files**: `docs/interface-boundary-spec.md`, `docs/interface-boundary-roadmap.md`, `docs/agent-interface-readiness.md`, `docs/plugin-development.md`, `docs/grammar_management.md`, `docs/user-guide.md`
- **Interfaces provided**: documented semantic resolver API, opt-in execution
  behavior, provenance and confidence semantics, schema migration guidance,
  plugin-author guidance, baseline compatibility rules
- **Interfaces consumed**: SL-0 public semantic contract; SL-1 plugin hook
  behavior; SL-2 enriched-output, diagnostics, cache, and `run.options`
  behavior
- **Parallel-safe**: no
- **Tasks**:
  - test: review executable coverage from SL-0 through SL-2 and add no docs-only
    assertions unless a documented semantic rule lacks a focused coverage hook.
  - impl: update `docs/interface-boundary-spec.md` with the finalized additive
    semantic schema, provenance fields, confidence semantics, diagnostic stage,
    and syntax-only baseline guarantees.
  - impl: update roadmap/readiness docs only where status wording or Phase 6
    scope descriptions drift from the settled implementation.
  - impl: update plugin and user-facing docs only where resolver authoring,
    explicit registration, lazy dependency guidance, or migration behavior is
    inaccurate or incomplete.
  - impl: explicitly preserve non-goals: no built-in full-language LSP rollout,
    no mandatory semantic dependency, and no confidence-to-policy decision in
    this repository.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_semantic_contract.py tests/test_boundary_ir_semantic_plugin_hooks.py tests/test_boundary_ir_semantic_enrichment.py tests/test_boundary_ir_semantic_determinism.py -q`
  - verify: `uv run --with toml --all-extras mkdocs build --strict`

## Verification

Planning wrote the artifact only; verification was not run. During execution,
run the semantic-focused checks first, then the repo-standard local CI loop
from `AGENTS.md`:

```bash
uv run --with toml --all-extras pytest tests/test_boundary_ir_semantic_contract.py tests/test_boundary_ir_semantic_plugin_hooks.py tests/test_boundary_ir_semantic_enrichment.py tests/test_boundary_ir_semantic_determinism.py tests/test_boundary_ir_observability_contract.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_incremental_runtime.py tests/test_plugin_system.py -q
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
```

Because this phase touches resolver/plugin loading, cache-key payloads,
incremental behavior, docs, and cross-platform path handling, run the standing
Windows preflight before pushing:

```bash
ssh leno 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
```

## Acceptance Criteria

- [ ] The uppercase execution artifact `plans/phase-plan-v1-SEMANTIC.md` is the
  authoritative Phase 6 plan for roadmap hash
  `8e02fa7e008f0a7df7dd7b28c36c2c2eb2ab79b5ebdc52cb8e3fd611efee277c`.
- [ ] `chunker.boundary` exports the frozen semantic constants, resolver
  context, edge contract, and resolver protocol required by the additive
  semantic surface.
- [ ] Semantic resolver discovery stays explicit and lazy through registered
  plugins, with stable resolver ordering and no baseline dependency on external
  semantic tooling.
- [ ] Syntax-only `extract_boundary_ir()` output remains byte-identical with
  `semantic_resolvers=None`, including unchanged syntax edge records and no
  semantic-only `run.options` fields.
- [ ] Enriched output uses the additive semantic schema version and emits only
  supplemental semantic edges with frozen provenance keys and confidence in
  `[0.0, 1.0]`.
- [ ] Resolver failures respect `fail_fast` and otherwise emit deterministic
  `boundary.semantic_resolver_error` diagnostics with `stage == "semantic"`.
- [ ] Semantic edge ordering, resolver ordering, deduplication, and
  highest-confidence tie handling are deterministic across repeated runs.
- [ ] Incremental semantic runs do not reuse syntax-only cache records and keep
  semantic fingerprints scoped to the additive semantic cache payload only when
  enrichment is requested.
- [ ] Docs accurately cover resolver authoring, explicit registration,
  migration behavior, provenance, confidence semantics, and syntax-only
  baseline guarantees.
- [ ] Phase 6 does not broaden into built-in mandatory LSP integrations,
  non-additive schema changes, relaxed canonical serialization, or
  ownership/authorization policy.

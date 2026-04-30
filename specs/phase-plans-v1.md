# Phase roadmap v1

## Context

This roadmap translates `docs/agent-interface-readiness.md` and `docs/interface-boundary-roadmap.md` into implementation phases for `treesitter-chunker`. The target is to make this repository a deterministic AST-derived boundary and interface IR provider for an external orchestrator, not to add agent policy enforcement to this package.

The existing foundation includes `CodeChunk.definition_id`, `qualified_route`, retrieval metadata, `chunk_file(..., include_retrieval_metadata=True)`, and `extract_symbol_graph()`. The main gaps are a first-class boundary IR export, explicit edge resolution status, strict deterministic behavior, conformance coverage, observability, incremental recomputation, and optional semantic enrichment hooks.

## Architecture North Star

`treesitter-chunker` remains the local extraction and graph front end. It produces a versioned, canonical boundary IR from chunk metadata and symbol graph records. External orchestrators consume this IR to attach ownership manifests, evaluate patch policy, and enforce allow/reject decisions.

The IR surface should be deterministic by default: identical repository snapshot plus identical tool version yields byte-identical output. Relationship inference may remain useful in permissive discovery modes, but strict boundary export must expose `resolved`, `ambiguous`, and `unresolved` states and avoid guessed policy-grade edges.

## Assumptions

- The policy engine, agent manifests, and patch authorization workflow live outside this repository.
- Python, JavaScript/TypeScript, and Go are the initial P0 target languages because the source roadmap names them as the deterministic baseline.
- Existing chunk metadata and symbol graph output are the source substrate; this roadmap does not assume a full type checker or LSP resolver in core.
- Go coverage may require fixture and grammar validation before it reaches the same confidence level as Python and JavaScript/TypeScript.
- Compatibility matters for current chunking, export, semantic query, and CLI consumers.

## Non-Goals

- No ownership-policy engine in `treesitter-chunker`.
- No multi-agent patch authorization service in this repository.
- No mandatory semantic resolver dependency for baseline extraction.
- No broad rewrite of parser management, plugin loading, or existing export formats unless needed to preserve the new IR contract.

## Cross-Cutting Principles

- Prefer stable structural identities: `definition_id`, then `module + qualified_name`, then `node_id`.
- Canonicalize ordering, serialization, and counters so outputs are reproducible and diff-friendly.
- Fail closed only in strict boundary export semantics; keep discovery-oriented behavior available where existing APIs need it.
- Preserve provenance on every relationship so downstream systems can decide whether an edge is enforcement-grade.
- Validate core language contracts with golden fixtures before expanding language breadth.
- Use `uv run` for all repo validation commands, matching `AGENTS.md`.

## Top Interface-Freeze Gates

- IF-0-SCHEMA-1 - Versioned boundary IR schema, canonical JSON serialization rules, identity precedence, and compatibility policy are frozen.
- IF-0-ADAPTER-2 - Chunk metadata plus symbol graph adapter produces canonical nodes, edges, files, diagnostics, and run metadata for core languages.
- IF-0-RESOLUTION-3 - Relationship resolution contract exposes `resolved`, `ambiguous`, and `unresolved` states with strict/permissive mode semantics.
- IF-0-CONFORMANCE-4 - Golden fixture and double-run determinism test contract is frozen for Python, JavaScript/TypeScript, and Go.
- IF-0-OBSERVABILITY-5 - Structured metrics, diagnostics, parse failure handling, and `fail_fast` contract are frozen.
- IF-0-INCREMENTAL-6 - Boundary cache key format, warm-run invalidation rules, and impacted-neighbor recomputation contract are frozen.
- IF-0-SEMANTIC-7 - Optional semantic enrichment plugin interface, provenance, confidence, and schema migration contract are frozen.
- IF-0-HYGIENE-8 - Release hygiene policy for docs navigation, expected warnings, and explicit test skips is frozen.
- IF-0-REGISTRY-9 - Tree-sitter registry compatibility contract avoids deprecated local grammar construction paths while preserving language-pack fallback.
- IF-0-RELEASE-10 - Version bump, release notes, packaging metadata, and pre-push validation gate are frozen.

## Phases

### Phase 0 — Boundary IR Contract Freeze (SCHEMA)

**Objective**

Define the public boundary IR contract before implementation work fans out.

**Exit criteria**
- [ ] Boundary IR schema is documented with schema version, top-level fields, node fields, edge fields, diagnostic fields, metrics fields, and run metadata.
- [ ] Identity precedence is documented as `definition_id` -> `module + qualified_name` -> `node_id`.
- [ ] Canonical JSON rules are documented, including stable key ordering, list ordering, newline behavior, and encoding.
- [ ] Backward compatibility policy is documented for schema evolution and downstream orchestrator consumers.

**Scope notes**

Likely lanes:
- Schema lane: define node, edge, file, diagnostics, and run metadata shapes.
- Serialization lane: define deterministic JSON rules and compatibility/migration expectations.

**Non-goals**

- Implementing adapters, strict mode, cache, or semantic enrichment.
- Defining ownership policy or agent manifests.

**Key files**

- `docs/interface-boundary-roadmap.md`
- `docs/agent-interface-readiness.md`
- `docs/interface-boundary-spec.md` if restored or created as the canonical schema spec
- `chunker/types.py`
- `chunker/core.py`
- `chunker/symbol_graph.py`

**Depends on**
- (none)

**Produces**
- IF-0-SCHEMA-1 - Versioned boundary IR schema, canonical JSON serialization rules, identity precedence, and compatibility policy are frozen.

### Phase 1 — Canonical Boundary IR Adapter (ADAPTER)

**Objective**

Implement the adapter layer that converts existing chunk metadata and symbol graph output into the frozen boundary IR.

**Exit criteria**
- [ ] A public Python API can generate boundary IR from a file or repository path using `chunk_file(..., extract_metadata=True, include_retrieval_metadata=True)` and `extract_symbol_graph()`.
- [ ] Nodes use deterministic identity precedence with deterministic deduplication.
- [ ] Edges, files, diagnostics, and run metadata are emitted in canonical order.
- [ ] CLI or export entry point can write canonical JSON for downstream orchestrator use.
- [ ] Existing chunking and symbol graph tests continue to pass without contract regressions.

**Scope notes**

Likely lanes:
- API/model lane: add boundary IR datatypes or structured dictionaries near the existing extraction surface.
- Adapter lane: map `CodeChunk`, retrieval metadata, symbol lookup, imports, dependencies, calls, and relationships into schema fields.
- Serialization/CLI lane: expose canonical JSON output without disrupting existing exports.

**Non-goals**

- Strict ambiguity classification beyond what Phase 2 freezes.
- Incremental recomputation.
- Semantic resolver integrations.

**Key files**

- `chunker/types.py`
- `chunker/core.py`
- `chunker/symbol_graph.py`
- `chunker/export/`
- `chunker/cli/`
- `cli/main.py`
- `tests/test_definition_id.py`
- `tests/test_metadata_extraction.py`
- `tests/test_symbol_graph.py`

**Depends on**
- IF-0-SCHEMA-1

**Produces**
- IF-0-ADAPTER-2 - Chunk metadata plus symbol graph adapter produces canonical nodes, edges, files, diagnostics, and run metadata for core languages.

### Phase 2 — Deterministic Resolution Modes (RESOLUTION)

**Objective**

Replace policy-relevant heuristic edge behavior with explicit resolution states and strict/permissive modes.

**Exit criteria**
- [ ] Every boundary IR edge has a resolution status: `resolved`, `ambiguous`, or `unresolved`.
- [ ] Strict mode emits no guessed target identity when resolution is ambiguous or unresolved.
- [ ] Permissive mode preserves discovery-friendly references with provenance and does not claim enforcement-grade resolution.
- [ ] Ambiguous and unresolved counters are emitted in run metadata.
- [ ] Existing `extract_symbol_graph()` behavior remains compatible or is versioned behind an opt-in mode.

**Scope notes**

Likely lanes:
- Resolver lane: refactor qualified-name and unique-name lookup to return candidate sets and status.
- Mode contract lane: thread strict/permissive behavior through boundary IR generation and CLI/export options.
- Compatibility lane: protect current symbol graph consumers and tests.

**Non-goals**

- Full type or binding resolution.
- Language-specific semantic augmentation.
- Ownership allow/reject decisions.

**Key files**

- `chunker/symbol_graph.py`
- `chunker/semantic_query.py`
- `chunker/cli/symbol_commands.py`
- `chunker/cli/cluster_commands.py`
- `tests/test_symbol_graph.py`
- `tests/test_relationship_tracker.py`

**Depends on**
- IF-0-SCHEMA-1
- IF-0-ADAPTER-2

**Produces**
- IF-0-RESOLUTION-3 - Relationship resolution contract exposes `resolved`, `ambiguous`, and `unresolved` states with strict/permissive mode semantics.

### Phase 3 — Golden Conformance And Determinism Gate (CONFORMANCE)

**Objective**

Audit and harden the existing deterministic conformance harness for the P0 core
languages.

**Exit criteria**
- [ ] Golden fixture repositories exist for Python, JavaScript/TypeScript, and Go.
- [ ] Same-input double-run tests assert byte-identical boundary IR output.
- [ ] Required fields are validated for nodes, edges, files, diagnostics, and run metadata.
- [ ] Per-language conformance checks cover `kind`, `qualified_name`, signatures, imports, dependencies, calls, and resolution states.
- [ ] Fast CI-equivalent smoke validation includes the deterministic boundary gate.

**Scope notes**

Likely lanes:
- Fixture audit lane: verify and extend the existing compact fixture repos so
  nested definitions, imports, calls, duplicate names, and unresolved
  references remain covered without assuming a greenfield fixture build.
- Test harness lane: harden the existing schema validation, golden snapshots,
  and double-run equivalence gates instead of rebuilding them from scratch.
- Language parity lane: identify and fix core-language metadata inconsistencies exposed by the fixtures.

This phase starts from the already-landed conformance baseline in the repo. It
should freeze field parity and determinism against live behavior before later
observability, incremental, or semantic work is treated as authoritative.

**Non-goals**

- Medium/large repo performance optimization.
- Broad language expansion outside the core baseline.
- Semantic resolver correctness beyond syntax-derived extraction.

**Key files**

- `tests/fixtures/` or existing fixture location selected by repo convention
- `tests/test_symbol_graph.py`
- `tests/test_metadata_extraction.py`
- `tests/test_javascript_language.py`
- `tests/test_python_language.py`
- Go language tests if present or added with existing language-test conventions
- `scripts/run_ci_smoke.py`

**Depends on**
- IF-0-ADAPTER-2
- IF-0-RESOLUTION-3

**Produces**
- IF-0-CONFORMANCE-4 - Golden fixture and double-run determinism test contract is frozen for Python, JavaScript/TypeScript, and Go.

### Phase 4 — Diagnostics And Run Observability (OBSERVABILITY)

**Objective**

Add structured visibility for large-repo and policy-pipeline consumers.

**Exit criteria**
- [ ] Boundary IR run metadata includes timings for parse, metadata normalization, graph assembly, resolution, and serialization.
- [ ] Run summaries include counters for files processed, skipped files, parse failures, ambiguous edges, unresolved edges, and emitted nodes/edges.
- [ ] Parse failures continue by default and are represented as structured diagnostics.
- [ ] A `fail_fast` option stops on first parser or extraction failure for strict pipelines.
- [ ] Diagnostics are covered by focused tests and are stable in canonical output.

**Scope notes**

Likely lanes:
- Metrics lane: add timing spans and counters around boundary extraction stages.
- Diagnostics lane: define structured diagnostics, failure buckets, and `fail_fast` behavior.
- CLI/reporting lane: expose concise run summaries without leaking unstable ordering into canonical JSON.

**Non-goals**

- External telemetry service integration.
- Performance tuning unless needed to make metrics reliable.
- Ownership SLI/SLO policy enforcement.

**Key files**

- `chunker/symbol_graph.py`
- Boundary IR module added in Phase 1
- `chunker/performance/`
- `chunker/optimization/`
- `cli/main.py`
- `tests/test_recovery.py`
- `tests/test_parallel_error_handling.py`

**Depends on**
- IF-0-ADAPTER-2
- IF-0-RESOLUTION-3
- IF-0-CONFORMANCE-4

**Produces**
- IF-0-OBSERVABILITY-5 - Structured metrics, diagnostics, parse failure handling, and `fail_fast` contract are frozen.

### Phase 5 — Incremental Boundary Recompute (INCREMENTAL)

**Objective**

Add warm-run boundary IR generation that recomputes changed files and impacted neighbors without sacrificing deterministic output.

**Exit criteria**
- [ ] Boundary cache records are keyed by file hash, language, grammar/tool version, schema version, and relevant extraction options.
- [ ] Warm-run output remains byte-identical to cold-run output for the same repository snapshot.
- [ ] Changed-file plus impacted-neighbor recomputation is implemented for relationship-sensitive boundary updates.
- [ ] Fixture or benchmark tests demonstrate measurable warm-run speedup.
- [ ] Cache invalidation behavior is documented and covered by tests.

**Scope notes**

Likely lanes:
- Cache contract lane: define and implement persisted boundary record keys and invalidation.
- Impact analysis lane: identify affected neighbors for imports, dependencies, and calls.
- Benchmark/test lane: compare cold and warm graph builds on fixture repos.

**Non-goals**

- Distributed cache service.
- Watch mode or daemonized indexing unless already supported by existing APIs.
- Relaxing canonical serialization to improve speed.

**Key files**

- Boundary IR module added in Phase 1
- `chunker/cache/`
- `chunker/performance/enhanced_chunker.py`
- `chunker/optimization/incremental.py`
- `tests/test_cache.py`
- `tests/test_performance.py`
- `tests/test_performance_features.py`

**Depends on**
- IF-0-ADAPTER-2
- IF-0-RESOLUTION-3
- IF-0-OBSERVABILITY-5

**Produces**
- IF-0-INCREMENTAL-6 - Boundary cache key format, warm-run invalidation rules, and impacted-neighbor recomputation contract are frozen.

### Phase 6 — Optional Semantic Enrichment Hooks (SEMANTIC)

**Objective**

Provide extension points for LSP or type-checker augmentation while preserving deterministic syntax-first baseline output.

**Exit criteria**
- [ ] Semantic resolver hook interface is documented and versioned.
- [ ] Enriched edges include provenance such as `source=syntax|semantic`, resolver identity, and confidence.
- [ ] Strict baseline output remains available without semantic dependencies.
- [ ] Schema migration notes describe how semantic enrichment affects downstream consumers.
- [ ] Tests prove semantic enrichment is opt-in and cannot mutate baseline syntax-only output.

**Scope notes**

Likely lanes:
- Plugin contract lane: define resolver inputs, outputs, error handling, and trust metadata.
- IR enrichment lane: merge semantic results without changing syntax-first identity or ordering guarantees.
- Compatibility lane: document schema version and migration behavior for consumers.

**Non-goals**

- Building full LSP integrations for every language.
- Making semantic enrichment mandatory.
- Treating semantic confidence as an ownership policy decision inside this repo.

**Key files**

- Boundary IR module added in Phase 1
- `chunker/languages/plugin_base.py`
- `chunker/plugin_manager.py`
- `chunker/symbol_graph.py`
- `docs/plugin-development.md`
- `docs/grammar_management.md`

**Depends on**
- IF-0-SCHEMA-1
- IF-0-RESOLUTION-3
- IF-0-CONFORMANCE-4

**Produces**
- IF-0-SEMANTIC-7 - Optional semantic enrichment plugin interface, provenance, confidence, and schema migration contract are frozen.

### Phase 7 — Release Hygiene Baseline (HYGIENE)

**Objective**

Make pre-release validation output intentional and reviewable by removing avoidable documentation and test-warning noise without changing parser runtime behavior.

**Exit criteria**
- [ ] MkDocs strict build has no broken-link warnings introduced by documented pages.
- [ ] Docs outside `mkdocs.yml` navigation are either added to an explicit nav section or documented as intentionally internal.
- [ ] Fallback-warning tests locally assert expected `FallbackWarning` behavior instead of leaking incidental warning noise into CI summaries.
- [ ] Explicit platform skips remain only where the test cannot be made deterministic on that platform, with reasons in the test body or marker.
- [ ] CI smoke and Windows preflight remain green with no xfail/xpass results.

**Scope notes**

Likely lanes:
- Docs lane: classify `agent-interface-readiness.md`, `interface-boundary-roadmap.md`, `grammar_management.md`, release/deployment docs, and final integration docs as public nav or internal docs.
- Warning-test lane: update fallback tests that intentionally trigger `FallbackWarning` to use local `pytest.warns()` or scoped warning captures.
- Test-policy lane: keep skips explicit and local; do not reintroduce centralized collection-time xfail policy.

**Non-goals**

- Changing fallback behavior or warning text unless tests expose a real product issue.
- Reworking parser registry loading.
- Publishing a release.

**Key files**

- `mkdocs.yml`
- `docs/index.md`
- `docs/agent-interface-readiness.md`
- `docs/interface-boundary-roadmap.md`
- `docs/grammar_management.md`
- `docs/development/DEPLOYMENT.md`
- `docs/development/RELEASE_CHECKLIST.md`
- `docs/final-integration-testing.md`
- `tests/test_fallback_chunking.py`
- `tests/test_auto.py`
- `tests/test_overlapping_fallback.py`
- `tests/conftest.py`

**Depends on**
- IF-0-CONFORMANCE-4
- IF-0-OBSERVABILITY-5

**Produces**
- IF-0-HYGIENE-8 - Release hygiene policy for docs navigation, expected warnings, and explicit test skips is frozen.

### Phase 8 — Tree-Sitter Registry Compatibility Hardening (REGISTRY)

**Objective**

Remove the local compiled-grammar `DeprecationWarning` path and harden parser registry loading across current and future `tree_sitter` versions without weakening language-pack fallback.

**Exit criteria**
- [ ] All local compiled grammar `Language` construction goes through one compatibility helper.
- [ ] Registry and factory tests pass with `-W error::DeprecationWarning`.
- [ ] Local compiled grammar validation does not mark a language unavailable solely because a deprecated construction path was attempted.
- [ ] `tree-sitter-language-pack` remains the final fallback for available languages and invalid languages still raise `LanguageNotFoundError`.
- [ ] Linux platform-core and Windows preflight pass after registry changes.

**Scope notes**

Likely lanes:
- Compatibility lane: inventory supported `tree_sitter.Language` construction APIs and add a helper such as `_language_from_ctypes_symbol()`.
- Fallback lane: ensure local compiled grammar failure falls through to `tree-sitter-language-pack` without poisoning `_languages` metadata.
- Test lane: add focused deprecation-as-error coverage for `LanguageRegistry`, `ParserFactory`, parser creation, CLI chunking, and golden Boundary IR snapshots.

**Non-goals**

- Rebuilding grammar artifacts as part of normal tests.
- Removing `tree-sitter-language-pack`.
- Broad parser-management rewrite beyond compatibility and warning containment.

**Key files**

- `chunker/_internal/registry.py`
- `chunker/_internal/language_pack.py`
- `chunker/_internal/factory.py`
- `chunker/parser.py`
- `tests/test_registry_fallback.py`
- `tests/test_factory.py`
- `tests/test_chunking.py`
- `tests/test_cli.py`
- `tests/test_boundary_ir_golden_snapshots.py`

**Depends on**
- IF-0-HYGIENE-8

**Produces**
- IF-0-REGISTRY-9 - Tree-sitter registry compatibility contract avoids deprecated local grammar construction paths while preserving language-pack fallback.

### Phase 9 — Version Bump And Release Gate (RELEASE)

**Objective**

Prepare and validate the version bump so pushing and tagging a release is a mechanical follow-through rather than another debugging phase.

**Exit criteria**
- [ ] Package version is bumped in the configured source of truth and matches the planned release tag.
- [ ] Release notes or changelog summarize Boundary IR observability, incremental extraction, semantic enrichment, and release-hygiene changes.
- [ ] Local smoke, formatting, lint, docs build, Linux platform core, and Windows preflight pass after the version bump.
- [ ] Packaging metadata can build and pass artifact checks locally or through the documented release workflow.
- [ ] Working tree is clean before push.

**Scope notes**

Likely lanes:
- Version lane: update `pyproject.toml` and any generated/version docs required by the repository.
- Release-notes lane: update `CHANGELOG.md` or the current release notes target if present.
- Packaging lane: run the package build/check commands from `docs/packaging.md` or document why CI release workflow owns a specific artifact check.

**Non-goals**

- Adding new Boundary IR functionality.
- Changing release workflow credentials or publishing paths.
- Tagging or pushing unless explicitly requested during execution.

**Key files**

- `pyproject.toml`
- `CHANGELOG.md` if present
- `docs/packaging.md`
- `docs/development/RELEASE_CHECKLIST.md`
- `.github/workflows/release.yml`
- `.github/workflows/build-wheels.yml`

**Depends on**
- IF-0-HYGIENE-8
- IF-0-REGISTRY-9

**Produces**
- IF-0-RELEASE-10 - Version bump, release notes, packaging metadata, and pre-push validation gate are frozen.

## Phase Dependency DAG

```text
Phase 0 (SCHEMA)
  -> Phase 1 (ADAPTER)
      -> Phase 2 (RESOLUTION)
          -> Phase 3 (CONFORMANCE)
              -> Phase 4 (OBSERVABILITY)
                  -> Phase 5 (INCREMENTAL)
          -> Phase 6 (SEMANTIC)
          -> Phase 7 (HYGIENE)
              -> Phase 8 (REGISTRY)
                  -> Phase 9 (RELEASE)
```

## Execution Notes

Plan Phase 0 first because every downstream phase depends on the schema and serialization contract. After Phase 0, Phase 1 should be planned next as the implementation base.

Phase 2 can begin after Phase 1 has produced the adapter contract. Phase 3
should wait for Phase 2 because the existing golden fixtures and determinism
gates must lock the final resolution status semantics before downstream
planning.

Phase 4 should wait until the conformance harness is re-frozen, because
diagnostics and metrics need stable expected output. Phase 5 should wait for
Phase 4 so cache behavior includes finalized metrics and diagnostics.

Phase 6 can be planned after Phase 2 and Phase 3. It does not need to wait for incremental recomputation, as long as it preserves baseline syntax-only output and the schema compatibility rules from Phase 0.

Phase 7 can be planned after the conformance and observability gates because it is a release-hardening pass over docs, expected warnings, and test policy. Phase 8 should follow Phase 7 so parser-registry changes are validated against the cleaned warning policy. Phase 9 should wait for Phase 8 if the release should include tree-sitter deprecation hardening; if that hardening is deferred, Phase 9 can depend only on Phase 7 by explicit release decision.

Within each implementation phase, use `codex-plan-phase` to split lanes by owned files before editing. Good first selectors are:
- `Phase 0 (SCHEMA)` for the interface-freeze plan.
- `Phase 1 (ADAPTER)` once schema is frozen.
- `Phase 7 (HYGIENE)` for the next release-hardening plan.
- `Phase 8 (REGISTRY)` once the warning policy is clean.

## Verification

Use the local-first validation sequence from `AGENTS.md` after implementation phases:

```bash
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
```

For phases touching config, paths, temp files, extraction, fallback logic, or export formatting, also run the Windows preflight before pushing:

```bash
ssh leno 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
```

Phase-specific verification should include targeted tests before the broader smoke command:

```bash
uv run --with toml --all-extras pytest tests/test_definition_id.py tests/test_metadata_extraction.py tests/test_symbol_graph.py
uv run --with toml --all-extras pytest <boundary-ir-tests>
```

Release-hardening phases should also use these targeted checks:

```bash
uv run --with toml --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict
uv run --with toml --all-extras pytest tests/test_auto.py tests/test_fallback_chunking.py tests/test_overlapping_fallback.py -q
uv run --with toml --all-extras pytest tests/test_registry_fallback.py tests/test_factory.py tests/test_chunking.py tests/test_cli.py tests/test_boundary_ir_golden_snapshots.py -q
uv run --with toml --all-extras pytest tests/test_registry_fallback.py tests/test_factory.py tests/test_chunking.py tests/test_cli.py tests/test_boundary_ir_golden_snapshots.py -q -W error::DeprecationWarning
uv run --with toml --all-extras python scripts/run_platform_core.py --platform linux
```

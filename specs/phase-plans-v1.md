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

Lock deterministic output and field parity for the P0 core languages.

**Exit criteria**
- [ ] Golden fixture repositories exist for Python, JavaScript/TypeScript, and Go.
- [ ] Same-input double-run tests assert byte-identical boundary IR output.
- [ ] Required fields are validated for nodes, edges, files, diagnostics, and run metadata.
- [ ] Per-language conformance checks cover `kind`, `qualified_name`, signatures, imports, dependencies, calls, and resolution states.
- [ ] Fast CI-equivalent smoke validation includes the deterministic boundary gate.

**Scope notes**

Likely lanes:
- Fixture lane: add compact, realistic fixture repos covering nested definitions, imports, calls, duplicate names, and unresolved references.
- Test harness lane: add schema validation, golden snapshots, and double-run equivalence.
- Language parity lane: identify and fix core-language metadata inconsistencies exposed by the fixtures.

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

## Phase Dependency DAG

```text
Phase 0 (SCHEMA)
  -> Phase 1 (ADAPTER)
      -> Phase 2 (RESOLUTION)
          -> Phase 3 (CONFORMANCE)
              -> Phase 4 (OBSERVABILITY)
                  -> Phase 5 (INCREMENTAL)
          -> Phase 6 (SEMANTIC)
```

## Execution Notes

Plan Phase 0 first because every downstream phase depends on the schema and serialization contract. After Phase 0, Phase 1 should be planned next as the implementation base.

Phase 2 can begin after Phase 1 has produced the adapter contract. Phase 3 should wait for Phase 2 because golden fixtures must lock the final resolution status semantics.

Phase 4 should wait until the conformance harness exists, because diagnostics and metrics need stable expected output. Phase 5 should wait for Phase 4 so cache behavior includes finalized metrics and diagnostics.

Phase 6 can be planned after Phase 2 and Phase 3. It does not need to wait for incremental recomputation, as long as it preserves baseline syntax-only output and the schema compatibility rules from Phase 0.

Within each implementation phase, use `codex-plan-phase` to split lanes by owned files before editing. Good first selectors are:
- `Phase 0 (SCHEMA)` for the interface-freeze plan.
- `Phase 1 (ADAPTER)` once schema is frozen.

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

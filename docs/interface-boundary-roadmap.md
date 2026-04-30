# Interface Boundary Parsing Roadmap (External Orchestrator + treesitter-chunker)

This roadmap focuses only on boundary parsing and IR generation.

## Milestone goals

- **P0**: deterministic boundary extraction works end-to-end for core languages.
- **P1**: scalability and quality hardening for medium/large repos.
- **P2**: advanced semantics and ecosystem integration.

---

## P0 (2–3 weeks): Deterministic baseline

### Outcomes

- Generate canonical boundary IR for at least Python, TypeScript/JavaScript, and Go.
- Reproducible outputs for identical repo snapshot + tool version.
- Explicit edge resolution states (`resolved|ambiguous|unresolved`).
- Implement against the frozen Phase 0 Boundary IR contract in
  `docs/interface-boundary-spec.md`.

### Work items

1. **IR adapter layer** _(implemented for the syntax-first Phase 1 baseline)_
   - Build adapter from `chunk_file(...include_retrieval_metadata=True)` and `extract_symbol_graph()` output to the frozen Boundary IR schema in `docs/interface-boundary-spec.md`.
   - Implement canonical node/edge sorting and stable JSON serialization.
   - Keep later `resolution_mode`, observability, incremental, and semantic
     surfaces documented as additive downstream extensions rather than part of
     the baseline adapter freeze.

2. **Boundary ID strategy**
   - Implement precedence: `definition_id` → `module+qualified_name` → `node_id`.
   - Add deterministic deduplication.

3. **Strict mode implementation** _(implemented)_
   - Boundary IR defaults to `resolution_mode="strict"`.
   - No guessed target node identity is emitted for ambiguous or unresolved edges.
   - Resolved, ambiguous, and unresolved edge counters are tracked from emitted
     edge statuses.

4. **Golden tests** _(implemented)_
   - Snapshot tests against fixture repos for deterministic output.
   - Run same input twice and assert byte-identical output.

### Exit criteria

- Determinism tests pass in CI.
- `docs/interface-boundary-spec.md` remains the canonical schema contract for
  adapter output, with later implemented capabilities treated as additive
  extensions to the Phase 0 baseline.
- Spec compliance checklist is fully green for core languages.

---

## P1 (3–5 weeks): Throughput and resilience

### Outcomes

- Faster repeated runs on incremental commits.
- Better diagnostics and quality metrics.
- Broader language coverage without breaking determinism.

### Work items

1. **Incremental recomputation** _(implemented for Boundary IR cache records)_
   - Re-extract only changed files and impacted neighbors.
   - Cache intermediate boundary records keyed by file hash.

2. **Observability** _(implemented for deterministic Boundary IR output)_
   - Add structured timings: parse, normalization, graph assembly, serialization.
   - Publish run summary counters and top failure buckets.

3. **Conformance suite expansion**
   - Add extractor conformance fixtures for additional languages.
   - Add per-language parity dashboards for key fields (`kind`, `qualified_name`, signatures).

4. **Robust failure handling** _(implemented for Boundary IR extraction)_
   - Continue on parse errors by default.
   - Add `fail_fast` toggle for strict pipelines.

### Exit criteria

- Incremental mode demonstrates measurable speedup on fixture repos. _(implemented with deterministic warm-run reprocessing coverage)_
- Diagnostics are sufficient to triage unresolved/ambiguous edge regressions.

---

## P2 (optional): Semantic enrichment hooks

### Outcomes

- Optional high-confidence enrichment of relationships where syntax-only extraction is insufficient.

### Work items

1. **Semantic plugin interface** _(implemented as optional Boundary IR hooks)_
   - Define hook points for LSP/type-checker enrichment.
   - Preserve provenance and confidence metadata.

2. **Trust-tiered edges** _(implemented as supplemental semantic provenance)_
   - Mark each edge with `source=syntax|semantic` and confidence value.
   - Keep strict mode defaults syntax-first.

3. **Compatibility guarantees** _(implemented for syntax-only baseline and enriched output)_
   - Version IR schema and publish migration notes.
   - Preserve syntax-only `schema_version == "1.0"` and use additive semantic
     schema `1.1` only when resolvers are supplied.

### Exit criteria

- Semantic enrichment is optional and cannot break baseline deterministic
  output. _(implemented with contract, enrichment, plugin hook, and determinism
  tests)_

---

## Suggested execution order (first 10 tasks)

1. Implement serializer for the frozen IR schema in `docs/interface-boundary-spec.md`.
2. Implement ID precedence logic.
3. Add deterministic sort + canonical JSON.
4. Add strict/permissive resolution policy. _(implemented)_
5. Build first golden fixtures (3 languages). _(implemented for P0 matrix)_
6. Add deterministic CI gate (double-run equivalence). _(implemented)_
7. Add structured metrics output. _(implemented for Boundary IR observability)_
8. Implement cache key strategy. _(implemented)_
9. Add incremental recomputation. _(implemented)_
10. Expand language conformance fixtures.
11. Add optional semantic resolver hooks. _(implemented)_

## Risk register

- **Risk**: cross-language metadata inconsistencies.  
  **Mitigation**: conformance fixtures + required-field validation.

- **Risk**: heuristic drift causing non-deterministic edges.  
  **Mitigation**: strict mode and explicit resolution states.

- **Risk**: output churn due to schema evolution.  
  **Mitigation**: versioned schema + migration policy.

- **Risk**: semantic confidence being mistaken for an enforcement decision.  
  **Mitigation**: semantic confidence is documented as data only; policy and
  authorization remain outside this repository.

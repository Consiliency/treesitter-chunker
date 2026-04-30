---
phase_loop_plan_version: 1
phase: SCHEMA
roadmap: specs/phase-plans-v1.md
roadmap_sha256: 60b1380b9de14b340499012c1e99f930e5f0ec91613b8ce57a3ea0297f62d4e7
---

# SCHEMA: Boundary IR Contract Freeze

## Context

Roadmap source: `specs/phase-plans-v1.md`, Phase 0 (`SCHEMA`). Canonical
`.phase-loop/state.json` currently marks `SCHEMA` as `unplanned`, with a clean
`main` worktree at `d67fa1e0`.

This repository is materially ahead of the original phase ordering. The
canonical schema document already exists at `docs/interface-boundary-spec.md`,
the public Boundary IR API lives under `chunker/boundary/`, and focused tests
already cover contract, serialization, determinism, resolution, observability,
incremental cache, and semantic enrichment behavior. SCHEMA execution should
not try to rewind or repartition that implementation history. It should freeze
the Phase 0 contract against the current implementation surface, tighten the
phase-owned documentation, and add or adjust only the executable contract
anchors needed to make the schema freeze explicit.

The phase remains bounded to schema, identity, canonical JSON, and
compatibility policy. It must not introduce new adapter behavior, resolution
logic, observability runtime, incremental recomputation, semantic resolver
runtime, or policy enforcement work. When current docs mention later-phase
contracts that are already implemented, SCHEMA should preserve them only as
clearly labeled additive downstream extensions to the Phase 0 base contract.

## Interface Freeze Gates

- [ ] IF-0-SCHEMA-1 — `docs/interface-boundary-spec.md` is the canonical
  implementation-facing Boundary IR contract, and the Phase 0 base contract is
  frozen around syntax-only `schema_version == "1.0"`.
- [ ] IF-0-SCHEMA-2 — The base top-level Boundary IR object keys are frozen as
  `schema_version`, `source`, `files`, `nodes`, `edges`, `diagnostics`,
  `metrics`, and `run`, matching the public constants exported from
  `chunker.boundary`.
- [ ] IF-0-SCHEMA-3 — Identity precedence is frozen exactly as
  `definition_id` -> `module + qualified_name` -> `node_id`, and the chosen
  source is documented as `node.identity.source`.
- [ ] IF-0-SCHEMA-4 — Canonical JSON rules are frozen and cross-checked against
  the live serializer contract: UTF-8 encoding, lexicographic object-key
  ordering, deterministic list ordering, compact separators, and exactly one
  trailing newline for file output.
- [ ] IF-0-SCHEMA-5 — Backward-compatibility policy is frozen for downstream
  consumers: additive-compatible changes stay within the major version; breaking
  changes require a major version bump; consumers may reject unknown major
  versions.
- [ ] IF-0-SCHEMA-6 — Any already-implemented later-phase contracts kept in the
  schema spec are clearly labeled additive downstream extensions, not Phase 0
  prerequisites.
- [ ] IF-0-SCHEMA-7 — Executable contract anchors cover the base schema version,
  top-level key set, canonical JSON invariants, and identity-precedence
  expectations without broadening Phase 0 into later runtime behavior.
- [ ] IF-0-SCHEMA-8 — Documentation navigation and readiness/roadmap docs point
  to the canonical spec and describe SCHEMA as the contract-freeze phase rather
  than a catch-all implementation phase.

## Lane Index & Dependencies

- SL-0 — Canonical schema spec normalization; Depends on: (none); Blocks:
  SL-1, SL-2; Parallel-safe: no
- SL-1 — Executable schema contract anchors; Depends on: SL-0; Blocks: SL-2;
  Parallel-safe: yes
- SL-2 — Cross-doc wiring and phase synthesis; Depends on: SL-0, SL-1; Blocks:
  (none); Parallel-safe: no

## Lanes

### SL-0 — Canonical Schema Spec Normalization

- **Scope**: Tighten `docs/interface-boundary-spec.md` so the Phase 0 contract
  is explicit, current, and clearly separated from additive downstream
  extensions already present in the repo.
- **Owned files**: `docs/interface-boundary-spec.md`
- **Interfaces provided**: IF-0-SCHEMA-1 through IF-0-SCHEMA-6; canonical base
  schema wording; explicit additive-extension labeling for later-phase content
- **Interfaces consumed**: `BOUNDARY_IR_SCHEMA_VERSION`,
  `BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION`, `TOP_LEVEL_KEYS`, `METRIC_KEYS`,
  `TIMING_KEYS` from `chunker/boundary/types.py`; `dumps_boundary_ir()` from
  `chunker/boundary/serialization.py`; identity behavior from
  `chunker/boundary/identity.py`, `chunker/types.py`, `chunker/core.py`, and
  `chunker/symbol_graph.py`; roadmap requirements from
  `docs/interface-boundary-roadmap.md` and
  `docs/agent-interface-readiness.md`
- **Parallel-safe**: no
- **Tasks**:
  - test: audit the current spec against the roadmap exit criteria and mark the
    sections that are truly Phase 0 base contract versus later additive
    contracts already documented.
  - test: confirm the spec text names the live public constants and functions
    the repo exports today instead of a hypothetical pre-implementation surface.
  - impl: rewrite the opening contract, versioning, identity, canonical JSON,
    and compatibility sections so the syntax-only `1.0` contract is unmistakably
    the Phase 0 baseline.
  - impl: keep resolution, observability, incremental, conformance, and
    semantic sections only if they are clearly labeled as additive downstream
    contracts layered on top of the SCHEMA baseline.
  - impl: keep or refresh the checklist so every SCHEMA gate is explicitly
    reviewable from the doc alone.
  - verify: `rg -n "schema_version|1\\.0|definition_id|module \\+
    qualified_name|node_id|Canonical JSON|Compatibility|Phase 0|additive"
    docs/interface-boundary-spec.md`
  - verify: `uv run --with toml --all-extras mkdocs build --strict`

### SL-1 — Executable Schema Contract Anchors

- **Scope**: Add or tighten focused tests so the frozen SCHEMA contract is
  enforced by executable anchors rather than documentation alone.
- **Owned files**: `tests/test_boundary_ir_contract.py`,
  `tests/test_boundary_ir_serialization.py`, `tests/test_definition_id.py`
- **Interfaces provided**: IF-0-SCHEMA-7; targeted test coverage for base
  schema version, top-level keys, canonical serialization invariants, and
  identity-precedence expectations
- **Interfaces consumed**: SL-0 schema wording; `BOUNDARY_IR_SCHEMA_VERSION`,
  `TOP_LEVEL_KEYS`, `dumps_boundary_ir()`, `extract_boundary_ir()`,
  `compute_definition_id()`, and the boundary identity-selection behavior
- **Parallel-safe**: yes
- **Tasks**:
  - test: add or tighten assertions that the base Boundary IR contract emits
    `schema_version == "1.0"` when semantic resolvers are not supplied and that
    the top-level object keys match the exported canonical key set.
  - test: add or tighten serialization assertions for lexicographic object-key
    ordering, deterministic schema-list ordering, compact JSON separators, UTF-8
    string output, and exactly one trailing newline from `dumps_boundary_ir()`.
  - test: add or tighten identity assertions that the documented precedence is
    `definition_id` first, then `module + qualified_name`, then `node_id`,
    using the smallest existing test surface that already covers those helpers.
  - impl: keep this lane test-only; if a production behavior mismatch appears,
    push that requirement back into planning instead of widening SCHEMA
    execution implicitly.
  - verify: `uv run --with toml --all-extras pytest
    tests/test_boundary_ir_contract.py tests/test_boundary_ir_serialization.py
    tests/test_definition_id.py -q`

### SL-2 — Cross-Doc Wiring And Phase Synthesis

- **Scope**: Align supporting docs and navigation with the normalized SCHEMA
  contract and phase ownership boundaries.
- **Owned files**: `docs/interface-boundary-roadmap.md`,
  `docs/agent-interface-readiness.md`, `mkdocs.yml`
- **Interfaces provided**: IF-0-SCHEMA-8; docs and nav consistently point to
  the canonical spec and describe later phases as additive work on top of the
  frozen schema contract
- **Interfaces consumed**: normalized base contract from SL-0; executable
  contract anchors from SL-1
- **Parallel-safe**: no
- **Tasks**:
  - test: audit existing roadmap/readiness/nav wording for statements that blur
    the SCHEMA contract freeze into later implementation phases.
  - impl: update `docs/interface-boundary-roadmap.md` so Phase 0 clearly points
    at the normalized spec and treats later implemented capabilities as work
    layered on that base contract.
  - impl: update `docs/agent-interface-readiness.md` so it describes the schema
    spec as the canonical contract source and keeps the orchestration/policy
    split explicit.
  - impl: adjust `mkdocs.yml` only if navigation labels or ordering need to
    better reflect the canonical Boundary IR documentation cluster.
  - impl: do not widen this lane into code examples, release notes, or later
    runtime documentation beyond what is required to keep the contract story
    consistent.
  - verify: `rg -n "interface-boundary-spec|Phase 0|SCHEMA|canonical contract|Boundary IR"
    docs/interface-boundary-roadmap.md docs/agent-interface-readiness.md mkdocs.yml`
  - verify: `uv run --with toml --all-extras mkdocs build --strict`

## Verification

Planning wrote the artifact only; verification was not run. During execution,
run the focused SCHEMA checks first, then the repo-standard local CI smoke:

```bash
uv run --with toml --all-extras pytest tests/test_boundary_ir_contract.py tests/test_boundary_ir_serialization.py tests/test_definition_id.py -q
uv run --with toml --all-extras mkdocs build --strict
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
```

## Acceptance Criteria

- [ ] `docs/interface-boundary-spec.md` remains the canonical Boundary IR
  contract and makes the syntax-only `1.0` Phase 0 baseline explicit.
- [ ] The spec documents the frozen top-level fields, identity precedence,
  canonical JSON rules, and backward-compatibility policy in Phase 0-owned
  sections.
- [ ] Later implemented contracts that remain documented in the spec are
  clearly labeled additive downstream extensions rather than prerequisites for
  completing SCHEMA.
- [ ] Focused tests enforce the base schema version, top-level key set,
  canonical JSON invariants, and identity-precedence expectations.
- [ ] Roadmap/readiness docs and MkDocs navigation point to the canonical spec
  and describe SCHEMA as the contract-freeze phase.
- [ ] SCHEMA execution does not introduce new adapter logic, resolution
  semantics, observability runtime, incremental runtime, semantic enrichment
  runtime, or ownership-policy behavior.

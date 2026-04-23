# SCHEMA: Boundary IR Contract Freeze

## Context

This plan targets Phase 0 from `specs/phase-plans-v1.md`. No phase selector was provided, so this uses the roadmap's execution note to plan the first executable phase, `Phase 0 (SCHEMA)`.

The roadmap artifact `specs/phase-plans-v1.md` is currently untracked. It is not protected from `git clean -fd`; preserve or stage it before execution work starts.

Phase 0 is a contract-only phase. It freezes the Boundary IR schema and canonical serialization rules before Phase 1 implements adapters or exports. The existing substrate is:

- `chunker.types.CodeChunk`, including `node_id`, `file_id`, `symbol_id`, `qualified_route`, and `definition_id`.
- `chunker.types.compute_definition_id()`, `compute_node_id()`, and `compute_symbol_id()`.
- `chunker.core.chunk_file(..., extract_metadata=True, include_retrieval_metadata=True)`.
- `chunker.core._build_retrieval_metadata()`, which currently normalizes `kind`, `symbol`, `qualified_name`, `parent_symbol`, `semantic_path`, `signature_text`, `imports`, `exports`, `dependencies`, and `semantic_text`.
- `chunker.symbol_graph.extract_symbol_graph()`, which currently emits `symbols`, `relationships`, `metadata`, `symbol_lookup`, and `errors`.

`docs/interface-boundary-spec.md` does not exist yet. Phase 0 should create it as the canonical public contract and update existing roadmap/readiness docs to point to it.

## Interface Freeze Gates

- [ ] IF-0-SCHEMA-1 — `docs/interface-boundary-spec.md` is the canonical Boundary IR contract and defines `schema_version` with initial version `1.0`.
- [ ] IF-0-SCHEMA-2 — The top-level Boundary IR object keys are frozen as `schema_version`, `source`, `files`, `nodes`, `edges`, `diagnostics`, `metrics`, and `run`.
- [ ] IF-0-SCHEMA-3 — File records are frozen with `id`, `path`, `language`, `content_hash`, `parser`, `status`, and `diagnostics`.
- [ ] IF-0-SCHEMA-4 — Node records are frozen with `id`, `identity`, `definition_id`, `node_id`, `symbol_id`, `file_id`, `path`, `language`, `kind`, `symbol`, `qualified_name`, `semantic_path`, `signature`, `span`, `parent`, `relationships`, `metadata`, and `provenance`.
- [ ] IF-0-SCHEMA-5 — Edge records are frozen with `id`, `source`, `target`, `type`, `resolution`, `reference`, `candidates`, `location`, `provenance`, and `metadata`.
- [ ] IF-0-SCHEMA-6 — Diagnostic records are frozen with `id`, `severity`, `code`, `message`, `path`, `location`, `stage`, and `details`.
- [ ] IF-0-SCHEMA-7 — Metrics and run metadata are frozen with deterministic counters separated from volatile timing fields so canonical deterministic output can remain byte-identical when requested.
- [ ] IF-0-SCHEMA-8 — Identity precedence is frozen as `definition_id` -> `module + qualified_name` -> `node_id`, with the chosen source recorded in `node.identity.source`.
- [ ] IF-0-SCHEMA-9 — Canonical JSON serialization is frozen: UTF-8 encoding, lexicographic object key ordering, deterministic list ordering, compact separators, and exactly one trailing newline for file output.
- [ ] IF-0-SCHEMA-10 — Schema evolution policy is frozen: additive-compatible changes retain the major version, breaking changes require a major version bump, and downstream consumers may reject unknown major versions.

## Lane Index & Dependencies

- SL-0 — Canonical contract spec; Depends on: (none); Blocks: SL-1; Parallel-safe: no
- SL-1 — Documentation wiring; Depends on: SL-0; Blocks: (none); Parallel-safe: no

## Lanes

### SL-0 — Canonical Contract Spec

- **Scope**: Create the canonical Boundary IR specification and freeze schema, identity, serialization, and compatibility rules without changing runtime behavior.
- **Owned files**: `docs/interface-boundary-spec.md`
- **Interfaces provided**: IF-0-SCHEMA-1 through IF-0-SCHEMA-10; canonical schema field names; canonical serialization contract; schema compatibility policy.
- **Interfaces consumed**: `CodeChunk` fields from `chunker/types.py`; retrieval metadata keys from `chunker/core.py`; current symbol graph output shape from `chunker/symbol_graph.py`; roadmap requirements from `docs/interface-boundary-roadmap.md` and `docs/agent-interface-readiness.md`.
- **Parallel-safe**: no
- **Tasks**:
  - test: Before editing, confirm the spec file is absent or intentionally being replaced with `test -f docs/interface-boundary-spec.md && sed -n '1,240p' docs/interface-boundary-spec.md || true`.
  - test: Add a doc-contract checklist inside the spec covering every IF-0-SCHEMA gate so review can verify the freeze explicitly.
  - impl: Create `docs/interface-boundary-spec.md` with sections for scope, non-goals, versioning, top-level object, file records, node records, edge records, diagnostics, metrics, run metadata, identity precedence, canonical JSON, and compatibility.
  - impl: Document strict wording that policy engines, ownership manifests, patch authorization, and allow/reject enforcement live outside `treesitter-chunker`.
  - impl: Document the deterministic output boundary: counters and structural records are canonical, while volatile timings must be omitted, null, or excluded from byte-identical deterministic exports unless a non-canonical observability report is requested.
  - impl: Include at least one minimal JSON example showing all top-level keys and one node/edge shape, using placeholder IDs rather than output from a real run.
  - verify: `rg -n "schema_version|definition_id|module \\+ qualified_name|node_id|Canonical JSON|Compatibility|Non-goals|diagnostics|metrics|run metadata" docs/interface-boundary-spec.md`
  - verify: `uv run --with toml --all-extras mkdocs build --strict`

### SL-1 — Documentation Wiring

- **Scope**: Point existing architecture/readiness docs and documentation navigation at the frozen canonical spec.
- **Owned files**: `docs/interface-boundary-roadmap.md`, `docs/agent-interface-readiness.md`, `mkdocs.yml`
- **Interfaces provided**: Published docs link to `docs/interface-boundary-spec.md`; roadmap/readiness docs no longer imply the spec lives only in another repository.
- **Interfaces consumed**: IF-0-SCHEMA-1 from SL-0; canonical spec path `docs/interface-boundary-spec.md`.
- **Parallel-safe**: no
- **Tasks**:
  - test: Confirm current references with `rg -n "interface-boundary-spec|Greenfield|canonical|Boundary IR" docs/interface-boundary-roadmap.md docs/agent-interface-readiness.md mkdocs.yml`.
  - impl: Update `docs/agent-interface-readiness.md` to state that the implementation-facing Boundary IR contract now lives in `docs/interface-boundary-spec.md` in this repository.
  - impl: Update `docs/interface-boundary-roadmap.md` to reference the frozen schema spec as the Phase 0 output.
  - impl: Add `Interface Boundary Spec: interface-boundary-spec.md` to `mkdocs.yml` navigation near Architecture or Export Formats.
  - verify: `rg -n "interface-boundary-spec.md|Interface Boundary Spec" docs/interface-boundary-roadmap.md docs/agent-interface-readiness.md mkdocs.yml`
  - verify: `uv run --with toml --all-extras mkdocs build --strict`

## Verification

Planning-only runs should not execute verification. During execution, run the narrow doc checks first, then the repo-standard checks:

```bash
rg -n "schema_version|definition_id|module \\+ qualified_name|node_id|Canonical JSON|Compatibility|Non-goals|diagnostics|metrics|run metadata" docs/interface-boundary-spec.md
rg -n "interface-boundary-spec.md|Interface Boundary Spec" docs/interface-boundary-roadmap.md docs/agent-interface-readiness.md mkdocs.yml
uv run --with toml --all-extras mkdocs build --strict
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
```

If execution changes only markdown and `mkdocs build --strict` is unavailable in the local extras, record that explicitly and run the remaining repo-standard checks.

## Acceptance Criteria

- [ ] `docs/interface-boundary-spec.md` exists and is the canonical Boundary IR schema spec.
- [ ] The spec documents schema version, top-level fields, file fields, node fields, edge fields, diagnostic fields, metrics fields, and run metadata.
- [ ] Identity precedence is documented exactly as `definition_id` -> `module + qualified_name` -> `node_id`.
- [ ] Canonical JSON rules document stable key ordering, list ordering, compact separators, UTF-8 encoding, and one trailing newline.
- [ ] The spec separates deterministic counters/records from volatile timing data so future double-run deterministic tests are not invalidated by observability fields.
- [ ] Compatibility policy documents additive changes, breaking changes, schema version bumps, and downstream consumer expectations.
- [ ] Existing docs and MkDocs navigation link to the canonical spec.
- [ ] No runtime adapter, strict mode, cache, semantic enrichment, ownership policy, or patch authorization behavior is implemented in this phase.

---
phase_loop_plan_version: 1
phase: CONFORMANCE
roadmap: specs/phase-plans-v1.md
roadmap_sha256: 602ecab108f0f5f143211a29b4945e2fef0bd97e0f467f646b1c78d775d46d7f
---

# CONFORMANCE: Golden Conformance And Determinism Gate

## Context

Roadmap source: `specs/phase-plans-v1.md`, Phase 3 (`CONFORMANCE`). Canonical
`.phase-loop/state.json` marks `CONFORMANCE` as `unplanned`, the repo is clean
on `main` at `cae153de`, and the canonical runner handoff points to this phase
as the next planned step.

This checkout is materially ahead of the original Phase 3 baseline. The live
repo already contains the P0 conformance corpus and helper surfaces under
`tests/fixtures/boundary_ir/`, `tests/boundary_ir_conformance.py`,
`tests/test_boundary_ir_required_fields.py`,
`tests/test_boundary_ir_determinism.py`,
`tests/test_boundary_ir_language_parity.py`,
`tests/test_boundary_ir_golden_snapshots.py`, and
`scripts/run_ci_smoke.py`. `docs/interface-boundary-spec.md` and
`docs/interface-boundary-roadmap.md` also already describe conformance-related
behavior as implemented.

CONFORMANCE execution should therefore not rebuild the harness from scratch. It
should audit and harden the already-landed conformance contract, close any drift
between the roadmap exit criteria and the live helper/fixture/test/doc surface,
and make only the smallest production or test corrections needed to keep P0
field parity and byte-identical determinism trustworthy before later phases rely
on them.

The older lowercase artifact was removed to avoid case-insensitive filesystem
collisions. Phase-loop execution for this run should follow this uppercase
`plans/phase-plan-v1-CONFORMANCE.md` artifact.

## Interface Freeze Gates

- [ ] IF-0-CONFORMANCE-4 — Golden fixture and double-run determinism test
  contract is frozen for Python, JavaScript/TypeScript, and Go.
- [ ] IF-0-CONFORMANCE-4A — `P0_BOUNDARY_LANGUAGES` is exactly
  `("python", "javascript", "typescript", "go")`, and fixture roots remain
  repo-relative under `tests/fixtures/boundary_ir/repos/<language>/`.
- [ ] IF-0-CONFORMANCE-4B — Checked golden snapshots live under
  `tests/fixtures/boundary_ir/golden/<language>.json`, and snapshot
  normalization mutates only `run.tool_version` to a sentinel value.
- [ ] IF-0-CONFORMANCE-4C — Required-field validation is driven by the live
  Boundary IR constants (`TOP_LEVEL_KEYS`, `METRIC_KEYS`, `TIMING_KEYS`) and
  freezes exact file, node, edge, diagnostic, source, run, and run-option key
  sets for the syntax-first conformance baseline.
- [ ] IF-0-CONFORMANCE-4D — Same-input double-run determinism compares raw
  canonical JSON bytes from `dumps_boundary_ir(extract_boundary_ir(...))`
  without additional normalization.
- [ ] IF-0-CONFORMANCE-4E — Manifest-driven parity assertions cover `kind`,
  `qualified_name`, signatures, imports, dependencies, calls, and
  `resolved`/`ambiguous`/`unresolved` edge states across the P0 matrix.
- [ ] IF-0-CONFORMANCE-4F — Go fixture coverage stays present even when the
  local Go grammar is unavailable; runtime skips use the existing
  `list_languages()` availability pattern rather than missing-fixture failure.
- [ ] IF-0-CONFORMANCE-4G — The fast local CI-equivalent smoke batch includes
  the deterministic Boundary IR conformance gate exactly once via
  `scripts/run_ci_smoke.py`.
- [ ] IF-0-CONFORMANCE-4H — Docs describe the implemented conformance contract
  without widening into observability, incremental recomputation, semantic
  enrichment, or non-P0 language scope.

## Lane Index & Dependencies

- SL-0 — Conformance contract audit and helper freeze; Depends on: (none);
  Blocks: SL-1, SL-2, SL-3, SL-4; Parallel-safe: no
- SL-1 — Fixture corpus and manifest audit; Depends on: SL-0; Blocks: SL-2,
  SL-3, SL-4; Parallel-safe: yes
- SL-2 — Required-field, determinism, and golden gate hardening; Depends on:
  SL-0, SL-1; Blocks: SL-3, SL-4; Parallel-safe: yes
- SL-3 — P0 parity closure and minimal extractor fixes; Depends on: SL-0,
  SL-1, SL-2; Blocks: SL-4; Parallel-safe: mixed
- SL-4 — Smoke-loop and documentation synthesis; Depends on: SL-0, SL-1, SL-2,
  SL-3; Blocks: (none); Parallel-safe: no

## Lanes

### SL-0 — Conformance Contract Audit And Helper Freeze

- **Scope**: Freeze the live conformance helper contract so every downstream
  fixture, golden, determinism, and parity assertion is grounded in one
  explicit source of truth.
- **Owned files**: `tests/boundary_ir_conformance.py`, `tests/test_boundary_ir_conformance_helpers.py`
- **Interfaces provided**: `P0_BOUNDARY_LANGUAGES`, `FIXTURE_ROOT`,
  `GOLDEN_ROOT`, `fixture_path(language)`, `grammar_available(language)`,
  `skip_if_grammar_unavailable(language)`, `extract_fixture_ir(language)`,
  `fixture_boundary_json_bytes(language)`, `normalize_ir_for_golden(ir)`,
  `assert_required_fields(ir)`
- **Interfaces consumed**: `chunker.boundary.extract_boundary_ir`,
  `chunker.boundary.dumps_boundary_ir`, `chunker.boundary.types.TOP_LEVEL_KEYS`,
  `METRIC_KEYS`, `TIMING_KEYS`, `chunker.parser.list_languages`
- **Parallel-safe**: no
- **Tasks**:
  - test: audit the current helper contract against the roadmap exit criteria
    and tighten helper tests so the exact P0 language tuple, repo-relative
    fixture/golden roots, tool-version-only normalization, grammar-availability
    behavior, and required-field sample shapes are all executable.
  - impl: reconcile any drift between helper tests and the live Boundary IR
    constant sets without inventing a second conformance abstraction layer.
  - impl: keep helper imports side-effect free and deterministic; do not read or
    rewrite golden files during module import.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_conformance_helpers.py -q`

### SL-1 — Fixture Corpus And Manifest Audit

- **Scope**: Audit and minimally extend the existing P0 fixture corpus and
  manifest so each language continues to prove nested definitions, imports,
  duplicate-name ambiguity, and unresolved references with small deterministic
  sources.
- **Owned files**: `tests/fixtures/boundary_ir/repos/**`, `tests/fixtures/boundary_ir/manifest.json`, `tests/test_boundary_ir_fixture_inventory.py`
- **Interfaces provided**: stable fixture repositories for `python`,
  `javascript`, `typescript`, and `go`; manifest expectations for kinds,
  qualified names, signatures, imports, dependencies, calls, resolution
  statuses, and strict reference targets
- **Interfaces consumed**: `P0_BOUNDARY_LANGUAGES`, `fixture_path(language)`
  from SL-0
- **Parallel-safe**: yes
- **Tasks**:
  - test: harden fixture inventory assertions so every P0 language has a
    repo-relative corpus, UTF-8 source files, and manifest coverage for the
    expected parity dimensions.
  - test: verify that Go stays represented in the corpus even when extraction
    must skip at runtime because the local grammar is unavailable.
  - impl: extend or correct the existing corpus only where the live fixtures no
    longer exercise the roadmap-required ambiguity, unresolved, import, or call
    scenarios.
  - impl: keep fixtures compact and reviewable; avoid generated metadata,
    lockfiles, or dependency-install side effects.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_fixture_inventory.py -q`

### SL-2 — Required-Field, Determinism, And Golden Gate Hardening

- **Scope**: Freeze the generic conformance tests so required fields, raw
  double-run equality, and checked golden snapshots all reflect the same
  canonical Boundary IR contract.
- **Owned files**: `tests/test_boundary_ir_required_fields.py`, `tests/test_boundary_ir_determinism.py`, `tests/test_boundary_ir_golden_snapshots.py`, `tests/fixtures/boundary_ir/golden/**`
- **Interfaces provided**: failing/contract tests for required fields,
  byte-identical double-run determinism, and checked golden snapshot equality
- **Interfaces consumed**: SL-0 helper surfaces; SL-1 fixtures and manifest;
  `chunker.boundary.dumps_boundary_ir`; live Boundary IR constants from
  `chunker.boundary.types`
- **Parallel-safe**: yes
- **Tasks**:
  - test: tighten required-field checks so they exercise the live top-level,
    file, node, edge, diagnostic, metrics, source, run, and run-option key
    contracts for each P0 fixture.
  - test: keep determinism checks on raw canonical JSON bytes from consecutive
    runs, including at least one diagnostic-producing path that proves stable
    error serialization.
  - test: keep golden snapshot comparison normalization limited to
    `run.tool_version`, and ensure snapshot failures report a clear intentional
    update path.
  - impl: regenerate or hand-update golden JSON only after helper, fixture, and
    determinism behavior is settled; do not normalize additional fields to make
    snapshots pass.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_required_fields.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_golden_snapshots.py -q`

### SL-3 — P0 Parity Closure And Minimal Extractor Fixes

- **Scope**: Close any live P0 language parity drift exposed by the conformance
  corpus without changing the frozen public Boundary IR or symbol-graph
  contract.
- **Owned files**: `tests/test_boundary_ir_language_parity.py`, `chunker/boundary/adapter.py`, `chunker/symbol_graph.py`, `chunker/metadata/languages/python.py`, `chunker/metadata/languages/javascript.py`, `chunker/metadata/languages/typescript.py`, `chunker/metadata/languages/go.py`
- **Interfaces provided**: stable P0 parity for `kind`, `qualified_name`,
  signatures, imports, dependencies, calls, and strict-mode resolution-state
  behavior
- **Interfaces consumed**: manifest expectations from SL-1; generic gates from
  SL-2; existing `extract_boundary_ir(..., resolution_mode="strict")`; existing
  `extract_symbol_graph(..., resolution_mode=...)`
- **Parallel-safe**: mixed
- **Tasks**:
  - test: keep parity assertions manifest-driven and explicit about any
    syntax-only limitation rather than weakening the whole language matrix.
  - test: preserve strict-mode checks that ambiguous and unresolved edges keep
    `target == reference` and do not gain guessed node identities.
  - impl: fix only the extractor or adapter inconsistencies exposed by the new
    or tightened tests, preferring existing metadata extractors and adapter
    normalization over new abstractions.
  - impl: validate Go expectations against real extractor output before changing
    assertions, especially where `struct` / `interface` labels come from
    content-derived or metadata-derived evidence.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_language_parity.py tests/test_boundary_ir_required_fields.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_golden_snapshots.py -q`

### SL-4 — Smoke-Loop And Documentation Synthesis

- **Scope**: Freeze the repo-standard smoke inclusion and the human-readable
  conformance contract after the producer lanes settle the exact live behavior.
- **Owned files**: `scripts/run_ci_smoke.py`, `docs/interface-boundary-spec.md`, `docs/interface-boundary-roadmap.md`
- **Interfaces provided**: deterministic smoke-batch inclusion for the boundary
  conformance gate; updated docs for fixture paths, normalization, determinism,
  parity, and known P0 limitations
- **Interfaces consumed**: SL-0 through SL-3 helper, fixture, golden, parity,
  and extractor findings
- **Parallel-safe**: no
- **Tasks**:
  - test: verify the smoke runner includes the deterministic Boundary IR
    conformance gate exactly once and still matches the repo’s preferred local
    CI smoke intent.
  - impl: update `docs/interface-boundary-spec.md` only where the implemented
    conformance contract or additive extension wording has drifted from the live
    tests.
  - impl: update `docs/interface-boundary-roadmap.md` only where current status
    prose or conformance-scope wording disagrees with the settled implementation
    and test surface.
  - impl: do not widen docs into observability, incremental recomputation,
    semantic enrichment, release hardening, or broader language-expansion
    planning.
  - verify: `uv run --with toml --all-extras pytest tests/test_boundary_ir_conformance_helpers.py tests/test_boundary_ir_fixture_inventory.py tests/test_boundary_ir_required_fields.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_language_parity.py tests/test_boundary_ir_golden_snapshots.py -q`
  - verify: `uv run --with toml --all-extras python scripts/run_ci_smoke.py`

## Verification

Planning wrote the artifact only; verification was not run. During execution,
run the phase-focused checks first, then the repo-standard local CI loop from
`AGENTS.md`:

```bash
uv run --with toml --all-extras pytest tests/test_boundary_ir_conformance_helpers.py tests/test_boundary_ir_fixture_inventory.py tests/test_boundary_ir_required_fields.py tests/test_boundary_ir_determinism.py tests/test_boundary_ir_language_parity.py tests/test_boundary_ir_golden_snapshots.py -q
uv run --with toml --all-extras pytest tests/test_boundary_ir_adapter.py tests/test_boundary_ir_resolution_modes.py tests/test_symbol_graph.py tests/test_symbol_graph_resolution.py tests/test_metadata_extraction.py tests/test_javascript_language.py tests/test_python_language.py tests/test_go_language.py -q
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
```

Because this phase may touch fixtures, extraction behavior, canonical output,
and path-sensitive tests, run the standing Windows preflight before pushing:

```bash
ssh win 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
```

## Acceptance Criteria

- [ ] The uppercase execution artifact
  `plans/phase-plan-v1-CONFORMANCE.md` is the authoritative CONFORMANCE plan for
  this phase-loop run, and the lowercase historical artifact is not used as the
  execution target.
- [ ] The P0 conformance matrix remains exactly `python`, `javascript`,
  `typescript`, and `go`, with repo-relative fixture sources and checked golden
  snapshots.
- [ ] Required-field validation enforces the live Boundary IR key contracts for
  top-level records, files, nodes, edges, diagnostics, metrics, source, run,
  and run options.
- [ ] Same-input double-run tests assert byte-identical canonical Boundary IR
  output without normalizing fields beyond the frozen golden snapshot
  `run.tool_version` sentinel.
- [ ] Manifest-driven parity checks cover `kind`, `qualified_name`,
  signatures, imports, dependencies, calls, and resolution states across the P0
  matrix, with any syntax-only limitation called out explicitly instead of being
  hidden by weaker assertions.
- [ ] Go fixture coverage remains present, and Go extraction skips only when the
  local grammar is unavailable.
- [ ] `scripts/run_ci_smoke.py` includes the deterministic Boundary IR
  conformance gate exactly once.
- [ ] Docs describe the implemented conformance contract accurately without
  widening into observability, incremental, semantic, or broad language
  expansion work.
- [ ] CONFORMANCE execution does not rebuild the conformance harness from
  scratch or broaden into later-phase functionality.

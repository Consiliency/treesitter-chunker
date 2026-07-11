---
phase_loop_plan_version: 1
phase: BOUNDARYFIX
roadmap: specs/phase-plans-v2.md
roadmap_sha256: 177445a267e92f2ef1ae5c894bc426638f7fb3b106cec3824e13666f237ca788
---

# BOUNDARYFIX: Boundary-IR Serializer Determinism

## Context

Three orphaned Boundary-IR MAJORs from the review, all confirmed in the current tree:

1. **Cross-language float divergence** — `chunker/boundary/serialization.py:150` `_floats_to_strings`
   uses Python `repr(value)`, whose exponent-switch thresholds differ from a JS `Number.toString`
   canon port (`repr(1e-05)=='1e-05'` vs JS `'0.00001'`; `'1e-07'` vs `'1e-7'`). A legal semantic
   `confidence` < 1e-4 would make the `parity_digest` diverge from the TypeScript canon port — the
   exact cross-tool float divergence canon exists to prevent. Cross-Cutting Principle #1 forbids
   float-repr variance, so this is mandatory.
2. **Constant grammar-version cache key** — `chunker/boundary/adapter.py:340` `_grammar_version()`
   returns the constant `f"tree-sitter-{language}"`; pack + runtime versions are NOT in
   `BOUNDARY_CACHE_KEY_FIELDS` (`types.py:31`). An incremental recompute across a pack bump would
   reuse stale cached node records → Frankenstein IR (the golden gate only exercises the cold path).
3. **Self-referential parity proof** — `tests/test_boundary_parity_view.py` asserts equality between
   two in-process computations; there is no committed cross-tool parity golden, so parity-view drift
   is silent.

BOUNDARYFIX corrects the serializer's float stringification to a JS-Number-parity rule, adds the
real pack/runtime grammar fingerprint to the cache key, and replaces the self-referential parity
assertion with a committed golden. The phase is bounded to `chunker/boundary/` + its tests, and
regenerates the boundary goldens (the shared artifact IDENTITY consumes next). It does NOT rewrite
the canon serializer's core algorithm — these are three targeted corrections.

## Interface Freeze Gates
- [ ] IF-0-BOUNDARYFIX-1 — the corrected serializer contract: a canon float-stringification function
  (`_canon_float_str`) matching JS `Number.prototype.toString` (no Python-`repr` exponent artifacts);
  a real `grammar_version` fingerprint (pack + tree_sitter runtime version) added to
  `BOUNDARY_CACHE_KEY_FIELDS`; and a committed cross-tool parity golden that
  `tests/test_boundary_parity_view.py` compares against a stored fixture (not a second in-process run).

## Lane Index & Dependencies

SL-1 — Canon float stringification
  Depends on: (none)
  Blocks: SL-3, SL-4
  Parallel-safe: yes

SL-2 — Real grammar-version cache key
  Depends on: (none)
  Blocks: SL-4
  Parallel-safe: yes

SL-3 — Committed cross-tool parity golden
  Depends on: SL-1
  Blocks: SL-4
  Parallel-safe: yes

SL-4 — Documentation & spec reconciliation (SL-docs)
  Depends on: SL-1, SL-2, SL-3
  Blocks: (none)
  Parallel-safe: no

## Lanes

### SL-1 — Canon float stringification
- **Scope**: Replace `repr()` float stringification with a JS-Number-parity `_canon_float_str` (matching `Number.prototype.toString`: no `1e-05`/`1e-7`-style exponent artifacts for the value range canon emits), and route `_floats_to_strings` through it. Regenerate goldens affected by the corrected formatting.
- **Owned files**: `chunker/boundary/serialization.py`, `tests/test_canon_float_parity.py`
- **Interfaces provided**: IF-0-BOUNDARYFIX-1 (`_canon_float_str`)
- **Interfaces consumed**: (none)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-1.1 | test | — | `tests/test_canon_float_parity.py` | `_canon_float_str(1e-05)=='0.00001'`, `1e-07`, `1e21`, `0.1`, `-0.0`, integers-as-float match the JS `Number.toString` reference values (not Python `repr`) | `uv run --with toml --all-extras python -m pytest tests/test_canon_float_parity.py -q` |
| SL-1.2 | impl | SL-1.1 | `chunker/boundary/serialization.py` | — | — |
| SL-1.3 | verify | SL-1.2 | serializer | float parity + determinism | `uv run --with toml --all-extras python -m pytest tests/test_canon_float_parity.py tests/test_boundary_ir_determinism.py -q` |

### SL-2 — Real grammar-version cache key
- **Scope**: Make `_grammar_version()` return a real fingerprint (tree-sitter-language-pack + tree_sitter runtime versions), and add `grammar_version` (already present) plus a `runtime_version` field to `BOUNDARY_CACHE_KEY_FIELDS` so an incremental recompute across a pack/runtime bump does not reuse stale nodes.
- **Owned files**: `chunker/boundary/adapter.py`, `chunker/boundary/types.py`, `tests/test_boundary_cache_key.py`
- **Interfaces provided**: IF-0-BOUNDARYFIX-1 (real grammar_version fingerprint + cache-key fields)
- **Interfaces consumed**: (none)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-2.1 | test | — | `tests/test_boundary_cache_key.py` | the boundary cache key CHANGES when the simulated pack/runtime version changes; is STABLE for the same versions; grammar_version reflects the real pack version, not a constant | `uv run --with toml --all-extras python -m pytest tests/test_boundary_cache_key.py -q` |
| SL-2.2 | impl | SL-2.1 | `chunker/boundary/adapter.py`, `chunker/boundary/types.py` | — | — |
| SL-2.3 | verify | SL-2.2 | cache key | cache-key + conformance | `uv run --with toml --all-extras python -m pytest tests/test_boundary_cache_key.py tests/boundary_ir_conformance.py -q` |

### SL-3 — Committed cross-tool parity golden
- **Scope**: Replace the self-referential parity assertion with a committed golden fixture: `tests/test_boundary_parity_view.py` compares the computed `parity_digest`/parity-view against a stored `parity-view.golden.json` (regenerated via the sanctioned path), not against a second in-process computation.
- **Owned files**: `tests/test_boundary_parity_view.py`, `tests/fixtures/boundary_ir/parity-view.golden.json`
- **Interfaces provided**: IF-0-BOUNDARYFIX-1 (committed parity golden)
- **Interfaces consumed**: `_canon_float_str` (SL-1, so the golden reflects corrected floats)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-3.1 | test | — | `tests/test_boundary_parity_view.py` | the parity view/digest equals the committed `parity-view.golden.json`; a deliberate mutation of the parity fields fails the test | `uv run --with toml --all-extras python -m pytest tests/test_boundary_parity_view.py -q` |
| SL-3.2 | impl | SL-3.1 | `tests/fixtures/boundary_ir/parity-view.golden.json` | — | — |
| SL-3.3 | verify | SL-3.2 | parity | parity golden | `uv run --with toml --all-extras python -m pytest tests/test_boundary_parity_view.py -q` |

### SL-4 — Documentation & spec reconciliation (SL-docs)
- **Scope**: Refresh the docs catalog, document the corrected float/cache-key/parity determinism guarantees, and append post-execution amendments to the BOUNDARYFIX roadmap section if any freeze was wrong.
- **Owned files**: `README.md`, `docs/**`, `.claude/docs-catalog.json`, `specs/phase-plans-v2.md`
- **Interfaces provided**: (none)
- **Interfaces consumed**: (none)
- **Parallel-safe**: no (terminal)
- **Depends on**: SL-1, SL-2, SL-3

**Tasks**:

| Task ID | Type | Depends on | Files in scope | Action |
|---|---|---|---|---|
| SL-4.1 | docs | — | `.claude/docs-catalog.json` | Rescan via `scaffold_docs_catalog.py --rescan` (record "helper unavailable" if absent). |
| SL-4.2 | docs | SL-4.1 | `docs/**`, `README.md` | Document the JS-parity float rule, real grammar-version cache key, and committed parity golden; append `BOUNDARYFIX` to `touched_by_phases`. |
| SL-4.3 | docs | SL-4.2 | `specs/phase-plans-v2.md` | Append `### Post-execution amendments` to the BOUNDARYFIX section if any freeze was empirically wrong. |
| SL-4.4 | verify | SL-4.3 | — | Run repo doc linters if configured; else no-op. |

## Execution Notes
- **Single-writer files**: `chunker/boundary/serialization.py` (SL-1 only), `chunker/boundary/adapter.py` + `types.py` (SL-2 only), `tests/test_boundary_parity_view.py` (SL-3 only). Disjoint. Boundary GOLDENS are regenerated by SL-1 (float correction) — SL-1 owns the golden regen; SL-2/SL-3 must rebase on SL-1's regenerated goldens if their changes also move bytes.
- **Shared artifact — boundary goldens**: this phase regenerates them (via the sanctioned `scripts/regenerate_boundary_goldens.py`); IDENTITY (next phase) regenerates them again on top. BOUNDARYFIX → IDENTITY is the serialized golden-writer order (roadmap Assumption 2).
- **Known destructive changes**: none — in-place serializer/adapter edits + additive tests/fixtures. The self-referential parity assertion is replaced (not a file deletion).
- **Expected add/add conflicts**: none.
- **SL-0 re-exports**: n/a.
- **Stale-base guidance** (verbatim): Lane teammates in isolated worktrees do not see sibling merges automatically. If SL-3 finds its base is pre-SL-1, it MUST stop and report rather than committing — the orchestrator will re-spawn or rebase. Silent `git reset --hard` or `git checkout HEAD~N -- …` in a stale worktree produces commits that destroy peer-lane work on `--no-ff` merge.
- **Baseline note**: the pre-existing env-sensitive boundary golden / phase-9 docstring failures are GATES-owned baseline (recorded in the xfail inventory) — BOUNDARYFIX must not regress determinism but is not responsible for those baseline artifacts.

## Acceptance Criteria
- [ ] `_canon_float_str` matches JS `Number.prototype.toString` for the canon value range (e.g. `1e-05 -> '0.00001'`, no `1e-7` artifacts), and `_floats_to_strings` uses it — proven by `tests/test_canon_float_parity.py`.
- [ ] The boundary cache key changes when the simulated pack/runtime version changes and is stable otherwise; `_grammar_version()` reflects the real pack version — proven by `tests/test_boundary_cache_key.py`.
- [ ] `tests/test_boundary_parity_view.py` compares against a committed `parity-view.golden.json` (not a second in-process run) and a deliberate parity-field mutation fails it — proven by the parity test.
- [ ] Boundary-IR determinism holds (double-run byte identity) with the corrected floats — proven by `tests/test_boundary_ir_determinism.py`; goldens regenerated and byte-stable.

## Verification
```bash
uv run --with toml --all-extras python -m pytest tests/test_canon_float_parity.py tests/test_boundary_cache_key.py tests/test_boundary_parity_view.py -q
uv run --with toml --all-extras python -m pytest tests/test_boundary_ir_determinism.py tests/boundary_ir_conformance.py -q
uv run python -c "from chunker.boundary.serialization import _canon_float_str; assert _canon_float_str(1e-05)=='0.00001', _canon_float_str(1e-05); print('JS float parity OK')"
```

## Spec Closeout Plan
- schema: `spec_delta_closeout.v1`
- decision: `canonical_spec_update`
- target surfaces: `chunker/boundary/serialization.py`, `chunker/boundary/types.py`, boundary goldens
- evidence paths: `logs/boundaryfix-parity-golden.txt`
- redaction posture: `metadata_only`
- downstream handling: `none`

## Execution Policy
- work-unit defaults: effort=high, reason=cross-tool serializer determinism is subtly wrong-prone and byte-exact
- SL-4: effort=low, reason=docs sweep only

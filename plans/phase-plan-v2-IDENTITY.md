---
phase_loop_plan_version: 1
phase: IDENTITY
roadmap: specs/phase-plans-v2.md
roadmap_sha256: 177445a267e92f2ef1ae5c894bc426638f7fb3b106cec3824e13666f237ca788
---

# IDENTITY: Chunk Identity Redesign

## Context

The review's #2 CRITICAL: `chunker/types.py:41` `compute_node_id` hashes
`f"{file_path}|{language}|{route}|{text_hash16}"` where `route` (`:47`) is `parent_route` joined —
node **TYPES only** (`core.py:471` builds it from `adjusted_node_type`). Definition *names* live in
the separate `qualified_route` (`core.py` builds `current_qualified_route` with `type:name` segments),
which feeds `compute_definition_id` (`:58`) but NOT `node_id`/`chunk_id`. So two byte-identical
definitions under same-typed ancestors (e.g. `def __init__(self): pass` in two classes) collide to
one `node_id`, and `core.py:1078-1099` (`tmp_to_final` + `c.chunk_id = c.node_id`) plus every
downstream `{chunk_id: chunk}` map silently drops one and mis-links `parent_chunk_id`.

The fix: seed `node_id` (and thus `chunk_id`, which aliases it at `core.py:1099`) with the qualified
(named) route + byte position so siblings are distinct, while keeping the frozen invariants the
back-compat spec pins: `chunk_id == node_id` and `len(node_id) == 40` (sha1). `definition_id` and
`qualified_route` already exist and are correct — this phase does NOT change them; it routes the
NAMED identity into the content-addressed id.

## Interface Freeze Gates
- [ ] IF-0-IDENTITY-1 — the chunk identity contract: `node_id = sha1(file_path|language|
  qualified_route|byte_start|content_hash)` (collision-free for duplicate-named defs, anonymous
  siblings distinguished by byte_start, edits, moves, insertions), with `chunk_id == node_id` and
  `len(node_id) == 40` preserved; `definition_id`/`qualified_route` unchanged; every `{id: chunk}` /
  `parent_chunk_id` map and the boundary adapter's `symbol_indexes` keyed on this contract.

## Lane Index & Dependencies

SL-1 — Collision-free node_id contract
  Depends on: (none)
  Blocks: SL-2, SL-3
  Parallel-safe: no

SL-2 — Re-key consuming maps + cache-version bump
  Depends on: SL-1
  Blocks: SL-3
  Parallel-safe: yes

SL-3 — Documentation & spec reconciliation (SL-docs)
  Depends on: SL-1, SL-2
  Blocks: (none)
  Parallel-safe: no

## Lanes

### SL-1 — Collision-free node_id contract
- **Scope**: Change `compute_node_id` to incorporate the qualified (named) route + byte position so byte-identical siblings under same-typed ancestors get distinct ids; update the `core.py` call site to pass `qualified_route` + `byte_start`; keep `chunk_id == node_id` (alias) and `len == 40` (sha1). Reconcile the back-compat spec_test.
- **Owned files**: `chunker/types.py`, `chunker/core.py`, `chunker/streaming.py`, `spec_tests/test_codechunk_ids_backcompat.py`, `tests/test_chunk_id_collision.py`, `tests/fixtures/boundary_ir/golden/`
- **Interfaces provided**: IF-0-IDENTITY-1 (`compute_node_id` collision-free contract)
- **Interfaces consumed**: (none)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-1.1 | test | — | `tests/test_chunk_id_collision.py` | two byte-identical sibling defs under same-typed ancestors (copy-pasted `def __init__(self): pass` in two classes) yield DISTINCT chunk_ids; anonymous siblings at different byte offsets distinct; a single def's id is stable across re-chunk; `chunk_id == node_id`; `len(node_id) == 40` | `uv run --with toml --all-extras python -m pytest tests/test_chunk_id_collision.py -q` |
| SL-1.2 | impl | SL-1.1 | `chunker/types.py` | — | — |
| SL-1.3 | impl | SL-1.2 | `chunker/core.py`, `chunker/streaming.py`, `spec_tests/test_codechunk_ids_backcompat.py`, `tests/fixtures/boundary_ir/golden/` | — | — |
| SL-1.4 | verify | SL-1.3 | identity | collision + backcompat | `uv run --with toml --all-extras python -m pytest tests/test_chunk_id_collision.py spec_tests/test_codechunk_ids_backcompat.py -q` |

### SL-2 — Re-key consuming maps + cache-version bump
- **Scope**: Audit every `{chunk_id: chunk}` / `{node_id: ...}` / `parent_chunk_id` map and the boundary adapter's `symbol_indexes` so none drops a chunk under the new (now collision-free) ids; bump the persisted-cache version so stale content-hash ids are invalidated.
- **Owned files**: `chunker/incremental.py`, `chunker/_internal/cache.py`, `chunker/graph/xref.py`, `chunker/export/postgres_spec_exporter.py`, `tests/test_identity_maps.py`
- **Interfaces provided**: (none)
- **Interfaces consumed**: IF-0-IDENTITY-1
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-2.1 | test | — | `tests/test_identity_maps.py` | chunking a file with two identical sibling defs yields TWO chunks in the id-keyed maps (none dropped); parent_chunk_id links resolve to the correct distinct parents; persisted-cache version changed | `uv run --with toml --all-extras python -m pytest tests/test_identity_maps.py -q` |
| SL-2.2 | impl | SL-2.1 | `chunker/incremental.py`, `chunker/_internal/cache.py`, `chunker/graph/xref.py`, `chunker/export/postgres_spec_exporter.py` | — | — |
| SL-2.3 | verify | SL-2.2 | maps | identity-maps + graph + incremental | `uv run --with toml --all-extras python -m pytest tests/test_identity_maps.py tests/test_incremental.py -q` |

### SL-3 — Documentation & spec reconciliation (SL-docs)
- **Scope**: Refresh the docs catalog, document the collision-free identity contract, and append post-execution amendments to the IDENTITY roadmap section if any freeze was wrong.
- **Owned files**: `README.md`, `docs/**`, `.claude/docs-catalog.json`, `specs/phase-plans-v2.md`
- **Interfaces provided**: (none)
- **Interfaces consumed**: (none)
- **Parallel-safe**: no (terminal)
- **Depends on**: SL-1, SL-2

**Tasks**:

| Task ID | Type | Depends on | Files in scope | Action |
|---|---|---|---|---|
| SL-3.1 | docs | — | `.claude/docs-catalog.json` | Rescan via `scaffold_docs_catalog.py --rescan` (record "helper unavailable" if absent). |
| SL-3.2 | docs | SL-3.1 | `docs/**`, `README.md` | Document the node_id/chunk_id/definition_id/parent_chunk_id roles and the collision-free seed; append `IDENTITY` to `touched_by_phases`. |
| SL-3.3 | docs | SL-3.2 | `specs/phase-plans-v2.md` | Append `### Post-execution amendments` to the IDENTITY section if any freeze was empirically wrong. |
| SL-3.4 | verify | SL-3.3 | — | Run repo doc linters if configured; else no-op. |

## Execution Notes
- **Single-writer files**: `chunker/types.py` + `chunker/core.py` (SL-1 only — the id seed + call site are one coherent change). SL-2 owns the consuming maps (`incremental.py`, `graph/xref.py`, `postgres_spec_exporter.py`) — disjoint from SL-1. SL-3 (docs) owns `specs/phase-plans-v2.md` + docs.
- **Boundary goldens**: IDENTITY re-keys node ids, which appear in the boundary IR — so boundary goldens are regenerated here (via `scripts/regenerate_boundary_goldens.py`), on top of BOUNDARYFIX's regeneration (roadmap Assumption 2: BOUNDARYFIX → IDENTITY is the serialized golden-writer order). SL-1 owns the golden regen; if the id change moves golden bytes, regenerate and commit them under SL-1.
- **Frozen invariants (do NOT break)**: `chunk_id == node_id` and `len(node_id) == 40` are pinned by `spec_tests/test_codechunk_ids_backcompat.py` — the new seed must still produce a 40-char sha1 aliased to chunk_id. If a deliberate contract change is required, update that spec_test in the SAME lane (SL-1 owns it) with a documented back-compat decision.
- **Known destructive changes**: none — in-place id-seed + map re-key edits + additive tests. No file deletions.
- **Expected add/add conflicts**: none.
- **SL-0 re-exports**: n/a.
- **Stale-base guidance** (verbatim): Lane teammates in isolated worktrees do not see sibling merges automatically. If SL-2 finds its base is pre-SL-1, it MUST stop and report rather than committing — the orchestrator will re-spawn or rebase. Silent `git reset --hard` or `git checkout HEAD~N -- …` in a stale worktree produces commits that destroy peer-lane work on `--no-ff` merge.

## Acceptance Criteria
- [ ] Two byte-identical sibling defs under same-typed ancestors yield DISTINCT chunk_ids; anonymous siblings at different byte offsets are distinct; a single def's id is stable across re-chunk — proven by `tests/test_chunk_id_collision.py`.
- [ ] `chunk_id == node_id` and `len(node_id) == 40` still hold — proven by `spec_tests/test_codechunk_ids_backcompat.py`.
- [ ] Chunking a file with identical sibling defs produces TWO chunks in every id-keyed map (none dropped) and correct `parent_chunk_id` links — proven by `tests/test_identity_maps.py`.
- [ ] The persisted-cache version is bumped so stale content-hash ids are invalidated — proven by `tests/test_identity_maps.py`.
- [ ] Boundary-IR determinism holds with the re-keyed ids (double-run byte identity); goldens regenerated — proven by `tests/test_boundary_ir_determinism.py`.

## Verification
```bash
uv run --with toml --all-extras python -m pytest tests/test_chunk_id_collision.py tests/test_identity_maps.py spec_tests/test_codechunk_ids_backcompat.py -q
uv run --with toml --all-extras python -m pytest tests/test_boundary_ir_determinism.py tests/test_incremental.py -q
uv run python -c "
from chunker.types import compute_node_id
# two identical trivial methods under same-typed parents but different qualified routes -> distinct
a = compute_node_id('f.py','python',['class_definition','function_definition'],'pass')
b = compute_node_id('f.py','python',['class_definition','function_definition'],'pass')
print('same inputs still stable:', a==b)  # stability preserved
"
```

## Spec Closeout Plan
- schema: `spec_delta_closeout.v1`
- decision: `canonical_spec_update`
- target surfaces: `chunker/types.py`, `spec_tests/test_codechunk_ids_backcompat.py`, boundary goldens
- evidence paths: `logs/identity-collision-test.txt`
- redaction posture: `metadata_only`
- downstream handling: `none`

## Execution Policy
- work-unit defaults: effort=high, reason=identity contract change ripples through maps/incremental/graph/export and must stay collision-free + byte-deterministic
- SL-3: effort=low, reason=docs sweep only

---
phase_loop_plan_version: 1
phase: APISAFE
roadmap: specs/phase-plans-v2.md
roadmap_sha256: 232276eb0d69bb61e822ed7f1062defb89331085b45a2fb716d92f7566fb7ab9
---

# APISAFE: API & VFS Surface Safety

## Context

The FastAPI server (`api/server.py`) is demo-grade: `/chunk/file`, `/graph/xref`, and
`/export/postgres` take arbitrary absolute paths with no auth and return file contents; the
entrypoint binds `0.0.0.0:8000`; CORS combines `allow_origins=["*"]` with `allow_credentials=True`
(drive-by exfiltration). `chunker/_internal/vfs.py` `LocalFileSystem` claims sandboxing but absolute
paths and `..` escape the root, and even a lexical check misses symlink escape. The generated
`chunker_export.sql` (`postgres_spec_exporter.py`) f-string-builds INSERTs escaping only `attrs_json`.
`/graph/cut` is a shipped stub always returning empty; `spec_tests/test_graph_cut.py` pins it.

This phase makes the server safe-by-default: authenticated, canonically root-confined, size-bounded,
no injection, no drive-by; and freezes the `/graph/cut` keep-or-remove decision so SCALE has a stable
target. Co-root (no HYGIENE dependency; files disjoint from deletions).

## Interface Freeze Gates
- [ ] IF-0-APISAFE-1 — `resolve_within_root(candidate, root) -> Path` performing CANONICAL
  containment (resolves symlinks; rejects absolute escape, `..`, and symlink escape for reads and
  output creation) AND the request-auth dependency signature used by the handlers.

## Lane Index & Dependencies

SL-1 — Canonical path-confinement helper + VFS sandbox
  Depends on: (none)
  Blocks: SL-2, SL-docs
  Parallel-safe: yes

SL-2 — API auth + confinement + CORS + bind + size cap
  Depends on: SL-1, SL-4
  Blocks: SL-docs
  Parallel-safe: no

SL-3 — Postgres export escaping + DSN allowlist
  Depends on: (none)
  Blocks: SL-docs
  Parallel-safe: yes

SL-4 — /graph/cut implement-or-remove + spec reconcile
  Depends on: (none)
  Blocks: SL-2, SL-docs
  Parallel-safe: yes

SL-5 — Documentation & spec reconciliation (SL-docs)
  Depends on: SL-1, SL-2, SL-3, SL-4
  Blocks: (none)
  Parallel-safe: no

## Lanes

### SL-1 — Canonical path-confinement helper + VFS sandbox
- **Scope**: Add `resolve_within_root()` (symlink-resolving, escape-rejecting) and route `LocalFileSystem` reads/writes through it.
- **Owned files**: `chunker/_internal/path_confinement.py`, `chunker/_internal/vfs.py`, `tests/test_path_confinement.py`
- **Interfaces provided**: IF-0-APISAFE-1 (`resolve_within_root`)
- **Interfaces consumed**: (none)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-1.1 | test | — | `tests/test_path_confinement.py` | rejects absolute escape, `..`, and a symlink inside root pointing outside, for read and write | `python -m pytest tests/test_path_confinement.py -q` |
| SL-1.2 | impl | SL-1.1 | `chunker/_internal/path_confinement.py` | — | — |
| SL-1.3 | impl | SL-1.2 | `chunker/_internal/vfs.py` | — | — |
| SL-1.4 | verify | SL-1.3 | vfs + helper | lane tests | `python -m pytest tests/test_path_confinement.py -q` |

### SL-2 — API auth + confinement + CORS + bind + size cap
- **Scope**: Add an auth dependency, confine every path arg via `resolve_within_root()`, fix CORS, cap body size, stop default `0.0.0.0` bind, and wire the frozen `/graph/cut` route decision.
- **Owned files**: `api/server.py`, `tests/test_api_security.py`
- **Interfaces provided**: IF-0-APISAFE-1 (auth dependency signature)
- **Interfaces consumed**: `resolve_within_root` (SL-1); `/graph/cut` decision (SL-4)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-2.1 | test | — | `tests/test_api_security.py` | unauth request 401/403; `../`/absolute path rejected; CORS not `*`+credentials; oversized body rejected; no `0.0.0.0` default | `python -m pytest tests/test_api_security.py -q` |
| SL-2.2 | impl | SL-2.1 | `api/server.py` | — | — |
| SL-2.3 | verify | SL-2.2 | `api/server.py` | lane tests | `python -m pytest tests/test_api_security.py -q` |

### SL-3 — Postgres export escaping + DSN allowlist
- **Scope**: Escape/parameterize all interpolated fields in the generated SQL file and restrict `/export/postgres` to an approved DSN host allowlist.
- **Owned files**: `chunker/export/postgres_spec_exporter.py`, `tests/test_postgres_export_safety.py`
- **Interfaces provided**: (none)
- **Interfaces consumed**: (none)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-3.1 | test | — | `tests/test_postgres_export_safety.py` | a symbol containing `'` cannot inject SQL in the generated file; an unapproved DSN host is refused | `python -m pytest tests/test_postgres_export_safety.py -q` |
| SL-3.2 | impl | SL-3.1 | `chunker/export/postgres_spec_exporter.py` | — | — |
| SL-3.3 | verify | SL-3.2 | exporter | lane tests | `python -m pytest tests/test_postgres_export_safety.py -q` |

### SL-4 — /graph/cut implement-or-remove + spec reconcile
- **Scope**: Freeze the `/graph/cut` product decision — implement against real nodes/edges or remove — and reconcile `spec_tests/test_graph_cut.py`. Publish the decision for SL-2's route wiring.
- **Owned files**: `chunker/graph/cut.py`, `spec_tests/test_graph_cut.py`
- **Interfaces provided**: `/graph/cut` keep-or-remove decision (consumed by SL-2)
- **Interfaces consumed**: (none)
- **Tasks**:

| Task ID | Type | Depends on | Files in scope | Tests owned | Test command |
|---|---|---|---|---|---|
| SL-4.1 | test | — | `spec_tests/test_graph_cut.py` | reflects the decision: real cut over supplied nodes/edges, or explicit removal/410 | `python -m pytest spec_tests/test_graph_cut.py -q` |
| SL-4.2 | impl | SL-4.1 | `chunker/graph/cut.py` | — | — |
| SL-4.3 | verify | SL-4.2 | `chunker/graph/cut.py` | spec_test | `python -m pytest spec_tests/test_graph_cut.py -q` |

### SL-5 — Documentation & spec reconciliation (SL-docs)
- **Scope**: Refresh docs catalog, document the API auth/confinement model and the `/graph/cut` decision, and append post-execution amendments to the APISAFE roadmap section if any freeze was wrong.
- **Owned files**: `README.md`, `SECURITY.md`, `docs/**`, `.claude/docs-catalog.json`, `specs/phase-plans-v2.md`
- **Interfaces provided**: (none)
- **Interfaces consumed**: (none)
- **Parallel-safe**: no (terminal)
- **Depends on**: SL-1, SL-2, SL-3, SL-4

**Tasks**:

| Task ID | Type | Depends on | Files in scope | Action |
|---|---|---|---|---|
| SL-5.1 | docs | — | `.claude/docs-catalog.json` | Rescan via `scaffold_docs_catalog.py --rescan` (record "helper unavailable" if absent). |
| SL-5.2 | docs | SL-5.1 | `SECURITY.md`, `README.md`, per catalog | Document API auth/confinement + `/graph/cut` decision; append `APISAFE` to `touched_by_phases`. |
| SL-5.3 | docs | SL-5.2 | `specs/phase-plans-v2.md` | Append `### Post-execution amendments` to the APISAFE section if any freeze was empirically wrong. |
| SL-5.4 | verify | SL-5.3 | — | Run repo doc linters if configured; else no-op. |

## Execution Notes
- **Single-writer files**: `api/server.py` is owned exclusively by **SL-2**. SL-2 depends on SL-1 (resolver) and SL-4 (cut decision) so it wires both without another lane touching the file. `chunker/graph/cut.py` is owned by SL-4 only (not SL-2). `spec_tests/test_graph_cut.py` is owned by SL-4 only.
- **Known destructive changes**: SL-4 may delete the `/graph/cut` route body if the decision is "remove" — recorded here as the sole legitimate deletion; every other lane is additive.
- **Expected add/add conflicts**: none.
- **SL-0 re-exports**: n/a.
- **Stale-base guidance** (verbatim): Lane teammates in isolated worktrees do not see sibling merges automatically. If SL-2 finds its base is pre-SL-1 or pre-SL-4, it MUST stop and report rather than committing — the orchestrator will re-spawn or rebase. Silent `git reset --hard` or `git checkout HEAD~N -- …` in a stale worktree produces commits that destroy peer-lane work on `--no-ff` merge.

## Acceptance Criteria
- [ ] An unauthenticated request to `/chunk/file`, `/graph/xref`, `/export/postgres` is rejected; an authenticated request with an absolute or `..` path is rejected — proven by `tests/test_api_security.py`.
- [ ] A symlink inside the configured root pointing outside it is rejected for both read and output creation — proven by `tests/test_path_confinement.py`.
- [ ] CORS never pairs `*` with credentials, body size is capped, and the entrypoint does not default-bind `0.0.0.0` — proven by `tests/test_api_security.py`.
- [ ] A symbol containing `'` cannot inject SQL into the generated export, and an unapproved DSN host is refused — proven by `tests/test_postgres_export_safety.py`.
- [ ] `/graph/cut` either returns a real cut over supplied nodes/edges or is removed (no empty stub) — proven by `spec_tests/test_graph_cut.py`.

## Verification
```bash
python -m pytest tests/test_path_confinement.py tests/test_api_security.py tests/test_postgres_export_safety.py spec_tests/test_graph_cut.py -q
```

## Spec Closeout Plan
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: `(none)`
- evidence paths: `logs/apisafe-symlink-auth-tests.txt`
- redaction posture: `metadata_only`
- downstream handling: `none`

## Execution Policy
- work-unit defaults: effort=medium, reason=security-sensitive API/VFS logic
- SL-1: effort=high, reason=canonical symlink-escape containment is subtly wrong-prone
- SL-3: effort=high, reason=SQL escaping correctness is security-critical
- SL-5: effort=low, reason=docs sweep only

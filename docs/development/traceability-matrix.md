# Remediation Traceability Matrix (v3.2.2 review → phases → tests)

Maps every CRITICAL and MAJOR finding from `CODE_REVIEW_v3.2.2.md` to the phase
that fixed it and the test(s) that prove it. RELEASE gate rule: no CRITICAL- or
MAJOR-linked finding may remain unmapped or covered only by a quarantined
xfail/skip.

## CRITICAL

| ID | Finding | Phase(s) | Proof test(s) | Status |
|----|---------|----------|---------------|--------|
| C1 | Shared tree-sitter Parser across threads → UB/segfault | PARSER (primitive) + SCALE SL-1/SL-7 (holder migration) | `tests/test_scale_parser_holders.py` (8 threads → 8 distinct parsers per holder); PARSER thread-local suite | ✅ Fixed |
| C2 | `chunk_id` collisions silently drop chunks | IDENTITY | `tests/test_chunk_id_collision.py` (content+position-seeded, collision-free) | ✅ Fixed |
| C3 | Mixed-language processing never worked (TypeError) | SCALE SL-3 | `tests/test_multilang_vfs.py::TestProcessMixedFile` (+ multibyte offset + node_id-distinct) | ✅ Fixed |
| C4 | VFS large-file streaming doubly broken (AttributeError + dup offsets) | SCALE SL-3 | `tests/test_multilang_vfs.py::TestVFSStreaming` (local >2MB + zip, non-dup file-relative offsets) | ✅ Fixed |
| C5 | Unauthenticated FastAPI = arbitrary file read + SSRF | APISAFE | API auth + confined-LocalFileSystem path tests (`tests/test_postgres_export_safety.py`, api server tests) | ✅ Fixed |
| C6 | Determinism pin-mirror drifted (gate false-green) | SUPPLY + CONFORMANCE | conformance/pack-pin tests; canon determinism double-run | ✅ Fixed |
| C7 | Quality gates hollow (ruff downgraded, mypy warning-only) | GATES | `scripts/mypy_gate.py` (baseline-relative, blocking); ruff F-rules on | ✅ Fixed |

## MAJOR

| Finding | Phase | Proof test(s) | Status |
|---------|-------|---------------|--------|
| Fallback almost never fires; invalid-UTF-8 crashes | COREFIX | `tests/test_fallback_robustness.py` | ✅ Fixed |
| Boundary `_grammar_version()` constant → cache poisoning | BOUNDARYFIX | boundary serialization/determinism tests | ✅ Fixed |
| `streaming.py` hardcodes Python node types → silent empty | SCALE SL-2 | `tests/test_streaming_languages.py` (Rust/Go/JS non-empty + explicit error) | ✅ Fixed |
| No integrity gate between grammar download and execution | SUPPLY | grammar-install hardening tests | ✅ Fixed |
| `export/formats/json.py` `gzip.Path` → compress=True broken | IFACE | `tests/test_export_json.py::test_structured_json_exporter_compress_writes_gzip` | ✅ Fixed |
| ~45–55k LOC dead phase-scaffolding shipped in the wheel | HYGIENE | surface-reduction / dead-code removal | ✅ Fixed |
| `leidenalg.find_partition` unseeded; `graph/xref` O(n²) | SCALE SL-4 | `tests/test_scale_graph_determinism.py` (seeded clusters, deterministic cut, index-based xref) | ✅ Fixed |
| Boundary serializer can emit bare `NaN` (invalid JSON) | BOUNDARYFIX | boundary canon serializer tests (`allow_nan=False`, `_canon_float_str`) | ✅ Fixed |

## Additional correctness work (panel-found, beyond the original review)

| Item | Phase | Proof |
|------|-------|-------|
| Class token-split spans must slice back to content (byte-offset contract) | COREFIX | `tests/test_corefix_iter3_residuals.py` |
| Mixed-lang char-vs-byte offset + node_id recompute | SCALE (panel fix) | `tests/test_multilang_vfs.py::test_multibyte_prefix_offsets_slice_back_and_ids_distinct` |
| `repo.ignored` ARG_MAX crash on large repos | SCALE (panel fix) | `tests/test_repo_processor_lifecycle.py` batched-ignore |
| Watch stale-commit silent data loss | SCALE (panel fix) | `tests/test_repo_processor_lifecycle.py::TestWatchStaleCommitFullScan` |
| Public `chunk_text` nondeterministic node_ids (temp round-trip) | IFACE | `tests/test_iface_public_chunk_text.py` |
| `.ts` mis-resolved to javascript in CLI | IFACE | `tests/test_iface_cli_detection.py` |
| Version single-source (stale 1.0.8 / 2.0.0 mirrors) | IFACE | `tests/test_iface_version_single_source.py` |

## Tracked residuals (documented, not silently skipped)

See `docs/development/xfail-inventory.md`:
- COREFIX fallback residuals: fallback `definition_id` collision, CSV slice-back, fallback O(n²) prefix rescans.
- SCALE streaming special-case node adjustments (Dart/R/Elixir/Svelte) — strict improvement over prior silent-empty.
- IFACE residual: CLI-stack consolidation + parquet-exporter dedup (internal refactors; scan-confirmed no external consumer).
- IDENTITY overload edge disambiguation (needs semantic resolver).
- mypy type-debt baseline (1241 signatures, baseline-relative gate).

## Deferred MAJOR (recorded, not a silent gap)

- **Config-system unification** — explicitly a Non-Goal of IFACE; deferred to a future config phase. Recorded here per the RELEASE traceability rule so it is not mistaken for coverage.

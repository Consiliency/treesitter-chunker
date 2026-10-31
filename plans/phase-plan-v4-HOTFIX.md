---
phase_loop_plan_version: 1
phase: HOTFIX
roadmap: specs/phase-plans-v4.md
roadmap_sha256: 44ce0acdaaed7e71fcf3df350331985f3ecf6c3af26a074c117961dd49d8cc6a
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_parallel_cache_identity.py tests/test_cache.py tests/test_user_grammar_publication.py tests/test_grammar_management.py tests/test_compiled_grammar_analysis_contract.py -q"
---

# HOTFIX: Tier 1 independent correctness repairs

## Context

Phase 2 of `specs/phase-plans-v4.md` (roadmap hash above, main `7440971a`)
lands two repairs that need no new shared design, plus a dependent coverage
slice:

- treesitter-chunker#358: the parallel helpers' SQLite chunk cache
  (`chunker/_internal/cache.py`) returned core chunks for a streaming request,
  and the reverse, and reused entries across runtime/grammar upgrades. Its
  entries were keyed only by path, language, content hash, mtime and
  `CACHE_VERSION`.
- treesitter-chunker#162: `UserGrammarTools.install_grammar` and
  `update_grammar` used `shutil.copy2` to overwrite `<language>.so` in place.
  That truncated a file a process could still have mapped, so the process
  could crash with SIGSEGV.
- treesitter-chunker#69 slice 17: the `cli/grammar_commands.py` command
  contract, which waited only on treesitter-chunker#162.

Status inputs at planning time: treesitter-chunker#534 and
treesitter-chunker#535 are merged; treesitter-chunker#435 and
treesitter-chunker#389 are closed. HOTFIX has no upstream phase. It produces
IF-0-HOTFIX-1, which TXNSPEC adopts for its restore path. TXN depends on this
phase closing.

The AST cache is deliberately not gated on the TXNSPEC transaction protocol. It
uses a different store, and its defect is entry identity, not writer/deleter
coordination. `chunker/boundary/cache.py` is out of scope.

## Interface Freeze Gates

- [ ] IF-0-HOTFIX-1 — staged same-directory native publication, published on
  day 1 in the treesitter-chunker#162 PR body under `IF-0-HOTFIX-1 signature`.

Module `chunker/_internal/user_grammar_tools.py`:

`publish_native_grammar(source: Path, destination: Path, language: str, *, provenance: Mapping[str, Any] | None, sample: bytes = b"", timeout: float = 10.0) -> NativeProbeResult`

1. Copy `source`'s bytes into a new sibling temporary file in
   `destination.parent` (`mkstemp`, prefix `.<stem>-`, suffix
   `.staged<suffix>`). Fsync it and copy `source`'s mode bits.
2. Admit the staged file with `probe_native_grammar`, passing the caller's
   single-language `provenance` record, `sample` and `timeout`. No other pin
   source is consulted, and there is no trust-all switch.
3. Only an admitted file is moved over `destination` with `os.replace`
   (`Path.replace`). The existing file is never opened for writing or
   truncated, and a symlink at `destination` is replaced, not followed.
4. Return the `NativeProbeResult`. On rejection, the staged file is removed
   and `destination` is left unchanged.
5. `OSError` from staging or replacement propagates after the staged file is
   removed. Windows raises here when a process has the destination loaded.
6. Callers invalidate their caches. `UserGrammarTools` drops the manager's
   `health_cache` and `compatibility_cache` entries for the language after
   every publication attempt.

A process that already loaded the old library keeps its mapping. Loading the
same path again in that process returns the existing handle; a new process
(including the admission probe child) loads the new file.

Cache identity (SL-1, internal to `chunker/_internal/cache.py`, not a phase
gate): `chunk_cache_identity(language, extraction="core") -> str` returns a
SHA-256 over these fields:

- `CACHE_VERSION`;
- the extraction mode (`core` or `streaming`; anything else raises `ValueError`);
- the `treesitter-chunker`, `tree-sitter` and `tree-sitter-language-pack`
  distribution versions;
- the grammar ABI, node-kind count, symbol name and `grammar_source`
  provenance from `get_language_info`.

`ASTCache.get_cached_chunks` and `cache_chunks` take keyword-only
`extraction="core"`. Entries live in a new `chunk_cache` table whose primary key
is `(file_path, language, extraction_identity)`. `CACHE_VERSION` is `3.0`. The
legacy `file_cache` table is never read, migrated or modified.
`ParallelChunker`, `chunk_files_parallel` and `chunk_directory_parallel` accept
`cache_dir=`.

## Lane Index & Dependencies

SL-1 — Parallel cache entry identity (treesitter-chunker#358)
  Depends on: (none)
  Blocks: (none)
  Parallel-safe: yes (disjoint files from SL-2)

SL-2 — Staged native publication (treesitter-chunker#162)
  Depends on: (none)
  Blocks: SL-17
  Parallel-safe: yes (disjoint files from SL-1)

SL-17 — treesitter-chunker#69 slice 17 grammar command contract
  Depends on: SL-2, and (see Execution Notes) ADMIT's production pin source
  Blocks: (none)
  Parallel-safe: no

## Lanes

### SL-1 — Parallel cache entry identity

- **Scope**: Key chunk-cache entries by extraction mode and runtime/grammar
  pairing, bump `CACHE_VERSION`, expose a caller cache directory and document
  migration. One PR.
- **Owned files**: `chunker/_internal/cache.py`, `chunker/parallel.py`,
  `tests/test_parallel_cache_identity.py`, `tests/test_cache.py`,
  `tests/test_identity_maps.py` (the `CACHE_VERSION` assertion only),
  `tests/test_benchmark_examples.py` (the table name in one SQL probe only),
  `docs/performance-guide.md`, `docs/api-reference.md`,
  `docs/architecture.md`, `CHANGELOG.md`, and the SL-1 entry in
  `scripts/run_platform_core.py`.
- **Tasks**:
  - test: Using real process workers, an isolated `HOME`/`USERPROFILE` and the
    checked-in `tests/fixtures/boundary_ir/repos/python/app/service.py`, warm
    core then request streaming, and the reverse. Each result must equal
    uncached output for the requested mode. Both entries are reused for their
    own mode, proven by re-storing annotated chunks.
  - test: Entries written under a different chunker, Tree-sitter or
    language-pack version, or a different grammar provenance, are not
    returned. Only the version/metadata lookup is substituted; the parser and
    workers are real.
  - test: With `cache_dir=` and a temporary home, the only file written is
    `<cache_dir>/ast_cache.db` and the home stays empty. A legacy `file_cache`
    row is ignored and left intact. An unknown extraction mode is rejected.
  - impl: Add the identity and new table, thread `extraction=` and
    `cache_dir=` through the parallel helpers, and document the identity, its
    limits (runtime language-config/plugin changes and rebuilt custom grammars
    with unchanged ABI, counts and provenance) and the 2.0→3.0 upgrade path.

### SL-2 — Staged native publication

- **Scope**: IF-0-HOTFIX-1 and its use by `install_grammar` and
  `update_grammar`. One PR, opened as a draft as soon as the signature was
  settled.
- **Owned files**: `chunker/_internal/user_grammar_tools.py`,
  `tests/test_user_grammar_publication.py`, the install/update cases in
  `tests/test_grammar_management.py` and
  `tests/test_compiled_grammar_analysis_contract.py`,
  `docs/grammar_management.md`,
  `docs/development/native-validation-contract.md`, `CHANGELOG.md`, the SL-2
  entry in `scripts/run_platform_core.py`, and this plan.
- **Tasks**:
  - test: Compile two real BAML revisions from
    `packages/baml-grammar/src/parser.c`: 0.1.0, and 0.2.0 with relocated code.
    In a fresh `-I` subprocess with stubbed Git/generator commands, install A,
    load it in-process, update to B and keep parsing with the A parser. Assert
    exit 0 (not SIGSEGV), a new inode, B's digest, healthy B admission, no
    staged leftovers, and that a fresh process parses the fixture with
    semantic version 0.2.0. On Windows, assert the refused-replacement error
    and the unchanged A library.
  - test: Update without an in-process load. Update with a stale pin (no
    publication, same inode). A symlink destination is replaced without
    writing its target (POSIX only).
  - impl: Add `publish_native_grammar` and use it for both copy sites. Map
    rejection and `OSError` to `error` results that say the installed library
    is unchanged, and invalidate the manager caches.
  - docs: Record the consumer impact. Unadmitted libraries, including unpinned
    ones, are no longer copied, so the legacy `grammar install`/`update` exit 1
    for new or changed libraries until treesitter-chunker#362 adds a CLI pin
    source.

### SL-17 — treesitter-chunker#69 slice 17

- **Scope**: The test-only command contract from
  `plans/detailed-coverage-contract-slices-20261001.md`: "a local installed
  grammar is listed/validated and a missing grammar produces a nonzero command
  result", with mutation **return success for failed grammar validation**.
- **Disposition**: re-placed after ADMIT; not executed in HOTFIX (see
  Execution Notes).

## Execution Notes

- Execute SL-1 and SL-2 in parallel on separate branches off `origin/main`,
  one issue per PR. The parent runs the two-reviewer panel (VB-4); the
  execution agent does not merge or request reviews.
- **SL-17 re-placement (EC-HOTFIX-3).** `chunker/cli/grammar_commands.py`
  `get_grammar_tools()` constructs `UserGrammarTools(build_dir, grammars_dir)`
  with no `trusted_artifacts`. Under the SAFELOAD contract an unpinned library
  is never `healthy`, so `grammar validate` cannot return 0 for any real local
  grammar, whatever treesitter-chunker#162 does. The slice's "listed/validated"
  contract therefore needs a healthy production result, which only the ADMIT
  production pin source (IF-0-ADMITPIN-1/IF-0-ADMIT-1) can supply. Patching
  `get_grammar_tools` or asserting the failure instead would weaken the
  contract. Slice 17 is re-placed to run after ADMIT; RECORDS reports this
  outcome.
- Host caps: one heavy run at a time per agent, at least 6 GiB available
  before a heavy run, `pytest -n` at most 4, and scratch under `$TMPDIR` that
  is removed in `finally`. `scripts/run_ci_smoke.py` hard-codes `-n auto`, so
  local smoke runs its `CI_SMOKE_TESTS` selection with `-n 4` instead; each PR
  records that substitution.
- Native subprocess tests count toward the heavy-run cap.

## Verification

- `uv run --locked --all-extras pytest tests/test_parallel_cache_identity.py tests/test_cache.py tests/test_parallel.py tests/test_benchmark_examples.py tests/test_identity_maps.py -q`
- `uv run --locked --all-extras pytest tests/test_user_grammar_publication.py tests/test_grammar_management.py tests/test_compiled_grammar_analysis_contract.py tests/test_native_grammar_library_contract.py -q -n 4`
- The CONTRIBUTING.md local validation block (Ruff, Black, mypy gate,
  governed body-type check, and the CI smoke selection at `-n 4`).
- treesitter-chunker#162: the standing Windows preflight run on the PR head,
  plus hosted Linux/macOS/Windows platform-core, which now enrolls both new
  test files.

Named mutations (each fails its focused test and passes once restored):

1. `M358-mode` — drop the extraction mode from the identity payload: both
   order tests, own-mode reuse and the cache-dir row check fail.
2. `M358-runtime` — drop the chunker/Tree-sitter/language-pack versions: the
   three other-runtime-pairing cases fail.
3. `M358-grammar` — drop grammar provenance: the other-provenance case fails.
4. `M358-cachedir` — ignore `cache_dir` (`ASTCache()`): confinement and reuse
   tests fail.
5. `M162-inplace` — restore `shutil.copy2(staged, destination)` in place of
   `os.replace`: the loaded-update child exits with SIGSEGV (-11), and the
   new-inode and symlink cases fail.

## Acceptance Criteria

- [ ] EC-HOTFIX-1 — treesitter-chunker#358, by
  `tests/test_parallel_cache_identity.py`; falsified by mutations 1–4.
- [ ] EC-HOTFIX-2 — treesitter-chunker#162, by
  `tests/test_user_grammar_publication.py`; falsified by `M162-inplace`.
- [ ] EC-HOTFIX-3 — slice 17 re-placed after ADMIT with the reason recorded
  above, rather than weakened.
- [ ] EC-HOTFIX-4 — VB-1 to VB-4 for each PR. treesitter-chunker#162 has the
  Windows preflight and hosted macOS/Windows evidence.

## Spec Closeout Plan

- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: issue acceptance for treesitter-chunker#358,
  treesitter-chunker#162, treesitter-chunker#69
- evidence paths: `plans/phase-plan-v4-HOTFIX.md`, PR verification logs
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`

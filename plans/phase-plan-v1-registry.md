# REGISTRY: Tree-Sitter Registry Compatibility Hardening

## Context

Roadmap source: `specs/phase-plans-v1.md`, Phase 8. The roadmap file is
tracked with staged modifications in this working tree (`M  specs/phase-plans-v1.md`),
so it is not an untracked `git clean -fd` risk; Phase 8 execution should
preserve those user-owned roadmap edits.

Phase 8 follows the Phase 7 release hygiene gate. The current Phase 7 plan
freezes warning policy as local assertions with no broad warning suppression,
so Phase 8 should make parser registry code clean under
`-W error::DeprecationWarning` rather than hiding tree-sitter warnings.

Current repo inspection found local compiled grammar construction in
`chunker/_internal/registry.py` through repeated `Language(lang_ptr)` calls in
validation, combined-library discovery, and individual-library loading. The
same registry also controls the final `tree-sitter-language-pack` fallback used
by `ParserFactory`, `chunker.parser`, CLI chunking, and Boundary IR golden
fixture extraction. The local environment has `tree-sitter` 0.24.0 and
`tree-sitter-language-pack` 0.9.0 installed; GitHub workflows also attempt to
install py-tree-sitter from `v0.25.2`. A PMCP Context7 check of current
py-tree-sitter docs showed grammar package loading through
`Language(package.language())`, while this repository must keep supporting
local compiled grammar symbols through `ctypes` and the language pack fallback.

This planning run did not execute tests, builds, formatters, generators,
grammar rebuilds, or preflight commands.

## Interface Freeze Gates

- [ ] IF-0-REGISTRY-9 -- Tree-sitter registry compatibility contract avoids deprecated local grammar construction paths while preserving language-pack fallback.
- [ ] IF-0-REGISTRY-9A -- Every local compiled grammar `Language` construction in `LanguageRegistry` goes through exactly one private helper, `LanguageRegistry._language_from_ctypes_symbol(...)`; no other `Language(...)` call remains in `chunker/_internal/registry.py`.
- [ ] IF-0-REGISTRY-9B -- `_language_from_ctypes_symbol(...)` accepts a loaded `ctypes.CDLL`, a tree-sitter symbol name, the library path, and the logical language name; it configures the symbol return type, rejects null language pointers, returns a `tree_sitter.Language`, and emits no `DeprecationWarning` under supported local and CI tree-sitter versions.
- [ ] IF-0-REGISTRY-9C -- `_validate_language_library()` returns `False` for local symbol, load, ABI, null-pointer, or deprecation failures and does not cache or publish that language as locally available solely because the deprecated construction path was attempted.
- [ ] IF-0-REGISTRY-9D -- `discover_languages()`, `has_language()`, and `get_language()` preserve the resolution order: local combined or per-language compiled grammar first, `tree-sitter-language-pack` as final fallback, then `LanguageNotFoundError` for unavailable languages.
- [ ] IF-0-REGISTRY-9E -- Local compiled grammar failures do not poison `LanguageRegistry._languages`; if a local grammar cannot be constructed cleanly, subsequent `has_language()` and `get_language()` calls still try `tree-sitter-language-pack`.
- [ ] IF-0-REGISTRY-9F -- `ParserFactory.get_parser()` and `chunker.parser.get_parser()` preserve public exceptions, alias normalization, parser config validation, cache behavior, and the existing incompatible-grammar fallback to `tree-sitter-language-pack`.
- [ ] IF-0-REGISTRY-9G -- Focused registry, factory, parser creation, CLI chunking, and Boundary IR golden snapshot coverage passes with `-W error::DeprecationWarning`.
- [ ] IF-0-REGISTRY-9H -- Phase 8 does not rebuild grammar artifacts as part of normal tests, remove `tree-sitter-language-pack`, change Boundary IR schema/golden semantics except for reviewed parser-availability effects, or add broad warning filters.

## Lane Index & Dependencies

- SL-0 -- Registry compatibility helper; Depends on: (none); Blocks: SL-1, SL-2, SL-3, SL-4; Parallel-safe: no
- SL-1 -- Parser factory and parser API propagation; Depends on: SL-0; Blocks: SL-2, SL-3, SL-4; Parallel-safe: no
- SL-2 -- CLI chunking and Boundary IR smoke coverage; Depends on: SL-0, SL-1; Blocks: SL-3, SL-4; Parallel-safe: yes
- SL-3 -- CI, platform-core, and Windows preflight coverage; Depends on: SL-0, SL-1, SL-2; Blocks: SL-4; Parallel-safe: no
- SL-4 -- Registry compatibility docs and release guidance; Depends on: SL-0, SL-1, SL-2, SL-3; Blocks: (none); Parallel-safe: no

## Lanes

### SL-0 -- Registry Compatibility Helper

- **Scope**: Centralize local compiled grammar construction and make registry fallback semantics warning-clean and non-poisoning.
- **Owned files**: `chunker/_internal/registry.py`, `tests/test_registry_fallback.py`, `tests/test_registry.py`
- **Interfaces provided**: `LanguageRegistry._language_from_ctypes_symbol(...)`; IF-0-REGISTRY-9A through IF-0-REGISTRY-9E; warning-clean local registry construction contract
- **Interfaces consumed**: existing `LanguageRegistry._load_library()`, `_discover_symbols()`, `_scan_directory_for_languages()`, `_validate_language_library()`, `_try_load_from_individual_library()`, `_try_load_from_language_pack()`, `_languages` metadata cache, `LanguageMetadata`, `LanguageNotFoundError`, `tree_sitter.Language`, `tree_sitter.Parser`
- **Parallel-safe**: no
- **Tasks**:
  - test: add focused registry tests that run representative `LanguageRegistry` local validation, `has_language("python")`, `get_language("python")`, and invalid-language paths under `pytest.mark.filterwarnings("error::DeprecationWarning")` or an equivalent scoped warning-error assertion.
  - test: add or adjust a regression test where a mocked local compiled grammar path raises a `DeprecationWarning` or construction failure and the registry still falls through to `tree-sitter-language-pack` without marking the language unavailable.
  - test: update stale registry unit expectations only where they conflict with the current missing-combined-library fallback contract; do not reintroduce a hard `LibraryNotFoundError` for missing default dev libraries.
  - impl: introduce `LanguageRegistry._language_from_ctypes_symbol(...)` near the other local library helpers, with path/name context used only for diagnostics and logging.
  - impl: replace every local `Language(lang_ptr)` construction in `chunker/_internal/registry.py` with the helper, including `_validate_language_library()`, combined-library discovery, and `_try_load_from_individual_library()`.
  - impl: ensure `_validate_language_library()` returns `False` on helper failure and leaves `_languages` untouched.
  - impl: ensure `discover_languages()` records language metadata only for clean local construction or deliberate placeholder metadata, and that placeholder metadata still permits later language-pack fallback.
  - impl: ensure `has_language()` and `get_language()` do not treat a failed local construction as terminal until `_try_load_from_language_pack()` has been attempted.
  - verify: `uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_registry_fallback.py tests/test_registry.py -q`
  - verify: `uv run --with toml --all-extras pytest tests/test_registry_fallback.py -q`

### SL-1 -- Parser Factory And Parser API Propagation

- **Scope**: Confirm parser creation paths consume the registry compatibility helper without changing public parser API behavior.
- **Owned files**: `chunker/_internal/factory.py`, `chunker/parser.py`, `tests/test_factory.py`, `tests/test_parser.py`, `tests/test_chunking.py`
- **Interfaces provided**: parser creation remains warning-clean under IF-0-REGISTRY-9F; public `get_parser()`, `list_languages()`, `get_language_info()`, `return_parser()`, and `clear_cache()` behavior remains unchanged
- **Interfaces consumed**: registry interfaces from SL-0; `ParserFactory._create_parser()`; `ParserFactory.get_parser()`; parser alias maps in `chunker/parser.py`; `tree-sitter-language-pack.get_parser()` fallback for incompatible grammar versions
- **Parallel-safe**: no
- **Tasks**:
  - test: add or adjust factory tests so `ParserFactory.get_parser("python")`, cached parser reuse, config-specific parser creation, and invalid language behavior pass under `-W error::DeprecationWarning`.
  - test: add or adjust parser API/chunking tests so `get_parser("python")`, `list_languages()`, and `chunk_file(..., "python")` pass under `-W error::DeprecationWarning`.
  - test: keep invalid language assertions expecting `LanguageNotFoundError` and available-language guidance, not parser initialization errors caused by local fallback attempts.
  - impl: avoid changing factory/cache/pool semantics unless the registry helper changes the type or exception shape returned by `get_language()`.
  - impl: if `ParserFactory._create_parser()` needs to distinguish local deprecation/ABI failures from real parser config failures, route only compatibility failures to the existing language-pack fallback and keep `ParserInitError` for true parser initialization failures.
  - impl: keep parser alias normalization local to `chunker/parser.py` and do not add new language aliases as part of this phase.
  - verify: `uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_factory.py tests/test_parser.py tests/test_chunking.py -q`
  - verify: `uv run --with toml --all-extras pytest tests/test_factory.py tests/test_chunking.py -q`

### SL-2 -- CLI Chunking And Boundary IR Smoke Coverage

- **Scope**: Exercise user-facing parser paths and Boundary IR fixture extraction under deprecation-as-error without changing export schemas.
- **Owned files**: `tests/test_cli.py`, `tests/test_boundary_ir_golden_snapshots.py`, `tests/boundary_ir_conformance.py`
- **Interfaces provided**: CLI language listing/chunking and Boundary IR golden snapshots consume warning-clean parser creation; reviewed golden snapshot updates only if parser availability changes actual canonical output
- **Interfaces consumed**: registry helper and parser behavior from SL-0 and SL-1; existing Typer `languages`, `chunk`, and `boundary` commands; `P0_BOUNDARY_LANGUAGES`; `extract_fixture_ir()`; `normalize_ir_for_golden()`
- **Parallel-safe**: yes
- **Tasks**:
  - test: add or adjust CLI tests for `languages` and a minimal Python chunking invocation under `-W error::DeprecationWarning`.
  - test: run Boundary IR golden snapshot extraction under `-W error::DeprecationWarning` so local registry warnings cannot be hidden behind snapshot comparison.
  - test: preserve the existing Go optional-grammar skip in `tests/boundary_ir_conformance.py`; do not convert optional grammar absence into failure.
  - impl: keep CLI command behavior unchanged unless warning-clean parser creation exposes a real command bug.
  - impl: do not update golden JSON snapshots unless execution produces a reviewed, deterministic parser-availability change; if snapshots are updated, document the exact parser/version reason in the execution summary.
  - impl: do not change Boundary IR schema, serialization ordering, metrics, diagnostics, or semantic enrichment behavior in this phase.
  - verify: `uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_cli.py tests/test_boundary_ir_golden_snapshots.py -q`
  - verify: `uv run --with toml --all-extras pytest tests/test_cli.py tests/test_boundary_ir_golden_snapshots.py -q`

### SL-3 -- CI, Platform-Core, And Windows Preflight Coverage

- **Scope**: Keep the standing validation batches aligned with the registry hardening behavior and avoid discovering platform failures first in GitHub Actions.
- **Owned files**: `scripts/run_ci_smoke.py`, `scripts/run_platform_core.py`, `scripts/run_windows_preflight.py`, `tests/test_cicd_pipeline.py`
- **Interfaces provided**: CI smoke, Linux platform-core, and Windows preflight continue to include registry/factory/fallback coverage relevant to IF-0-REGISTRY-9
- **Interfaces consumed**: warning-clean registry/factory/CLI/Boundary IR checks from SL-0 through SL-2; AGENTS local-first validation commands; current GitHub `CI` and `Test Suite` workflow split
- **Parallel-safe**: no
- **Tasks**:
  - test: review `CI_SMOKE_TESTS`, platform-core tests, and Windows preflight tests for existing registry/factory/CLI coverage before adding new entries.
  - test: if a focused warning-clean test is added in a new file, add that file to the smallest standing batch that must guard the release gate and update `tests/test_cicd_pipeline.py` accordingly.
  - impl: keep existing script order and `uv run` compatibility; do not turn these scripts into broad full-suite runners.
  - impl: do not add grammar rebuild steps to smoke/preflight scripts; grammar fetching/building remains workflow or explicit developer setup, not normal test execution.
  - impl: if no script changes are needed, record that decision in execution closeout after verifying the existing batches already include `tests/test_registry_fallback.py`, `tests/test_factory.py`, `tests/test_cli.py`, and `tests/test_boundary_ir_golden_snapshots.py` where appropriate.
  - verify: `uv run --with toml --all-extras pytest tests/test_cicd_pipeline.py -q`
  - verify: `uv run --with toml --all-extras python scripts/run_platform_core.py --platform linux`
  - verify: `uv run --with toml --all-extras python scripts/run_ci_smoke.py`

### SL-4 -- Registry Compatibility Docs And Release Guidance

- **Scope**: Update or consciously skip docs and release guidance after the runtime and validation contracts are settled.
- **Owned files**: `docs/grammar_management.md`, `docs/troubleshooting.md`, `docs/development/RELEASE_CHECKLIST.md`
- **Interfaces provided**: maintainer-facing guidance for tree-sitter registry compatibility, deprecation-as-error validation, and language-pack fallback expectations
- **Interfaces consumed**: implementation outcome and validation commands from SL-0 through SL-3; Phase 7 warning policy; existing grammar management and troubleshooting docs
- **Parallel-safe**: no
- **Tasks**:
  - test: no docs-only test is required unless execution changes docs navigation or link targets; rely on MkDocs strict build in whole-phase verification.
  - impl: update grammar management or troubleshooting docs only if Phase 8 changes user-visible guidance for compiled local grammars, ABI/deprecation failures, or the language-pack fallback order.
  - impl: update the release checklist with the Phase 8 focused deprecation-as-error commands if those commands become part of release validation.
  - impl: if docs do not need changes, record the no-docs-change decision after reviewing the outputs from SL-0 through SL-3.
  - impl: do not document standalone grammar-package dependencies as required; `tree-sitter-language-pack` remains the supported final fallback.
  - verify: `uv run --with toml --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict`

## Verification

Lane-specific verification is listed in each lane. After all lanes are
integrated, run the focused warning-clean commands first:

```bash
uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_registry_fallback.py tests/test_registry.py -q
uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_factory.py tests/test_parser.py tests/test_chunking.py -q
uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_cli.py tests/test_boundary_ir_golden_snapshots.py -q
```

Then run the repo-standard validation sequence from `AGENTS.md`:

```bash
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
```

Because Phase 8 changes parser registry behavior that is explicitly covered by
the platform-core and Windows preflight lanes, also run:

```bash
uv run --with toml --all-extras python scripts/run_platform_core.py --platform linux
ssh leno 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
```

If docs are changed, run the MkDocs strict build:

```bash
uv run --with toml --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict
```

## Acceptance Criteria

- [ ] All local compiled grammar `Language` construction in `LanguageRegistry` goes through `LanguageRegistry._language_from_ctypes_symbol(...)`.
- [ ] No `DeprecationWarning` is emitted by registry, factory, parser creation, CLI chunking, or Boundary IR golden snapshot extraction under the focused `-W error::DeprecationWarning` commands.
- [ ] Local compiled grammar validation does not mark a language unavailable solely because a deprecated construction path or local construction failure was attempted.
- [ ] `tree-sitter-language-pack` remains the final fallback for available languages when local compiled grammars are missing, incompatible, or warning-unsafe.
- [ ] Invalid languages still raise `LanguageNotFoundError` with available-language guidance.
- [ ] `ParserFactory` cache/pool/config behavior and `chunker.parser` public API behavior remain backward-compatible.
- [ ] CLI `languages` and Python chunking coverage still pass.
- [ ] Boundary IR golden snapshots remain deterministic; any snapshot updates are reviewed and justified by parser availability, not schema drift.
- [ ] No grammar artifacts are rebuilt or committed as part of normal Phase 8 tests.
- [ ] No broad warning filters, global `filterwarnings`, xfail markers, or xpass-dependent release gates are introduced.
- [ ] Linux platform-core and Windows preflight pass after registry changes.
- [ ] Phase 8 does not remove `tree-sitter-language-pack`, add standalone grammar package requirements, broaden parser management beyond compatibility hardening, bump the package version, or publish a release.

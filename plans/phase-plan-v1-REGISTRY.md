---
phase_loop_plan_version: 1
phase: REGISTRY
roadmap: specs/phase-plans-v1.md
roadmap_sha256: ed2f074348a946a5642d1e02904b35ac4076153923aa5932623c28d304c494a2
---

# REGISTRY: Tree-Sitter Registry Compatibility Hardening

## Context

Roadmap source: `specs/phase-plans-v1.md`, Phase 8 (`REGISTRY`). Canonical
runner state in `.phase-loop/state.json` marks `HYGIENE` complete, `REGISTRY`
as the current unplanned phase, and the repo clean on `main` at
`7b866676a272dcf5d25358d2cfc1014c24796b15` with no dirty paths. The roadmap
file is tracked, unmodified in the current worktree, and its live SHA-256
matches the required planning hash
`ed2f074348a946a5642d1e02904b35ac4076153923aa5932623c28d304c494a2`.

This repo is no longer at a blank Phase 8 starting point. `chunker/_internal/registry.py`
already contains a private `_language_from_ctypes_symbol(...)` helper that wraps
local grammar pointers through a `PyCapsule` before constructing
`tree_sitter.Language`, and the standing release guidance already lists the
focused `-W error::DeprecationWarning` commands. Execution for this phase should
therefore be a verification-and-tightening pass over the live registry,
fallback, parser, CLI, and standing-validation surfaces rather than a broad
greenfield rewrite.

The remaining risk is consistency, not concept discovery: every local compiled
grammar construction path must still flow through the compatibility helper,
failed local construction must not poison later `tree-sitter-language-pack`
fallback, parser-facing APIs must preserve current aliases and exceptions, and
the standing smoke/platform-core/Windows release gates must still prove the
contract under deprecation-as-error mode.

The older lowercase artifact `plans/phase-plan-v1-registry.md` exists as
historical context only. Phase-loop execution for this run should follow this
uppercase `plans/phase-plan-v1-REGISTRY.md` artifact.

This planning run wrote the artifact only; it did not execute tests, builds,
formatters, docs builds, or Windows preflight commands.

## Interface Freeze Gates

- [ ] IF-0-REGISTRY-1 - The uppercase artifact
  `plans/phase-plan-v1-REGISTRY.md` is the authoritative Phase 8 execution
  plan for roadmap hash
  `ed2f074348a946a5642d1e02904b35ac4076153923aa5932623c28d304c494a2`.
- [ ] IF-0-REGISTRY-2 - Every local compiled-grammar `tree_sitter.Language`
  construction in `chunker/_internal/registry.py` flows through exactly one
  compatibility helper, `LanguageRegistry._language_from_ctypes_symbol(...)`;
  no raw local grammar pointer is wrapped by an alternate constructor path.
- [ ] IF-0-REGISTRY-3 - `_validate_language_library()`,
  `discover_languages()`, `has_language()`, `get_language()`, and
  `_try_load_from_individual_library_safely()` never make failed local
  compiled-grammar construction terminal before
  `chunker._internal.language_pack.get_language_from_pack(...)` is attempted as
  the final supported fallback.
- [ ] IF-0-REGISTRY-4 - `ParserFactory.get_parser()` and
  `chunker.parser.get_parser()` preserve current alias normalization,
  `LanguageNotFoundError` behavior, parser cache/pool semantics, and the
  existing incompatible-grammar fallback to `tree-sitter-language-pack` while
  remaining clean under `-W error::DeprecationWarning`.
- [ ] IF-0-REGISTRY-5 - Focused registry, factory, parser, CLI, and Boundary
  IR golden snapshot coverage passes with deprecations treated as errors, and
  the standing local release gates remain the authoritative whole-phase proof:
  repo smoke, Linux platform-core, and Windows preflight.
- [ ] IF-0-REGISTRY-6 - Phase 8 does not rebuild grammar artifacts as part of
  normal tests, remove `tree-sitter-language-pack`, add broad warning filters,
  or broaden into release-versioning/publishing work that belongs to `RELEASE`.
- [ ] IF-0-REGISTRY-7 - Maintainer guidance changes only if execution shows
  drift between the live fallback/validation contract and
  `docs/development/RELEASE_CHECKLIST.md` or `docs/grammar_management.md`; the
  AGENTS Windows preflight host remains `leno`, not an alternate host alias.

## Lane Index & Dependencies

- SL-0 - Registry compatibility and non-poisoning fallback contract; Depends
  on: (none); Blocks: SL-1, SL-2, SL-3; Parallel-safe: no
- SL-1 - Parser factory and parser API propagation; Depends on: SL-0; Blocks:
  SL-2, SL-3; Parallel-safe: no
- SL-2 - CLI and Boundary IR warning-clean coverage; Depends on: SL-0, SL-1;
  Blocks: SL-3; Parallel-safe: yes
- SL-3 - Standing validation scripts and maintainer guidance; Depends on:
  SL-0, SL-1, SL-2; Blocks: (none); Parallel-safe: no

## Lanes

### SL-0 - Registry Compatibility And Non-Poisoning Fallback Contract

- **Scope**: Prove and tighten the local grammar construction and fallback
  behavior inside `LanguageRegistry` so warning-clean local failures never
  suppress supported language-pack resolution.
- **Owned files**: `chunker/_internal/registry.py`, `chunker/_internal/language_pack.py`, `tests/test_registry.py`, `tests/test_registry_fallback.py`
- **Interfaces provided**: IF-0-REGISTRY-2, IF-0-REGISTRY-3, IF-0-REGISTRY-6;
  single-helper local grammar construction; non-poisoning fallback semantics;
  preserved `LanguageNotFoundError` behavior
- **Interfaces consumed**: current `LanguageRegistry._load_library()`,
  `_discover_symbols()`, `_validate_language_library()`,
  `_try_load_from_individual_library()`,
  `_try_load_from_individual_library_safely()`, `discover_languages()`,
  `has_language()`, `get_language()`, `get_language_from_pack()`,
  `list_pack_languages()`, `LanguageMetadata`, `tree_sitter.Language`
- **Parallel-safe**: no
- **Tasks**:
  - test: audit `chunker/_internal/registry.py` for every local
    `tree_sitter.Language` construction path and keep the helper as the only
    local compiled-grammar constructor.
  - test: tighten or add focused registry tests that run discovery,
    `has_language("python")`, `get_language("python")`, and invalid-language
    paths under `pytest.mark.filterwarnings("error::DeprecationWarning")`.
  - test: keep or add a regression where local individual-library loading fails
    with a deprecation or construction error and the registry still falls
    through to `tree-sitter-language-pack` without poisoning `_languages`
    metadata.
  - impl: if helper drift exists, normalize it in `chunker/_internal/registry.py`
    instead of introducing a second compatibility abstraction.
  - impl: keep fallback ordering explicit: local combined/per-language
    grammars first, language-pack last, `LanguageNotFoundError` only after both
    are exhausted.
  - impl: keep language-pack list probing side-effect-light; do not eagerly
    load many fallback grammars merely to advertise availability.
  - verify: `uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_registry.py tests/test_registry_fallback.py -q`

### SL-1 - Parser Factory And Parser API Propagation

- **Scope**: Confirm parser-creation surfaces consume the settled registry
  contract without changing public parser behavior or exception shapes.
- **Owned files**: `chunker/_internal/factory.py`, `chunker/parser.py`, `tests/test_factory.py`, `tests/test_parser.py`, `tests/test_chunking.py`
- **Interfaces provided**: IF-0-REGISTRY-4; warning-clean parser creation;
  preserved alias normalization, cache/pool behavior, and public parser/module
  exceptions
- **Interfaces consumed**: registry contract from SL-0; `ParserFactory._create_parser()`;
  `ParserFactory.get_parser()`; parser alias handling in `chunker/parser.py`;
  fallback parser loading from `tree-sitter-language-pack`
- **Parallel-safe**: no
- **Tasks**:
  - test: tighten or add focused tests so `ParserFactory.get_parser("python")`,
    cached parser reuse, config-specific parser creation, and invalid-language
    paths pass under `-W error::DeprecationWarning`.
  - test: keep invalid-language assertions anchored on
    `LanguageNotFoundError` and available-language guidance, not incidental
    parser initialization failures caused by fallback probing.
  - test: confirm `chunker.parser.get_parser()`, alias normalization for
    `csharp`/`c_sharp`/`typescript`/`tsx`, and `chunk_file(..., "python")`
    remain warning-clean.
  - impl: avoid changing cache, pool, or parser config semantics unless the
    registry contract exposes a real incompatibility.
  - impl: if fallback error translation needs refinement, keep
    incompatible-grammar routing limited to the existing language-pack fallback
    path and preserve `ParserInitError` for genuine parser setup failures.
  - verify: `uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_factory.py tests/test_parser.py tests/test_chunking.py -q`

### SL-2 - CLI And Boundary IR Warning-Clean Coverage

- **Scope**: Exercise user-facing parser paths and deterministic Boundary IR
  extraction under deprecation-as-error mode without changing export schemas.
- **Owned files**: `tests/test_cli.py`, `tests/test_boundary_ir_golden_snapshots.py`, `tests/boundary_ir_conformance.py`
- **Interfaces provided**: IF-0-REGISTRY-5; CLI and Boundary IR coverage that
  proves parser resolution is warning-clean and still deterministic
- **Interfaces consumed**: registry and parser behavior from SL-0 and SL-1;
  current Typer CLI language/chunking commands; Boundary IR snapshot helpers
  and P0 language coverage
- **Parallel-safe**: yes
- **Tasks**:
  - test: add or tighten CLI tests for language listing and a minimal Python
    chunking path under `-W error::DeprecationWarning`.
  - test: run Boundary IR golden snapshot extraction under
    `-W error::DeprecationWarning` so local registry warnings cannot hide behind
    snapshot comparison.
  - test: keep optional-grammar behavior explicit; do not convert missing
    optional local grammars into hard failures where language-pack fallback or
    existing optional skips are the settled behavior.
  - impl: update golden snapshots only if execution produces a reviewed,
    deterministic parser-availability change; do not accept schema drift here.
  - impl: do not alter Boundary IR schema, canonical ordering, observability,
    incremental semantics, or semantic-enrichment behavior in this lane.
  - verify: `uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_cli.py tests/test_boundary_ir_golden_snapshots.py -q`

### SL-3 - Standing Validation Scripts And Maintainer Guidance

- **Scope**: Keep the standing release-gate scripts and maintainer guidance in
  sync with the live Phase 8 contract after the runtime/test lanes settle.
- **Owned files**: `scripts/run_ci_smoke.py`, `scripts/run_platform_core.py`, `scripts/run_windows_preflight.py`, `tests/test_cicd_pipeline.py`, `docs/development/RELEASE_CHECKLIST.md`, `docs/grammar_management.md`
- **Interfaces provided**: IF-0-REGISTRY-5, IF-0-REGISTRY-7; authoritative
  whole-phase validation batches and maintainer-facing fallback/release guidance
- **Interfaces consumed**: warning-clean registry/factory/parser/CLI/Boundary
  IR behavior from SL-0 through SL-2; `AGENTS.md` local-first CI contract; live
  Windows host guidance from repo instructions
- **Parallel-safe**: no
- **Tasks**:
  - test: review the existing smoke, platform-core, and Windows preflight
    batches before adding new entries; keep this lane grounded in the current
    standing scripts rather than broadening them into full-suite runners.
  - test: extend `tests/test_cicd_pipeline.py` only if execution changes the
    set of tests that must remain pinned in smoke or platform-core coverage.
  - impl: if the current scripts already include the relevant registry/factory,
    CLI, and Boundary IR tests, preserve that footprint and record the
    no-script-change decision in execution closeout.
  - impl: update `docs/development/RELEASE_CHECKLIST.md` only if the focused
    deprecation-as-error commands or the Windows preflight host drift from the
    repo's actual release gate; use `ssh leno ...` if the AGENTS contract still
    governs the Windows preflight hop.
  - impl: update `docs/grammar_management.md` only if local grammar fallback
    order, compatibility expectations, or user-visible troubleshooting guidance
    changes during execution.
  - impl: do not add grammar rebuild steps, broad warning suppression, or
    release-versioning/publishing work in this lane.
  - verify: `uv run --with toml --all-extras pytest tests/test_cicd_pipeline.py -q`
  - verify: `uv run --with toml --all-extras python scripts/run_ci_smoke.py`
  - verify: `uv run --with toml --all-extras python scripts/run_platform_core.py --platform linux`
  - verify: `ssh leno 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'`

## Verification

Planning wrote the artifact only; verification was not run. During execution,
run the focused deprecation-as-error checks first:

```bash
uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_registry.py tests/test_registry_fallback.py -q
uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_factory.py tests/test_parser.py tests/test_chunking.py -q
uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_cli.py tests/test_boundary_ir_golden_snapshots.py -q
```

Then run the repo-standard local validation loop from `AGENTS.md` plus the
standing cross-platform checks already tied to this phase:

```bash
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
uv run --with toml --all-extras python scripts/run_platform_core.py --platform linux
ssh leno 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
```

If `docs/development/RELEASE_CHECKLIST.md` or `docs/grammar_management.md`
changes, also run:

```bash
uv run --with toml --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict
```

## Acceptance Criteria

- [ ] `plans/phase-plan-v1-REGISTRY.md` is the authoritative uppercase Phase 8
  execution artifact for roadmap hash
  `ed2f074348a946a5642d1e02904b35ac4076153923aa5932623c28d304c494a2`.
- [ ] Every local compiled-grammar `tree_sitter.Language` construction in
  `chunker/_internal/registry.py` goes through
  `LanguageRegistry._language_from_ctypes_symbol(...)`.
- [ ] Failed local compiled-grammar construction does not poison `_languages`
  metadata or suppress later `tree-sitter-language-pack` fallback.
- [ ] Invalid languages still raise `LanguageNotFoundError` with available
  language guidance after local and language-pack probes are exhausted.
- [ ] `ParserFactory` and `chunker.parser` preserve current alias
  normalization, exception shapes, and parser cache/pool behavior.
- [ ] Registry, factory, parser, CLI, and Boundary IR focused coverage passes
  with `-W error::DeprecationWarning`.
- [ ] `scripts/run_ci_smoke.py`, `scripts/run_platform_core.py --platform linux`,
  and the standing Windows preflight on `leno` pass after any Phase 8 changes.
- [ ] `tests/test_cicd_pipeline.py` remains aligned with any standing-script
  coverage changes required by this phase.
- [ ] Release and grammar-management guidance matches the live Phase 8 contract
  if execution changes those surfaces; otherwise the execution closeout records
  a no-docs-change decision.
- [ ] No grammar artifacts are rebuilt or committed as part of normal Phase 8
  verification.
- [ ] No broad `filterwarnings`, centralized warning suppression, xfail-based
  release gate, package version bump, or publishing workflow change is
  introduced by this phase.

## Closeout

Artifact state: staged

Next phase: REGISTRY - execution ready

Next command: `codex-execute-phase plans/phase-plan-v1-REGISTRY.md`

```yaml
automation:
  status: planned
  next_skill: codex-execute-phase
  next_command: codex-execute-phase plans/phase-plan-v1-REGISTRY.md
  next_model_hint: execute
  next_effort_hint: medium
  human_required: false
  blocker_class: none
  blocker_summary: none
  required_human_inputs: []
  verification_status: not_run
  artifact: /home/viperjuice/code/treesitter-chunker/plans/phase-plan-v1-REGISTRY.md
  artifact_state: staged
```

# HYGIENE: Release Hygiene Baseline

## Context

Roadmap source: `specs/phase-plans-v1.md`, Phase 7. The roadmap file is tracked and modified in this working tree (` M specs/phase-plans-v1.md`), so it is not an untracked `git clean -fd` risk; Phase 7 execution should preserve those user-owned roadmap edits.

Phase 7 is a release-hardening pass, not parser-runtime work. Current repo inspection found `mkdocs.yml` has an explicit `nav` and no `not_in_nav` declaration, while the Markdown docs currently outside nav include `docs/agent-interface-readiness.md`, `docs/interface-boundary-roadmap.md`, `docs/grammar_management.md`, `docs/development/DEPLOYMENT.md`, `docs/development/RELEASE_CHECKLIST.md`, and `docs/final-integration-testing.md`. Current MkDocs supports `not_in_nav` patterns for intentionally omitted pages, so the phase should classify pages explicitly instead of suppressing omitted-file warnings with a broad wildcard.

Fallback warning coverage currently uses local `warnings.catch_warnings()` in `tests/test_fallback_chunking.py` and `tests/test_overlapping_fallback.py`; `tests/test_auto.py` exercises fallback behavior through the zero-config API. There is no centralized `filterwarnings` policy in `pyproject.toml`, no collection-time xfail policy in `tests/conftest.py`, and no current `pytest.mark.xfail` usage. Phase 7 should keep that shape: warnings are asserted locally where they are expected, and platform skips stay local with clear reasons.

This planning run did not execute tests, builds, formatters, MkDocs, or preflight commands.

## Interface Freeze Gates

- [ ] IF-0-HYGIENE-8 -- Release hygiene policy for docs navigation, expected warnings, and explicit test skips is frozen.
- [ ] IF-0-HYGIENE-8A -- Every Markdown page under `docs/` is either listed in `mkdocs.yml` `nav` or intentionally listed in `mkdocs.yml` `not_in_nav`; `not_in_nav: *` and other docs-wide wildcards are forbidden.
- [ ] IF-0-HYGIENE-8B -- Phase 7 public docs navigation includes `agent-interface-readiness.md`, `interface-boundary-roadmap.md`, `interface-boundary-spec.md`, and `grammar_management.md` in explicit nav sections; `development/DEPLOYMENT.md`, `development/RELEASE_CHECKLIST.md`, and `final-integration-testing.md` are intentionally internal through exact `not_in_nav` entries.
- [ ] IF-0-HYGIENE-8C -- Internal docs omitted from nav contain an explicit maintainer/internal classification near the top of the page and remain reachable through direct links from maintainer-facing docs where useful.
- [ ] IF-0-HYGIENE-8D -- Tests that intentionally trigger `FallbackWarning` use local `pytest.warns(FallbackWarning, match=...)` or a scoped warning capture that asserts the expected `FallbackWarning`; no global warning filter is added to hide expected fallback behavior.
- [ ] IF-0-HYGIENE-8E -- Phase 7 does not change fallback runtime behavior, warning class names, warning message text, parser registry loading, or tree-sitter language-pack fallback semantics unless a focused test exposes a real product bug.
- [ ] IF-0-HYGIENE-8F -- `tests/conftest.py` remains free of collection-time xfail/skip mutation for Phase 7; no `pytest.mark.xfail` markers are introduced.
- [ ] IF-0-HYGIENE-8G -- Platform skips remain local to the test that cannot be deterministic on that platform and include a reason naming the unavailable platform feature or dependency.
- [ ] IF-0-HYGIENE-8H -- Phase 7 completion requires the MkDocs strict build, fallback-warning pytest batch, CI smoke command, and Windows preflight command to pass without xfail or xpass results.

## Lane Index & Dependencies

- SL-0 -- MkDocs navigation contract preamble; Depends on: (none); Blocks: SL-4; Parallel-safe: no
- SL-1 -- Fallback manager and zero-config warning assertions; Depends on: (none); Blocks: SL-3, SL-4; Parallel-safe: yes
- SL-2 -- Overlapping fallback warning assertions; Depends on: (none); Blocks: SL-3, SL-4; Parallel-safe: yes
- SL-3 -- Test skip and xfail policy anchors; Depends on: SL-1, SL-2; Blocks: SL-4; Parallel-safe: no
- SL-4 -- Documentation and release-hygiene synthesis; Depends on: SL-0, SL-1, SL-2, SL-3; Blocks: (none); Parallel-safe: no

## Lanes

### SL-0 -- MkDocs Navigation Contract Preamble

- **Scope**: Make MkDocs page classification explicit before docs content updates depend on the public/internal split.
- **Owned files**: `mkdocs.yml`
- **Interfaces provided**: exact Phase 7 docs navigation classification, exact `not_in_nav` patterns, no wildcard omitted-page suppression
- **Interfaces consumed**: existing `nav` structure in `mkdocs.yml`; MkDocs `not_in_nav` pattern semantics; current docs file inventory
- **Parallel-safe**: no
- **Tasks**:
  - test: no executable test in this lane; rely on the SL-4 MkDocs strict build after docs content settles.
  - impl: add a `Boundary IR` or equivalent explicit nav grouping for `agent-interface-readiness.md`, `interface-boundary-roadmap.md`, and existing `interface-boundary-spec.md`.
  - impl: add `grammar_management.md` to an explicit public nav location near grammar discovery or advanced topics.
  - impl: add exact `not_in_nav` entries for `/development/DEPLOYMENT.md`, `/development/RELEASE_CHECKLIST.md`, and `/final-integration-testing.md`.
  - impl: do not use `not_in_nav: *`, do not hide the whole `docs/development/` tree unless every omitted Markdown file in that tree is intentionally internal, and do not move Sphinx docs as part of this phase.
  - verify: `uv run --with toml --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict`

### SL-1 -- Fallback Manager And Zero-Config Warning Assertions

- **Scope**: Convert expected fallback warnings in fallback-manager and zero-config tests into local assertions so warning summaries only contain unexpected warnings.
- **Owned files**: `tests/test_fallback_chunking.py`, `tests/test_auto.py`
- **Interfaces provided**: local expected-warning assertions for `FallbackWarning` from line-based fallback and fallback manager paths
- **Interfaces consumed**: existing `FallbackWarning`, `FallbackManager.chunk_file()`, `ZeroConfigAPI.auto_chunk_file()`, current fallback warning message text
- **Parallel-safe**: yes
- **Tasks**:
  - test: update `test_fallback_warning_emitted` to assert the warning with `pytest.warns(FallbackWarning, match=...)` or an equivalent scoped capture limited to `FallbackWarning`.
  - test: update fallback-manager tests that intentionally call `manager.chunk_file()` to assert the expected warning locally and continue asserting returned chunks.
  - test: add or adjust zero-config fallback coverage in `tests/test_auto.py` so fallback warnings produced by text fallback are asserted locally instead of leaking into the pytest warning summary.
  - impl: import `pytest` or `FallbackWarning` only where needed and keep fallback behavior assertions unchanged.
  - impl: avoid changes to `chunker/fallback/`, `chunker/fallback_overlap/`, `chunker/auto.py`, or warning message text in this lane.
  - verify: `uv run --with toml --all-extras pytest tests/test_fallback_chunking.py tests/test_auto.py -q`

### SL-2 -- Overlapping Fallback Warning Assertions

- **Scope**: Normalize overlapping fallback tests so every intentional `FallbackWarning` is locally asserted or deliberately scoped away.
- **Owned files**: `tests/test_overlapping_fallback.py`
- **Interfaces provided**: local expected-warning assertions for overlapping, asymmetric, dynamic, empty, single-chunk, metadata, boundary-condition, unicode, and extension-detection fallback paths
- **Interfaces consumed**: existing `FallbackWarning`, `OverlappingFallbackChunker`, `OverlapStrategy`, `TreeSitterOverlapError`, current overlapping fallback warning message text
- **Parallel-safe**: yes
- **Tasks**:
  - test: replace bare `warnings.catch_warnings(record=True)` usages around warning-producing fallback calls with `pytest.warns(FallbackWarning, match=...)` when the warning is part of the contract.
  - test: keep tests that inspect warning content asserting the strategy-specific terms such as `overlapping fallback`, `asymmetric`, and `dynamic`.
  - test: where warning details are not the behavior under test, use a small local helper or scoped capture that asserts exactly one expected `FallbackWarning` and returns the chunks.
  - impl: remove the `warnings` import only if all manual warning captures are eliminated; otherwise keep manual capture narrow and category-specific.
  - impl: do not change overlap chunking behavior, tree-sitter support detection, or `TreeSitterOverlapError` paths.
  - verify: `uv run --with toml --all-extras pytest tests/test_overlapping_fallback.py -q`

### SL-3 -- Test Skip And Xfail Policy Anchors

- **Scope**: Preserve the repo's no-central-xfail policy and make Phase 7 skip/warning policy mechanically reviewable.
- **Owned files**: `tests/conftest.py`, `tests/test_release_hygiene_policy.py`
- **Interfaces provided**: release hygiene policy tests for xfail absence, no collection-time skip/xfail mutation, and scoped fallback warning expectations
- **Interfaces consumed**: warning assertion patterns from SL-1 and SL-2; existing `tests/conftest.py`; existing pytest config in `pyproject.toml`
- **Parallel-safe**: no
- **Tasks**:
  - test: add `tests/test_release_hygiene_policy.py` to assert there are no `pytest.mark.xfail` markers, no `pytest.xfail()` calls, and no collection-time xfail injection in `tests/conftest.py`.
  - test: assert `tests/conftest.py` does not define `pytest_collection_modifyitems` or broad warning filters for `FallbackWarning`.
  - test: assert the Phase 7 fallback test files do not contain bare `warnings.catch_warnings(record=True)` blocks without an accompanying `FallbackWarning` assertion.
  - impl: leave `tests/conftest.py` unchanged if it still only contains fixture setup; if execution discovers a central xfail/skip mutation, remove it here instead of compensating in individual tests.
  - impl: do not add global `filterwarnings`, `xfail_strict`, or broad pytest addopts as a substitute for local warning/skip cleanup.
  - verify: `uv run --with toml --all-extras pytest tests/test_release_hygiene_policy.py -q`

### SL-4 -- Documentation And Release-Hygiene Synthesis

- **Scope**: Update docs and maintainer-facing release guidance after the nav contract, warning tests, and skip-policy anchors are settled.
- **Owned files**: `docs/index.md`, `docs/agent-interface-readiness.md`, `docs/interface-boundary-roadmap.md`, `docs/grammar_management.md`, `docs/development/DEPLOYMENT.md`, `docs/development/RELEASE_CHECKLIST.md`, `docs/final-integration-testing.md`
- **Interfaces provided**: documented public/internal docs classification, release-hygiene validation guidance, expected warning policy, no-xfail/no-xpass release gate
- **Interfaces consumed**: MkDocs classification from SL-0; fallback warning assertion behavior from SL-1 and SL-2; release hygiene policy tests from SL-3; existing AGENTS local-first validation commands
- **Parallel-safe**: no
- **Tasks**:
  - test: review docs against the executable checks from SL-1 through SL-3 and add no docs-only tests unless a documented rule has no focused coverage.
  - impl: update `docs/index.md` quick links or contributor guidance so public Boundary IR and grammar management docs linked from nav are also discoverable from the landing page where appropriate.
  - impl: add a short internal/maintainer classification near the top of `docs/development/DEPLOYMENT.md`, `docs/development/RELEASE_CHECKLIST.md`, and `docs/final-integration-testing.md` to match their `not_in_nav` status.
  - impl: keep `docs/agent-interface-readiness.md`, `docs/interface-boundary-roadmap.md`, and `docs/grammar_management.md` framed as public documentation if they are added to nav.
  - impl: update `docs/development/RELEASE_CHECKLIST.md` with Phase 7 release-hygiene gates: MkDocs strict build, focused fallback-warning tests, no xfail/xpass results, CI smoke, and Windows preflight.
  - impl: do not broaden this lane into parser registry compatibility, release publishing, version bumps, or fallback-runtime behavior changes.
  - verify: `uv run --with toml --all-extras pytest tests/test_release_hygiene_policy.py tests/test_auto.py tests/test_fallback_chunking.py tests/test_overlapping_fallback.py -q`
  - verify: `uv run --with toml --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict`

## Verification

Lane-specific verification is listed in each lane. After all lanes are integrated, run:

```bash
uv run --with toml --all-extras pytest tests/test_release_hygiene_policy.py tests/test_auto.py tests/test_fallback_chunking.py tests/test_overlapping_fallback.py -q
uv run --with toml --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
```

Because this phase touches warning-sensitive tests in the CI smoke batch and the Windows preflight batch, run the standing Windows preflight before pushing:

```bash
ssh leno 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
```

## Acceptance Criteria

- [ ] MkDocs strict build has no broken-link or omitted-page warnings for the documented pages touched by Phase 7.
- [ ] `mkdocs.yml` explicitly lists all public Phase 7 docs in `nav` and all intentionally internal Phase 7 Markdown docs in exact `not_in_nav` entries.
- [ ] Docs outside `mkdocs.yml` navigation are documented as intentionally internal near the top of the page.
- [ ] Tests that intentionally trigger `FallbackWarning` assert those warnings locally and do not leak incidental fallback warnings into pytest summaries.
- [ ] Phase 7 does not change fallback behavior, warning text, parser runtime behavior, parser registry loading, or language-pack fallback semantics.
- [ ] `tests/conftest.py` remains free of centralized collection-time xfail/skip mutation and broad `FallbackWarning` filters.
- [ ] No `pytest.mark.xfail`, `pytest.xfail()`, xfail, or xpass results are introduced by the focused tests, CI smoke, or Windows preflight.
- [ ] Platform skips remain local, explicit, and reasoned by unavailable platform feature or optional dependency.
- [ ] Focused fallback-warning tests pass: `tests/test_auto.py`, `tests/test_fallback_chunking.py`, and `tests/test_overlapping_fallback.py`.
- [ ] CI-equivalent smoke validation remains green with `uv run --with toml --all-extras python scripts/run_ci_smoke.py`.
- [ ] Windows preflight remains green with `uv run --with toml --all-extras python scripts/run_windows_preflight.py` on `leno`.
- [ ] Phase 7 does not publish a release, bump the package version, rework parser registry loading, or introduce centralized warning suppression.

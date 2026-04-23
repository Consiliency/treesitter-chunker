# RELEASE: Version Bump And Release Gate

## Context

Roadmap source: `specs/phase-plans-v1.md`, Phase 9. The roadmap file is
tracked with staged modifications in this working tree (`M  specs/phase-plans-v1.md`),
so it is not an untracked `git clean -fd` risk; Phase 9 execution should
preserve those user-owned roadmap edits.

Phase 9 follows the Phase 7 release hygiene gate and the Phase 8 registry
compatibility gate. The Phase 7 plan freezes docs navigation, expected warning,
and no-xfail policy. The Phase 8 plan freezes tree-sitter registry compatibility
and deprecation-as-error validation. Phase 9 should not add new Boundary IR,
parser registry, semantic enrichment, or release workflow capability; it should
turn the version bump, release notes, package checks, and pre-push validation
into a mechanical release-prep change.

Current repo inspection found `pyproject.toml` is the package version source of
truth and is currently `2.2.22`. `chunker.__version__` reads installed package
metadata through `importlib.metadata.version("treesitter-chunker")`, so
`chunker/__init__.py` is not a release-version source. `docs/packaging.md` states
that release tags must be `vX.Y.Z` and match `pyproject.toml`.
`.github/workflows/release.yml` enforces tag/version equality, checks PyPI for an
existing version, builds distributions with `python -m build`, checks artifacts
with `twine check dist/*`, publishes through trusted publishing, and then
updates `CHANGELOG.md` with `git-cliff` on tag pushes. `.github/workflows/build-wheels.yml`
builds wheel artifacts but does not publish.

A PMCP Context7 check against the Python Packaging User Guide confirmed the
standard local release-artifact shape remains `python -m build` followed by
`twine check` for distribution validation. In this repo, those commands must be
run through `uv run --with toml --all-extras`.

This planning run did not execute tests, builds, formatters, generators,
packaging commands, GitHub Actions, tag creation, pushes, or Windows preflight.

## Interface Freeze Gates

- [ ] IF-0-RELEASE-10 -- Version bump, release notes, packaging metadata, and pre-push validation gate are frozen.
- [ ] IF-0-RELEASE-10A -- `pyproject.toml` `[project].version` is the only package version source of truth; release tags use `vX.Y.Z` and must equal `v{project.version}`.
- [ ] IF-0-RELEASE-10B -- Phase 9 execution chooses one explicit `TARGET_VERSION` before edits; `pyproject.toml`, the top `CHANGELOG.md` release entry, package artifacts, and the eventual tag all use that same version.
- [ ] IF-0-RELEASE-10C -- `chunker/__init__.py` is not edited for the release version because runtime version reporting comes from installed package metadata.
- [ ] IF-0-RELEASE-10D -- The top `CHANGELOG.md` entry for `TARGET_VERSION` summarizes Boundary IR observability, incremental extraction, semantic enrichment, release hygiene, and registry compatibility hardening as applicable to completed prior phases.
- [ ] IF-0-RELEASE-10E -- `.github/workflows/release.yml` continues to guard tag/version mismatch, already-published PyPI versions, build failures, artifact check failures, and trusted-publishing permissions before production publish.
- [ ] IF-0-RELEASE-10F -- `.github/workflows/build-wheels.yml` continues to build/upload wheel artifacts only and does not publish to PyPI or require release credentials.
- [ ] IF-0-RELEASE-10G -- Local package validation builds into a new ignored `dist/phase9-release-check-*` directory, checks only those fresh artifacts with `twine check`, and confirms artifact filenames contain `TARGET_VERSION`.
- [ ] IF-0-RELEASE-10H -- Required pre-push validation after the bump includes release policy tests, Phase 7 hygiene gates, Phase 8 registry gates, MkDocs strict build, Linux platform core, lint, format check, CI smoke, package build/check, and Windows preflight.
- [ ] IF-0-RELEASE-10I -- Phase 9 does not create tags, push commits or tags, publish packages, change release credentials, delete legacy credential items, or clean the working tree unless explicitly requested during execution.
- [ ] IF-0-RELEASE-10J -- Working tree must be clean before the human or automation performs the release push/tag; generated ignored package artifacts under `dist/` do not count as release source changes.

## Lane Index & Dependencies

- SL-0 -- Release contract test anchors; Depends on: (none); Blocks: SL-1, SL-2, SL-3, SL-4, SL-5; Parallel-safe: no
- SL-1 -- Version source bump; Depends on: SL-0; Blocks: SL-2, SL-3, SL-4, SL-5; Parallel-safe: no
- SL-2 -- Changelog release notes; Depends on: SL-0, SL-1; Blocks: SL-4, SL-5; Parallel-safe: yes
- SL-3 -- Workflow and artifact gate review; Depends on: SL-0, SL-1; Blocks: SL-4, SL-5; Parallel-safe: yes
- SL-4 -- Packaging docs and release checklist; Depends on: SL-0, SL-1, SL-2, SL-3; Blocks: SL-5; Parallel-safe: no
- SL-5 -- Release readiness verification reducer; Depends on: SL-0, SL-1, SL-2, SL-3, SL-4; Blocks: (none); Parallel-safe: no

## Lanes

### SL-0 -- Release Contract Test Anchors

- **Scope**: Add focused tests that make the release gate mechanically reviewable before the version bump and release-note edits depend on it.
- **Owned files**: `tests/test_cicd_pipeline.py`
- **Interfaces provided**: release policy tests for `pyproject.toml` version parsing, top changelog version alignment, release workflow tag/version guard, PyPI duplicate-version guard, trusted publishing, and build-wheels non-publish behavior
- **Interfaces consumed**: existing `yaml` workflow parsing tests, `pyproject.toml` `[project].version`, `CHANGELOG.md` heading format, `.github/workflows/release.yml`, `.github/workflows/build-wheels.yml`
- **Parallel-safe**: no
- **Tasks**:
  - test: add a helper that reads `pyproject.toml` with `tomllib` and returns `[project].version`.
  - test: assert the first `CHANGELOG.md` release heading matches the current `pyproject.toml` version so the test fails after SL-1 until SL-2 updates release notes.
  - test: assert `.github/workflows/release.yml` contains a tag/version equality guard comparing `TAG_NAME` with `v$PACKAGE_VERSION`.
  - test: assert `.github/workflows/release.yml` checks PyPI for an existing package version before production publish and uses `pypa/gh-action-pypi-publish`.
  - test: assert `.github/workflows/build-wheels.yml` uploads wheel artifacts but contains no PyPI publish action, token-based upload command, or trusted-publishing environment.
  - impl: keep the tests textual and structural enough to catch release-gate regressions without depending on GitHub's full workflow schema.
  - verify: `uv run --with toml --all-extras pytest tests/test_cicd_pipeline.py -q`

### SL-1 -- Version Source Bump

- **Scope**: Update the package version source of truth to the selected release version and leave non-source version readers alone.
- **Owned files**: `pyproject.toml`
- **Interfaces provided**: `[project].version == TARGET_VERSION`; release tag target `vTARGET_VERSION`; package metadata consumed by build and installed runtime version reporting
- **Interfaces consumed**: IF-0-RELEASE-10A through IF-0-RELEASE-10C; SL-0 pyproject/changelog alignment test; current release decision for `TARGET_VERSION`
- **Parallel-safe**: no
- **Tasks**:
  - test: before editing, confirm the chosen `TARGET_VERSION` is greater than the current `pyproject.toml` version and uses a SemVer-compatible `X.Y.Z` form.
  - impl: update only `[project].version` in `pyproject.toml` to `TARGET_VERSION`.
  - impl: do not edit `chunker/__init__.py` for version reporting and do not blanket-replace historical fixed-in version references such as troubleshooting notes.
  - impl: if `TARGET_VERSION` is already present on PyPI during execution, stop and choose a new version before continuing rather than reusing the release number.
  - verify: `uv run --with toml --all-extras pytest tests/test_cicd_pipeline.py -q`

### SL-2 -- Changelog Release Notes

- **Scope**: Update the top changelog entry so the release notes match the selected version and completed phase outcomes.
- **Owned files**: `CHANGELOG.md`
- **Interfaces provided**: top `CHANGELOG.md` entry for `TARGET_VERSION`; release-note summary covering Boundary IR observability, incremental extraction, semantic enrichment, release hygiene, and registry compatibility where those prior phases landed
- **Interfaces consumed**: `TARGET_VERSION` from SL-1; completed Phase 4 through Phase 8 implementation summaries or git history; `cliff.toml` grouping conventions; SL-0 changelog alignment test
- **Parallel-safe**: yes
- **Tasks**:
  - test: run the SL-0 release policy test after editing so changelog and package version alignment is enforced.
  - impl: update or regenerate the top `CHANGELOG.md` entry using the existing Keep a Changelog/git-cliff style.
  - impl: keep the entry concise but explicit about Boundary IR observability, incremental cache/extraction behavior, semantic enrichment hooks, release hygiene gates, and registry deprecation hardening if those changes are included in the release.
  - impl: do not commit generated transient `RELEASE_NOTES.md`; `.github/workflows/release.yml` creates runtime release notes for GitHub releases.
  - impl: do not rewrite older historical changelog sections except to fix clearly broken ordering or duplicate release headings caused by the current release entry.
  - verify: `uv run --with toml --all-extras pytest tests/test_cicd_pipeline.py -q`

### SL-3 -- Workflow And Artifact Gate Review

- **Scope**: Confirm release workflows and package artifact checks still enforce the frozen release gate after the version bump.
- **Owned files**: `.github/workflows/release.yml`, `.github/workflows/build-wheels.yml`
- **Interfaces provided**: guarded release workflow, non-publishing wheel artifact workflow, local artifact build/check command set for `TARGET_VERSION`
- **Interfaces consumed**: SL-0 workflow policy tests; `pyproject.toml` version from SL-1; current `docs/packaging.md` release model; PyPA build and twine-check command shape
- **Parallel-safe**: yes
- **Tasks**:
  - test: run SL-0 workflow tests to confirm release workflow tag/version, PyPI duplicate, trusted publishing, and build-wheels non-publish guards.
  - test: build fresh ignored local artifacts in a unique directory such as `dist/phase9-release-check-TARGET_VERSION` or a timestamped variant if that directory already exists.
  - test: check only the fresh artifacts with `twine check` and assert both wheel and sdist filenames contain `TARGET_VERSION`.
  - impl: leave workflow files unchanged if SL-0 tests and the local package commands confirm the current guards.
  - impl: if workflow edits are required, keep them limited to release-gate validation or artifact checking; do not alter publishing credentials, environments, concurrency, tag triggers, or release creation behavior.
  - impl: do not make `.github/workflows/build-wheels.yml` a publishing workflow.
  - verify: `uv run --with toml --all-extras pytest tests/test_cicd_pipeline.py -q`
  - verify: `uv run --with toml --all-extras python -m build --outdir dist/phase9-release-check-TARGET_VERSION`
  - verify: `uv run --with toml --all-extras python -m twine check dist/phase9-release-check-TARGET_VERSION/*`

### SL-4 -- Packaging Docs And Release Checklist

- **Scope**: Align maintainer-facing release documentation with the frozen Phase 9 gate and the final validation commands.
- **Owned files**: `docs/packaging.md`, `docs/development/RELEASE_CHECKLIST.md`, `README.md`, `docs/troubleshooting.md`
- **Interfaces provided**: documented `TARGET_VERSION` flow, pre-push validation checklist, local package build/check commands through `uv run`, final clean-tree requirement, tag/push boundary
- **Interfaces consumed**: version source from SL-1; changelog expectations from SL-2; workflow and artifact checks from SL-3; Phase 7 hygiene commands; Phase 8 registry commands; AGENTS local-first validation sequence
- **Parallel-safe**: no
- **Tasks**:
  - test: no docs-only test is required unless execution changes links or nav; rely on MkDocs strict build in SL-5.
  - impl: update `docs/packaging.md` if needed so local package validation uses `uv run --with toml --all-extras python -m build` and `uv run --with toml --all-extras python -m twine check`, not host-installed tools.
  - impl: update `docs/development/RELEASE_CHECKLIST.md` with the Phase 9 sequence: choose `TARGET_VERSION`, bump `pyproject.toml`, update `CHANGELOG.md`, run focused release tests, run hygiene and registry gates, build/check package artifacts, run smoke/platform/Windows validation, confirm clean tree, then tag/push only when explicitly ready.
  - impl: review hard-coded version examples in `README.md`; update only release-current package filename examples that should follow `TARGET_VERSION`.
  - impl: review `docs/troubleshooting.md` fixed-in version references and leave historical fix-version notes unchanged unless this release actually changes that historical guidance.
  - impl: do not document new credential flows, alternate PyPI token paths, or direct local publishing as part of Phase 9.
  - verify: `uv run --with toml --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict`

### SL-5 -- Release Readiness Verification Reducer

- **Scope**: Run the final validation matrix, collect readiness results, and stop before any tag, push, or publish action.
- **Owned files**: (none; execution closeout and command results only)
- **Interfaces provided**: release-readiness decision for `TARGET_VERSION`; final list of passed commands; clean-tree status before handoff to tag/push
- **Interfaces consumed**: release policy tests from SL-0; version source from SL-1; changelog from SL-2; workflow and package artifact checks from SL-3; docs/checklist from SL-4; Phase 7 and Phase 8 validation commands
- **Parallel-safe**: no
- **Tasks**:
  - test: run focused release policy tests after all file edits settle.
  - test: run the Phase 7 hygiene pytest batch and MkDocs strict build.
  - test: run the Phase 8 deprecation-as-error registry, factory/parser/chunking, CLI, and Boundary IR golden snapshot batches.
  - test: run local package build/check in the fresh ignored `dist/phase9-release-check-*` output directory and confirm artifacts use `TARGET_VERSION`.
  - test: run lint, Black check, CI smoke, Linux platform core, and Windows preflight.
  - impl: collect failures and route any code/doc fixes back to the owning upstream lane instead of editing files from this reducer lane.
  - impl: confirm `git status --short` shows only intentional tracked release-prep changes and no untracked source artifacts before recommending tag/push.
  - impl: do not run `git tag`, `git push`, GitHub workflow dispatch, PyPI publish, or destructive cleanup in this lane unless the user explicitly asks during execution.
  - verify: `git status --short`

## Verification

Lane-specific verification is listed in each lane. After all lanes are
integrated, run the focused release-policy and package commands first:

```bash
uv run --with toml --all-extras pytest tests/test_cicd_pipeline.py -q
uv run --with toml --all-extras python -m build --outdir dist/phase9-release-check-TARGET_VERSION
uv run --with toml --all-extras python -m twine check dist/phase9-release-check-TARGET_VERSION/*
```

Then run the Phase 7 hygiene gates:

```bash
uv run --with toml --all-extras pytest tests/test_release_hygiene_policy.py tests/test_auto.py tests/test_fallback_chunking.py tests/test_overlapping_fallback.py -q
uv run --with toml --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict
```

Then run the Phase 8 registry compatibility gates:

```bash
uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_registry_fallback.py tests/test_registry.py -q
uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_factory.py tests/test_parser.py tests/test_chunking.py -q
uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_cli.py tests/test_boundary_ir_golden_snapshots.py -q
```

Then run the repo-standard local-first validation sequence from `AGENTS.md`:

```bash
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
```

Because this phase is the release gate and depends on platform-core and Windows
preflight confirmation, also run:

```bash
uv run --with toml --all-extras python scripts/run_platform_core.py --platform linux
ssh leno 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
git status --short
```

## Acceptance Criteria

- [ ] `TARGET_VERSION` is selected once, is greater than the previous package version, and uses `X.Y.Z` SemVer form.
- [ ] `pyproject.toml` `[project].version` equals `TARGET_VERSION`.
- [ ] The intended release tag is exactly `vTARGET_VERSION`.
- [ ] `chunker/__init__.py` remains unmodified for release-version reporting.
- [ ] The first `CHANGELOG.md` release heading matches `TARGET_VERSION`.
- [ ] The top changelog entry summarizes completed Boundary IR observability, incremental extraction, semantic enrichment, release hygiene, and registry compatibility work that belongs in this release.
- [ ] Release policy tests cover changelog/version alignment, release workflow tag/version guard, PyPI duplicate-version guard, trusted publishing, and non-publishing wheel artifact workflow behavior.
- [ ] `.github/workflows/release.yml` still fails on tag/version mismatch, already-published PyPI versions, package build failures, and `twine check` failures before publishing.
- [ ] `.github/workflows/build-wheels.yml` still builds/uploads wheel artifacts only and does not publish to PyPI.
- [ ] Local package validation builds fresh ignored artifacts and `twine check` passes against only those artifacts.
- [ ] Fresh local wheel and sdist artifact names contain `TARGET_VERSION`.
- [ ] Packaging and release checklist docs describe the `uv run --with toml --all-extras` release validation flow.
- [ ] Phase 7 hygiene gates pass after the version bump.
- [ ] Phase 8 registry deprecation-as-error gates pass after the version bump.
- [ ] Lint, Black check, CI smoke, Linux platform core, MkDocs strict build, package build/check, and Windows preflight pass before push.
- [ ] `git status --short` is clean before release tag/push, except ignored package artifacts under `dist/` may remain locally.
- [ ] Phase 9 does not tag, push, publish, change release credentials, alter trusted-publishing setup, add a token-based PyPI path, or delete/clean unrelated local files.

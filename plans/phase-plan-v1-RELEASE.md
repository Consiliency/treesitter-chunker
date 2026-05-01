---
phase_loop_plan_version: 1
phase: RELEASE
roadmap: specs/phase-plans-v1.md
roadmap_sha256: ed2f074348a946a5642d1e02904b35ac4076153923aa5932623c28d304c494a2
---

# RELEASE: Version Bump And Release Gate

## Context

Roadmap source: `specs/phase-plans-v1.md`, Phase 9 (`RELEASE`). The roadmap is
tracked, clean in the current worktree, and its live SHA-256 matches the
required planning hash
`ed2f074348a946a5642d1e02904b35ac4076153923aa5932623c28d304c494a2`.
Canonical runner state exists in `.phase-loop/`; `.phase-loop/state.json`
still records `REGISTRY` as the current phase and `RELEASE` as unplanned, but
this run was explicitly invoked to plan `RELEASE`, so the direct-run artifact
written here is the authoritative execution plan for this phase.

Current release authority in the repo is broader than a single file. The live
source of truth is `pyproject.toml` for package versioning, `CHANGELOG.md` for
the top release entry, `docs/packaging.md` plus
`docs/development/RELEASE_CHECKLIST.md` for maintainer flow, and
`.github/workflows/release.yml` for the only production PyPI publishing path.
That workflow already guards tag/version mismatch, checks PyPI for duplicate
versions, builds distributions, runs `twine check`, creates a GitHub Release,
and publishes through trusted publishing. `.github/workflows/build-wheels.yml`
remains an artifact-only wheel builder.

Repo inspection also found a second, older release-helper surface under
`chunker/distribution/` with tests in `tests/unit/distribution/` and
`tests/test_distribution_impl.py`. Those helpers still encode release behavior
that conflicts with the current release docs and workflow contract, including
updating `chunker/__init__.py`, touching `setup.py`, and creating tags during
"prepare release". Phase 9 should either align that helper surface with the
current authoritative release process or explicitly narrow/document its role;
it should not leave contradictory release authority in place.

`chunker/__init__.py` is not a release version source of truth here. Runtime
version reporting reads installed package metadata through
`importlib.metadata.version("treesitter-chunker")`, while the tracked fallback
literal there is only a build/import fallback. `chunker/_version.py` is a
generated file and should not become the manual bump target for this phase.

The historical lowercase artifact `plans/phase-plan-v1-release.md` exists as
context only. Phase-loop execution for this run should follow this uppercase
`plans/phase-plan-v1-RELEASE.md` artifact.

This planning run wrote the artifact only; it did not choose a target version,
edit package metadata, edit changelog entries, build distributions, run tests,
dispatch GitHub workflows, tag, push, or publish.

## Interface Freeze Gates

- [ ] IF-0-RELEASE-1 - The uppercase artifact
  `plans/phase-plan-v1-RELEASE.md` is the authoritative Phase 9 execution plan
  for roadmap hash
  `ed2f074348a946a5642d1e02904b35ac4076153923aa5932623c28d304c494a2`.
- [ ] IF-0-RELEASE-2 - Phase 9 is a release-preparation phase, not a release
  dispatch phase: it may bump version sources, update changelog/docs, align
  release-helper code, and run validation, but it does not tag, push, manually
  dispatch `.github/workflows/release.yml`, or publish to PyPI unless the user
  explicitly expands scope later.
- [ ] IF-0-RELEASE-3 - `pyproject.toml` `[project].version` is the only manual
  package version source of truth for the release bump; the selected release
  tag must be `vTARGET_VERSION`, and the top `CHANGELOG.md` entry plus fresh
  build artifact names must all match `TARGET_VERSION`.
- [ ] IF-0-RELEASE-4 - `chunker/__init__.py` and generated
  `chunker/_version.py` are not manually bumped for Phase 9 release prep; if
  older release helpers currently expect otherwise, they must be aligned or
  narrowed rather than preserved as conflicting authority.
- [ ] IF-0-RELEASE-5 - `.github/workflows/release.yml` remains the only
  production publish path, keeps the tag/version equality guard, rejects
  already-published PyPI versions before publish, runs package build plus
  `twine check`, and uses trusted publishing permissions.
- [ ] IF-0-RELEASE-6 - `.github/workflows/build-wheels.yml` remains
  artifact-only and does not gain a second publish path, trusted-publishing
  environment, or token-based PyPI upload step.
- [ ] IF-0-RELEASE-7 - Maintainer-facing release docs name the actual local
  validation sequence for this repo: focused release-policy tests, Phase 7
  hygiene gates, Phase 8 registry gates, package build/check, repo smoke,
  lint/format checks, Linux platform-core, and Windows preflight on `leno`.
- [ ] IF-0-RELEASE-8 - Any supported release-helper APIs under
  `chunker/distribution/` either align with the Phase 9 authority split
  (`pyproject.toml` + changelog + workflow release gate) or are explicitly
  documented/tested as non-authoritative compatibility helpers.
- [ ] IF-0-RELEASE-9 - Local artifact validation writes into a fresh ignored
  `dist/phase9-release-check-*` directory, checks only those artifacts with
  `twine check`, and confirms both wheel and sdist filenames contain
  `TARGET_VERSION`.
- [ ] IF-0-RELEASE-10 - Phase completion requires a clean tracked worktree
  except for ignored package artifacts under `dist/`, and Phase 9 must not
  broaden into parser-registry runtime changes, Boundary IR schema changes, new
  release credential flows, destructive cleanup, or release dispatch.

## Lane Index & Dependencies

- SL-0 - Release contract anchors; Depends on: (none); Blocks: SL-1, SL-2,
  SL-3, SL-4, SL-5; Parallel-safe: no
- SL-1 - Version source and top changelog entry; Depends on: SL-0; Blocks:
  SL-4, SL-5; Parallel-safe: no
- SL-2 - Distribution helper alignment; Depends on: SL-0; Blocks: SL-4, SL-5;
  Parallel-safe: yes
- SL-3 - Workflow guard and artifact gate review; Depends on: SL-0; Blocks:
  SL-4, SL-5; Parallel-safe: yes
- SL-4 - Maintainer release docs and spec sync; Depends on: SL-0, SL-1, SL-2,
  SL-3; Blocks: SL-5; Parallel-safe: no
- SL-5 - Release readiness verification reducer; Depends on: SL-0, SL-1, SL-2,
  SL-3, SL-4; Blocks: (none); Parallel-safe: no

## Lanes

### SL-0 - Release Contract Anchors

- **Scope**: Make the Phase 9 release gate mechanically reviewable with focused
  tests that pin the current authoritative version, changelog, workflow, and
  artifact-only wheel contract.
- **Owned files**: `tests/test_cicd_pipeline.py`
- **Interfaces provided**: IF-0-RELEASE-3, IF-0-RELEASE-5,
  IF-0-RELEASE-6; executable checks for package-version source, top changelog
  alignment, release workflow tag/version and PyPI-duplicate guards, trusted
  publishing, and non-publishing wheel workflow behavior
- **Interfaces consumed**: `pyproject.toml` `[project].version`,
  `CHANGELOG.md` top release heading, `.github/workflows/release.yml`,
  `.github/workflows/build-wheels.yml`, `scripts/run_ci_smoke.py`
- **Parallel-safe**: no
- **Tasks**:
  - test: keep or tighten the helper that reads `pyproject.toml` with
    `tomllib` and returns `[project].version`.
  - test: keep the top-changelog-version assertion so the release bump fails
    until both `pyproject.toml` and `CHANGELOG.md` are updated together.
  - test: keep textual workflow assertions for the tag/version equality guard,
    PyPI duplicate-version rejection, trusted publishing, and artifact-only
    wheel workflow behavior.
  - impl: keep these tests structural and repo-local; do not depend on the full
    GitHub Actions schema or external network state.
  - impl: extend the test only if execution reveals a real unguarded Phase 9
    contract surface.
  - verify: `uv run --with toml --all-extras pytest tests/test_cicd_pipeline.py -q`

### SL-1 - Version Source And Top Changelog Entry

- **Scope**: Apply the chosen `TARGET_VERSION` exactly once to the package
  version source of truth and the top changelog entry, without widening the
  version bump to unrelated files.
- **Owned files**: `pyproject.toml`, `CHANGELOG.md`
- **Interfaces provided**: IF-0-RELEASE-3, IF-0-RELEASE-9; `[project].version
  == TARGET_VERSION`; top changelog entry for `TARGET_VERSION`; release artifact
  naming target `vTARGET_VERSION`
- **Interfaces consumed**: release-policy tests from SL-0; current package
  version in `pyproject.toml`; current changelog structure; execution-time
  choice of `TARGET_VERSION`
- **Parallel-safe**: no
- **Tasks**:
  - test: before editing, confirm `TARGET_VERSION` is greater than the current
    `pyproject.toml` version and uses `X.Y.Z` form.
  - impl: update only `[project].version` in `pyproject.toml`; do not
    mass-replace historical version references elsewhere.
  - impl: update the top `CHANGELOG.md` entry to `TARGET_VERSION` and summarize
    the completed prior-phase work that is actually shipping in this release,
    including release hygiene and registry hardening where applicable.
  - impl: keep older changelog sections intact except for minimal formatting or
    ordering fixes needed to preserve the top-entry contract.
  - impl: do not edit `chunker/__init__.py` or `chunker/_version.py` here.
  - verify: `uv run --with toml --all-extras pytest tests/test_cicd_pipeline.py -q`

### SL-2 - Distribution Helper Alignment

- **Scope**: Reconcile public release-helper code and tests with the current
  authoritative Phase 9 release process so the repo no longer advertises
  contradictory release authority.
- **Owned files**: `chunker/distribution/release_manager.py`, `chunker/distribution/release.py`, `chunker/distribution/distributor.py`, `chunker/contracts/distribution_contract.py`, `chunker/contracts/distribution_stub.py`, `chunker/distribution/__init__.py`, `tests/unit/distribution/test_release_manager.py`, `tests/test_distribution_impl.py`, `tests/test_phase13_contracts.py`
- **Interfaces provided**: IF-0-RELEASE-4, IF-0-RELEASE-8; supported helper
  semantics that do not manually bump `chunker/__init__.py`, do not assume
  `setup.py` as a release source of truth, and do not create tags or publish as
  part of ordinary release preparation unless explicitly documented
- **Interfaces consumed**: package-version source from `pyproject.toml`;
  release workflow authority from SL-0; current distribution contract/export
  surface; maintainer flow from `docs/packaging.md`
- **Parallel-safe**: yes
- **Tasks**:
  - test: audit current helper behavior for version-file mutation, tag
    creation, build commands, and changelog generation against the live release
    docs and workflow contract.
  - test: tighten or update distribution tests so they assert the intended
    authority split instead of preserving obsolete `setup.py` or
    `chunker/__init__.py` bump behavior.
  - impl: if these helpers remain supported, align them to the current Phase 9
    contract: `pyproject.toml` as the bump target, changelog update as release
    prep, local build/check as validation, and workflow/tag/publish as later
    steps.
  - impl: if a helper is intentionally legacy/non-authoritative, narrow its
    exposed role explicitly instead of leaving behavior that silently conflicts
    with docs and workflows.
  - impl: do not introduce direct local publish, credential handling, or
    automatic tagging/pushing into these helpers.
  - verify: `uv run --with toml --all-extras pytest tests/unit/distribution/test_release_manager.py tests/test_distribution_impl.py tests/test_phase13_contracts.py -q`

### SL-3 - Workflow Guard And Artifact Gate Review

- **Scope**: Verify that release workflows and local artifact validation still
  enforce the frozen release gate after the version bump and helper alignment.
- **Owned files**: `.github/workflows/release.yml`, `.github/workflows/build-wheels.yml`
- **Interfaces provided**: IF-0-RELEASE-5, IF-0-RELEASE-6,
  IF-0-RELEASE-9; guarded release workflow; artifact-only wheel workflow; local
  package build/check contract for `TARGET_VERSION`
- **Interfaces consumed**: release-policy tests from SL-0; `TARGET_VERSION`
  from SL-1; release helper authority from SL-2 where relevant; current release
  docs and workflow inputs
- **Parallel-safe**: yes
- **Tasks**:
  - test: rerun the SL-0 release-policy tests after any workflow edits.
  - test: build fresh ignored artifacts in a unique directory such as
    `dist/phase9-release-check-TARGET_VERSION`.
  - test: run `twine check` against only those fresh artifacts and confirm both
    wheel and sdist filenames contain `TARGET_VERSION`.
  - impl: leave workflow files unchanged if the current guards and local
    artifact checks already satisfy the contract.
  - impl: if workflow edits are required, keep them limited to release-gate
    validation, artifact checks, or release-note packaging behavior; do not add
    alternate publish paths, change trusted-publishing posture, or fold dispatch
    into this phase.
  - verify: `uv run --with toml --all-extras pytest tests/test_cicd_pipeline.py -q`
  - verify: `uv run --with toml --all-extras python -m build --outdir dist/phase9-release-check-TARGET_VERSION`
  - verify: `uv run --with toml --all-extras python -m twine check dist/phase9-release-check-TARGET_VERSION/*`

### SL-4 - Maintainer Release Docs And Spec Sync

- **Scope**: Keep the release docs and active release-process spec aligned with
  the settled Phase 9 contract after the code and workflow lanes finish.
- **Owned files**: `docs/packaging.md`, `docs/development/RELEASE_CHECKLIST.md`, `docs/development/DEPLOYMENT.md`, `docs/cli-reference.md`, `specs/active/release-process-spec.md`
- **Interfaces provided**: IF-0-RELEASE-2, IF-0-RELEASE-7,
  IF-0-RELEASE-10; accurate maintainer flow covering version bump, changelog,
  local validation, clean-tree requirement, and the tag/push boundary
- **Interfaces consumed**: release-policy anchors from SL-0; `TARGET_VERSION`
  and changelog expectations from SL-1; helper semantics from SL-2; workflow
  and artifact gate behavior from SL-3; `AGENTS.md` local-first validation loop
- **Parallel-safe**: no
- **Tasks**:
  - test: rely on MkDocs strict build for link correctness unless execution
    introduces a new focused doc-specific regression test.
  - impl: update `docs/packaging.md` and
    `docs/development/RELEASE_CHECKLIST.md` so they describe the actual release
    prep order: choose `TARGET_VERSION`, bump `pyproject.toml`, update the top
    `CHANGELOG.md` entry, run release-policy tests, run Phase 7 and Phase 8
    gates, build/check fresh artifacts, run repo smoke plus platform checks,
    confirm a clean tracked tree, then tag/push only when explicitly ready.
  - impl: update `specs/active/release-process-spec.md` only if execution
    changes the supported release authority or trigger wording.
  - impl: update `docs/development/DEPLOYMENT.md` or `docs/cli-reference.md`
    only where they drift from the settled release guidance.
  - impl: do not document alternate credential flows, local production publish
    commands, or a new release-dispatch authority here.
  - verify: `uv run --with toml --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict`

### SL-5 - Release Readiness Verification Reducer

- **Scope**: Run the final Phase 9 validation matrix, reduce results, and stop
  at a clean release-prep handoff without tagging, pushing, or publishing.
- **Owned files**: `none`
- **Interfaces provided**: release-readiness decision for `TARGET_VERSION`;
  final passed-command inventory; clean-tree gate before any later human or
  automation dispatch step
- **Interfaces consumed**: release-policy anchors from SL-0; version/changelog
  outputs from SL-1; helper alignment from SL-2; workflow/artifact gate from
  SL-3; maintainer-doc updates from SL-4
- **Parallel-safe**: no
- **Tasks**:
  - test: rerun `tests/test_cicd_pipeline.py` after all file edits settle.
  - test: run the Phase 7 hygiene batch and MkDocs strict build.
  - test: run the Phase 8 deprecation-as-error registry, parser/factory, CLI,
    and Boundary IR snapshot batches.
  - test: run the distribution-helper test batch from SL-2.
  - test: run local package build/check in the fresh
    `dist/phase9-release-check-*` directory and confirm artifact names match
    `TARGET_VERSION`.
  - test: run lint, Black check, CI smoke, Linux platform-core, and Windows
    preflight on `leno`.
  - impl: route any discovered fixes back to the upstream owning lane instead
    of editing tracked files from this reducer lane.
  - impl: confirm `git status --short` is clean except for ignored `dist/`
    artifacts before recommending any later tag/push step.
  - impl: do not create tags, push commits or tags, manually dispatch
    workflows, or publish to PyPI in this lane.
  - verify: `git status --short`

## Verification

Planning wrote the artifact only; verification was not run. During execution,
run the release-policy and version-alignment checks first:

```bash
uv run --with toml --all-extras pytest tests/test_cicd_pipeline.py -q
uv run --with toml --all-extras pytest tests/unit/distribution/test_release_manager.py tests/test_distribution_impl.py tests/test_phase13_contracts.py -q
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
uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_registry.py tests/test_registry_fallback.py -q
uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_factory.py tests/test_parser.py tests/test_chunking.py -q
uv run --with toml --all-extras pytest -W error::DeprecationWarning tests/test_cli.py tests/test_boundary_ir_golden_snapshots.py -q
```

Then run the repo-standard local-first validation loop plus standing
platform checks:

```bash
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
uv run --with toml --all-extras python scripts/run_platform_core.py --platform linux
ssh leno 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
git status --short
```

## Acceptance Criteria

- [ ] `plans/phase-plan-v1-RELEASE.md` is the authoritative uppercase Phase 9
  execution artifact for roadmap hash
  `ed2f074348a946a5642d1e02904b35ac4076153923aa5932623c28d304c494a2`.
- [ ] Phase 9 remains a release-prep phase only; it does not tag, push,
  manually dispatch `release.yml`, or publish to PyPI.
- [ ] `TARGET_VERSION` is chosen once, is greater than the prior package
  version, and uses `X.Y.Z` form.
- [ ] `pyproject.toml` `[project].version` equals `TARGET_VERSION`.
- [ ] The intended release tag is exactly `vTARGET_VERSION`.
- [ ] The first `CHANGELOG.md` release heading matches `TARGET_VERSION`.
- [ ] `chunker/__init__.py` and generated `chunker/_version.py` remain outside
  the manual release-bump path.
- [ ] `tests/test_cicd_pipeline.py` enforces changelog/version alignment,
  release workflow tag/version guard, PyPI duplicate-version rejection,
  trusted publishing, and artifact-only wheel workflow behavior.
- [ ] Any supported release helper surface under `chunker/distribution/`
  matches the current release authority split or is explicitly narrowed as a
  non-authoritative compatibility surface.
- [ ] `.github/workflows/release.yml` remains the only production publish path
  and still fails early on tag/version mismatch, duplicate PyPI version, build
  failure, or `twine check` failure.
- [ ] `.github/workflows/build-wheels.yml` remains artifact-only and does not
  publish to PyPI.
- [ ] Fresh local wheel and sdist artifacts built in
  `dist/phase9-release-check-*` contain `TARGET_VERSION` in their filenames and
  pass `twine check`.
- [ ] `docs/packaging.md`, `docs/development/RELEASE_CHECKLIST.md`, and
  `specs/active/release-process-spec.md` describe the actual release-prep
  validation flow for this repo.
- [ ] Phase 7 hygiene gates pass after the release-prep edits.
- [ ] Phase 8 registry compatibility gates pass after the release-prep edits.
- [ ] Distribution-helper tests, lint, Black check, CI smoke, Linux
  platform-core, MkDocs strict build, package build/check, and Windows
  preflight on `leno` pass before any later tag/push step.
- [ ] `git status --short` is clean before release handoff, except for ignored
  package artifacts under `dist/`.
- [ ] Phase 9 does not add alternate publish paths, new credential handling,
  destructive cleanup, parser runtime changes, or Boundary IR contract changes.

## Closeout

Artifact state: staged

Next phase: RELEASE - execution ready

Next command: `codex-execute-phase plans/phase-plan-v1-RELEASE.md`

```yaml
automation:
  status: planned
  next_skill: codex-execute-phase
  next_command: codex-execute-phase plans/phase-plan-v1-RELEASE.md
  next_model_hint: execute
  next_effort_hint: medium
  human_required: false
  blocker_class: none
  blocker_summary: none
  required_human_inputs: []
  verification_status: not_run
  artifact: /home/viperjuice/code/treesitter-chunker/plans/phase-plan-v1-RELEASE.md
  artifact_state: staged
```

---
phase_loop_plan_version: 1
phase: HYGIENE
roadmap: specs/phase-plans-v1.md
roadmap_sha256: 8e02fa7e008f0a7df7dd7b28c36c2c2eb2ab79b5ebdc52cb8e3fd611efee277c
---

# HYGIENE: Release Hygiene Baseline

## Context

Roadmap source: `specs/phase-plans-v1.md`, Phase 7 (`HYGIENE`). Canonical
runner state in `.phase-loop/state.json` marks `SEMANTIC` complete,
`HYGIENE` as the current unplanned phase, and the repo clean on `main` at
`2572dbd3fccde62a47886f0f211274b4eb33f479` with no dirty paths. The roadmap
hash in `.phase-loop/state.json` matches the required planning hash
`8e02fa7e008f0a7df7dd7b28c36c2c2eb2ab79b5ebdc52cb8e3fd611efee277c`.

This repository is already partway through the Phase 7 hygiene outcome.
`mkdocs.yml` already contains explicit `Boundary IR` navigation entries plus
exact `not_in_nav` paths for the current maintainer-only docs.
`tests/test_fallback_chunking.py`, `tests/test_auto.py`, and
`tests/test_overlapping_fallback.py` already use local `pytest.warns(...)`
assertions for intentional `FallbackWarning` behavior. The repo also already
has `tests/test_release_hygiene_policy.py` and maintainer/internal notices at
the top of `docs/development/DEPLOYMENT.md`,
`docs/development/RELEASE_CHECKLIST.md`, and
`docs/final-integration-testing.md`.

Execution for this phase should therefore be a verification-and-tightening pass
over the already-landed docs navigation, fallback-warning, and skip-policy
surfaces. It should preserve the current runtime behavior, keep warning policy
local to the tests that trigger it, and avoid reopening parser registry,
release publishing, or fallback implementation work that belongs to later or
different phases.

The older lowercase artifact was removed to avoid case-insensitive filesystem
collisions. Phase-loop execution for this run should follow this uppercase
`plans/phase-plan-v1-HYGIENE.md` artifact.

This planning run wrote the artifact only; it did not execute tests, docs
builds, formatters, or Windows preflight commands.

## Interface Freeze Gates

- [ ] IF-0-HYGIENE-1 - The uppercase artifact
  `plans/phase-plan-v1-HYGIENE.md` is the authoritative Phase 7 execution plan
  for roadmap hash
  `8e02fa7e008f0a7df7dd7b28c36c2c2eb2ab79b5ebdc52cb8e3fd611efee277c`.
- [ ] IF-0-HYGIENE-2 - Every Phase 7 public Markdown page under `docs/`
  remains either explicitly listed in `mkdocs.yml` `nav` or intentionally
  listed in exact `not_in_nav` entries; wildcard omitted-page suppression such
  as `not_in_nav: *` is forbidden.
- [ ] IF-0-HYGIENE-3 - `docs/agent-interface-readiness.md`,
  `docs/interface-boundary-roadmap.md`, `docs/interface-boundary-spec.md`, and
  `docs/grammar_management.md` remain discoverable as public docs through
  explicit nav and landing-page links, while
  `docs/development/DEPLOYMENT.md`,
  `docs/development/RELEASE_CHECKLIST.md`, and
  `docs/final-integration-testing.md` remain intentionally internal.
- [ ] IF-0-HYGIENE-4 - Internal docs omitted from nav keep a clear
  maintainer/internal notice near the top of the page and remain reachable from
  maintainer-facing guidance where useful.
- [ ] IF-0-HYGIENE-5 - Tests that intentionally trigger `FallbackWarning`
  assert those warnings locally with `pytest.warns(FallbackWarning, match=...)`
  or an equally narrow scoped capture; no global warning filter is added to
  hide expected fallback behavior.
- [ ] IF-0-HYGIENE-6 - `tests/conftest.py`, `pyproject.toml`, and the focused
  Phase 7 test files remain free of collection-time xfail injection, broad
  `FallbackWarning` suppression, and centralized skip/xfail policy mutation.
- [ ] IF-0-HYGIENE-7 - Platform skips remain local to tests that genuinely need
  them and include explicit reasons tied to unavailable platform features or
  dependencies.
- [ ] IF-0-HYGIENE-8 - Phase 7 does not change fallback runtime behavior,
  warning class names, parser registry loading, tree-sitter language-pack
  fallback semantics, or release publishing/versioning behavior unless focused
  evidence shows a real product bug.
- [ ] IF-0-HYGIENE-9 - Phase completion requires the MkDocs strict build, the
  focused fallback-warning pytest batch, repo smoke validation, and the
  standing Windows preflight command to pass without xfail or xpass results.

## Lane Index & Dependencies

- SL-0 - Docs navigation and inventory contract; Depends on: (none); Blocks:
  SL-3; Parallel-safe: no
- SL-1 - Fallback-warning assertions for base and zero-config paths; Depends on:
  (none); Blocks: SL-2, SL-3; Parallel-safe: yes
- SL-2 - Overlapping fallback warning and test-policy anchors; Depends on:
  SL-1; Blocks: SL-3; Parallel-safe: mixed
- SL-3 - Maintainer docs and release-hygiene synthesis; Depends on: SL-0,
  SL-1, SL-2; Blocks: (none); Parallel-safe: no

## Lanes

### SL-0 - Docs Navigation And Inventory Contract

- **Scope**: Preserve and tighten the explicit MkDocs public-versus-internal
  document classification around the current Phase 7 doc set.
- **Owned files**: `mkdocs.yml`, `docs/index.md`
- **Interfaces provided**: IF-0-HYGIENE-2, IF-0-HYGIENE-3; explicit nav and
  `not_in_nav` contract for the Phase 7 doc inventory; landing-page discovery
  for public Boundary IR and grammar guidance
- **Interfaces consumed**: current docs inventory under `docs/`; existing
  `mkdocs.yml` nav structure; current maintainer/internal doc split
- **Parallel-safe**: no
- **Tasks**:
  - test: audit the current `docs/` inventory against `mkdocs.yml` so this
    phase verifies the existing explicit nav contract instead of assuming it.
  - test: confirm the current explicit `not_in_nav` entries stay narrow and do
    not hide additional docs by wildcard or broad directory suppression.
  - impl: keep the existing `Boundary IR` nav grouping explicit and update it
    only if repo inventory drift leaves a live Phase 7 page undiscoverable.
  - impl: keep `docs/index.md` aligned with the public docs surfaced in nav,
    especially the Boundary IR and grammar-management entry points.
  - impl: do not move docs between public and internal buckets without
    repository evidence that the current classification is wrong.
  - verify: `uv run --with toml --all-extras mkdocs build --strict`

### SL-1 - Fallback-Warning Assertions For Base And Zero-Config Paths

- **Scope**: Keep expected fallback warnings local and reviewable in the base
  fallback and zero-config test surfaces.
- **Owned files**: `tests/test_fallback_chunking.py`, `tests/test_auto.py`
- **Interfaces provided**: IF-0-HYGIENE-5; local expected-warning assertions
  for line-based fallback, fallback manager, and zero-config fallback paths
- **Interfaces consumed**: `FallbackWarning`; `FallbackManager`; zero-config
  auto-chunk behavior; current fallback warning message text
- **Parallel-safe**: yes
- **Tasks**:
  - test: audit current fallback-warning assertions in
    `tests/test_fallback_chunking.py` and `tests/test_auto.py` to verify they
    already cover every intentionally warning-producing path touched by Phase 7.
  - test: add or tighten local assertions only where a warning-producing path
    still leaks into pytest summaries or where the current `match=` text is too
    weak to make the behavior reviewable.
  - impl: keep imports and helper code minimal; prefer local `pytest.warns(...)`
    scopes over new shared fixtures or global filters.
  - impl: do not modify `chunker/fallback/`, `chunker/auto.py`, or warning text
    in this lane unless focused tests demonstrate a real product bug.
  - verify: `uv run --with toml --all-extras pytest tests/test_fallback_chunking.py tests/test_auto.py -q`

### SL-2 - Overlapping Fallback Warning And Test-Policy Anchors

- **Scope**: Preserve the overlapping fallback warning contract and make the
  no-central-xfail/no-global-warning-policy rules mechanically reviewable.
- **Owned files**: `tests/test_overlapping_fallback.py`, `tests/test_release_hygiene_policy.py`, `tests/conftest.py`
- **Interfaces provided**: IF-0-HYGIENE-5, IF-0-HYGIENE-6, IF-0-HYGIENE-7;
  local overlapping fallback warning assertions; executable hygiene policy
  checks for xfail absence and centralized warning-policy drift
- **Interfaces consumed**: warning assertion shape from SL-1; current
  overlapping fallback helpers; existing `tests/conftest.py`; pytest project
  configuration in `pyproject.toml`
- **Parallel-safe**: mixed
- **Tasks**:
  - test: verify `tests/test_overlapping_fallback.py` continues to assert each
    intentional `FallbackWarning` locally, including helper-assisted warning
    checks for overlapping and asymmetric strategies.
  - test: keep `tests/test_release_hygiene_policy.py` focused on repo hygiene
    invariants: no `pytest.mark.xfail`, no `pytest.xfail(...)`, no
    collection-time policy mutation in `tests/conftest.py`, and no broad
    `FallbackWarning` filter in repo config.
  - test: tighten the policy test only if current repo evidence reveals a
    missing executable guard for a real Phase 7 contract.
  - impl: leave `tests/conftest.py` unchanged if it remains fixture-only and
    free of centralized skip/xfail mutation; if not, fix the central policy
    problem here instead of compensating in individual tests.
  - impl: do not alter overlap chunking behavior, warning class names, or
    platform skip semantics except to make reasons more explicit where needed.
  - verify: `uv run --with toml --all-extras pytest tests/test_overlapping_fallback.py tests/test_release_hygiene_policy.py -q`

### SL-3 - Maintainer Docs And Release-Hygiene Synthesis

- **Scope**: Reduce the settled Phase 7 hygiene rules into accurate maintainer
  docs and release guidance after the producer lanes confirm the live contract.
- **Owned files**: `docs/agent-interface-readiness.md`, `docs/interface-boundary-roadmap.md`, `docs/grammar_management.md`, `docs/development/DEPLOYMENT.md`, `docs/development/RELEASE_CHECKLIST.md`, `docs/final-integration-testing.md`
- **Interfaces provided**: IF-0-HYGIENE-3, IF-0-HYGIENE-4, IF-0-HYGIENE-8,
  IF-0-HYGIENE-9; accurate public/internal doc framing; release-hygiene gate
  guidance for strict docs, focused warning tests, smoke validation, and
  Windows preflight
- **Interfaces consumed**: doc classification from SL-0; warning-policy
  evidence from SL-1 and SL-2; repo-standard validation loop from `AGENTS.md`
- **Parallel-safe**: no
- **Tasks**:
  - test: review the maintainer docs against the executable checks from SL-0
    through SL-2 and add no docs-only assertions unless a documented rule lacks
    a focused verification hook.
  - impl: preserve or tighten the maintainer/internal notices at the top of
    the intentionally omitted docs so their status stays explicit.
  - impl: update `docs/development/RELEASE_CHECKLIST.md` only where Phase 7
    release-hygiene gates drift from the live repo contract: strict MkDocs
    build, focused fallback-warning tests, no xfail/xpass results, smoke
    validation, and the standing `leno` Windows preflight.
  - impl: update public docs named in this phase only where their wording
    drifts from the settled release-hygiene posture; do not reopen Boundary IR
    scope, parser registry behavior, or release publishing flows here.
  - impl: do not broaden this lane into Phase 8 registry hardening, Phase 9
    version bumps/releases, or fallback runtime behavior changes.
  - verify: `uv run --with toml --all-extras pytest tests/test_release_hygiene_policy.py tests/test_auto.py tests/test_fallback_chunking.py tests/test_overlapping_fallback.py -q`
  - verify: `uv run --with toml --all-extras mkdocs build --strict`

## Verification

Planning wrote the artifact only; verification was not run. During execution,
run the Phase 7-focused checks first, then the repo-standard local validation
loop from `AGENTS.md`:

```bash
uv run --with toml --all-extras pytest tests/test_release_hygiene_policy.py tests/test_auto.py tests/test_fallback_chunking.py tests/test_overlapping_fallback.py -q
uv run --with toml --all-extras mkdocs build --strict
uv run --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --with toml --all-extras python scripts/run_ci_smoke.py
```

Because this phase touches warning-sensitive tests, docs strictness, and
cross-platform release hygiene, run the standing Windows preflight before
pushing:

```bash
ssh win 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
```

## Acceptance Criteria

- [ ] `plans/phase-plan-v1-HYGIENE.md` is the authoritative uppercase Phase 7
  execution artifact for roadmap hash
  `8e02fa7e008f0a7df7dd7b28c36c2c2eb2ab79b5ebdc52cb8e3fd611efee277c`.
- [ ] MkDocs strict build passes without broken-link or omitted-page warnings
  for the documented pages touched by Phase 7.
- [ ] `mkdocs.yml` keeps the public Phase 7 docs in explicit nav and keeps the
  intentionally internal Phase 7 docs in exact `not_in_nav` entries.
- [ ] `docs/index.md` keeps the public Boundary IR and grammar-management docs
  discoverable from the landing page.
- [ ] Maintainer/internal docs omitted from nav keep an explicit maintainer note
  near the top of the page.
- [ ] Tests that intentionally trigger `FallbackWarning` assert those warnings
  locally and do not leak incidental fallback warnings into pytest summaries.
- [ ] `tests/conftest.py`, `pyproject.toml`, and the focused Phase 7 test files
  remain free of centralized `FallbackWarning` suppression and xfail-policy
  mutation.
- [ ] No `pytest.mark.xfail`, `pytest.xfail(...)`, xfail results, or xpass
  results are introduced by the focused Phase 7 tests, smoke validation, or
  Windows preflight.
- [ ] Platform skips that remain in the touched Phase 7 surfaces are local,
  explicit, and reasoned by unavailable platform features or optional
  dependencies.
- [ ] The focused Phase 7 pytest batch passes:
  `tests/test_release_hygiene_policy.py`, `tests/test_auto.py`,
  `tests/test_fallback_chunking.py`, and `tests/test_overlapping_fallback.py`.
- [ ] Repo smoke validation remains green with
  `uv run --with toml --all-extras python scripts/run_ci_smoke.py`.
- [ ] Windows preflight remains green with
  `uv run --with toml --all-extras python scripts/run_windows_preflight.py` on
  `win`.
- [ ] Phase 7 does not publish a release, bump package versions, rework parser
  registry loading, or change fallback runtime behavior except for a real
  evidence-backed bug fix discovered during execution.

## Closeout

Artifact state: staged

Next phase: HYGIENE - execution ready

Next command: `codex-execute-phase plans/phase-plan-v1-HYGIENE.md`

```yaml
automation:
  status: planned
  next_skill: codex-execute-phase
  next_command: codex-execute-phase plans/phase-plan-v1-HYGIENE.md
  next_model_hint: execute
  next_effort_hint: medium
  human_required: false
  blocker_class: none
  blocker_summary: none
  required_human_inputs: []
  verification_status: not_run
  artifact: /home/viperjuice/code/treesitter-chunker/plans/phase-plan-v1-HYGIENE.md
  artifact_state: staged
```

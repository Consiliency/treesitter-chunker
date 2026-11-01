---
phase_loop_plan_version: 1
phase: CIFAST
roadmap: specs/phase-plans-v4.md
roadmap_sha256: a96ef9073df2cd1bd860b1a151d75abc0a7edde7f242d8a2d7613c3fb38726c9
automation:
  # Post-merge suite. Each lane adds its own test file; until a lane merges,
  # drop its file from this command.
  suite_command: "uv run --locked --all-extras pytest tests/test_lint_path_policy.py tests/test_release_hygiene_policy.py tests/test_symbol_analysis_deadline.py tests/test_language_smoke.py tests/test_compiled_grammar_analysis_contract.py tests/test_workflow_permissions_policy.py tests/test_scratch_root_policy.py -q -n 4"
---

# CIFAST: CI and infrastructure hygiene

## Context

CIFAST is Phase 6 of `specs/phase-plans-v4.md` (roadmap hash above). It was
planned from main `2cdcc846` (treesitter-chunker#548 merge). treesitter-chunker#534
is merged, so no lane edits a Python-version field.

All five issues were re-read on 2026-10-31 with `gh issue view N --comments`.
All are open. Each reproduces at `2cdcc846`:

| Issue | Observed on `2cdcc846` |
|---|---|
| treesitter-chunker#517 | `ruff check --show-files` with the CI arguments lists every tracked `.py` under `chunker/`, `cli/` and `tests/` except the four `chunker/build/*.py` files. `ruff check chunker/build/` reports F401 at `chunker/build/builder.py:538:44` (`wheel.metadata.pkginfo_to_metadata`). Both the `.gitignore` entry `build/` and the `[tool.ruff]` `exclude` entry `"build"` match the directory. |
| treesitter-chunker#207 | `GrammarAnalyzer.analyze_grammar_symbols` runs `nm` with a five-second wall deadline. On expiry it logs a warning and returns empty symbol lists, which callers count as `symbols_count == 0`, the same as a grammar with no symbols. |
| treesitter-chunker#143 | `tests/language_smoke.py::load_language` maps a five-second wall-deadline expiry to `fails_to_load`. CPU starvation and the genuinely non-terminating COBOL parser therefore produce the same outcome as a grammar that cannot load. |
| treesitter-chunker#507 (source) | Every workflow has a top-level `contents: read`, but 10 of 15 jobs have no `permissions:` block. `docs.yml` grants `contents: write` to its whole job, including pull-request builds that run `pip install -e .`. A scoped scan of `uv.lock` found advisories in 18 packages (7 in the base runtime set). The issue's `package-lock.json` and template `requirements.txt` rows still apply. |
| treesitter-chunker#481 (repo part) | Tracked scripts, tools and tests still name literal `/tmp` scratch roots, for example `.ai-dev-kit/skills/spawn/agent/fork_terminal.py`, `.claude/hooks/test_multi_instance.py` and `api/examples/curl_examples.sh`. CONTRIBUTING.md has no scratch rule. |

The exact commands and outputs go in each PR body (VB-1).

## Interface Freeze Gates

- [ ] IF-0-CIFAST-1 — the canonical lint/format path list and Ruff inclusion
  policy. Published by SL-lint in `tests/test_lint_path_policy.py`, which
  asserts it:

  ```
  uv run --locked --all-extras ruff check chunker/ chunker/build/ cli/ tests/ tools/governed_group.py tools/governed_scope.py tools/sync_governed_test_transport.py --exclude archive --exclude logs --exclude site
  uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/ tools/governed_group.py tools/governed_scope.py tools/sync_governed_test_transport.py
  ```

  Inclusion policy: the `.gitignore` `build/` entry and the `[tool.ruff]`
  `"build"` exclusion stay, because they keep generated build output out of
  Ruff. The tracked source package is named on the command line as
  `chunker/build/`; Ruff does not apply its exclusions to explicitly named paths
  while `force-exclude` is unset. `.github/workflows/ci.yml`,
  `.github/workflows/release.yml` and CONTRIBUTING.md each contain exactly these
  two commands. PY314 consumes this list for the release type-check lines.
  Black has the same discovery gap: `.gitignore` applies inside an explicitly
  named directory too. That is treesitter-chunker#566 and is not changed here.
- [ ] IF-0-CIFAST-2 — the treesitter-chunker#507 settings proposal, in the body
  of the SL-perm workflow PR: the current and proposed
  `default_workflow_permissions` (read via
  `gh api repos/Consiliency/treesitter-chunker/actions/permissions/workflow`),
  the per-job `permissions:` audit table, and a rollback that never restores
  read/write. SETTINGS consumes it. No agent changes the setting.

## Lane Index & Dependencies

SL-lint — CI Ruff discovery of tracked `chunker/build` (treesitter-chunker#517)
  Depends on: (none)
  Blocks: SL-perm-wf (`ci.yml`, `release.yml`), SL-scratch (`CONTRIBUTING.md`)
  Parallel-safe: yes

SL-deadline — truthful deadline outcomes (treesitter-chunker#207, then treesitter-chunker#143)
  Depends on: (none)
  Blocks: (none)
  Parallel-safe: yes (merges one at a time with ADMIT SL-ins on `grammar_analyzer.py`)

SL-perm-wf — explicit least-privilege workflow permissions (treesitter-chunker#507)
  Depends on: SL-lint (stacked on its branch)
  Blocks: SETTINGS
  Parallel-safe: no (single writer of workflow files after SL-lint)

SL-perm-deps — dependency advisory triage (treesitter-chunker#507)
  Depends on: (none)
  Blocks: (none)
  Parallel-safe: yes (disjoint files)

SL-scratch — disk scratch rule and literal `/tmp` check (treesitter-chunker#481)
  Depends on: SL-lint (stacked on its branch)
  Blocks: PY314 (`CONTRIBUTING.md` order)
  Parallel-safe: no (`CONTRIBUTING.md`)

## Lanes

### SL-lint — treesitter-chunker#517

- **Scope**: IF-0-CIFAST-1 and the newly exposed findings. One PR, which also
  carries this plan.
- **Owned files**: `.github/workflows/ci.yml` and `.github/workflows/release.yml`
  (lint and format lines only), `pyproject.toml` `[tool.ruff]` (comment only),
  `chunker/build/builder.py` (the F401 line only), `CONTRIBUTING.md`,
  `tests/test_lint_path_policy.py`, the wheel-fallback cases in
  `tests/test_release_hygiene_policy.py`, the SL-lint entry in
  `scripts/run_ci_smoke.py`, and this plan.
- **Tasks**:
  - test: `tests/test_lint_path_policy.py` asserts that the three command files
    hold exactly the canonical commands, and that `ruff check --show-files` with
    the canonical arguments discovers every tracked `.py`/`.pyi` under the
    listed directories. Its discriminator builds a disposable Git checkout from
    `pyproject.toml`, `.gitignore`, the tracked `chunker/build` sources and the
    governed tools, with `chunker/build` force-tracked as in the real
    repository. The clean tree passes the canonical command. An F401 appended to
    the tracked `chunker/build/builder.py` fails it at that line. An ignored
    `build/lib/generated.py` with the same violation is never reported.
  - impl: Add `chunker/build/` to the Ruff command in `ci.yml`, `release.yml`
    and CONTRIBUTING.md. Bring the `release.yml` Ruff and Black lines to the
    canonical list (they lacked the governed tools). Remove the unused
    `wheel.metadata.pkginfo_to_metadata` import. Under the locked
    `wheel==0.45.1` both modules exist, so the wheel path is unchanged. The ZIP
    fallback test now blocks `wheel.wheelfile`, the import the fallback
    actually depends on.
  - No baseline, `noqa`, per-file ignore or global ignore is added.

### SL-deadline — treesitter-chunker#207 then treesitter-chunker#143

- **Scope**: truthful cause reporting for the two five-second deadlines. The
  production deadline stays five seconds. One PR with one commit per issue.
- **Owned files**: `chunker/languages/compatibility/grammar_analyzer.py`
  (`GrammarAnalyzer.analyze_grammar_symbols` only), `tests/language_smoke.py`,
  `tests/test_language_smoke.py`, the BAML capabilities case in
  `tests/test_compiled_grammar_analysis_contract.py`, the new
  `tests/test_symbol_analysis_deadline.py`, the new
  `scripts/run_deadline_load_harness.py`, `CHANGELOG.md`, and the SL-deadline
  entry in `scripts/run_ci_smoke.py`.
- **Tasks**:
  - impl (treesitter-chunker#207): `analyze_grammar_symbols(path, *, timeout=5.0)`
    adds a non-list `analysis` entry to its result: `status` is `complete`,
    `deadline_expired`, `unavailable` (Windows or no `nm`) or `failed`, plus
    `deadline_seconds` and a `detail` string. Symbol lists and their counting
    are unchanged; `symbols_count` and feature detection already ignore
    non-list values. The keyword defaults to the existing five seconds, and
    no caller changes it.
  - test (treesitter-chunker#207): with the real compiled BAML grammar and real
    `nm`, a normal run reports `complete` with symbols. `timeout=1e-6` kills the
    real `nm` and reports `deadline_expired` with empty lists. An empty `PATH`
    reports `unavailable`, and a non-ELF file reports `failed`. The BAML
    capabilities case records each real analysis outcome. When an analysis
    completed, it asserts `symbols_count > 0` as before. When it reports
    `deadline_expired`, it asserts that the expiry was reported (not a silent
    zero), then re-analyzes the same artifact under a load-tolerant bound and
    asserts symbols are found. Any other outcome fails.
  - impl (treesitter-chunker#143): `load_language(name, *, deadline=5)` returns
    `deadline_expired` for a wall-deadline expiry, separate from
    `fails_to_load`. `confirm_load` re-probes a `deadline_expired` result once
    under the load-tolerant bound. `compute_coverage` uses it, except for
    `UNSAFE_PACK_LANGUAGES` (COBOL loops natively and is never re-probed). A
    confirmed expiry is still recorded as `fails_to_load` with the deadline
    error, so the committed coverage oracle is unchanged.
  - test (treesitter-chunker#143): a tiny deadline kills a real Python probe
    and reports `deadline_expired`, while a missing grammar still reports
    `fails_to_load`. The per-language load test uses `confirm_load` and still
    asserts `loads`. The COBOL test asserts `deadline_expired`, so a real hang
    is never re-labelled as starvation.
  - harness: `scripts/run_deadline_load_harness.py` (Linux) pins N busy
    processes and a niced probe child to one CPU, then runs the real `nm`
    analysis and the Python load probe. It prints the outcomes as JSON. On
    unchanged main it shows the false `fails_to_load` and the silent empty
    symbol lists. With the fix it shows `deadline_expired`. It is a heavy run
    under the host caps.
- **Load-tolerant bound**: 45 seconds, applied only after a recorded expiry and
  only in tests and the coverage sweep, below the CI smoke's 60-second pytest
  timeout. A real hang, a load error or a missing symbol table still fails. A
  grammar that needs 5–45 seconds to parse one byte passes the availability
  smoke, because the issues ask to separate availability from a performance
  budget.

### SL-perm-wf — treesitter-chunker#507 workflow permissions

- **Scope**: every job gets an explicit `permissions:` block, with write scopes
  only where publication needs them. IF-0-CIFAST-2 goes in the PR body. No
  repository setting is changed.
- **Owned files**: the `permissions:` blocks of all `.github/workflows/*.yml`,
  the `docs.yml` job split, `tests/test_workflow_permissions_policy.py`, and
  its `scripts/run_ci_smoke.py` entry.
- **Tasks**:
  - test: every workflow and job declares `permissions:`; only an allowlisted
    (workflow, job, scope) set may hold `write`, and each entry names its
    publication step. A job holding `id-token: write` must use
    `pypa/gh-action-pypi-publish` behind a GitHub environment. Mutations:
    removing a job's block, or granting `contents: write` to the docs build job,
    fail it.
  - impl: add job-level blocks (`contents: read`, or `{}` for jobs that never
    read the repository). Split `docs.yml` into a read-only build job and a
    deploy job that runs only on pushes to `main`, holds `contents: write`, and
    publishes the uploaded artifact with the same pinned action.

### SL-perm-deps — treesitter-chunker#507 dependency triage

- **Scope**: scoped advisory scans of `uv.lock`,
  `ide/vscode/treesitter-chunker/package-lock.json` and
  `.ai-dev-kit/dev-tools/mcp/_templates/python/requirements.txt`. Applicable
  matches get the smallest compatible change; the rest are recorded as
  inapplicable or deferred with reasons. No blanket upgrade, no parser or
  runtime pin change, and no `pyproject.toml` floor change.
- **Owned files**: the three manifests and `CHANGELOG.md`.
- **Tasks**: deduplicate advisory aliases. Classify each package as base
  runtime, extra, dev/CI or template, and record installed versions. Upgrade
  only listed packages with `uv lock --upgrade-package <name>==<fixed>`, and
  inspect the lock diff. Re-scan, then run the CI smoke and the platform-core
  tier. The triage table goes in the PR body, with evidence restricted to
  metadata.

### SL-scratch — treesitter-chunker#481 repo part

- **Scope**: the CONTRIBUTING scratch rule and a repository check. The issue
  stays open for agent-harness#1220 and dotfiles#68.
- **Owned files**: its `CONTRIBUTING.md` paragraph,
  `tests/test_scratch_root_policy.py`, its `scripts/run_ci_smoke.py` entry, and
  the tracked scripts/tools/tests whose literal `/tmp` scratch roots it
  replaces.
- **Tasks**:
  - test: scan tracked `.py`, `.sh`, `.bash` and `.ps1` files outside
    `archive/`, `site/`, `tests/fixtures/` and the product package `chunker/`.
    No line may name a `/tmp` root, except an exact-line allowlist of synthetic
    path labels that are never created on disk, each with a reason.
  - impl: replace the scratch uses with `tempfile`/`mktemp` under the inherited
    `TMPDIR`, removed when done.
  - docs: CONTRIBUTING states the rule: verification scratch goes under the
    inherited disk `TMPDIR` via `tempfile` or `mktemp`, never a literal `/tmp`,
    and disposable trees are removed in `finally`.

## Execution Notes

- One branch per lane off `origin/main`. SL-perm-wf and SL-scratch are stacked
  on SL-lint and retarget to `main` after it merges. Merge order:
  - `ci.yml` and `release.yml`: SL-lint, then SL-perm-wf.
  - `CONTRIBUTING.md`: SL-lint, then SL-scratch.
  - `grammar_analyzer.py`: SL-deadline and ADMIT SL-ins
    (treesitter-chunker#563) merge one at a time; the second rebases.
  - `chunker/build/builder.py`: SL-lint edits one import line. ADMIT
    treesitter-chunker#556 edits the wheel inventory; the second rebases.
- SL-perm is split into two PRs for treesitter-chunker#507. The workflow PR
  carries IF-0-CIFAST-2, so SETTINGS is not held behind the lockfile review.
- Discovered and filed separately: treesitter-chunker#566 (Black skips
  `chunker/build` the same way) and treesitter-chunker#567
  (`scripts/run_ci_smoke.py` hard-codes `pytest -n auto`, which breaks the
  host's four-worker cap). treesitter-chunker#481 covers scratch location, not
  worker counts, so treesitter-chunker#567 is filed rather than folded in.
- Host caps: at most one heavy run from this phase at a time, at least 6 GiB
  available first, `pytest -n` no more than 4, and scratch under `$TMPDIR`.
  Local CI smoke runs the `CI_SMOKE_TESTS` selection with `-n 4` in place of
  `-n auto`; each PR records that substitution.
- Windows preflight: in a fresh temporary clone of the exact PR head on `win`,
  removed afterwards. Code Integrity 3077 blocks of freshly compiled unsigned
  DLLs are recorded, not chased (treesitter-chunker#547).
- The parent runs the two-reviewer panel (VB-4). The execution agent does not
  merge or request reviews.

## Verification

- `uv run --locked --all-extras pytest tests/test_lint_path_policy.py tests/test_release_hygiene_policy.py -q`
- `uv run --locked --all-extras pytest tests/test_symbol_analysis_deadline.py tests/test_compiled_grammar_analysis_contract.py tests/test_language_smoke.py -q -n 4`
- `uv run --locked --all-extras pytest tests/test_workflow_permissions_policy.py tests/test_scratch_root_policy.py -q`
- `uv run --locked --all-extras python scripts/run_deadline_load_harness.py` (heavy; Linux)
- The CONTRIBUTING.md local validation block, with the CI smoke selection at
  `-n 4`.

Named mutations (each fails its focused test):

1. `M517-path`: drop `chunker/build/` from the canonical Ruff paths. The
   discovery test and the deliberate-violation discriminator fail.
2. `M207-silent`: map `TimeoutExpired` back to empty lists with no `analysis`
   status. The deadline-expiry case fails.
3. `M143-conflate`: map `TimeoutExpired` in `load_language` back to
   `fails_to_load`. The expiry and COBOL cases fail.
4. `M507-job`: delete one job's `permissions:` block, or grant
   `contents: write` to the docs build job. The workflow policy test fails.
5. `M481-tmp`: add `Path("/tmp")` scratch to a tracked script. The scratch
   policy test fails.

## Acceptance Criteria

- [ ] EC-CIFAST-1 — treesitter-chunker#517, by `tests/test_lint_path_policy.py`;
  falsified by `M517-path`. The `builder.py` F401 is removed without ignores.
- [ ] EC-CIFAST-2 — treesitter-chunker#207 and treesitter-chunker#143, by
  `tests/test_symbol_analysis_deadline.py`, `tests/test_language_smoke.py` and
  the load harness; falsified by `M207-silent` and `M143-conflate`.
- [ ] EC-CIFAST-3 — treesitter-chunker#507 source part: the workflow PR (with
  IF-0-CIFAST-2) and the dependency triage PR; falsified by `M507-job`. No
  repository setting changed.
- [ ] EC-CIFAST-4 — treesitter-chunker#481 repo part, by
  `tests/test_scratch_root_policy.py`; falsified by `M481-tmp`.
- [ ] EC-CIFAST-5 — VB-1 to VB-4 for each PR.

## Spec Closeout Plan

- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: issue acceptance for treesitter-chunker#517,
  treesitter-chunker#207, treesitter-chunker#143, treesitter-chunker#507
  (source), treesitter-chunker#481 (repo part)
- evidence paths: `plans/phase-plan-v4-CIFAST.md`, PR verification logs
- redaction posture: `metadata_only` (confidential treesitter-chunker#507 audit
  evidence is never committed or quoted)
- missing or malformed evidence: `blocker_class=contract_bug`

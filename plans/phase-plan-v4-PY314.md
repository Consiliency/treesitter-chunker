---
phase_loop_plan_version: 1
phase: PY314
roadmap: specs/phase-plans-v4.md
roadmap_sha256: a96ef9073df2cd1bd860b1a151d75abc0a7edde7f242d8a2d7613c3fb38726c9
automation:
  # Post-merge suite (default interpreter). After SL-env, also run it with
  # UV_PYTHON=3.14 in a separate UV_PROJECT_ENVIRONMENT.
  suite_command: "uv run --locked --all-extras pytest tests/test_type_gate_policy.py tests/test_lint_path_policy.py tests/test_release_hygiene_policy.py tests/test_workflow_permissions_policy.py -q -n 4"
---

# PY314: Python 3.14 locked environment and type/release-validation debt

## Context

PY314 is Phase 11 of `specs/phase-plans-v4.md` (roadmap hash above). It was
planned from main `17d73d46` (the treesitter-chunker#571 merge).

Entry check (EC-PY314-1): treesitter-chunker#534 merged as `afff90a6`, so
`.python-version` pins 3.12 on main. CIFAST is complete: IF-0-CIFAST-1
(treesitter-chunker#568) and the explicit least-privilege `permissions:` blocks
(treesitter-chunker#571) are on main.

treesitter-chunker#502 was re-read on 2026-11-01 with `gh issue view 502 --comments`.
It is open and has no comments. The roadmap requires an issue for the type and
release-validation debt before SL-types is planned. It is
treesitter-chunker#587, opened 2026-11-01.

| Item | Observed on `17d73d46` |
|---|---|
| treesitter-chunker#502 | On dev0 (CPython 3.14.5, uv 0.12.11 as in CI), `uv sync --locked --all-extras --python 3.14` exits 1 building `cffi==1.17.1`: `Package 'libffi' not found` and `fatal error: ffi.h`. With `cffi` omitted, `pydantic-core==2.33.2` then fails, because pyo3 0.24.1 rejects the 3.14 interpreter (`the configured Python interpreter version (3.14) is newer than` its maximum). `httptools`, `markupsafe`, `line-profiler` and `uvloop` build from sdists on this host. A wheel scan of `uv.lock` finds no cp314-installable wheel for `cffi` 1.17.1, `httptools` 0.6.4, `line-profiler` 5.0.0, `markupsafe` 3.0.2, `pydantic-core` 2.33.2 or `uvloop` 0.21.0, nor for `watchfiles` 1.1.0 on Windows. Every parser and runtime pin has one: `tree-sitter` 0.26.0, `tree-sitter-language-pack` 1.20.0, the 0.25.0 Python and JavaScript grammars, and the BAML companion. `unicodedata2` is not installed on CPython 3.14. |
| treesitter-chunker#587 (gate) | The baseline has 1,353 signatures. With mypy 1.17.0 the gate reports 2,062 errors in 1,348 signatures, all baselined; 5 baseline entries are stale. `mypy_gate.py --update` writes every current signature. In a disposable worktree, an appended `return "not an int"` fails the gate, `--update` adds its signature (`+chunker/utils/text.py: error: Incompatible return value type (got "str", expected "int")  [return-value]`), and the gate then passes. |
| treesitter-chunker#587 (interpreter) | Raw mypy output is byte-identical (SHA-256 `8bc52868…`) under 3.12.14 with the full lock, 3.12.14 without `cffi`/`pydantic-core`, and 3.14.5 without them. `[tool.mypy] python_version = "3.12"` fixes the checked target, and `tests/test_release_hygiene_policy.py` keeps that value equal to the floor. The 3.12 run without those two packages controls for the omission. |
| treesitter-chunker#587 (release) | `release.yml` `release-validation` runs Ruff, Black and the gate, but not the governed-tools body-type check that CI and CONTRIBUTING.md run. `docs/development/RELEASE_CHECKLIST.md` lists neither type command. |

The exact commands and outputs go in each PR body (VB-1).

## Interface Freeze Gates

- (none produced). PY314 consumes IF-0-CIFAST-1 unchanged.

## Lane Index & Dependencies

SL-types — shrink-only type gate, release type-check alignment, first package (treesitter-chunker#587)
  Depends on: CIFAST (`ci.yml`, `release.yml`, `CONTRIBUTING.md` order)
  Blocks: SL-env (`release.yml`, `ci.yml`, `CONTRIBUTING.md`; re-measurement before any lock change)
  Parallel-safe: no (single writer of the workflow files after CIFAST)

SL-env — locked 3.14 environment and validation switch (treesitter-chunker#502)
  Depends on: SL-types (stacked on its branch; retargets to `main` after it merges)
  Blocks: RECORDS
  Parallel-safe: no

## Lanes

### SL-types — treesitter-chunker#587

- **Scope**: one PR, which also carries this plan. The re-measurement above
  (3.12 and 3.14 on unchanged main) is its VB-1 and lands before any lock
  change.
- **Owned files**: `scripts/mypy_gate.py`, `docs/development/mypy-baseline.txt`,
  the type-check line of `.github/workflows/release.yml` `release-validation`,
  the type commands in `docs/development/RELEASE_CHECKLIST.md`, the type-gate
  paragraphs of `CONTRIBUTING.md`, type-only annotations in `cli/`, the new
  `tests/test_type_gate_policy.py`, its `scripts/run_ci_smoke.py` entry,
  `CHANGELOG.md`, and this plan.
- **Tasks**:
  - impl: `--update` compares first. If mypy reports a signature that is not in
    the baseline, it prints it and exits 1 without writing. Otherwise it writes
    the current set, which can only remove entries.
  - impl: add the governed-tools body-type check to `release-validation`, and
    both type commands to the release checklist.
  - debt: remove the 5 stale entries. Type-only fixes in the top-level `cli/`
    package (return annotations on Typer commands, local container
    annotations, a typed `check_node`) clear 8 signatures. The baseline goes
    from 1,353 (measured on `17d73d46`; the roadmap's "1,356" is stale) to
    1,340, with no line added. Starting with `cli/` is a deliberate deviation
    from the roadmap, which assigns SL-types "the type-only fixes in
    `chunker/**`". `cli/` is a separate top-level package that no in-flight
    lane touches, while most `chunker/` packages with pure-annotation debt are
    owned by open ADMIT/TXN/SMALLFIX PRs. Later SL-types PRs take one
    `chunker/` package each. Signatures that need a behavior
    change stay in the baseline: `CodeChunk` has no `chunk_type`/`name` in
    `cli/repo_command.py`, and the graphviz fallback stubs in
    `cli/debug/commands.py`.
  - test: `tests/test_type_gate_policy.py` drives the real gate with its mypy
    subprocess replaced by fixed output lines. `--update` with a new signature
    exits 1 and leaves the baseline byte-identical. `--update` with only
    cleared debt removes it. The committed baseline is sorted and unique. The
    gate and governed-tools commands appear exactly once, byte-identical, in
    `ci.yml`, `release.yml`, CONTRIBUTING.md and the release checklist.
- Gate follow-ups from the round-1 review, filed under treesitter-chunker#587
  and not implemented here: treesitter-chunker#593 (a reviewable reseed for
  diagnostic-format migrations, since `--update` can no longer add) and
  treesitter-chunker#594 (per-signature counts, so a new instance of a
  baselined signature is caught).
- Other packages' type debt goes in later SL-types PRs under
  treesitter-chunker#587, one top-level package each. They avoid packages owned
  by in-flight ADMIT, TXN or FOLLOWUP lanes until those merge.

### SL-env — treesitter-chunker#502

- **Scope**: one PR, stacked on the SL-types branch. It retargets to `main`
  after SL-types merges, and nothing in it lands first.
- **Owned files**: `uv.lock`, the dependency sections of `pyproject.toml` (only
  if the lock cannot be fixed within the current ranges), the interpreter
  fields of `.github/workflows/ci.yml`, `test.yml` and `release.yml`, the
  interpreter assertions of `tests/test_release_hygiene_policy.py`,
  `specs/active/release-process-spec.md`, the CI/interpreter paragraphs of
  `CONTRIBUTING.md`, and `CHANGELOG.md`.
- **Tasks**:
  - lock: `uv lock --upgrade-package <name>==<version>` only for the packages
    blocked above, each to the smallest release that ships cp314 wheels for the
    platforms it resolves on. PyPI metadata on 2026-11-01: `cffi` 2.0.0,
    `httptools` 0.7.1, `line-profiler` 5.0.1, `markupsafe` 3.0.3, `uvloop`
    0.22.1, `watchfiles` 1.1.1. For `pydantic-core`, use the smallest
    `pydantic` release whose exact `pydantic-core` pin ships cp314 wheels. Read
    the lock diff. Any other moved package is either a required transitive
    change, recorded with the reason, or the change is reverted. Result:
    `pydantic` 2.12.0 (the first release whose exact `pydantic-core` pin,
    2.41.1, ships cp314 wheels), plus `typing-inspection` 0.4.1 → 0.4.2, which
    pydantic 2.12.0 requires (`typing-inspection>=0.4.2`). Nothing else moved. No parser or
    runtime pin moves. If a pinned dependency has no 3.14 wheel, the lane stops
    and reports.
  - host prerequisites: with the new lock, 3.14 needs no compiler, libffi or
    Rust on Linux, macOS or Windows. The PR records the sync output that shows
    wheels only, or names any sdist build and its prerequisite.
  - interpreter layout (no more jobs than now). **Maintainer decision,
    2026-11-01: 3.14 is the main version.** This supersedes an earlier same-day
    split that kept the scheduled full tier on 3.12.
    - `ci.yml` `test`: 3.14 for every run. Pushes and pull requests run Ruff,
      Black, the type gate, the governed check and the smoke tier; the
      scheduled run is the full tier. No interpreter is selected by event. The
      `conftest.py` forkserver preload applies to these 3.14 runs.
    - `test.yml` platform-core: Linux 3.12 (the focused minimum), macOS 3.14
      and Windows 3.14. That is still three jobs, with no version-by-OS cross
      product, and the cache key gets the matrix interpreter.
    - `release.yml`: `release-validation` is `['3.14']`, and
      `build-distributions` moves to 3.14. `verify-installed-wheel` keeps
      `['3.12', '3.14']`, so the minimum stays release-tested.
    - `docs.yml` and the manual `build-wheels.yml` move to 3.14.
      `baml-grammar-wheels.yml` keeps 3.12 in its `source` and `wheel` jobs:
      they check, build and smoke-test the separate BAML companion on its own
      3.12 minimum. The companion's `cp312-abi3` floor comes from
      `packages/baml-grammar/setup.py` (`Py_LIMITED_API=0x030C0000`,
      `py_limited_api="cp312"`) and `CIBW_BUILD: 'cp312-*'`, not from the
      runner interpreter. The policy test asserts both settings.
    - So 3.12 appears only in Linux platform-core, the installed-wheel check
      and those two BAML companion jobs. `tests/test_release_hygiene_policy.py`
      enforces this and rejects any event-selected interpreter. It also runs a
      **plain-text scan** of every workflow line (`.yml` and `.yaml`), with no
      shell parsing. This replaced #591's shell-parsing scan after the
      maintainer chose a simpler, stricter check (2026-11-01, successor PR).
      Flag broadly, exempt narrowly:
      - **What is scanned:** comments, `echo` text and heredoc bodies too.
        Lines are attributed to jobs from the composed YAML node positions, not
        indentation. Job names must match the parsed `jobs:` keys, quoted keys
        included, and YAML anchors and aliases are rejected.
      - **Exempt:** whole jobs whose `FLOOR_ALLOWED` family is `None`. For the
        Linux platform-core entry, only that family's literal matrix include
        entry is exempt; the rest of the job is scanned.
      - **What fails elsewhere:** `--python`; every `-p` short-option cluster
        (`-p`, `-qp`, `"-p"`, `-p=`, any value), except `pytest -p no:`,
        `mkdir -p` and `tar -cpf`; `UV_PYTHON` in any case; `PYENV_VERSION`;
        `python3.N`; `Python3NN` paths; `python@3`; `py -3.N`, `py -V:3.N` and
        `py.exe`; `uv python pin|install|find`; and any `python-version`.
      - **The one exemption:** a canonical 3.14 setting at the start of a line
        (`python-version:`/`UV_PYTHON:` set to 3.14, or to a literal list of
        only 3.14). `${{ matrix.python-version }}` counts only over a literal
        matrix whose non-3.14 values are allowed floor entries. The rest of
        that line, trailing comments included, is still scanned.
      - The failure message says how to fix it: reword the text, or add the job
        to `FLOOR_ALLOWED` with a reason.
      - 44 named mutations (`M502-text-*`) cover both panels' bypasses,
        including a `.yaml` file, quoted job keys, anchors, the macOS leg,
        computed `include`, trailing comments and every `-p` form.
    - The type gate runs once per CI run, on 3.14. Its output does not depend
      on the interpreter (re-measurement above).
  - 3.12 deprecation: `requires-python` and `.python-version` stay at 3.12
    until the next major release (7.0) drops it. The CHANGELOG (Deprecated),
    README, getting-started, user guide and packaging docs carry the notice.
    treesitter-chunker#599 tracks the drop and records downstream readiness:
    Greenfield, Spec and jev-assembler do not yet resolve on 3.14, blocked on
    `consiliency-canon-core` cp314 wheels and unconditional `unicodedata2`
    pins.
  - `.python-version` stays `3.12`, the roadmap default. A plain
    `uv sync --locked --all-extras` keeps developing on the floor, so 3.12
    regressions show up locally first. 3.14 commands select the interpreter
    explicitly (`--python 3.14` or `UV_PYTHON=3.14`) in a separate project
    environment.
  - 3.14 test compatibility (test-only; no product change): the 3.14 tiers
    found three tests that only worked on 3.12.
    - CPython 3.14 bounds the json C decoder's recursion by the process stack
      size, so `tests/test_governed_scope.py::test_unexpected_recursion_exit`
      runs the driver with an 8 MiB `RLIMIT_STACK` and a 100,000-level
      request.
    - 3.14 makes `forkserver` the default Linux start method, and its
      bootstrap rebuilds `sys.path` from its repr. A `Path` that
      `tests/test_overlapping_fallback_isolated.py` put on `sys.path` at
      collection killed every later forkserver start. The entry is now a str.
    - `tests/test_parallel_error_handling.py::test_deadlock_prevention` passes
      closures as `Process` targets, which forkserver cannot pickle. It now
      uses an explicit `fork` context; the test is Linux full-tier only.
  - **Decided (maintainer, 2026-11-01): preload in the test harness.**
    `tests/test_performance_advanced.py::TestConcurrentPerformance::test_multiprocess_scaling`
    asserts a speedup above 2.0 with 4 workers on a sub-second workload. On
    3.14 under pytest it got 1.1–1.6 (3.12 passes). With forkserver, each new
    pool's workers re-import `chunker` inside the timed region, because pytest,
    not chunker, is `__main__`. `tests/conftest.py` now calls
    `multiprocessing.set_forkserver_preload(["__main__", "chunker.parallel"])`,
    and only when forkserver is the start method in use; fork and spawn are
    unaffected. There is no product change, and the `> 2.0` assertion is
    unchanged. `docs/api-reference.md` and CHANGELOG.md tell library users to
    keep the `if __name__ == "__main__":` guard, which 3.14 Linux now needs as
    macOS and Windows already did.
  - spec and docs: `release-process-spec.md` and CONTRIBUTING.md describe the
    3.14 validation interpreter, the 3.12 minimum coverage, and the 3.14 local
    commands.
  - test: `tests/test_release_hygiene_policy.py` asserts the new layout: the
    release validation matrix, a 3.12 job in platform-core, a 3.14 CI lint/type
    job, and that no workflow gains jobs. On old code it fails at
    `matrix == ['3.14']`. `tests/test_python314_lock_wheels.py` reads `uv.lock`
    offline. On each runner platform, a package with a cp312 wheel must also
    have a cp314-installable one; a pure wheel counts. On the old lock it lists
    exactly the blocked packages.
  - evidence: on Linux, `uv sync --locked --all-extras --python 3.14` (heavy,
    one at a time) and on 3.12. On 3.14, the CONTRIBUTING block, docs build,
    a clean wheel/sdist build and hashed install with the chunk CLI, and the
    full suite (one heavy run). On 3.12, the CONTRIBUTING block and
    platform-core. On Windows, the same sync and the preflight in a clean
    temporary clone. On macOS, hosted CI at the exact head.

## Execution Notes

- Single-writer order: `ci.yml` and `release.yml` go CIFAST (done), then
  SL-types, then SL-env. `CONTRIBUTING.md` goes CIFAST (done), then SL-types,
  then SL-env. `.python-version` and `specs/active/release-process-spec.md`
  belong to SL-env only. `docs/development/mypy-baseline.txt` is also edited
  by in-flight ADMIT/TXN/SMALLFIX PRs; those edits only delete lines, so
  conflicts are resolved by keeping both deletions.
- A 3.14 environment counts as a heavy run. Never build two interpreters'
  environments at once. Run each only with at least 6 GiB available and load
  under about 28. Scratch environments go under `$TMPDIR`
  (`UV_PROJECT_ENVIRONMENT`), never the 3.12 `.venv`.
- Local CI smoke runs the `CI_SMOKE_TESTS` selection with `-n 4`
  (treesitter-chunker#567); each PR records the substitution.
- Windows preflight: in a fresh temporary clone of the exact PR head on `win`.
  Abort unless `git rev-parse HEAD` matches, run every `uv` with
  `--directory <clone>`, and remove the clone afterwards. Code Integrity 3077
  blocks and the native-probe flakes (treesitter-chunker#547,
  treesitter-chunker#574) are recorded, not chased.
- The parent runs the two-reviewer panel (VB-4). The execution agent does not
  merge or request reviews, and publishes nothing.

## Verification

- `uv run --locked --all-extras pytest tests/test_type_gate_policy.py tests/test_lint_path_policy.py tests/test_release_hygiene_policy.py tests/test_workflow_permissions_policy.py -q -n 4`
- `uv run --locked --all-extras python scripts/mypy_gate.py` on 3.12 and, after
  SL-env, on 3.14
- `uv sync --locked --all-extras --python 3.14` (heavy)
- The CONTRIBUTING.md local validation block, with the CI smoke selection at
  `-n 4`

Named mutations (each fails its focused test):

1. `M587-absorb`: restore the old `--update` that writes the full current set.
   `test_update_refuses_to_absorb_new_signature` fails.
2. `M587-release`: drop the governed-tools line from `release-validation`.
   `test_type_commands_match_ci[.github/workflows/release.yml]` fails.
3. `M502-lock`: restore the pre-SL-env `uv.lock`.
   `test_every_locked_native_package_has_a_cp314_wheel` fails.
4. `M502-matrix`: put `release-validation`, `build-distributions` or
   `docs.yml` back on 3.12, select the `ci.yml` interpreter by event (for
   example 3.12 when scheduled), or drop the 3.12 platform-core job. The
   release-hygiene layout tests fail.

## Acceptance Criteria

- [ ] EC-PY314-1: treesitter-chunker#534 is merged (`afff90a6`).
- [ ] EC-PY314-2: treesitter-chunker#502, by the SL-env PR. The 3.14 locked sync
  passes on Linux, Windows and hosted macOS, and the full checks pass on 3.14.
  The 3.12 minimum is kept and CI has no more jobs. Falsified by
  `M502-lock` and `M502-matrix`.
- [ ] EC-PY314-3: treesitter-chunker#587, by the SL-types PR. The baseline was
  re-measured on 3.12 and 3.14 and shrinks by cleared debt only, and the
  release type commands match CI. Falsified by `M587-absorb` and
  `M587-release`.
- [ ] EC-PY314-4: VB-1 to VB-4 for each PR. No parser or runtime pin changes,
  and nothing is published.

## Spec Closeout Plan

- schema: `spec_delta_closeout.v1`
- decision: `canonical_spec_update`
- target surfaces: `specs/active/release-process-spec.md` (SL-env),
  `CONTRIBUTING.md`
- evidence paths: `plans/phase-plan-v4-PY314.md`, PR verification logs, platform
  install logs
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`;
  treesitter-chunker#534 not merged is reported as an external precondition

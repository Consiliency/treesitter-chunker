---
phase_loop_plan_version: 1
phase: CLEANUP
roadmap: specs/phase-plans-v3.md
roadmap_sha256: d89176be38022c12d110aec465e9bd6f6ebef8a3c83bec6ee8dc02d96d997cc9
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_core_grammar_cache_cleanup.py tests/test_public_grammar_cli.py tests/test_public_grammar_config.py tests/test_grammar_self_test_workflow.py -q"
---

# CLEANUP: Cache deletion and auxiliary self-test safety

## Context

Plan three separately reviewed repairs: treesitter-chunker#323 (concurrent cache publication), treesitter-chunker#324 (static mixed-age CLI fallback), and treesitter-chunker#177 (auxiliary self-tests). Two implementation lanes preserve the roadmap decomposition; a terminal reducer assembles documentation and acceptance evidence. This is an executable plan, not independent design approval or a produced IF gate.

`GrammarManager._cleanup_directory` scans descendants then calls `rmtree`, leaving a publication race. `_cleanup_cache_fallback` checks only parent age; its current parametrized test incorrectly expects deletion of a stale directory containing a fresh child. `CacheManager` separately evicts files by age, size and explicit clear without writer coordination. Installer downloads/builds mutate shared directories; `copy2` preserves source age. No common process lock currently exists.

`IntegrationTester` partially isolates its normal workflow, but auxiliary methods call stale APIs. `CLIValidator` creates a default-home CLI; `SystemValidator`, `PerformanceBenchmark` and `run_complete_test_suite` also use ambient defaults, including a host-home results file. Some scenarios return success without exercising behavior.

CLEANUP has no upstream dependency. GRAMMARS consumes its accepted gate for future installed-library publication; mapped-inode replacement, native admission, reload semantics and CACHE helper propagation remain downstream work. Serialize shared core/CLI/config/docs ownership with other phases. The tracked roadmap matches the frontmatter digest. Canonical `.phase-loop/events.jsonl` selects CLEANUP as unplanned at the clean starting HEAD; its newer event supersedes the SAFELOAD cursor in `.phase-loop/state.json`. Do not modify runner state or consult legacy compatibility state as authority.

## Interface Freeze Gates

- [ ] IF-0-CLEANUP-1 — Accepted cache transaction, staging and publication-recency contract below, implemented by every participating writer/deleter and demonstrated by static, interleaving, no-follow and independent review evidence. Design approval alone does not produce this gate.

### Cache ownership and transaction contract

Place shared private primitives in existing `config.py`, which has no core dependency, so fallback cleanup can use them when core imports fail: `_cache_transaction(cache_root)` and `_record_cache_publication(cache_root, entry_path)`. Retain public signatures and cleanup result keys. Keep primitives independent of optional native components.

The root is the actual parent of participating `downloads`, `builds` and optional `tmp` namespaces: core/CLI use their supplied cache root; `CacheManager` uses `directory_manager.get_directory("cache")`. Do not infer a different home root or treat CLI `grammars/build` as this `builds` namespace. Installed grammars and operator sources are outside age/size/clear cleanup.

Use one persistent `.cleanup.lock` per root, never unlinking it during cleanup. Combine a process-local reentrant lock with an OS advisory lock (`fcntl` on POSIX, `msvcrt` on Windows); no dependency addition. Cover threads and separate processes, nested installer calls, abnormal process exit and bounded lock acquisition. Lock acquisition failure returns an actionable existing error result; it never permits unlocked deletion. Refuse unsafe lock/root paths, including links/reparse points. This coordinates participating application processes, not hostile same-user filesystem mutation.

Writers build/download in uniquely owned `cache_root/.staging/<operation-id>/`, outside all scanned namespaces on the same filesystem. The owner retains its transaction through final publication and consumption of temporary inputs; cleanup cannot reclaim live staging. Publish completed cache entries under the root lock, then record publication before releasing it. Installer rollback and `_cleanup_cache(language)` must obey the same ownership rule and never delete another operation's staging. Retain abandoned staging conservatively; recovery policy is a separate explicit action, not age-based guessing.

Store publication metadata in `cache_root/.publications.json`, atomically replaced under the same lock: `schema="cache_publication.v1"`, `entries={relative_entry_path: {generation: operation_id, state: "pending"|"published", published_at_ns: integer|null}}`. Paths are relative to that root, never absolute or parent-traversing. Markers belong outside deletion targets, cannot come from downloaded content, and are excluded from payload counts. Record real publication time even when bytes arrive through `copy2`. A pending record with null timestamp precedes rename; replace it with published state and current time before unlocking. Pending/interrupted entries are preserved and reported until reconciled under lock. Missing legacy records use a no-follow descendant-age scan; malformed records fail closed. A fresh marker or fresh descendant protects the whole mixed-age entry. Markers for successfully deleted entries are removed under lock.

Freeze one cleanup-start cutoff/candidate generation. Hold the transaction across eligibility revalidation and deletion; publications after invocation survive even if cleanup waited for the writer. Age cleanup requires every relevant descendant and its publication record to be expired. Explicit clear and size eviction may remove eligible preexisting recent content by their documented purpose, but never active staging or a generation published after their invocation. Preserve that distinction in tests and docs.

Use `lstat`/reparse checks for roots, ancestors and descendants; never traverse symlinks, junctions or redirected roots, and never account for target bytes. Preserve and report entries containing unsafe links, including dangling links; update the old dangling-link deletion expectation explicitly. Detect candidate replacement before deletion. Where the platform cannot establish safe containment, skip with diagnostics. A pre-scan followed by unchecked recursive deletion is not sufficient. Remove only eligible validated entries and count successful operations; preserve managed namespace roots. Keep core/CLI `files_removed` as removed top-level entries plus existing validation-cache entry counts, and config counts as regular files; document these existing units. Failed/skipped removal adds no reclaimed bytes. Existing validation JSON pruning semantics remain unchanged.

Inventory participants before implementation: core `_download_grammar`, `_build_grammar` (including make/copy), rollback and `_cleanup_cache`, `GrammarManager.cleanup_cache/_cleanup_directory`; CLI fallback cleanup and any fetch/build/remove path actually sharing these cache namespaces; config age/size/clear/auto and empty-directory removal. Record paths outside those namespaces as exclusions. Older concurrent versions do not honor locks: document stopping them before migration; do not advertise race safety for arbitrary external writers.

### Auxiliary suite contract

Retain bounded local discovery/list, fixture parsing, missing grammar, corrupt local artifact, invalid arguments and removal of a suite-owned fixture. Use current signatures and inspect their results; `TypeError`/`AttributeError` from stale calls is a harness failure, never successful recovery. Use an empty or text corrupt file that fails validation without loading unreviewed native code. Positive parsing uses a trusted locally available grammar copied into the disposable root.

Every retained entrypoint creates or receives one disposable root; pass root-scoped managers/config/CLI objects explicitly. In subprocess tests set HOME/USERPROFILE/XDG paths before imports and supply the trusted fixture beforehand. Caller-supplied roots survive cleanup; only automatically owned roots are removed, in `finally`. Reports stay under the root. Keep cleanup ownership valid through all suites, including CLI/system/benchmark construction; never mutate process-global home concurrently.

Retire external versions/fetch/build simulation, pretend disk-full/permission recovery, constant-pass UX scores and destructive performance optimization from the default auxiliary suite. Report them explicitly as unsupported with reasons, excluded from tested/passed totals. Retain network-failure coverage only through a local deterministic transport seam with no real DNS/URL request; otherwise retire it. Optional bounded local benchmarks remain diagnostic, not correctness assertions. No network access, host grammar removal or minute-long stability loop in default execution. Default calls without required local inputs return actionable unmet-input results, never auto-download. Do not repair unrelated CLI info/native-admission semantics; retire any auxiliary assertion requiring unresolved GRAMMARS behavior.

## Lane Index & Dependencies

SL-1 — Cache writer/deleter protocol and fallback repair
  Depends on: (none)
  Blocks: SL-2, SL-3
  Parallel-safe: no

SL-2 — Auxiliary self-test isolation
  Depends on: SL-1
  Blocks: SL-3
  Parallel-safe: no

SL-3 — Documentation and acceptance reducer
  Depends on: SL-1, SL-2
  Blocks: (none)
  Parallel-safe: no

## Lanes

### SL-1 — Cache writer/deleter protocol and fallback repair

- **Scope**: Implement the shared transaction contract and repair core concurrency and CLI fallback age selection in two separate PRs.
- **Owned files**: `chunker/grammar_management/core.py`, `chunker/grammar_management/cli.py`, `chunker/grammar_management/config.py`, `tests/test_core_grammar_cache_cleanup.py`, `tests/test_public_grammar_cli.py`, `tests/test_public_grammar_config.py`, `tests/test_grammar_installer_language_safety.py`, `tests/test_grammar_source_validation.py`, `docs/development/cache-cleanup-contract.md`
- **Interfaces provided**: `CLEANUP cache implementation`, `CLEANUP contract review`, `CLEANUP cache fixture and mutation evidence`
- **Interfaces consumed**: `public cache APIs (pre-existing)`, `local Python parse fixture (pre-existing)`
- **Parallel-safe**: no
- **Tasks**:
  - test: Extend existing tests with a recent child inside an old directory, entirely expired directories, exact-cutoff content, empty roots, denied deletion and truthful counters. Correct the fallback test that currently codifies mixed-age deletion. Keep real parse assertions on preserved fixture bytes.
  - test: Use barriers/events, not sleeps, to pause at scan/delete and writer/publication boundaries. Exercise core, actual core-unavailable CLI, config age/size/clear, installer cleanup and two concurrent deleters in real processes. Test late additions, same-path replacement, old-mtime copies with fresh markers, cleanup waiting on writers, pending-marker crash recovery, lock contention and active staging. Assert the schedule actually entered each production path.
  - test: Exercise file/directory symlinks, dangling links, redirected namespace roots, ancestor substitution and real Windows junctions with outside sentinels. No outside bytes may change or count as reclaimed. Test failing removal after eligibility without overcounting.
  - impl: Write and independently review `docs/development/cache-cleanup-contract.md`, including the participant/root matrix and pending-publication transitions, before changing deletion. Resolve blocking disagreement. Implement treesitter-chunker#323 first: shared primitives, core/config integration and lock/staging hooks for all participants, with code and tests together. Then implement treesitter-chunker#324 in a distinct PR against that reviewed dependency: fallback mixed-age selection, diagnostics and wholly expired deletion. Neither the static repair nor the protocol-only PR alone produces the IF gate.
  - verify: Run the cache-focused and installer/source suites in Verification, then the cache mutations. Supply command outcomes, controls and per-platform findings to SL-3; preserve separate issue acceptance records.
  - verify: `uv run --locked --all-extras pytest tests/test_core_grammar_cache_cleanup.py tests/test_public_grammar_cli.py tests/test_public_grammar_config.py tests/test_grammar_installer_language_safety.py tests/test_grammar_source_validation.py -q`

### SL-2 — Auxiliary self-test isolation

- **Scope**: Repair or explicitly retire auxiliary scenarios under one disposable root for treesitter-chunker#177.
- **Owned files**: `chunker/grammar_management/testing.py`, `tests/test_grammar_self_test_workflow.py`
- **Interfaces provided**: `CLEANUP auxiliary implementation`, `CLEANUP auxiliary disposition and test evidence`
- **Interfaces consumed**: `CLEANUP cache implementation`, `current grammar APIs (pre-existing)`, `trusted local fixture (pre-existing)`
- **Parallel-safe**: no
- **Tasks**:
  - test: Extend the existing workflow tests through `test_error_scenarios`, `CLIValidator.test_all_commands/test_error_handling` and `run_complete_test_suite`. Cover missing/corrupt/valid fixtures, actual failure aggregation, explicit unsupported reasons, caller-owned versus auto-owned root cleanup, and exceptions mid-suite.
  - test: Seed an operator-home grammar sentinel outside the suite root. Deny network operations and capture filesystem writes/removals; run retained paths in an isolated subprocess. Assert the sentinel is unchanged, reports remain confined, and only suite-owned removal succeeds. Parameterize CLI core availability where supported; no skips may count as passes.
  - impl: Route all retained helpers through scoped objects, replace stale API calls, retire unsupported scenarios according to the contract, remove ambient report writes, and propagate truthful results. Keep the already repaired bounded parse/health workflow intact. Treat newly exposed production defects as separately filed work, not silent expansion.
  - verify: `uv run --locked --all-extras pytest tests/test_grammar_self_test_workflow.py -q`
  - verify: Follow with the focused suite and auxiliary mutations. Record supported/retired scenarios and any unmet local inputs for SL-3.

### SL-3 — Documentation and acceptance reducer

- **Scope**: Synthesize both implementation lanes into consumer documentation, issue-specific acceptance and the final IF decision.
- **Owned files**: `docs/grammar_management.md`, `CHANGELOG.md`, `docs/development/cleanup-verification.md`
- **Interfaces provided**: `CLEANUP acceptance evidence`, `IF-0-CLEANUP-1`
- **Interfaces consumed**: `CLEANUP cache implementation`, `CLEANUP contract review`, `CLEANUP cache fixture and mutation evidence`, `CLEANUP auxiliary implementation`, `CLEANUP auxiliary disposition and test evidence`
- **Parallel-safe**: no
- **Tasks**:
  - test: Check every documented cache/root/statistic and auxiliary scenario against the observed results; reject unsupported platform, review or mutation claims.
  - impl: Document cleanup migration, skips, statistics, disposable-root usage and retired scenarios; add issue-specific Unreleased changelog entries. Prepare the corresponding documentation hunks for each repair PR. Record independent design and implementation review, commands, fixtures, killed mutations and platform outcomes in `docs/development/cleanup-verification.md`. Emit IF-0-CLEANUP-1 only after both cache repairs meet the entire contract and final review acceptance; require SL-2 evidence for phase completion. No issue closes solely because its PR or parent merged.
  - verify: Run whole-phase checks and docs build below after all producers. Record unresolved failures explicitly; do not claim ratification without independent evidence, including cross-vendor ablation for any Sol-authored ratified review.
  - verify: `uv run --locked --all-extras pytest tests/test_core_grammar_cache_cleanup.py tests/test_public_grammar_cli.py tests/test_public_grammar_config.py tests/test_grammar_self_test_workflow.py -q`

## Execution Notes

Run `codex-execute-phase plans/phase-plan-v3-CLEANUP.md`. Execute SL-1, SL-2, then SL-3 serially. No writer fanout is authorized. Nine SL-1 paths, two SL-2 paths and three SL-3 paths are disjoint; shared files have one owner, and the reducer explicitly depends on both producers. Amend ownership before touching any additional tracked file. No dependency/env change, parser-pin update or Boundary IR golden generation is planned. Runner evidence belongs under canonical `.phase-loop/`, not lane-owned ledger edits.

Keep three separately reviewed repair PRs; execution is not authorization to merge or close issues. Policy precedence is CLI/operator override, phase-plan policy, roadmap policy, Dispatch Hints, then registry defaults. Dispatch Hints remain executor-only fallback; silent model/effort downgrade requires explicit fallback or default inheritance.

## Execution Policy

- SL-1: work-unit=`lane_execute`, reason=`cache implementation and regression tests`
- SL-2: work-unit=`lane_execute`, reason=`auxiliary implementation and regression tests`
- SL-3: work-unit=`phase_reducer`, reason=`terminal documentation and acceptance synthesis`

## Verification

Prepare the locked environment at execution time with `uv sync --locked --all-extras`; provision trusted parser fixtures before isolated offline tests. Planning validates command intake through IF-0-VC-2 without running product tests or claiming acceptance. The frontmatter supplies the effective `automation.suite_command`.

- `uv run --locked --all-extras pytest tests/test_core_grammar_cache_cleanup.py tests/test_public_grammar_cli.py tests/test_public_grammar_config.py -q`
- `uv run --locked --all-extras pytest tests/test_grammar_installer_language_safety.py tests/test_grammar_source_validation.py -q`
- `uv run --locked --all-extras pytest tests/test_grammar_self_test_workflow.py -q`
- `uv run --locked --all-extras pytest tests/test_core_grammar_cache_cleanup.py tests/test_public_grammar_cli.py tests/test_public_grammar_config.py tests/test_grammar_self_test_workflow.py -q`
- `uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site`
- `uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/`
- `uv run --locked --all-extras python scripts/mypy_gate.py`
- `uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py`
- `uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux`
- `uv run --locked --with toml --all-extras python scripts/run_full_suite.py`

Build docs in a temporary directory: `uv run --locked --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict --site-dir "$(mktemp -d)"`. Never generate tracked `site/` output. Run CONTRIBUTING.md's standing Windows preflight before pushing; additionally run the focused suites on the actual changed revision on Linux/macOS/Windows. Standing-main results do not prove changed-code acceptance. Missing junction privileges or unsupported platform primitives leave the relevant acceptance unresolved, not silently passed.

Named mutations, each with baseline pass, path-entered control, failing mutant and restored pass:

1. `bypass_cache_transaction`: bypass the core/config critical section; controlled writer/delete interleavings must lose protection.
2. `trust_copied_mtime`: ignore fresh/pending publication metadata; an old-mtime newly published fixture must fail preservation.
3. `fallback_parent_age_only`: restore parent-only fallback eligibility; the mixed-age public CLI test must fail.
4. `follow_cache_link`: replace no-follow/reparse handling with target-following traversal; outside sentinel/count assertions must fail.
5. `ambient_auxiliary_root`: construct the CLI with defaults instead of its suite root; guarded outside-write/removal assertions must fail.
6. `auxiliary_false_success`: force success for a failing retained scenario; aggregate status and tested/passed assertions must fail.

Record metadata-only evidence in `docs/development/cleanup-verification.md`, referencing runner-owned `.phase-loop/` artifacts. Review and remote-platform evidence require runner-stamped amendments carrying artifact paths/digests; never hand-edit admitted ledgers or substitute proxy evidence without a roadmap amendment.

## Acceptance Criteria

- [ ] EC-CLEANUP-1 — proven by `uv run --locked --all-extras pytest tests/test_core_grammar_cache_cleanup.py tests/test_public_grammar_cli.py tests/test_public_grammar_config.py -q`; falsified by `bypass_cache_transaction`, `trust_copied_mtime` and `fallback_parent_age_only` at `chunker/grammar_management/core.py:GrammarManager._cleanup_directory`, `chunker/grammar_management/config.py:_record_cache_publication` and `chunker/grammar_management/cli.py:ComprehensiveGrammarCLI._cleanup_cache_fallback`, with path-entered subprocess barriers and parsed surviving fixtures.
- [ ] EC-CLEANUP-2 — proven by `uv run --locked --all-extras pytest tests/test_grammar_self_test_workflow.py -q`; falsified by `ambient_auxiliary_root` and `auxiliary_false_success` at `chunker/grammar_management/testing.py:CLIValidator.__init__` and `chunker/grammar_management/testing.py:run_complete_test_suite`, with path-entered retained-scenario calls, outside sentinels and deliberately failing local fixtures.

## Spec Closeout Plan

- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: `docs/development/cache-cleanup-contract.md`, `docs/development/cleanup-verification.md`, `docs/grammar_management.md`, `CHANGELOG.md`
- evidence paths: `docs/development/cleanup-verification.md`, `.phase-loop/`
- redaction posture: `metadata_only`
- downstream handling: `none`

This implements existing roadmap acceptance without amending canonical specifications. GRAMMARS may consume the gate only after accepted implementation; planning itself produces no IF gate.

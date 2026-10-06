---
phase_loop_plan_version: 1
phase: CLEANUP
roadmap: specs/phase-plans-v3.md
roadmap_sha256: 3adf700dd9c28440b04071e104039cc497b07699fa812dc55a6a3e2e10cde15a
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_core_grammar_cache_cleanup.py tests/test_public_grammar_cli.py tests/test_public_grammar_config.py tests/test_grammar_self_test_workflow.py tests/test_grammar_installer_language_safety.py tests/test_grammar_source_validation.py -q"
---

# CLEANUP: Cache deletion and auxiliary self-test safety

## Context

Plan three separately reviewed repairs: treesitter-chunker#323 (concurrent cache publication), treesitter-chunker#324 (static mixed-age CLI fallback), and treesitter-chunker#177 (auxiliary self-tests). Two implementation lanes preserve the roadmap decomposition; a terminal reducer assembles documentation and acceptance evidence. This is an executable plan, not independent design approval or a produced IF gate.

### Independently landable slices

This phase plan coordinates three PRs; it is not authorization to implement them all on one branch. Before each slice, produce an active bounded detailed plan with its own code, tests, consumer documentation, changelog and issue-specific evidence ownership. Shared documentation is edited serially in separate worktrees, never by concurrent lane writers. Publish, review and land that slice before advancing its dependent slice. The parent reducer runs only after all three accepted slices; per-PR documentation and evidence never wait for that reducer.

1. Static public fallback: treesitter-chunker#324 plus its coupled import-boundary defect treesitter-chunker#369. Repair mixed-age/no-follow selection and real core-unavailable package exports. Test a fresh subprocess denying core import and the distinct real manager-construction-failure fallback. Normal core exports remain unchanged; unavailable core types are omitted, never fabricated. This slice claims static preservation only; concurrent publication remains explicitly unresolved in treesitter-chunker#323. Kill fallback_parent_age_only, follow_cache_link and unconditional_core_import. It produces no IF gate.
2. Auxiliary isolation: treesitter-chunker#177 can land independently of either cache slice. Keep the existing core-cleanup assertions in tests/test_grammar_self_test_workflow.py intact. Its own documentation/evidence describes retired scenarios and disposable-root results. Kill ambient_auxiliary_root and auxiliary_false_success. It produces no cache IF gate.
3. Shared transaction: treesitter-chunker#323 and separately filed validation persistence/containment defect treesitter-chunker#370. Consume the accepted static fallback; wire every participating writer/deleter, including fallback and validation JSON, before claiming concurrent safety. Each PR leaves the remaining issues open with truthful limits. Re-run the existing workflow cleanup assertions as integration evidence. IF-0-CLEANUP-1 requires this complete accepted protocol, not a partial rollout.

`GrammarManager._cleanup_directory` scans descendants then calls `rmtree`, leaving a publication race. `_cleanup_cache_fallback` checks only parent age; its current parametrized test incorrectly expects deletion of a stale directory containing a fresh child. `CacheManager` separately evicts files by age, size and explicit clear without writer coordination. Installer downloads/builds mutate shared directories; `copy2` preserves source age. No common process lock currently exists.

`IntegrationTester` partially isolates its normal workflow, but auxiliary methods call stale APIs. `CLIValidator` creates a default-home CLI; `SystemValidator`, `PerformanceBenchmark` and `run_complete_test_suite` also use ambient defaults, including a host-home results file. Some scenarios return success without exercising behavior.

CLEANUP has no upstream dependency. GRAMMARS consumes its accepted gate for future installed-library publication; mapped-inode replacement, native admission, reload semantics and CACHE helper propagation remain downstream work. Serialize shared core/CLI/config/docs ownership with other phases. The tracked roadmap matches the frontmatter digest. Canonical `.phase-loop/events.jsonl` selects CLEANUP as unplanned at the clean starting HEAD; its newer event supersedes the SAFELOAD cursor in `.phase-loop/state.json`. Do not modify runner state or consult legacy compatibility state as authority.

## Interface Freeze Gates

- [ ] IF-0-CLEANUP-1 — Accepted cache transaction, staging and publication-recency contract below, implemented by every participating writer/deleter and demonstrated by static, interleaving, no-follow and independent review evidence. Design approval alone does not produce this gate.

### Cache ownership and transaction contract

Place shared private primitives in existing `config.py`, which has no core dependency, so fallback cleanup can use them when core imports fail: `_cache_transaction(cache_root)` and `_record_cache_publication(cache_root, entry_path)`. Retain public signatures and cleanup result keys. Keep primitives independent of optional native components.
The package initializer currently imports core unconditionally. Its coupled repair is explicitly owned by the static fallback slice; toggling an availability flag after import is insufficient evidence for treesitter-chunker#369.

The root is the actual parent of participating `downloads`, `builds` and optional `tmp` namespaces: core/CLI use their supplied cache root; `CacheManager` uses `directory_manager.get_directory("cache")`. Do not infer a different home root or treat CLI `grammars/build` as this `builds` namespace. Installed grammars and operator sources are outside age/size/clear cleanup.

Resolve the operator-established base anchor once and pin its identity; platform aliases above that anchor (macOS /var, Fedora /home and the configured workspace view) are trusted layout, not cache payload. Validate original configured path components at and below that anchor before get_directory resolves or creates them. Reject root/descendant symlinks and reparse redirection; preserve normal lexical .. aliases only when their traversed components are safe. Pin the resulting root identity and use one actual root for locking. Test linked configured roots and linked intermediate components beneath the trusted anchor. A resolved path alone is not validation.

Use one persistent `.cleanup.lock` per actual root, never unlinking it during cleanup. Key the process-local reentrant lock by file identity, not path spelling. Mandate fcntl.flock on POSIX, not lockf; on Windows lock byte zero of a regular nonempty lock file with msvcrt and keep the owning handle through the transaction. Nested calls reuse the held lock rather than reopening/closing another descriptor. Cover threads/processes, alternate root spellings, nested calls, abnormal exit and bounded acquisition. Lock failure returns an actionable error and performs no deletion. This coordinates participating processes, not hostile same-user mutation outside the protocol.

Writers create uniquely owned cache_root/.staging/<operation-id>/ under a short transaction, then release the root lock during clone/build. Staging is excluded from every age/size/clear/empty-directory operation; live inputs stay operation-owned until consumption finishes. Final publication alone holds the root lock. For an existing nonempty destination, rename the old entry into that operation's private retired area, then rename the completed staging entry into the now-empty destination. Never assume os.replace overwrites a nonempty directory. Readers that consume these cache entries participate in the transaction. On failure/crash retain pending state and both recoverable generations with diagnostics; do not advertise rollback or remove someone else's bytes. Installer rollback/_cleanup_cache delete only an entry whose recorded operation_id and generation still match the caller's captured ownership. Explicit operator remove_grammar remains a separately documented removal operation. Retain abandoned staging conservatively; no age-based recovery guessing.

Store metadata in cache_root/.publications.json: schema=cache_publication.v1, current_generation=nonnegative integer, entries keyed by canonical top-level relative entry paths. Each record has operation_id, generation, state=pending|published and published_at_ns=integer|null. Increment the monotonic logical generation under lock for each pending and published transition, never reuse it. Use forward-slash relative keys and the filesystem's case identity; reject absolute/parent-traversing/alias-colliding keys. The marker owns the entire downloads/builds/tmp top-level entry and all descendants. Age, size and clear evict whole entries, never individual files from a published structured entry. Preserve config's regular-file counter by counting removed regular descendants; core/CLI retain top-level-entry counts. Remove a marker only after successful whole-entry deletion.

Metadata writes use UTF-8 and an exclusively created same-directory temporary regular file, closed before atomic replacement. No metadata comes from downloaded payloads. A pending marker with null publication time precedes the retire/rename sequence; committed publication records the real wall-clock time independent of copy2 mtimes and a new logical generation. Pending/interrupted entries and private retired bytes are preserved/reported. Missing legacy records use no-follow descendant ages. Malformed records stop deletion with diagnostics until explicit validated recovery; cleanup never silently resets authority metadata.

At public cleanup invocation, before waiting for the lock, read one immutable, no-follow, atomically published metadata snapshot and capture its current_generation (zero only for genuinely absent metadata), pending entries and age cutoff. A read/validation failure stops deletion. After acquiring the lock, reread fresh metadata: generations greater than that captured fence and pending entries survive every age/size/clear operation. Incrementing again at the published transition protects a writer that was pending at invocation. This compares ordered logical generations, not UUIDs or wall-clock ordering. Hold the transaction across candidate identity/eligibility revalidation and deletion. Age eligibility requires all descendants and the marker expired; clear/size may evict recent preexisting whole entries, but never staging or post-invocation publications. Require writer-held-lock barriers for all three modes.

Never traverse payload links or junctions or account for target bytes. An eligible in-entry link, including a dangling link, may be unlinked as a leaf using its own lstat age; target bytes/counts are zero. Preserve the existing expired-directory/dangling-link acceptance. Root/namespace links are rejected. POSIX deletion is anchored to opened directories with dir_fd, no-follow opens, identity rechecks and unlink/rmdir, not an unchecked path rmtree. Windows walks validated non-reparse directories under the transaction, rechecks root/candidate file identity immediately before unlink/rmdir, and removes junctions as leaves with rmdir, never recursion. Participating writers cannot substitute ancestors while this lock is held; controlled replacement before acquisition must be detected. Hostile nonparticipating same-user mutation is excluded. Unavailable containment primitives produce a reported failure, never a silent platform pass or a Windows-wide no-op. Real ordinary deletion and junction/outside-sentinel tests are required on Windows. Preserve managed roots; failed/skipped removals count no reclaimed bytes.

DirectoryManager.cleanup_empty_directories is restricted to validated participating cache namespaces under the same root transaction; it never sweeps base_dir, installed grammars, .staging, lock/metadata files or another nested root. If config's root is X/cache while core's is X, they are distinct protocols: never recurse from X into X/cache, and do not acquire nested locks. Inventory every actual configured root and reject overlapping managed deletion namespaces. No global base-directory empty sweep survives.

Validation JSON keeps its expiration rule but joins the same transaction (treesitter-chunker#370). Writers and pruners freshly read/merge disk state under lock, validate the regular no-follow file, then atomically replace closed UTF-8 temporary output. Never overwrite from an instance-local stale snapshot or follow an outside JSON symlink. Test two real writers, a writer/pruner barrier and an outside JSON sentinel.

Inventory participants before implementation: core download/build consumers, rollback, owned cache cleanup, validation-cache load/write/prune and manager cleanup; CLI fallback and actual fetch/build/remove participants; config age/size/clear/auto and scoped empty-directory removal. Record installed grammars/operator sources and distinct nested roots as exclusions. Use real subprocess barriers at existing publication/cleanup helpers with test-only wrappers; no timing sleeps or mock replacement of the behavior under test. Older versions and arbitrary external writers do not honor locks: stop them before migration and document this boundary.

### Auxiliary suite contract

Retain bounded local discovery/list, fixture parsing, missing grammar, corrupt local artifact, invalid arguments and removal of a suite-owned fixture. Use current signatures and inspect their results; `TypeError`/`AttributeError` from stale calls is a harness failure, never successful recovery. Use an empty or text corrupt file that fails validation without loading unreviewed native code. Positive parsing uses a trusted locally available grammar copied into the disposable root.

Every retained entrypoint creates or receives one disposable root; pass root-scoped managers/config/CLI objects explicitly. In subprocess tests set HOME/USERPROFILE/XDG paths before imports and supply the trusted fixture beforehand. Caller-supplied roots survive cleanup; only automatically owned roots are removed, in `finally`. Reports stay under the root. Keep cleanup ownership valid through all suites, including CLI/system/benchmark construction; never mutate process-global home concurrently.

Retire external versions/fetch/build simulation, pretend disk-full/permission recovery, constant-pass UX scores and destructive performance optimization from the default auxiliary suite. Report them explicitly as unsupported with reasons, excluded from tested/passed totals. Retain network-failure coverage only through a local deterministic transport seam with no real DNS/URL request; otherwise retire it. Optional bounded local benchmarks remain diagnostic, not correctness assertions. No network access, host grammar removal or minute-long stability loop in default execution. Default calls without required local inputs return actionable unmet-input results, never auto-download. Do not repair unrelated CLI info/native-admission semantics; retire any auxiliary assertion requiring unresolved GRAMMARS behavior.

## Lane Index & Dependencies

SL-1 — Cache writer/deleter protocol and fallback repair
  Depends on: (none)
  Blocks: SL-3
  Parallel-safe: no

SL-2 — Auxiliary self-test isolation
  Depends on: (none)
  Blocks: SL-3
  Parallel-safe: no

SL-3 — Documentation and acceptance reducer
  Depends on: SL-1, SL-2
  Blocks: (none)
  Parallel-safe: no

## Lanes

### SL-1 — Cache writer/deleter protocol and fallback repair

- **Scope**: Implement the shared transaction contract and repair core concurrency and CLI fallback age selection in two separate PRs.
- **Owned files**: `chunker/grammar_management/__init__.py`, `chunker/grammar_management/core.py`, `chunker/grammar_management/cli.py`, `chunker/grammar_management/config.py`, `tests/test_core_grammar_cache_cleanup.py`, `tests/test_public_grammar_cli.py`, `tests/test_public_grammar_config.py`, `tests/test_grammar_installer_language_safety.py`, `tests/test_grammar_source_validation.py`, `docs/development/cache-cleanup-contract.md`
- **Interfaces provided**: `CLEANUP cache implementation`, `CLEANUP contract review`, `CLEANUP cache fixture and mutation evidence`
- **Interfaces consumed**: `public cache APIs (pre-existing)`, `local Python parse fixture (pre-existing)`
- **Parallel-safe**: no
- **Tasks**:
  - test: Extend existing tests with a recent child inside an old directory, entirely expired directories, exact-cutoff content, empty roots, denied deletion and truthful counters. Correct the fallback test that currently codifies mixed-age deletion. Keep real parse assertions on preserved fixture bytes.
  - test: Use barriers/events, not sleeps, to pause at scan/delete and writer/publication boundaries. Exercise core, actual core-unavailable CLI, config age/size/clear, installer cleanup and two concurrent deleters in real processes. Test late additions, same-path replacement, old-mtime copies with fresh markers, cleanup waiting on writers, pending-marker crash recovery, lock contention and active staging. Assert the schedule actually entered each production path.
  - test: Exercise file/directory symlinks, dangling links, redirected namespace roots, ancestor substitution and real Windows junctions with outside sentinels. No outside bytes may change or count as reclaimed. Test failing removal after eligibility without overcounting.
  - impl: Freeze and review this transaction contract before protocol implementation. First independently land treesitter-chunker#324/treesitter-chunker#369 with static mixed-age/no-follow/public import acceptance only. Then land treesitter-chunker#323/treesitter-chunker#370 with the complete participant/root/pending/publication protocol. Follow the active per-slice detailed plan for code/tests/docs ownership and acceptance. Never claim the concurrency IF gate from the static PR.
  - verify: Run the cache-focused and installer/source suites in Verification, then the cache mutations. Supply command outcomes, controls and per-platform findings to SL-3; preserve separate issue acceptance records.
  - verify: `uv run --locked --all-extras pytest tests/test_core_grammar_cache_cleanup.py tests/test_public_grammar_cli.py tests/test_public_grammar_config.py tests/test_grammar_installer_language_safety.py tests/test_grammar_source_validation.py -q`

### SL-2 — Auxiliary self-test isolation

- **Scope**: Repair or explicitly retire auxiliary scenarios under one disposable root for treesitter-chunker#177.
- **Owned files**: `chunker/grammar_management/testing.py`, `tests/test_grammar_self_test_workflow.py`
- **Interfaces provided**: `CLEANUP auxiliary implementation`, `CLEANUP auxiliary disposition and test evidence`
- **Interfaces consumed**: `current grammar APIs (pre-existing)`, `trusted local fixture (pre-existing)`
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

Next intake is codex-plan-detailed for the static fallback slice, followed by codex-execute-detailed of that bounded plan. Do not dispatch this parent as one multi-repair implementation branch. Per-slice plans explicitly own their code/tests/docs/evidence; they permit serial shared-document edits on distinct branches. After the three accepted PRs, execute only the parent's final reduction. The parent has ten SL-1 paths, two SL-2 paths and three final-reducer paths; producer source ownership is disjoint. Per-PR reducers belong to the active bounded plan, not this final reducer. No writer fanout, dependency/env change, parser-pin update or golden generation is authorized. Evidence remains runner-owned.

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
7. `lock_failure_allows_delete`: ignore acquisition failure; contention/error tests must detect removal.
8. `rollback_deletes_other_generation`: omit operation/generation ownership; another writer's fixture is removed.
9. `stale_validation_snapshot`: overwrite fresh disk state from an old instance; two-writer/pruner assertions fail.
10. `unconditional_core_import`: restore the package's unconditional core import; the fresh public fallback subprocess fails.

Record metadata-only evidence in `docs/development/cleanup-verification.md`, referencing runner-owned `.phase-loop/` artifacts. Review and remote-platform evidence require runner-stamped amendments carrying artifact paths/digests; never hand-edit admitted ledgers or substitute proxy evidence without a roadmap amendment.

## Acceptance Criteria

- [ ] EC-CLEANUP-1 — proven by `uv run --locked --all-extras pytest tests/test_core_grammar_cache_cleanup.py tests/test_public_grammar_cli.py tests/test_public_grammar_config.py tests/test_grammar_installer_language_safety.py tests/test_grammar_source_validation.py tests/test_grammar_self_test_workflow.py -q`; falsified by bypass_cache_transaction, trust_copied_mtime, fallback_parent_age_only, follow_cache_link, lock_failure_allows_delete, rollback_deletes_other_generation, stale_validation_snapshot and unconditional_core_import at the owned core/config/CLI/package construction sites, with path-entered barriers, parsed surviving fixtures and outside JSON/link sentinels.
- [ ] EC-CLEANUP-2 — proven by `uv run --locked --all-extras pytest tests/test_grammar_self_test_workflow.py -q`; falsified by `ambient_auxiliary_root` and `auxiliary_false_success` at `chunker/grammar_management/testing.py:CLIValidator.__init__` and `chunker/grammar_management/testing.py:run_complete_test_suite`, with path-entered retained-scenario calls, outside sentinels and deliberately failing local fixtures.

## Spec Closeout Plan

- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: `docs/development/cache-cleanup-contract.md`, `docs/development/cleanup-verification.md`, `docs/grammar_management.md`, `CHANGELOG.md`
- evidence paths: `docs/development/cleanup-verification.md`, `.phase-loop/`
- redaction posture: `metadata_only`
- downstream handling: `none`

This implements existing roadmap acceptance without amending canonical specifications. GRAMMARS may consume the gate only after accepted implementation; planning itself produces no IF gate.

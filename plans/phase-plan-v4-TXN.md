---
phase_loop_plan_version: 1
phase: TXN
roadmap: specs/phase-plans-v4.md
roadmap_sha256: a96ef9073df2cd1bd860b1a151d75abc0a7edde7f242d8a2d7613c3fb38726c9
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_validation_cache_transactions.py tests/test_core_grammar_cache_cleanup.py -q -n 4"
---

# TXN: Transactional cache writers, cleanup and rollback

## Context

TXN is phase 10 of the v4 roadmap. It implements IF-0-TXNSPEC-1, the cache
transaction contract frozen in `docs/development/cache-transaction-contract.md`
(treesitter-chunker#540, merge `d681d8bf`), for its three consumers in
`chunker/grammar_management/core.py`:

- validation-record merge and containment (treesitter-chunker#370);
- concurrency-safe cleanup of `downloads/` and `builds/` entries
  (treesitter-chunker#323);
- a failed update that restores the previous installation
  (treesitter-chunker#363).

Forward publication and restore use IF-0-HOTFIX-1, `publish_native_grammar`
(treesitter-chunker#539, merge `60a5518f`), unchanged.

Main at planning time is `2d5e406b`. The defects still reproduce there:

- `GrammarValidator._cache_validation_result` writes the instance snapshot
  with `open("w")`, which follows a symlink at `validation_cache.json`. The
  `cleanup_cache` validation block reads, then rewrites, with no lock.
- `GrammarManager._cleanup_directory` checks ages, sums sizes, then calls
  `shutil.rmtree`.
- `GrammarInstaller._create_rollback_point` records metadata only, and
  `_perform_rollback` removes the metadata while logging that it restored.

**Runner decision D-a (binding for this phase).** Every installer publication
through `publish_native_grammar` needs ADMIT SL-core-2's
`GrammarInstaller(*, trusted_artifacts=)`. That is not on main yet, and ADMIT
is merge-gated on the Windows fix treesitter-chunker#547. TXN therefore:

1. lands treesitter-chunker#370 first;
2. then lands the parts of treesitter-chunker#323 that need no pins;
3. builds treesitter-chunker#363 so that it takes pins from callers and test
   fixtures, but does not open it for merge until ADMIT SL-core-2 has merged.
   Its PR body says so.

## Interface Freeze Gates

- (consumed) IF-0-TXNSPEC-1 — the frozen helper signatures and rules.
- (consumed) IF-0-HOTFIX-1 — `publish_native_grammar`.
- (consumed, treesitter-chunker#363 only) IF-0-ADMITPIN-1 via ADMIT SL-core-2,
  `GrammarInstaller(*, trusted_artifacts=)`.

TXN produces no new interface. Each public helper function lands in the PR
of the consumer that first needs it, with exactly the frozen signature.

## Carried-over review findings (treesitter-chunker#540 panel outcome)

The runner's panel outcome on treesitter-chunker#540 carries 15 non-blocking
findings into TXN. Each is addressed in the PR named below, and that PR's body
says how. The runner allows TXN to add private test pause points and to change
how a test injects its fault, as long as every named mutation is still
reliably killed. A change to a public signature or rule needs a reviewed
contract amendment; none is planned. Contract text edits below only bring the
text in line with these findings and with merged facts.

| Finding | Resolution | PR |
|---|---|---|
| Codex 1 — post-commit cache/cleanup failures | Failures after the installation is committed (cache-entry publication, staging disposal) become warnings; the install still reports success. A test forces one. | treesitter-chunker#323 (kept by treesitter-chunker#363) |
| Codex 2 / Claude N4 — ADMITPIN keys and admitted records | The record key stays whatever main's `_get_cache_key` defines (ADMIT SL-core-2 replaces it). The tests persist `ok` records from two distinct real compiled revisions, so they hold under either key. Contract Primitive 1 text updated. | treesitter-chunker#370 |
| Codex 3 / Claude N2 — supersession test | `restore` observes the pair again after `restore.before_artifact` and returns `superseded` if it changed. Test (c) replaces the destination before the call, and a second case at the barrier. | treesitter-chunker#363 |
| Claude N1 — `commit_without_lock` | Private point `commit.after_metadata` (context `section="commit"`) after the nested metadata hold is released. | treesitter-chunker#363 |
| Claude N3 — failed-update injection | The test pauses at the commit's `lock.before_acquire` and corrupts the staged artifact as a non-participant. "False-returning failure" and "handle release" are defined in the PR and test docstrings. | treesitter-chunker#363 |
| Claude N5 — group confirmation | Kill the group before reaping the leader (`waitid(..., WNOWAIT)` where available). "Empty" means no non-zombie member, using `psutil`. The helper reaps its own child. | treesitter-chunker#323 |
| Claude N6 — Windows staging and read-only files | `discard_staging` retires staging into `.txn/retired/` before deleting. The anchored deleter clears the read-only attribute on Windows before `unlink`, without following links. | treesitter-chunker#323 |
| Claude N7 — exceptions in the commit | Any exception from commit steps 2–3 goes to restore. `BaseException` is re-raised after restore. A metadata digest that differs from intent is not reported as `superseded`. | treesitter-chunker#363 |
| Claude N8 — verify `metadata.prev.json` | Checked against `Mp` before any metadata restore, and in the operator procedure. | treesitter-chunker#363 |
| Claude N9 — leftover mismatch | Before capture, compare the current metadata's `artifact_sha256` with the destination; warn and name any retained `rollback.json` for the language. Restore-time crashes added to the crash table. | treesitter-chunker#363 |
| Claude N10 — lock and marker lists | The lock-scope list says "including" and names initialization, staging creation/discard and garbage claiming. Every directory the helper creates under `.txn/` gets a marker; a missing marker is re-created idempotently. The 60 s rationale includes the probe's stop grace. Polling acquisition is documented as not fair. | treesitter-chunker#370 (infrastructure and text), treesitter-chunker#323 (retired/claimed directories) |
| Claude N11 — one filesystem | `open_cache_root` refuses a root whose existing `downloads`, `builds`, `grammars` or `.txn` lies on another device. | treesitter-chunker#370 |
| Claude N12 — HOTFIX citation | Cite merge `60a5518f`, the `.staged` suffix, and discharge the re-review trigger. State that the probe child never takes the cache lock. | treesitter-chunker#370 |

## Lane Index & Dependencies

```
SL-cache  #370 (helper module + validator cache) ──► #323 (staging, entries, pruner)
SL-rollback #363 (commit, restore, removal) ── rebases on #323; merges after ADMIT SL-core-2
```

- SL-cache #370 — Depends on: TXNSPEC, HOTFIX. Blocks: #323, #363.
- SL-cache #323 — Depends on: #370. Blocks: #363 (rebase).
- SL-rollback #363 — Depends on: #323; merge gate ADMIT SL-core-2 (D-a).

`core.py` follows the cross-phase merge order: ADMIT SL-core → TXN
treesitter-chunker#370 → ADMITFIX → TXN treesitter-chunker#323 → TXN
treesitter-chunker#363. Only one `core.py` PR is in its merge window at a
time; whichever is ready first merges and the others rebase.

`chunker/build/builder.py` (wheel inventory) is cross-phase with CIFAST
SL-lint and ADMIT SL-core-1. Whichever merges second rebases and recomputes
the pinned count and digest in `tests/test_supported_wheel_verification.py`.

## Lanes

### SL-cache — treesitter-chunker#370 (PR 1)

- **Scope**: Create the helper module with the root, lock, control area,
  containment primitives, the test seam and Primitive 1. Route the validator
  cache and the `cleanup_cache` validation block through it.
- **Owned files**:
  - `chunker/grammar_management/_transactions.py` (new)
  - `chunker/grammar_management/core.py`: `GrammarValidator._load_validation_cache`,
    `_cache_validation_result`, and the validation-cache block of
    `GrammarManager.cleanup_cache`
  - `chunker/build/builder.py` and `tests/test_supported_wheel_verification.py`
    (inventory line, count and digest only)
  - `tests/test_validation_cache_transactions.py` (new),
    `tests/test_grammar_compatibility_contract.py` (the
    treesitter-chunker#401 `all(...)` lookup only)
  - `scripts/run_platform_core.py` (registration)
  - `docs/development/cache-transaction-contract.md` (carried-over text),
    `docs/grammar_management.md`, `CHANGELOG.md`, this plan
- **Public functions landed**: `open_cache_root`, `cache_lock`,
  `read_json_records`, `update_json_records`, the four error classes, the
  constants and `Namespace`.
- **Tests (contract table)**: two writers in both orders; writer and pruner;
  outside-symlink sentinel. Each in real subprocesses driven by the seam.
- **Mutations**: `stale_validation_snapshot`, `pruner_stale_rewrite`,
  `follow_validation_symlink`.
- **Helper checks**: lock not inheritable; fork handler; nested-root refusal
  at open; different-device refusal; marker re-creation.

### SL-cache — treesitter-chunker#323 (PR 2)

- **Scope**: Primitive 2. Staging, `run_in_staging` with process groups and
  Windows job objects, `publish_entry`, `remove_entry`, `prune_entries`,
  `discard_staging`, the anchored deleter and garbage claiming. Route the
  installer download/build functions, `_cleanup_cache`, the staging routing in
  `install_grammar` and `GrammarManager.cleanup_cache`/`_cleanup_directory`
  through it. Installation itself keeps today's path until
  treesitter-chunker#363; no `publish_native_grammar` call is added here.
- **Owned files**: the helper module (Primitive 2 additions); `core.py`
  `_download_grammar`, `_build_grammar`, `_build_with_*`, `_get_commit_hash`,
  `_cleanup_cache`, the `install_grammar` staging routing,
  `GrammarManager.cleanup_cache`/`_cleanup_directory`;
  `tests/test_cache_entry_transactions.py` (new);
  `tests/test_core_grammar_cache_cleanup.py` (only where an assertion pins
  the old race); `scripts/run_platform_core.py`; `CHANGELOG.md`.
- **Tests**: writer and pruner; link boundaries (Linux, macOS, Windows);
  descendants (exit, timeout, parent death); owned inputs; republication
  failures; nested roots.
- **Mutations**: `prune_without_recheck`, `trust_copied_mtime`,
  `overcount_failed_removal`, `follow_cache_link`,
  `publish_before_group_empty`, `fallback_after_timeout`,
  `consume_published_input`, `no_rename_back`, `nested_root_retire`.

### SL-rollback — treesitter-chunker#363 (PR 3)

- **Scope**: Primitive 3. Installation metadata read/write, rollback point,
  restore, discard and installation removal. Route the commit section of
  `install_grammar`, `_create_rollback_point`, `_perform_rollback`,
  `_install_grammar_file`, `_save_installation_info`,
  `_load_installation_info`, `_remove_installation_info` and both
  `remove_grammar` methods through it. Pins come from callers and test
  fixtures; production pins arrive with ADMIT SL-core-2.
- **Merge gate**: ADMIT SL-core-2 merged (D-a). Until then the PR states that
  it is not ready to merge.
- **Tests**: failed update restores the pair; direct `restore` branches;
  serialization and crash.
- **Mutations**: `omit_restore`, `rollback_removes_metadata`,
  `restore_without_admission`, `restore_metadata_independently`,
  `commit_without_lock`, `inheritable_lock_fd`.

## Execution Notes

- Every PR records VB-1 (reproduction on unchanged main with SHA, command and
  output) and VB-2 (each named mutation fails its test; the fix passes). Named
  mutations are applied as temporary source patches, never as runtime flags.
- Concurrency tests use real subprocesses that install the private `_BARRIER`
  seam and block on a pipe, never on sleeps. Generous safety timeouts only
  bound hung children; no test asserts wall-clock behavior.
- The only permitted substitution is a `git` shim on `PATH` inside the test
  subprocess. Builds, probes and helper code stay real.
- The Windows preflight runs via `ssh win` only in a clean temporary checkout
  of the exact PR head, which is removed afterwards. A Code Integrity 3077
  block of a freshly compiled unsigned DLL is recorded as evidence and is
  treesitter-chunker#547's, not a TXN defect.
- Host caps: one heavy run at a time, `free -g` at least 6 GiB available,
  `pytest -n` at most 4, scratch under `$TMPDIR`. `scripts/run_ci_smoke.py`
  hard-codes `-n auto`; its selection runs at `-n 4` instead.
- The implementer does not merge, review or start subagents. The parent runs
  the VB-4 panel.

## Execution Policy

- SL-cache #370: work-unit=`lane_execute`, reason=`helper module and first consumer`
- SL-cache #323: work-unit=`lane_execute`, reason=`serial after #370`
- SL-rollback #363: work-unit=`lane_execute`, reason=`merge-gated on ADMIT SL-core-2 (D-a)`

## Verification

```bash
uv run --locked --all-extras pytest <new and touched test files> -q -n 4
uv run --locked --all-extras ruff check chunker/ cli/ tests/ tools/governed_group.py tools/governed_scope.py tools/sync_governed_test_transport.py --exclude archive --exclude logs --exclude site
uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/ tools/governed_group.py tools/governed_scope.py tools/sync_governed_test_transport.py
uv run --locked --all-extras python scripts/mypy_gate.py
uv run --locked --all-extras mypy --follow-imports=silent --allow-untyped-defs --allow-incomplete-defs --allow-untyped-calls --check-untyped-defs --no-pretty --no-error-summary --show-error-codes tools/sync_governed_test_transport.py
uv run --locked --with toml --all-extras python -c "import sys, pytest; sys.path.insert(0, 'scripts'); from run_ci_smoke import CI_SMOKE_TESTS; sys.exit(pytest.main(['-n', '4', '--timeout=60', '-q', *CI_SMOKE_TESTS]))"
uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
uv run --locked --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict --site-dir "$(mktemp -d)"
# Windows preflight, in a clean temporary checkout of the exact head, removed afterwards
```

Hosted Linux, macOS and Windows CI must be green at the exact head.

## Acceptance Criteria

- [ ] EC-TXN-1 — treesitter-chunker#370: two real `GrammarValidator`
  instances writing in either order both keep their records; a symlinked
  `validation_cache.json` leaves the outside sentinel unchanged; the
  stale-snapshot, pruner-stale-rewrite and symlink-follow mutations fail;
  expiration semantics are unchanged.
- [ ] EC-TXN-2 — treesitter-chunker#323: a deterministic writer/cleanup
  interleaving cannot delete a newly published entry, `bytes_freed` is
  truthful, and link and junction boundaries hold on Linux, macOS and Windows.
- [ ] EC-TXN-3 — treesitter-chunker#363: a real installation followed by a
  deterministic failed update restores the previous artifact and metadata,
  the next parse uses the previous revision, the omit-restore mutation fails,
  and handle release is shown on Windows.
- [ ] EC-TXN-4 — Every PR meets VB-1 to VB-4, and each carried-over finding
  above is answered in its PR.

## Spec Closeout Plan

- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: issue acceptance for treesitter-chunker#323,
  treesitter-chunker#363, treesitter-chunker#370
- evidence paths: `plans/phase-plan-v4-TXN.md`, PR logs, platform runs
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`

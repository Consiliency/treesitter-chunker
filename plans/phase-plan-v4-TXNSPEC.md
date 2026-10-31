---
phase_loop_plan_version: 1
phase: TXNSPEC
roadmap: specs/phase-plans-v4.md
roadmap_sha256: a28a7aa83f7f2c4754dedf4ed0455d61b3bfb79865c1aae64afab6d13bc41a38
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_release_hygiene_policy.py -q"
---

# TXNSPEC: Cache and persistence transaction protocol

## Context

TXNSPEC is phase 3 of the v4 roadmap. It produces IF-0-TXNSPEC-1: a narrowly
scoped writer/pruner/rollback contract for exactly three consumers in
`chunker/grammar_management/core.py`:

- `validation_cache.json` (treesitter-chunker#370);
- core cleanup directory deletion (treesitter-chunker#323);
- the installer rollback point (treesitter-chunker#363).

It succeeds the CLEANUP design in treesitter-chunker#364. That design
exhausted its three review rounds at head `4465de92`, and its final verdict on
treesitter-chunker#323 named seven blocking gaps. The full proposal is
preserved at `69606f61:plans/phase-plan-v3-CLEANUP.md`. The successor narrows
scope rather than repairing that general design. It drops:

- the publication journal and generation counters;
- root registration and configured-anchor derivation;
- size and clear eviction;
- `config.py` and CLI-fallback participation;
- automatic crash recovery.

It also keeps the transaction lock out of subprocess lifetimes.

Current construction sites, read only at main `7440971a`:

- `GrammarValidator._load_validation_cache` and `_cache_validation_result`
  overwrite the file from an instance snapshot and follow links.
- `GrammarManager.cleanup_cache` and `_cleanup_directory` check ages, then call
  `rmtree`.
- `GrammarInstaller._create_rollback_point` records metadata only.
  `_perform_rollback` deletes the previous metadata and logs that it restored.
- `_install_grammar_file` uses `copy2` in place.

This phase migrates no consumer.

**Interface-availability gate.** HOTFIX SL-2 runs in parallel and publishes the
IF-0-HOTFIX-1 signature in the treesitter-chunker#162 PR body, under the
heading `IF-0-HOTFIX-1 signature`. The contract is drafted against the
roadmap's IF-0-HOTFIX-1 text. The PR stays a draft until the published
signature exists and the restore section cites it by commit. If the signature
changes before approval, the restore section is reviewed again.

Reconciliation status: the signature is published in treesitter-chunker#539 at
head `7710fb7c699db33c244c95bf7d24d8730b91ea5b`. It is
`publish_native_grammar(source, destination, language, *, provenance, sample,
timeout) -> NativeProbeResult` in `chunker/_internal/user_grammar_tools.py`.
Admission cannot be separated from replacement in that function. The first
draft's admission-free identity restore was therefore replaced. Restore now
calls the function unchanged, with the caller's pin for the previous revision,
and fails closed without one. The installer commit order makes artifact
publication the last fallible step, so ordinary failed updates never need the
artifact republished. The signature was re-checked unchanged at
treesitter-chunker#539 head `cf1de762`. The contract does not depend on how
the staged temporary file is named; a pending treesitter-chunker#539 change
gives it a suffix that is not `*.so`. A change to the signature triggers a
re-review of the restore section.

## Interface Freeze Gates

- [ ] IF-0-TXNSPEC-1 — `docs/development/cache-transaction-contract.md`,
  including the frozen signatures of the future
  `chunker/grammar_management/_transactions.py`. It covers:
  - the locked fresh-read/merge/atomic-replace JSON update with no-follow
    containment;
  - staged publication with a deletion-time stale re-check and
    retire-then-delete, no-follow and junction-safe;
  - a rollback point with restorable copies, and `restore` through the
    unchanged IF-0-HOTFIX-1 `publish_native_grammar`;
  - the lock file `<root>/.txn.lock`, single-host scope and supported
    platforms;
  - a disposition for each of the seven treesitter-chunker#364 gaps.

  The gate is produced only by independent approval (EC-TXNSPEC-3).

## Lane Index & Dependencies

SL-1 — Transaction contract
  Depends on: (none); interface-availability gate on IF-0-HOTFIX-1 publication
  Blocks: TXN
  Parallel-safe: no

## Lanes

### SL-1 — Transaction contract

- **Scope**: Write the contract and this plan in one draft PR.
  Reconcile the restore section with the published IF-0-HOTFIX-1 signature
  before the PR is marked ready.
- **Owned files**:
  - `docs/development/cache-transaction-contract.md`
  - `plans/phase-plan-v4-TXNSPEC.md`
  - `mkdocs.yml` (`not_in_nav` line only)
  - `tests/test_release_hygiene_policy.py` (`INTERNAL_DOCS` entry only)
- **Interfaces provided**: `IF-0-TXNSPEC-1`
- **Interfaces consumed**:
  - `IF-0-HOTFIX-1` (published signature; interface-availability gate)
  - `probe_native_grammar`/`verify_artifact` (pre-existing,
    `chunker/grammar/integrity.py`)
  - `IF-0-ADMITPIN-1` (roadmap text: one pin per language)
- **Parallel-safe**: no
- **Tasks**:
  - doc: Write scope, the participant and non-participant tables, the lock
    and control area, the containment rules, the three primitives and the
    gap-disposition table.
  - doc: For each consumer, name the deterministic barrier test and the
    mutation it must kill (EC-TXNSPEC-2).
  - doc: Freeze the helper signatures as text. No stub module is added: a new
    package file would change the pinned wheel payload inventory
    (`tests/test_supported_wheel_verification.py`). TXN SL-cache creates the
    module and updates that inventory.
  - reconcile: Find the treesitter-chunker#162 PR
    (`gh pr list --search "162 in:title,body" --state open`) and compare its
    `IF-0-HOTFIX-1 signature` with the restore section. Cite the signature by
    commit. If the published function cannot run its replacement steps without
    probe admission, stop and report a scope question. Do not define a second
    publish path.
  - verify: Run the CONTRIBUTING.md local validation block, the strict docs
    build and the hygiene test.

## Execution Notes

- This preamble phase is interface-only, so a single lane is justified. The
  only output is one contract PR. Implementation fans out in TXN as SL-cache
  (treesitter-chunker#370 → treesitter-chunker#323) and SL-rollback
  (treesitter-chunker#363).
- The contract asks the TXN plan to assign `GrammarInstaller._download_grammar`,
  `_build_grammar` and `_cleanup_cache` (the writer side of
  treesitter-chunker#323) to the treesitter-chunker#323 PR. SL-rollback then
  rebases.
- Do not touch `chunker/_internal/cache.py`, `chunker/boundary/cache.py`, any
  `core.py` code or parser pins.
- The implementer does not run reviews or merge. The parent runs the
  two-reviewer panel (VB-4) after the gate is met. If the design is not
  approved within three rounds, the phase stops with `human_required=true`,
  `blocker_class=product_decision_missing` and decision S-TXN.
- Host resource caps apply: one heavy run at a time, at least 6 GiB available
  in `free -g`, `pytest -n` of at most 4, and scratch under `$TMPDIR`.

## Execution Policy

- SL-1: work-unit=`lane_execute`, reason=`interface-only contract`

## Verification

```bash
uv run --locked --all-extras pytest tests/test_release_hygiene_policy.py -q
uv run --locked --all-extras ruff check chunker/ cli/ tests/ tools/governed_group.py tools/governed_scope.py tools/sync_governed_test_transport.py --exclude archive --exclude logs --exclude site
uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/ tools/governed_group.py tools/governed_scope.py tools/sync_governed_test_transport.py
uv run --locked --all-extras python scripts/mypy_gate.py
uv run --locked --all-extras mypy --follow-imports=silent --allow-untyped-defs --allow-incomplete-defs --allow-untyped-calls --check-untyped-defs --no-pretty --no-error-summary --show-error-codes tools/sync_governed_test_transport.py
uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
uv run --locked --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict --site-dir "$(mktemp -d)"
```

There is no runtime behavior change, so platform-core, full-suite and Windows
preflight runs are not required. Hosted CI must be green at the exact head.

## Acceptance Criteria

- [ ] EC-TXNSPEC-1 — The contract gives:
  - the IF-0-TXNSPEC-1 signatures;
  - the lock location `<root>/.txn.lock`;
  - the single-host scope and supported platforms;
  - a seven-row `addressed`/`scoped out` table with rationale.

  Proven by review of `docs/development/cache-transaction-contract.md`.
- [ ] EC-TXNSPEC-2 — Each consumer has its named barrier test and mutation:
  - two-writer and writer/pruner tests (treesitter-chunker#370);
  - the outside-symlink sentinel (treesitter-chunker#370);
  - writer/pruner and link-boundary tests (treesitter-chunker#323);
  - the failed-update restore (treesitter-chunker#363).
- [ ] EC-TXNSPEC-3 — Two independent reviewers approve within three rounds,
  after the restore section cites the published IF-0-HOTFIX-1 signature.
  Otherwise S-TXN applies.

## Spec Closeout Plan

- schema: `spec_delta_closeout.v1`
- decision: `canonical_spec_update`
- target surfaces: `docs/development/cache-transaction-contract.md`
- evidence paths: `plans/phase-plan-v4-TXNSPEC.md`, review record
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`; a design
  rejected at the cap is `product_decision_missing` (S-TXN)

---
phase_loop_plan_version: 1
phase: ADMITPIN
roadmap: specs/phase-plans-v4.md
roadmap_sha256: 44ce0acdaaed7e71fcf3df350331985f3ecf6c3af26a074c117961dd49d8cc6a
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_release_hygiene_policy.py -q"
---

# ADMITPIN: Native admission pin source and load inventory

## Context

ADMITPIN is Phase 1 of `specs/phase-plans-v4.md`. It is an interface-only
preamble to treesitter-chunker#362. Since treesitter-chunker#519, `grammar
info` and `grammar diagnose` return 1 for every real grammar, because no
production pin source exists. This phase settles where production callers and
the CLI get approved pins, and gives every native load site a disposition, so
that ADMIT can split the integration by file.

The plan starts from main `7440971a` (roadmap merge, treesitter-chunker#533).
Status since the roadmap snapshot: treesitter-chunker#534 and
treesitter-chunker#535 are merged; treesitter-chunker#435 and
treesitter-chunker#389 are closed. None of these change this phase.
treesitter-chunker#537 (OWNERDEC records) is open, and nothing here depends on
it.

The raw material already exists. `probe_native_grammar` and `NativeProbeResult`
in `chunker/grammar/integrity.py` are the accepted admission primitive
(treesitter-chunker#510). `docs/development/native-validation-contract.md`
already defines keyword-only `trusted_artifacts` for `GrammarAnalyzer`,
`SmartGrammarManager` and `UserGrammarTools`. This phase extends that
document and writes no parallel contract.

Facts from the inventory survey at `7440971a`:

- `grep -rn 'ctypes.CDLL\|cdll.LoadLibrary\|Language(' chunker/` returns 19
  hits. Fifteen are real loads or capsule constructions; four are type
  annotations or a comment in `chunker/_internal/registry.py`.
- `load_compiled_grammar` (`core.py:127`) has five callers: the probe child
  (`integrity.py:131`), `GrammarValidator` (`core.py:229`, `core.py:260`), the
  grammar test command (`cli.py:1945`) and the testing reload
  (`testing.py:153`). The grep does not match those calls, so the inventory
  lists them separately.
- The legacy `TreeSitterGrammarValidator` constructor always raises
  `TypeError` (treesitter-chunker#400). Its static `check_abi_compatibility`
  can still be called without construction and loads in-process.
- `GrammarDownloadManager.validate_grammar` and
  `GrammarMetadataExtractor.extract_from_dependencies` have no in-repository
  callers.
- `GrammarInstaller` builds its own unpinned `GrammarValidator`
  (`core.py:587`). So do the two validators in `compatibility.py` (lines 148
  and 770) when no validator is passed in.
- The argparse `grammar` group (`chunker/cli/grammar_commands.py`) is the
  `grammar info` path named in EC-ADMIT-1. The click `grammar_cli` group
  (`ComprehensiveGrammarCLI`) is exported but not wired to a console script.

## Interface Freeze Gates

- [ ] IF-0-ADMITPIN-1 — Pin mapping, the one CLI pin source, the in-process
  pattern for using an admitted grammar, and the verdict-reuse key, as written
  in the "Production pin source and native-load inventory (ADMITPIN)" section
  of `docs/development/native-validation-contract.md`.
- [ ] IF-0-ADMITPIN-2 — The inventory table in the same section, with a
  disposition for every site and the treesitter-chunker#400 decision (retire).

Decisions this plan makes, which are open to challenge in review:

1. **Pin source name.** The CLI option `--trusted-artifacts PATH`, accepted
   by both grammar command groups before the subcommand. The file schema is
   `chunker.trusted_artifacts.v1`. No configuration file under the cache
   directory is read. Build, download and cleanup commands write there, so a
   pin file in that directory would be a manifest written beside the
   artifacts it approves, which the existing contract says confers no trust.
   The cost is that the `chunker.parser` parse path gets no ambient pin
   source. It falls back to the official wheels, the language-pack and the
   BAML companion. The caller-migration notes state this.
2. **No-pin outcome.** The caller reports `untrusted` without calling the
   probe, as IF-0-ADMITPIN-1 requires. ADMIT also aligns the existing
   SAFELOAD consumers, so an unpinned language with no library reports
   `untrusted` rather than `missing`.
3. **Using a grammar in-process after admission.** Make a private copy,
   verify it, probe it, then load only that copy. This reuses
   `verify_artifact` and the probe; it adds no second trust protocol.
4. **treesitter-chunker#400.** Retire. The class has no working consumer.
   Repairing it would duplicate `GrammarValidator`.
5. **Legacy sites.** Retire V1, D1, T1, T2 and A1. Integrate M1 with the
   probe only, adding the keyword-only `trusted_artifacts` argument to legacy
   `chunker.grammar_manager.GrammarManager`.
6. **Out of scope.** The language-pack, the official Python/JavaScript wheels
   and the BAML companion `Language(...)` constructions are package-supplier
   loads, outside this contract.

## Lane Index & Dependencies

SL-1 — Contract freeze (single lane)
  Depends on: (none)
  Blocks: ADMIT
  Parallel-safe: no (single writer of `docs/development/native-validation-contract.md` until ADMIT starts)

A single lane is justified: the only output is one reviewed contract-doc PR.
The implementation fans out in ADMIT.

## Lanes

### SL-1 — Contract freeze

- **Scope**: Extend the native validation contract with IF-0-ADMITPIN-1 and
  IF-0-ADMITPIN-2. No product code changes.
- **Owned files**: `docs/development/native-validation-contract.md`,
  `plans/phase-plan-v4-ADMITPIN.md`
- **Read only**: `chunker/grammar/integrity.py`, every inventoried site
- **Interfaces provided**: IF-0-ADMITPIN-1, IF-0-ADMITPIN-2
- **Interfaces consumed**: `probe_native_grammar`, `NativeProbeResult`,
  `verify_artifact` (pre-existing, unchanged)
- **Tasks**:
  - Survey every native load at the base commit, including the
    `load_compiled_grammar` callers and the `ldd` path that the grep cannot
    see.
  - Write the pin mapping, the CLI pin source, the in-process pattern, the
    verdict-reuse key, the treesitter-chunker#400 disposition, the inventory
    and the caller migration notes.
  - Point the existing "Scope and trust" text at the new section instead of
    writing a parallel contract.
  - Reconcile the grep with the tables (Verification), then run the
    CONTRIBUTING.md validation block.
  - Open the PR. The parent runs the two-reviewer panel (VB-4) and records
    approvals below. At most three rounds; after that, a reviewed successor is
    needed.

## Notes for the ADMIT plan

- The roadmap's ADMIT lanes do not cover `chunker/cli/grammar_commands.py`,
  `chunker/_internal/grammar_management.py` or
  `chunker/grammar_management/compatibility.py`. The contract proposes SL-core
  for all three, because SL-core owns the CLI pin path for EC-ADMIT-1. It also
  assigns the `_test_compiled_grammar` load (`cli.py:1945`) to SL-core and the
  `examples/manage_grammars.py` update to SL-legacy.
- `GrammarInstaller` gains the keyword-only argument. The roadmap gives the
  GrammarInstaller region of core.py to TXN SL-rollback, so this one-line
  constructor edit by ADMIT SL-core must be agreed with that lane and follow
  the core.py merge order in the roadmap's Execution Notes.
- Inventory line numbers refer to `7440971a`. ADMIT keeps the site IDs,
  updates the status column, and adds a row for any new direct load.

## Execution Notes

- Do not touch `chunker/grammar/integrity.py`, `_read_child` or launcher
  reaping.
- Respect the host resource caps: one heavy run at a time, at least 6 GiB
  available (`free -g`) before it starts, `pytest -n` no higher than 4, and
  scratch space under `$TMPDIR`.
- Do not merge from the lane; the parent owns review and merge.

## Verification

```bash
# EC-ADMITPIN-1: every grep hit appears as a path:line reference in the tables
export LC_ALL=C
scratch="$(mktemp -d)"
grep -rn 'ctypes.CDLL\|cdll.LoadLibrary\|Language(' chunker/ | cut -d: -f1,2 | sort -u > "$scratch/grep.txt"
grep -oE '`chunker/[^` ]+:[0-9]+`' docs/development/native-validation-contract.md | tr -d '`' | sort -u > "$scratch/table.txt"
comm -23 "$scratch/grep.txt" "$scratch/table.txt"   # must print nothing

# No product code changes
git diff --name-only origin/main...HEAD   # only the two owned files

# CONTRIBUTING.md validation block (VB-3)
uv run --locked --all-extras ruff check chunker/ cli/ tests/ tools/governed_group.py tools/governed_scope.py tools/sync_governed_test_transport.py --exclude archive --exclude logs --exclude site
uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/ tools/governed_group.py tools/governed_scope.py tools/sync_governed_test_transport.py
uv run --locked --all-extras python scripts/mypy_gate.py
uv run --locked --all-extras mypy --follow-imports=silent --allow-untyped-defs --allow-incomplete-defs --allow-untyped-calls --check-untyped-defs --no-pretty --no-error-summary --show-error-codes tools/sync_governed_test_transport.py
uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
uv run --locked --all-extras pytest tests/test_release_hygiene_policy.py -q
uv run --locked --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict --site-dir "$(mktemp -d)"
```

There is no Windows preflight: no path, native, temp-file, export or config
code changes. VB-1 and VB-2 do not apply to an interface-only document; there
is no defect to reproduce and no regression test.

## Acceptance Criteria

- [ ] EC-ADMITPIN-1 — The inventory table is in the contract, and the
  reconciliation above prints nothing.
- [ ] EC-ADMITPIN-2 — The pin signature, the `--trusted-artifacts` CLI source,
  the caller migration notes and the treesitter-chunker#400 disposition
  (retire) are in the contract.
- [ ] EC-ADMITPIN-3 — Two independent reviewers approve within three rounds
  (VB-4), recorded below. The diff touches no product code.

## Review record

Pending. The parent records each reviewer, the reviewed head SHA and the
verdict here, or in the PR, before merge.

## Spec Closeout Plan

- schema: `spec_delta_closeout.v1`
- decision: `canonical_spec_update`
- target surfaces: `docs/development/native-validation-contract.md`
- evidence paths: `plans/phase-plan-v4-ADMITPIN.md`, the contract PR review record
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`

# Tree-sitter Chunker — Phase Plan v4 (Open Backlog, 2026-10-31 Triage)

> How to use this document: run `/claude-plan-phase <ALIAS>` to produce the lane-level plan for each phase (→ `plans/phase-plan-v4-<alias>.md`), then `/claude-execute-phase <alias>` to build it. `claude-phase-loop` can drive the whole DAG; it stops at the human-gated phases named in Execution Notes.

---

## Context

This roadmap schedules the open backlog of `Consiliency/treesitter-chunker` (40 open issues on 2026-10-31) from the triage done against main `98129bde`. It is a new roadmap, not an append to v3. `specs/phase-plans-v3.md` remains a historical input, and its phases are not edited. Its SAFELOAD contract has since landed (treesitter-chunker#510; treesitter-chunker#151, treesitter-chunker#164 and treesitter-chunker#165 closed today), its WHEELS issues are closed, and its CLEANUP transaction design (treesitter-chunker#364) failed its three-round cap. So the remaining v3 scope needs a fresh schedule rather than more of the same phases. treesitter-chunker#283 also closed today.

The backlog clusters into a few shared designs and many small, disjoint repairs:

- **Native admission (theme A).** treesitter-chunker#362 is the umbrella. Since treesitter-chunker#519 merged, `grammar info`/`diagnose` return 1 for every real grammar, because no production pin source exists yet. That makes treesitter-chunker#362 the most urgent item. Its pieces are an interface freeze (where production pins come from, and the disposition of each native load site) followed by per-entrypoint integration. `probe_native_grammar` in `chunker/grammar/integrity.py` (from treesitter-chunker#510) is the one admission mechanism to reuse; no second trust protocol may be introduced. treesitter-chunker#128, treesitter-chunker#120 and treesitter-chunker#117 follow it, and treesitter-chunker#400 sits inside it.
- **Cache and persistence transactions (theme C).** treesitter-chunker#370 and treesitter-chunker#323 both need a writer/pruner protocol. treesitter-chunker#363 needs a restorable rollback point. The last design attempt (treesitter-chunker#364) was rejected, with seven named blocking gaps. This roadmap re-opens the design as a narrowly scoped interface-only phase with an explicit stop if it fails again. treesitter-chunker#358 (the parallel AST cache) is deliberately **not** gated on this protocol: it uses a different store (`chunker/_internal/cache.py`) and different files, and its defect is entry identity, not writer/deleter coordination.
- **Reference lookup (theme B).** One shared real-parser fixture suite feeds one Python PR and one JavaScript PR.
- **Smaller themes**, mostly independent of each other: GraphML exporters (D), load-sensitive deadlines (E), selection metadata (F), Go build constraints (G), and CI hygiene.

Raw material to reuse: `probe_native_grammar` and `docs/development/native-validation-contract.md` (admission); the treesitter-chunker#364 design history and its seven blocking findings (transaction protocol); the existing per-language scope contract tests in `tests/test_python_scope_*` and `tests/test_javascript_scope_*` (references); `scripts/mypy_gate.py` with `docs/development/mypy-baseline.txt`, which has 1,356 lines (type debt).

---

## Assumptions (fail-loud if wrong)

1. treesitter-chunker#534 (merged 2026-10-31 as `afff90a6`) aligns the remaining Python version declarations with the 3.12 floor. It touches `.github/workflows/release.yml` (`UV_PYTHON` on the verify-installed-wheel job), `specs/active/release-process-spec.md`, `chunker/build/builder.py` (`Requires-Python` in both the wheel and ZIP fallback paths), a new `.python-version` that pins 3.12, the conda/Homebrew formulas, READMEs/docs and `tests/test_release_hygiene_policy.py`. PY314's precondition (treesitter-chunker#534 merged) is therefore met.
2. treesitter-chunker#435 was a bug, not a pin change: it reproduced on Python 3.12 and 3.14, where a blocking `read()` in the `chunker/core.py` file-read path (around line 1276) on a FIFO ignored SIGINT. The owner chose the fix (reject non-regular inputs, meaning FIFOs, devices, sockets and directories, with a clear error). treesitter-chunker#535 implemented it and merged on 2026-10-31 (`d3d6b20e`), closing treesitter-chunker#435. No phase depends on it; the first step of the `chunker/core.py` single-writer chain is done (see Execution Notes).
3. The pinned stack stays Tree-sitter 0.26 with language-pack 1.20. No phase changes parser pins or hand-edits Boundary IR goldens.
4. `probe_native_grammar(path, language, *, provenance, sample, timeout, inspect_artifact)` and its `NativeProbeResult` remain the accepted admission primitive. If treesitter-chunker#508 or treesitter-chunker#509 recurs and shows a defect in it, ADMIT is paused and re-planned.
5. The transaction protocol can be scoped to a single host (in-process and cross-process writers in one cache root) and still satisfy treesitter-chunker#370, treesitter-chunker#323 and treesitter-chunker#363. If independent review rejects that scope, TXN does not run (see stop condition S-TXN).
6. The host has about 29 GiB RAM and 24 cores and has hit memory pressure. The resource caps in Cross-Cutting Principles are sized for that host.
7. All 40 open issues were read on 2026-10-31. An issue that has changed state when its phase is planned must be re-read and re-placed, not executed from this snapshot.

---

## Non-Goals

- Held or in-flight items (see **Held / In Flight**): treesitter-chunker#508, treesitter-chunker#509, and the GROUP adapter on Windows/macOS.
- Any Python version floor change beyond what treesitter-chunker#534 lands. PY314 moves validation to 3.14 but keeps a 3.12 minimum and does not publish a package.
- Package publication, release dispatch, consumer lock updates, and repository-settings changes made by an agent. Settings changes are the owner's, via SETTINGS.
- A general cache framework. TXNSPEC covers only the three named consumers. The AST cache and `chunker/boundary/cache.py` stay outside it.
- A full Go build-constraint evaluator. Go hint work (treesitter-chunker#438) defines truthful minimums or an explicit "unknown".
- Coverage-percentage gates. treesitter-chunker#69 stays behavior-and-mutation slices only.
- Svelte `each_block` metadata (treesitter-chunker#265) is parked (see **Unplaced**).
- Opening, closing or editing GitHub issues as part of writing this roadmap. Phases may later comment on and close issues they complete, under the repo's rules.

---

## Cross-Cutting Principles

1. **Verification bar (every PR, every phase).** The bar has four parts, and each phase's exit criteria cite them as VB-1 to VB-4:
   - **VB-1 — Reproduction first.** Reproduce the defect on unchanged main before any product edit. Record the main SHA, the exact command and the observed output in the PR. If it no longer reproduces, stop and report; do not "fix" it.
   - **VB-2 — Regression that fails on old code.** The new regression test runs against unchanged code, or against a named mutation that restores the old behavior, and fails. It then passes on the fix. Record both runs.
   - **VB-3 — Repository checks.** Run the narrow tests, then the CONTRIBUTING.md local validation block (Ruff, Black, mypy gate, governed body-type check, CI smoke). Run platform-core for broad changes. Run the standing Windows preflight for path, native, temp-file, export-formatting or config changes. Hosted Linux/macOS/Windows CI must be green at the exact head.
   - **VB-4 — Two-reviewer panel.** Two independent reviewers (different vendors where available) review the exact head. Merge only with both approving and no unresolved blocking finding. Each PR gets at most three review rounds; after that, a reviewed successor is required, not a fourth round.
2. **Host resource caps (memory pressure).**
   - At most **one** full-suite or coverage run on the host at a time.
   - At most **two** concurrent heavy runs of any kind: platform-core, full suite, native-probe/compiled-grammar suites, wheel builds, `uv sync` of a new interpreter.
   - At most **four** concurrent focused pytest runs across all lanes. No `pytest -n` above 4 workers.
   - At most **three** phases executing at once.
   - Before a heavy run, check that `free -g` shows at least 6 GiB available; otherwise wait.
   - Scratch goes under the inherited disk `TMPDIR` via `tempfile`, never a literal `/tmp`, and disposable trees are removed in `finally` (the treesitter-chunker#481 lesson).
3. **One issue per PR**, except theme B, which is one PR per language as the triage directs. Even there, each issue keeps its own fixture contract and named mutation. Defects found along the way are filed separately and never folded in silently.
4. **One admission mechanism.** Every native load either goes through `probe_native_grammar` with an independently approved pin, is documented as a caller-trusted low-level primitive, or is retired. No trust-all switch. No hashing discovered bytes to promote them into approvals.
5. **Real parsers and real fixtures.** No native-method mocks. Destructive and native tests run in isolated homes or subprocesses.
6. **Owner decisions are never guessed.** A phase that needs one stops with `human_required=true` and `blocker_class=product_decision_missing` (or `admin_approval` for settings). It names the decision ID and the non-secret options.
7. **Repository qualification.** Issue and PR references are qualified with the repository, e.g. `treesitter-chunker#69`.

---

## Held / In Flight

These are excluded from every phase. Re-triage them if their state changes.

| Item | Status | Why held | Interaction with this roadmap |
|---|---|---|---|
| treesitter-chunker#508 | Hold | Windows manager admission rejection in an unmerged candidate; on hold until it recurs | If it recurs during ADMIT's Windows checks, pause ADMIT (Assumption 4) |
| treesitter-chunker#509 | Hold | Pre-constructor Windows probe `PermissionError` on 3.13; on hold until it recurs | Same as treesitter-chunker#508 |
| treesitter-chunker#389 | Closed (not reproducible), 2026-10-31 | No longer held | ADMIT and ADMITFIX still leave `_read_child` launcher reaping in `chunker/grammar/integrity.py` unchanged; it is outside their scope |
| treesitter-chunker#435 | Closed (fixed by treesitter-chunker#535, merged `d3d6b20e`) | No longer held: non-regular inputs (FIFOs, devices, sockets, directories) are rejected with a clear error | `chunker/core.py` single-writer chain: step 1 (treesitter-chunker#535) is done; FOLLOWUP SL-cr builds on current main |
| treesitter-chunker#534 | Merged 2026-10-31 (`afff90a6`) | No longer held: the 3.12 floor declarations and `.python-version` pin are on main | PY314 precondition met. CIFAST lanes that touch `release.yml` or `chunker/build/builder.py` build on current main and never edit Python-version fields |
| GROUP adapter on Windows/macOS | Deferred | Waiting for a consumer to need it | None |

## Unplaced

| Item | Why not placed |
|---|---|
| treesitter-chunker#265 | Low value, and unverifiable on the pinned stack: the pinned Svelte parser never emits `each_block`, so a fix cannot be exercised with a real parser (the repo forbids mocking that node). Revisit only when a supported parser emits `each_block`, or when the owner closes it as won't-fix. |

---

## Owner Decision Points

**Status (2026-10-31):** The owner answered D1–D5 in issue comments, and `docs/development/backlog-decisions-v4.md` records each answer with its comment URL. OWNERDEC is resolved: D1 = (c) both (a verified prewarm route plus a configurable download deadline with an actionable error); D2 = (b) a namespaced caller-label key, with `label` kept structural; D3 = (a) CR→LF for parsing with an exact raw byte-offset map; D4 = (a) implement, with goldens regenerated by tooling in the same PR. D5 = audit first, then flip: CIFAST SL-perm lands the least-privilege `permissions:` audit. After it merges, the maintainer authorizes switching the default workflow permissions to read-only via the GitHub API. SETTINGS settles who makes that call with the owner (EC-SETTINGS-3); no phase agent changes the setting. S-TXN is still conditional.

| ID | Item | Decision needed | Gate phase | Consumer |
|---|---|---|---|---|
| D1 | treesitter-chunker#357 | First-use download policy: (a) documented verified prewarm route, (b) a configurable download deadline propagated to language-pack, (c) both, or (d) docs-only / won't-fix | OWNERDEC | FOLLOWUP lane SL-dl |
| D2 | treesitter-chunker#453 | GraphML label interop: (a) rename the caller-label `attr.name` (a schema migration at the 6.0.0 boundary), (b) a namespaced/prefixed caller key, (c) document the NetworkX limitation only | OWNERDEC | FOLLOWUP lane SL-gml |
| D3 | treesitter-chunker#471 | CR-only Python policy: (a) translate CR→LF for parsing with a byte-offset map that keeps raw spans, (b) reject or warn on CR-only input with guidance, (c) document only | OWNERDEC | FOLLOWUP lane SL-cr |
| D4 | treesitter-chunker#516 | Whether to commission emitting outer call sites for callable-return expressions. This changes Boundary IR goldens and the call facts consumers see. Options: (a) implement, (b) defer | OWNERDEC | FOLLOWUP lane SL-call |
| D5 | treesitter-chunker#507 | Change the repository default Actions workflow permissions to read-only (a repo setting; needs the owner's admin action) | SETTINGS | Closes treesitter-chunker#507 |
| S-TXN | Theme C (conditional) | Only if TXNSPEC's design fails its three-round review: narrow scope further, accept a documented single-process limitation, or drop the transaction goal | TXNSPEC (stop) | TXN |

---

## Phase Dependency DAG

```
Roots (all start immediately, run in parallel subject to the 3-phase cap):

  ADMITPIN  (treesitter-chunker#362 freeze) ──► ADMIT (treesitter-chunker#362, treesitter-chunker#400) ──► ADMITFIX (treesitter-chunker#128, treesitter-chunker#120, treesitter-chunker#117) ──┐
                                                                                   │
  TXNSPEC   (theme C freeze) ──┐                                                   │
                               ├──► TXN (treesitter-chunker#370 → treesitter-chunker#323, treesitter-chunker#363) ───────────────────────┤
  HOTFIX    (treesitter-chunker#358, treesitter-chunker#162, treesitter-chunker#69 slice 17) ──┘                                         │
                                                                                   │
  REFS      (treesitter-chunker#274, treesitter-chunker#294, treesitter-chunker#278 | treesitter-chunker#289, treesitter-chunker#293) ───────────────────────────────────────┤
  GRAPHML   (treesitter-chunker#489 | treesitter-chunker#488) ──────────────┬──────────────────────────────────────────┤
  SMALLFIX  (treesitter-chunker#133, treesitter-chunker#134, treesitter-chunker#344 | treesitter-chunker#170 | treesitter-chunker#437 → treesitter-chunker#438) ──────────────────────────────┤
  CIFAST    (treesitter-chunker#517, treesitter-chunker#207, treesitter-chunker#143, treesitter-chunker#507 source, treesitter-chunker#481) ──┬──► PY314 (treesitter-chunker#502, type debt) ──┤
                                                    │      [treesitter-chunker#534 merged ✓]       ▼
                                                    └──► SETTINGS [owner: D5]   RECORDS (treesitter-chunker#361, treesitter-chunker#69 refresh)
  OWNERDEC  [owner: D1–D4 ✓] ──┐
                             ├──► FOLLOWUP (treesitter-chunker#357, treesitter-chunker#453, treesitter-chunker#471, treesitter-chunker#516 per decision)
  GRAPHML ···················┘    [GRAPHML gates lane SL-gml (treesitter-chunker#453) only]

  parallel after start: ADMITPIN, TXNSPEC, HOTFIX, REFS, GRAPHML, CIFAST, SMALLFIX, OWNERDEC
  parallel after ADMITPIN: ADMIT  (in parallel with TXN once TXNSPEC+HOTFIX close)
  parallel after CIFAST:   PY314, SETTINGS
  parallel after OWNERDEC: FOLLOWUP lanes SL-dl, SL-cr, SL-call; SL-gml also waits for GRAPHML
  RECORDS is terminal; it does not wait on the human-gated FOLLOWUP or SETTINGS.
```

Edges: ADMITPIN→ADMIT; ADMIT→ADMITFIX; TXNSPEC→TXN; HOTFIX→TXN; CIFAST→PY314; CIFAST→SETTINGS; OWNERDEC→FOLLOWUP; GRAPHML→FOLLOWUP (lane SL-gml only; see FOLLOWUP scope notes); ADMITFIX→RECORDS; TXN→RECORDS; REFS→RECORDS; GRAPHML→RECORDS; SMALLFIX→RECORDS; PY314→RECORDS.

Non-DAG gates: PY314 also needs treesitter-chunker#534 merged (external; met 2026-10-31). TXNSPEC's review submission needs the IF-0-HOTFIX-1 signature to be published (an interface-availability gate, not a phase edge; see TXNSPEC).

---

## Top Interface-Freeze Gates

1. **IF-0-ADMITPIN-1** — The production pin source. A keyword-only `trusted_artifacts: Mapping[str, Mapping[str, str]]` (language → `{"sha256": <64-hex>}`), copied at construction, accepted by `GrammarRegistry`, `GrammarValidator` and `GrammarManager` (`chunker/grammar_management/core.py`), by `ComprehensiveGrammarCLI` (`chunker/grammar_management/cli.py`) and by `LanguageRegistry` (`chunker/_internal/registry.py`). It is never forwarded whole. For each probe, the caller looks up `trusted_artifacts[language]` and passes a copy of that single record (`{"sha256": ...}`) as `provenance=` to `probe_native_grammar`, which reads `provenance.get("sha256")`. If the language has no entry, the caller fails closed and reports the artifact as untrusted/unsupported without loading it; it never passes the whole mapping, `None` or an empty record. It comes with exactly one CLI/config pin source: a named option or a config file under the cache dir, with the exact name fixed by the ADMITPIN plan. A missing pin means unsupported. There is no trust-all switch.
2. **IF-0-ADMITPIN-2** — The native-load inventory table in `docs/development/native-validation-contract.md`. Each load site gets a disposition: `integrated` / `caller-trusted primitive` / `retired`. The sites are:
   - `chunker/grammar_management/core.py` module-level `load_compiled_grammar` (defined at line 127, called from GrammarValidator at lines 229 and 260);
   - `chunker/grammar_management/cli.py` `ctypes.CDLL` sites: `_validate_compiled_grammar` (around line 2272) and the `build_grammar` post-build load check (around line 1552);
   - each `registry.py` CDLL site;
   - `chunker/grammar/validator.py`, including whether treesitter-chunker#400 repairs or retires the legacy validator;
   - `chunker/grammar/download.py`;
   - `chunker/grammar_manager.py`;
   - `chunker/grammar_management/testing.py` (the reload);
   - `GrammarMetadataExtractor.extract_from_dependencies` (the `ldd` path);
   - `chunker/_internal/language_pack.py` (around line 109, the `Language(module.language())` load of the pinned `tree_sitter_python`/`tree_sitter_javascript` packages), listed as a pack-managed supplier, out of scope for this contract.

   It also fixes the verdict-reuse key: content digest plus provenance, never path/mtime/size.
3. **IF-0-ADMIT-1** — A single admitted-health accessor that every CLI status/validate/list consumer reads. It is a `GrammarManager` method returning the existing legacy health mapping (`healthy`/`missing`/`corrupted`/`incompatible` with `validation_reason`), computed only from `probe_native_grammar` with IF-0-ADMITPIN-1 pins. ADMITFIX consumes it for treesitter-chunker#128 and treesitter-chunker#120.
4. **IF-0-HOTFIX-1** — Staged same-directory native publication for the legacy tools: write to a sibling temp name in the destination directory, admit it via `probe_native_grammar`, then `os.replace` it. Never truncate or overwrite an existing inode. Invalidate the instance cache after replacement. The treesitter-chunker#162 lane publishes the function signature on day 1. TXNSPEC adopts this shape for the restore path rather than redefining it, and its review waits for this signature (TXNSPEC interface-availability gate).
5. **IF-0-TXNSPEC-1** — `docs/development/cache-transaction-contract.md` plus the helper module's public signatures (module path fixed by the TXNSPEC plan, e.g. `chunker/grammar_management/_transactions.py`):
   - a locked fresh-read/merge/atomic-replace JSON record update, with no-follow containment under a named root;
   - deletion-time stale re-check with no-follow and junction safety;
   - a rollback point that stores a restorable artifact copy, and `restore`, reusing IF-0-HOTFIX-1 publication.

   It also fixes the lock-file location, the concurrency scope (single host), and an explicit disposition (addressed / scoped out, with rationale) for each of the seven treesitter-chunker#364 blocking gaps.
6. **IF-0-REFS-1** — The shared reference fixture suite: the layout `tests/fixtures/references/{python,javascript}/` and an oracle schema listing, per fixture, expected definitions, binding targets and expression uses with their scope. Both language lanes consume it.
7. **IF-0-CIFAST-1** — The single canonical lint/format path list and Ruff inclusion policy, including tracked `chunker/build/**`. It is used identically by `.github/workflows/ci.yml`, `.github/workflows/release.yml` and `CONTRIBUTING.md`. PY314's release-validation lane consumes it.
8. **IF-0-CIFAST-2** — The treesitter-chunker#507 settings proposal: the reviewed before/after Actions default-permission setting, the per-job `permissions:` audit result, and an explicit rollback that does not restore read/write. It lives in the merged treesitter-chunker#507 source PR body. SETTINGS consumes it.
9. **IF-0-OWNERDEC-1** — The D1 (treesitter-chunker#357) decision record in `docs/development/backlog-decisions-v4.md`.
10. **IF-0-OWNERDEC-2** — The D2 (treesitter-chunker#453) decision record, same file.
11. **IF-0-OWNERDEC-3** — The D3 (treesitter-chunker#471) decision record, same file.
12. **IF-0-OWNERDEC-4** — The D4 (treesitter-chunker#516) decision record, same file.

---

## Phases

### Phase 1 — Native admission pin source and load inventory (ADMITPIN)

**Objective**
Freeze where production callers and the CLI get approved native pins, and classify every native load site. This lets treesitter-chunker#362 integration fan out by file and ends the post-treesitter-chunker#519 state where real grammars always report nonhealthy.

**Exit criteria**
- [ ] EC-ADMITPIN-1 — `docs/development/native-validation-contract.md` contains the IF-0-ADMITPIN-2 inventory table. A grep for `ctypes.CDLL\|cdll.LoadLibrary\|Language(` under `chunker/` finds no site missing from the table.
- [ ] EC-ADMITPIN-2 — The IF-0-ADMITPIN-1 signature and the CLI/config pin source are written down with caller migration notes. The treesitter-chunker#400 disposition (repair or retire) is decided in the doc.
- [ ] EC-ADMITPIN-3 — Two independent reviewers approve the contract (VB-4) within three rounds. The approval is recorded in the plan/PR. No product code changes in this phase.

**Scope notes**
- Preamble / interface-only phase — single lane justified. The output is one reviewed contract-doc PR. Implementation fans out in ADMIT.
- Start from `probe_native_grammar` and the existing `trusted_artifacts` text in the contract doc. Extend that contract; do not write a parallel one.
- The doc is single-writer for `docs/development/native-validation-contract.md` until ADMIT starts.
- Do not touch `_read_child` or launcher reaping (out of scope; treesitter-chunker#389 closed as not reproducible).

**Non-goals**
- Implementing any integration. Changing the probe. Pack-managed artifact trust, which is a separate supplier boundary.

**Key files**
- `docs/development/native-validation-contract.md`
- `chunker/grammar/integrity.py` (read only)

**Depends on**
- (none)

**Produces**
- IF-0-ADMITPIN-1
- IF-0-ADMITPIN-2

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `canonical_spec_update`
- target surfaces: `docs/development/native-validation-contract.md`
- evidence paths: `plans/phase-plan-v4-ADMITPIN.md`, the contract PR review record
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`

---

### Phase 2 — Tier 1 independent correctness repairs (HOTFIX)

**Objective**
Land the Tier 1 repairs that need no new shared design: parallel-cache entry identity (treesitter-chunker#358) and safe replacement of a loaded legacy grammar (treesitter-chunker#162). Then land treesitter-chunker#69 slice 17, which waited only on treesitter-chunker#162.

**Exit criteria**
- [ ] EC-HOTFIX-1 — treesitter-chunker#358: real-process fixture tests warm core then request streaming, and the reverse order. Each equals uncached output for the requested mode. Entries from a different runtime/grammar pairing are rejected or invalidated. A caller-supplied cache directory confines all writes, proven with a temp home. Existing-entry migration guidance is documented.
- [ ] EC-HOTFIX-2 — treesitter-chunker#162: a subprocess regression installs, loads, updates and reloads a real compiled grammar without a crash (no exit 139). The next load parses the new revision. A named mutation that restores the in-place `shutil.copy2` makes the subprocess test fail.
- [ ] EC-HOTFIX-3 — treesitter-chunker#69 slice 17 lands as a test-only PR on top of treesitter-chunker#162, with its named mutation. If its command contract needs a healthy production result, it is re-placed after ADMIT and the reason recorded, rather than weakened.
- [ ] EC-HOTFIX-4 — Every PR meets VB-1 to VB-4. treesitter-chunker#162 includes the Windows preflight and hosted macOS/Windows evidence.

**Scope notes**
- Decompose into two lanes with disjoint files:
  - **SL-1 (cache)** owns `chunker/parallel.py`, `chunker/_internal/cache.py`, and `tests/test_parallel*.py` / `tests/test_cache.py`.
  - **SL-2 (replace)** owns `chunker/_internal/user_grammar_tools.py`, its tests, then the slice 17 test file.
- SL-2 publishes the IF-0-HOTFIX-1 signature on day 1, so TXNSPEC can reference it while SL-2 implements.
- SL-2 reuses `probe_native_grammar` with caller-supplied pins, as SAFELOAD already does for legacy tools. If production pins are needed, it takes them only from fixtures/callers and never anticipates ADMITPIN's CLI source.
- `CACHE_VERSION` bump plus key-schema change is a single PR in SL-1. Do not touch `chunker/boundary/cache.py`.
- Native subprocess tests count toward the heavy-run cap.

**Non-goals**
- The transaction protocol. Failed-update rollback (treesitter-chunker#363, in TXN). Registry suffix discovery (treesitter-chunker#117, in ADMITFIX).

**Key files**
- `chunker/parallel.py`
- `chunker/_internal/cache.py`
- `chunker/_internal/user_grammar_tools.py`
- `tests/test_parallel.py`
- `tests/test_cache.py`

**Depends on**
- (none)

**Produces**
- IF-0-HOTFIX-1

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: issue acceptance for treesitter-chunker#358, treesitter-chunker#162, treesitter-chunker#69
- evidence paths: `plans/phase-plan-v4-HOTFIX.md`, PR verification logs
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`

---

### Phase 3 — Cache and persistence transaction protocol (TXNSPEC)

**Objective**
Produce an independently accepted, narrowly scoped writer/pruner/rollback protocol for exactly three consumers: `validation_cache.json` (treesitter-chunker#370), core cleanup directory deletion (treesitter-chunker#323) and the installer rollback point (treesitter-chunker#363). It is the successor to the rejected treesitter-chunker#364 design.

**Exit criteria**
- [ ] EC-TXNSPEC-1 — `docs/development/cache-transaction-contract.md` gives the IF-0-TXNSPEC-1 signatures, lock location, single-host scope and supported platforms. It has a table giving each of the seven treesitter-chunker#364 blocking gaps an `addressed` or `scoped out` disposition with a rationale.
- [ ] EC-TXNSPEC-2 — For each consumer, the doc names the deterministic barrier test (two-writer, writer/pruner, outside-symlink sentinel, failed-update restore) that its TXN lane must implement, and the named mutation it must kill.
- [ ] EC-TXNSPEC-3 — Two independent reviewers approve within three rounds (VB-4). If not, the phase stops with `human_required=true`, `blocker_class=product_decision_missing` and decision **S-TXN**. It must not start a fourth round or proceed.

**Scope notes**
- Preamble / interface-only phase — single lane justified. The output is one contract-doc PR plus, optionally, signature-only stubs. No consumer is migrated here.
- Read the treesitter-chunker#364 history and the treesitter-chunker#323 comment that lists the gaps first. Narrowing scope is preferred to re-proposing the general design.
- Adopt IF-0-HOTFIX-1 for publication; do not define a second publish path.
- **Interface-availability gate:** TXNSPEC may be planned and drafted concurrently with HOTFIX, but its contract may not be submitted for review (EC-TXNSPEC-3) until HOTFIX SL-2 has published the IF-0-HOTFIX-1 signature. The contract cites that published signature by commit. If the signature changes before TXNSPEC is approved, the restore section is re-reviewed.
- Out of scope: `chunker/_internal/cache.py` (HOTFIX owns it) and `chunker/boundary/cache.py`.

**Non-goals**
- Implementing consumers. A general cache framework. Cross-host or network-filesystem guarantees.

**Key files**
- `docs/development/cache-transaction-contract.md`
- `chunker/grammar_management/core.py` (read only)

**Depends on**
- (none)

**Interface gate** (not a phase edge): the IF-0-HOTFIX-1 signature must be published by HOTFIX lane 2 before this contract is submitted for review. See scope notes.

**Produces**
- IF-0-TXNSPEC-1

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `canonical_spec_update`
- target surfaces: `docs/development/cache-transaction-contract.md`
- evidence paths: `plans/phase-plan-v4-TXNSPEC.md`, review record
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`; a design rejected at the cap is `product_decision_missing` (S-TXN)

---

### Phase 4 — Reference lookup accuracy (REFS)

**Objective**
Make Python and JavaScript definition, scope and reference lookup truthful against one shared real-parser fixture suite. Tier 1 items treesitter-chunker#274 and treesitter-chunker#289 land first in their language PRs.

**Exit criteria**
- [ ] EC-REFS-1 — The shared fixture suite (IF-0-REFS-1) lands first. It contains positive and negative cases for every issue in the phase.
- [ ] EC-REFS-2 — The Python PR covers treesitter-chunker#274 (module function/class definitions found, no cross-scope false positives), treesitter-chunker#294 (loop/with/except/lambda targets are bindings; default values are uses) and treesitter-chunker#278 (walrus in comprehensions binds in the containing function; defaults and lambdas/comprehensions in defaults evaluate in the enclosing scope). Each issue has its own named mutation that fails.
- [ ] EC-REFS-3 — The JavaScript PR covers treesitter-chunker#289 (a generator's dependency context omits body locals, including the exported generator form) and treesitter-chunker#293 (default-import, named function-expression, bare arrow param, default-param and array-pattern bindings are not uses; shorthand object references are found). Each has its own named mutation.
- [ ] EC-REFS-4 — Every PR meets VB-1 to VB-4. If an intentional Boundary IR change is needed, goldens are regenerated on the locked stack; never by hand.

**Scope notes**
- Decompose into three lanes:
  - **SL-fix (fixtures)** owns `tests/fixtures/references/**` and the oracle helper, and lands first as a small PR.
  - **SL-py** owns `chunker/context/languages/python.py` plus Python tests: one PR, ordered treesitter-chunker#274 → treesitter-chunker#294 → treesitter-chunker#278 as separate commits.
  - **SL-js** owns `chunker/context/languages/javascript.py` plus JS tests: one PR, treesitter-chunker#289 → treesitter-chunker#293.
- SL-py and SL-js are disjoint and run in parallel once SL-fix publishes IF-0-REFS-1. The schema can be published on day 1, before the fixtures merge.
- One PR per language follows the triage. Reviewers accept per issue within the PR.
- Shared files (the base classes both language modules import: `chunker/context/scope_analyzer.py`, `chunker/context/symbol_resolver.py`, `chunker/context/extractor.py` and `chunker/context/filter.py`) are single-writer: if both language lanes need a base change, SL-py owns it and SL-js rebases.

**Non-goals**
- Svelte (treesitter-chunker#265). Call graph emission (treesitter-chunker#516). New languages.

**Key files**
- `chunker/context/languages/python.py`
- `chunker/context/languages/javascript.py`
- `tests/fixtures/references/`

**Depends on**
- (none)

**Produces**
- IF-0-REFS-1

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: issue acceptance for treesitter-chunker#274, treesitter-chunker#278, treesitter-chunker#289, treesitter-chunker#293, treesitter-chunker#294
- evidence paths: `plans/phase-plan-v4-REFS.md`, PR verification logs
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`

---

### Phase 5 — GraphML exporter fidelity (GRAPHML)

**Objective**
Preserve whitespace-containing caller IDs in the package GraphML exporter (treesitter-chunker#489, Tier 1), and stop compact direct/yEd file output from doubling CRLF leaf breaks on Windows (treesitter-chunker#488, Tier 3).

**Exit criteria**
- [ ] EC-GRAPHML-1 — treesitter-chunker#489: real parsed chunks with TAB/LF/CR in caller IDs round-trip with distinct IDs and directed endpoints through package exporter streams and UTF-8 files on actual Python 3.12. A named mutation restoring the minidom reparse fails.
- [ ] EC-GRAPHML-2 — treesitter-chunker#488: the compact file and string decoded-text policy is documented. Real fixtures with CR, LF and CRLF leaves plus non-ASCII data, across plain, yEd and delegated routes, pass on **native Windows** (Windows preflight and hosted Windows job). There is no blanket whitespace normalization.
- [ ] EC-GRAPHML-3 — Every PR meets VB-1 to VB-4.

**Scope notes**
- Decompose into two lanes with disjoint files:
  - **SL-pkg** owns `chunker/export/formats/graph.py` (treesitter-chunker#489).
  - **SL-direct** owns `chunker/export/graphml_exporter.py` and `chunker/export/graphml_yed_exporter.py` (treesitter-chunker#488).
- `chunker/export/graph_exporter_base.py` is single-writer, owned by SL-direct if needed.
- The docs must distinguish the two exporter APIs. SL-pkg owns that doc paragraph.
- SL-direct needs a Windows host run. Schedule it so it does not overlap another heavy run.

**Non-goals**
- Label-key interop (treesitter-chunker#453); it is gated on D2 and lives in FOLLOWUP.

**Key files**
- `chunker/export/formats/graph.py`
- `chunker/export/graphml_exporter.py`
- `chunker/export/graphml_yed_exporter.py`
- `tests/test_graphml_exporter.py`

**Depends on**
- (none)

**Produces**
- (none)

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: issue acceptance for treesitter-chunker#488, treesitter-chunker#489
- evidence paths: `plans/phase-plan-v4-GRAPHML.md`, PR logs, Windows preflight log
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`

---

### Phase 6 — CI and infrastructure hygiene (CIFAST)

**Objective**
Make CI lint cover tracked `chunker/build` sources (treesitter-chunker#517). Stop load-sensitive deadline flakes from producing false failures (treesitter-chunker#207 `nm`, treesitter-chunker#143 parse smoke). Prepare the treesitter-chunker#507 workflow-permission and dependency triage source changes. Land the repo-side scratch guidance for treesitter-chunker#481.

**Exit criteria**
- [ ] EC-CIFAST-1 — treesitter-chunker#517: a discriminator proves a deliberate violation in a tracked `chunker/build/*.py` file fails the CI Ruff command. The newly exposed findings (at least the `builder.py` F401) are fixed without baseline absorption or global ignores. `ci.yml`, `release.yml` and CONTRIBUTING use the IF-0-CIFAST-1 path list.
- [ ] EC-CIFAST-2 — treesitter-chunker#207 and treesitter-chunker#143: under a reproducible CPU-load harness, symbol analysis and the language smoke distinguish a deadline expiry from unsupported or failed-to-load. Normal runs keep their assertions. No assertion is weakened and no blanket timeout increase hides a real failure.
- [ ] EC-CIFAST-3 — treesitter-chunker#507 source part: every workflow and job has explicit least-privilege `permissions:`. Applicable dependency advisories are fixed with the smallest compatible change, and the rest are recorded as inapplicable or deferred with reasons. The settings proposal (IF-0-CIFAST-2) is in the PR body. **No repository-setting change is made by an agent.**
- [ ] EC-CIFAST-4 — treesitter-chunker#481 repo part: CONTRIBUTING states the disk-`TMPDIR`/`tempfile` rule for verification scratch. A repo test or check proves that no tracked script, tool or test hardcodes a literal `/tmp` scratch root. The issue stays open for agent-harness#1220 and dotfiles#68.
- [ ] EC-CIFAST-5 — Every PR meets VB-1 to VB-4.

**Scope notes**
- Decompose into four lanes:
  - **SL-lint** (treesitter-chunker#517) owns `pyproject.toml` `[tool.ruff]`, `chunker/build/**` fixes, and the lint lines of `.github/workflows/ci.yml` and `release.yml`.
  - **SL-deadline** (treesitter-chunker#207 then treesitter-chunker#143) owns `chunker/languages/compatibility/grammar_analyzer.py` `GrammarAnalyzer.analyze_grammar_symbols` only, `tests/language_smoke.py` and `tests/test_language_smoke.py`.
  - **SL-perm** (treesitter-chunker#507) owns the `permissions:` blocks of all workflows, `ide/vscode/treesitter-chunker/package-lock.json`, `.ai-dev-kit/dev-tools/mcp/_templates/python/requirements.txt`, and `uv.lock` changes limited to the advisory fixes.
  - **SL-scratch** (treesitter-chunker#481) owns its CONTRIBUTING paragraph and its check.
- Single-writer files:
  - `.github/workflows/ci.yml`: SL-lint merges first, then SL-perm rebases.
  - `.github/workflows/release.yml`: treesitter-chunker#534 (`UV_PYTHON` on verify-installed-wheel) → SL-lint → SL-perm.
  - `chunker/build/builder.py`: treesitter-chunker#534 (`Requires-Python` in the wheel and ZIP fallback paths) → SL-lint (the F401 fix for treesitter-chunker#517).
  - `CONTRIBUTING.md`: one PR at a time, in the order SL-lint → SL-scratch.
  - treesitter-chunker#534 has merged (`afff90a6`); SL-lint and SL-perm build on current main and never edit Python-version fields.
- `grammar_analyzer.py` is shared with ADMIT lane SL-ins (`extract_from_dependencies`). Edits stay in disjoint functions and merge one at a time.
- The load harness for SL-deadline is itself a heavy run and counts toward the two-run cap.
- treesitter-chunker#357 is not in this phase. It is gated on D1.

**Non-goals**
- Python 3.14 and type debt (PY314). The settings change (SETTINGS). Production parse-deadline semantics beyond truthful cause reporting.

**Key files**
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `pyproject.toml`
- `chunker/build/builder.py`
- `chunker/languages/compatibility/grammar_analyzer.py`
- `tests/language_smoke.py`
- `tests/test_language_smoke.py`
- `CONTRIBUTING.md`

**Depends on**
- (none)

**Produces**
- IF-0-CIFAST-1
- IF-0-CIFAST-2

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: issue acceptance for treesitter-chunker#517, treesitter-chunker#207, treesitter-chunker#143, treesitter-chunker#507 (source), treesitter-chunker#481 (repo part)
- evidence paths: `plans/phase-plan-v4-CIFAST.md`, PR logs
- redaction posture: `metadata_only` (confidential treesitter-chunker#507 audit evidence is never committed or quoted)
- missing or malformed evidence: `blocker_class=contract_bug`

---

### Phase 7 — Selection metadata, version semantics and Go hints (SMALLFIX)

**Objective**
Repair independent Tier 4 selection and version defects that need no admission or transaction design: treesitter-chunker#133, treesitter-chunker#134, treesitter-chunker#344, treesitter-chunker#170 (theme F), and Go build-constraint minimums treesitter-chunker#437 then treesitter-chunker#438 (theme G).

**Exit criteria**
- [ ] EC-SMALLFIX-1 — treesitter-chunker#133: a successful caller sample counts as evidence and does not by itself yield `DEGRADED`. treesitter-chunker#134: USER and PACKAGE artifacts carry their own version and metadata, and only true same-version conflicts group. treesitter-chunker#344: global constraints are enforced or rejected explicitly. Each has a real local-artifact fixture and a named mutation.
- [ ] EC-SMALLFIX-2 — treesitter-chunker#170: ES versions compare in documented order, or uncomparable values are rejected. Out-of-range ES versions fail min/max checks in direct comparison and in grammar selection.
- [ ] EC-SMALLFIX-3 — treesitter-chunker#437: legacy comma conjunctions keep the highest positive release tag in either order (killing the last-tag mutation). Then treesitter-chunker#438: `&&`/`||`/`!` expressions report truthful minimums or an explicit unknown, with module precedence preserved. treesitter-chunker#438 has its own detailed plan.
- [ ] EC-SMALLFIX-4 — Every PR meets VB-1 to VB-4.

**Scope notes**
- Decompose into three lanes with disjoint files:
  - **SL-sel** owns `chunker/grammar_management/compatibility.py` as serial PRs treesitter-chunker#133 → treesitter-chunker#134 → treesitter-chunker#344.
  - **SL-ver** owns `chunker/languages/compatibility/schema.py` (treesitter-chunker#170).
  - **SL-go** owns `chunker/languages/version_detection/go_detector.py` and `tests/test_go_version_hints_contract.py` (treesitter-chunker#437 → treesitter-chunker#438).
- treesitter-chunker#133 should be fixed in `compatibility.py`. If it needs `grammar_management/core.py` (the `_validate_standard` warning), that edit joins the core.py merge order (see Execution Notes) and must not touch GrammarValidator's native-load or cache regions.
- Database migration for duplicate/NULL rows, if treesitter-chunker#134 needs it, is documented and tested against a reopened legacy database.

**Non-goals**
- Native admission changes. A full Go constraint evaluator.

**Key files**
- `chunker/grammar_management/compatibility.py`
- `chunker/languages/compatibility/schema.py`
- `chunker/languages/version_detection/go_detector.py`

**Depends on**
- (none)

**Produces**
- (none)

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: issue acceptance for treesitter-chunker#133, treesitter-chunker#134, treesitter-chunker#170, treesitter-chunker#344, treesitter-chunker#437, treesitter-chunker#438
- evidence paths: `plans/phase-plan-v4-SMALLFIX.md`, PR logs
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`

---

### Phase 8 — Integrate remaining native admission paths (ADMIT)

**Objective**
Route every native discovery, validation and health path through `probe_native_grammar` with IF-0-ADMITPIN-1 pins, or retire or document it per IF-0-ADMITPIN-2 (treesitter-chunker#362, including treesitter-chunker#400). After this phase, real pinned grammars report healthy again from the CLI.

**Exit criteria**
- [ ] EC-ADMIT-1 — With approved pins from the IF-0-ADMITPIN-1 CLI source, `grammar info <lang>` returns 0 for a real compiled fixture grammar. Without pins, it returns 1 with an "untrusted" cause. Both are covered by real-artifact tests on Linux, macOS and Windows.
- [ ] EC-ADMIT-2 — Every inventory site is integrated, retired, or documented as caller-trusted, matching IF-0-ADMITPIN-2. A named bypass mutation per integrated site (restore the direct `ctypes.CDLL`) fails a test.
- [ ] EC-ADMIT-3 — Verdict reuse rejects same-stat byte replacement and provenance change (named cache mutation). Dependency inspection of unapproved libraries is secured or retired.
- [ ] EC-ADMIT-4 — treesitter-chunker#400: the legacy validator is either constructible through the admission contract (and reports unsupported timeout capability explicitly) or retired with documented migration.
- [ ] EC-ADMIT-5 — Every PR meets VB-1 to VB-4, including the Windows preflight. If treesitter-chunker#508 or treesitter-chunker#509 recurs, the phase pauses (Assumption 4).

**Scope notes**
- Decompose into four lanes by file:
  - **SL-reg** owns `chunker/_internal/registry.py` (discovery and fallback loads).
  - **SL-core** owns the `chunker/grammar_management/core.py` `load_compiled_grammar` / GrammarValidator native-load region and verdict reuse, both `chunker/grammar_management/cli.py` CDLL sites (the `build_grammar` post-build load check and the admission step inside `_validate_compiled_grammar`), and publishes IF-0-ADMIT-1.
  - **SL-legacy** owns `chunker/grammar/validator.py` (treesitter-chunker#400), `chunker/grammar/download.py` and `chunker/grammar_manager.py`.
  - **SL-ins** owns `chunker/grammar_management/testing.py` and `GrammarMetadataExtractor.extract_from_dependencies` in `grammar_analyzer.py`.
- SL-core publishes the IF-0-ADMIT-1 accessor signature on day 1.
- `_validate_compiled_grammar` is split so EC-ADMIT-2 can close in this phase. SL-core replaces its direct `ctypes.CDLL` with `probe_native_grammar` (a pinned admission, failing closed without a pin) and adds the bypass mutation, while keeping today's command output and exit codes as they are. The observable `validate` behaviour (verifying the requested language and giving an actionable cause, treesitter-chunker#128) stays with ADMITFIX SL-cli in its own PR.
- `grammar_analyzer.py` is shared with CIFAST SL-deadline (disjoint functions) and merges one at a time. `core.py` follows the cross-phase merge order in Execution Notes.
- Do not change `chunker/grammar/integrity.py` lifecycle code (out of scope; treesitter-chunker#389 closed as not reproducible).
- Document caller migration for changed health/exit codes in the changelog.

**Non-goals**
- treesitter-chunker#128, treesitter-chunker#120, treesitter-chunker#117 (ADMITFIX). Pack-managed supplier trust.

**Key files**
- `chunker/_internal/registry.py`
- `chunker/grammar_management/core.py`
- `chunker/grammar_management/cli.py`
- `chunker/grammar/validator.py`
- `chunker/grammar/download.py`
- `chunker/grammar_manager.py`
- `chunker/grammar_management/testing.py`
- `chunker/languages/compatibility/grammar_analyzer.py`

**Depends on**
- ADMITPIN

**Produces**
- IF-0-ADMIT-1

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `canonical_spec_update`
- target surfaces: `docs/development/native-validation-contract.md` (inventory status column), `CHANGELOG.md`
- evidence paths: `plans/phase-plan-v4-ADMIT.md`, PR logs, platform runs
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`

---

### Phase 9 — Admission-dependent command repairs (ADMITFIX)

**Objective**
On top of the integrated admission, make `validate` verify the requested language (treesitter-chunker#128), make `list` rows agree with the validated summary (treesitter-chunker#120), and make `GrammarRegistry` discover macOS and Windows native suffixes (treesitter-chunker#117).

**Exit criteria**
- [ ] EC-ADMITFIX-1 — treesitter-chunker#128: a wrong library (for example the language-pack native lib relabelled `libpython.so`) makes `validate python` exit nonzero with an actionable cause. A correct pinned fixture passes.
- [ ] EC-ADMITFIX-2 — treesitter-chunker#120: for an invalid local candidate, `grammar list` shows no `healthy` row, and the summary and rows agree. Both read IF-0-ADMIT-1.
- [ ] EC-ADMITFIX-3 — treesitter-chunker#117: `GrammarRegistry` finds `.dylib`/`.dll` candidates on their platforms, or enforces a documented platform contract. This is proven on native macOS and Windows hosts (hosted jobs plus the Windows preflight).
- [ ] EC-ADMITFIX-4 — Every PR meets VB-1 to VB-4.

**Scope notes**
- Decompose into two lanes:
  - **SL-cli** owns `chunker/grammar_management/cli.py` as serial PRs treesitter-chunker#128 → treesitter-chunker#120 (display).
  - **SL-regsfx** owns the `chunker/grammar_management/core.py` GrammarRegistry `_discover_in_directory` region (treesitter-chunker#117).
- If treesitter-chunker#120 also needs `GrammarManager.get_grammar_metadata` in core.py, that edit is a separate commit in SL-cli's PR. It follows the core.py merge order and does not overlap SL-regsfx's region.

**Non-goals**
- New admission behavior beyond consuming IF-0-ADMIT-1.

**Key files**
- `chunker/grammar_management/cli.py`
- `chunker/grammar_management/core.py`

**Depends on**
- ADMIT

**Produces**
- (none)

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: issue acceptance for treesitter-chunker#117, treesitter-chunker#120, treesitter-chunker#128
- evidence paths: `plans/phase-plan-v4-ADMITFIX.md`, PR logs, platform runs
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`

---

### Phase 10 — Transactional cache writers, cleanup and rollback (TXN)

**Objective**
Implement IF-0-TXNSPEC-1 for its three consumers: validation-cache merge and containment (treesitter-chunker#370), then concurrency-safe cleanup (treesitter-chunker#323), and a failed update that actually restores the previous installation (treesitter-chunker#363).

**Exit criteria**
- [ ] EC-TXN-1 — treesitter-chunker#370: two real `GrammarValidator` instances writing in either order both keep their records on disk. A symlinked `validation_cache.json` pointing to an outside sentinel leaves the sentinel unchanged. Stale-snapshot and symlink-follow mutations fail. Expiration semantics are unchanged.
- [ ] EC-TXN-2 — treesitter-chunker#323: deterministic writer/cleanup interleaving cannot delete a newly published file, and `bytes_freed` is truthful. Symlink and junction boundaries hold on Linux, macOS and Windows.
- [ ] EC-TXN-3 — treesitter-chunker#363: a real local installation followed by a deterministic failed update restores the previous artifact and metadata, and the next parse uses the previous revision. A named omit-restore mutation fails. Handle release is shown on Windows.
- [ ] EC-TXN-4 — Every PR meets VB-1 to VB-4.

**Scope notes**
- Decompose into two lanes:
  - **SL-cache** owns the new transaction helper module, the `chunker/grammar_management/core.py` GrammarValidator cache region (`_load_validation_cache`/`_cache_validation_result`) and the `GrammarManager.cleanup_cache`/`_cleanup_directory` region, as serial PRs treesitter-chunker#370 → treesitter-chunker#323. The treesitter-chunker#323 PR also owns the GrammarInstaller download/build/cache-entry functions (`_download_grammar`, `_build_grammar` and the `_build_with_*` helpers, `_get_commit_hash`, `_cleanup_cache`) and the staging routing in `install_grammar` (TXNSPEC roadmap runner decision D-b, 2026-10-31).
  - **SL-rollback** owns the core.py `GrammarInstaller` installation region for treesitter-chunker#363: the commit section of `install_grammar`, `_create_rollback_point`, `_perform_rollback`, `_install_grammar_file`, `_save_installation_info`, `_load_installation_info`, `_remove_installation_info`, and `GrammarInstaller.remove_grammar`/`GrammarManager.remove_grammar` (decision D-b). It consumes the helper and IF-0-HOTFIX-1. It rebases on treesitter-chunker#323, and it merges only after ADMIT SL-core's `GrammarInstaller(trusted_artifacts=)` change is on main (TXNSPEC roadmap runner decision D-a).
- SL-cache lands the helper module in its first PR. SL-rollback develops against the frozen signatures and rebases.
- In treesitter-chunker#401's test, use exact-key or `any(...)` lookup (see the treesitter-chunker#370 comment) so record preservation is not pinned out.
- `core.py` follows the cross-phase merge order.

**Non-goals**
- The AST cache (HOTFIX). Native admission (ADMIT).

**Key files**
- `chunker/grammar_management/core.py`
- `chunker/grammar_management/_transactions.py`
- `tests/test_core_grammar_cache_cleanup.py`

**Depends on**
- TXNSPEC
- HOTFIX

**Produces**
- (none)

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: issue acceptance for treesitter-chunker#323, treesitter-chunker#363, treesitter-chunker#370
- evidence paths: `plans/phase-plan-v4-TXN.md`, PR logs, platform runs
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`

---

### Phase 11 — Python 3.14 locked environment and type/release-validation debt (PY314)

**Objective**
Make the full locked development environment install and pass on Python 3.14 while keeping 3.12 as the minimum (treesitter-chunker#502). Reduce the 1,356-line mypy baseline and align release validation with CI. The type and release-validation debt has **no issue yet; an issue must be opened** before this lane is planned. This roadmap did not open one.

**Exit criteria**
- [ ] EC-PY314-1 — Entry check: treesitter-chunker#534 is merged on main. If it is not, the phase stops as blocked and names treesitter-chunker#534. It does not proceed.
- [ ] EC-PY314-2 — treesitter-chunker#502: `uv sync --locked --all-extras --python 3.14` succeeds on the selected Linux/macOS/Windows hosts, with dependency changes and host prerequisites explicit. Full suite, lint, type, docs and clean wheel/sdist checks pass on 3.14. 3.12 minimum coverage remains, and CI is no larger than before.
- [ ] EC-PY314-3 — Type debt (issue to open): the baseline is first re-measured on unchanged main under 3.12 and 3.14 to separate interpreter-dependent output. Then the baseline shrinks by cleared debt only, with no `--update` absorption of new errors. `release.yml` lint, format and type commands match IF-0-CIFAST-1 and the CI governed checks.
- [ ] EC-PY314-4 — Every PR meets VB-1 to VB-4. No parser or runtime pin changes. No publication.

**Scope notes**
- Decompose into two lanes:
  - **SL-env** (treesitter-chunker#502) owns `uv.lock`, the dependency sections of `pyproject.toml`, `.python-version`, and the final CI/release matrix switch in `.github/workflows/ci.yml`, `test.yml` and `release.yml`. It must account for treesitter-chunker#534's 3.12 pin: 3.14 commands select the interpreter explicitly (`--python 3.14` or `UV_PYTHON`) rather than relying on `.python-version`, the `UV_PYTHON` on release.yml's verify-installed-wheel job is changed only deliberately, and any change to `.python-version` keeps 3.12 as the default development interpreter unless the plan records why not.
  - **SL-types** (issue to open) owns `docs/development/mypy-baseline.txt`, `scripts/mypy_gate.py`, the type-only fixes in `chunker/**`, and the `release.yml` lint/type validation lines.
- Ordering: SL-types' re-measurement runs before any SL-env lock change lands. The SL-types `release.yml` edit merges before SL-env's matrix switch. Type fixes are partitioned by top-level package, one package per PR, to stay reviewable.
- Installing a 3.14 environment counts toward the heavy-run cap. Never build two interpreters' full environments at once.
- `specs/active/release-process-spec.md` is updated by SL-env only, after treesitter-chunker#534's edits are in.

**Non-goals**
- A Python floor bump. Fleet-wide adoption claims. Package publication.

**Key files**
- `uv.lock`
- `pyproject.toml`
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `.python-version`
- `docs/development/mypy-baseline.txt`
- `scripts/mypy_gate.py`
- `specs/active/release-process-spec.md`

**Depends on**
- CIFAST

**Produces**
- (none)

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `canonical_spec_update`
- target surfaces: `specs/active/release-process-spec.md`, `CONTRIBUTING.md`
- evidence paths: `plans/phase-plan-v4-PY314.md`, platform install logs
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`; treesitter-chunker#534 not merged is reported as an external precondition

---

### Phase 12 — Owner product decisions (OWNERDEC)

**Objective**
Get the owner's recorded decisions D1 to D4 for treesitter-chunker#357, treesitter-chunker#453, treesitter-chunker#471 and treesitter-chunker#516, so FOLLOWUP implements chosen policy instead of guessing.

**Exit criteria**
- [ ] EC-OWNERDEC-1 — `docs/development/backlog-decisions-v4.md` records, for each of D1 to D4: the chosen option from the Owner Decision Points table, the owner's attribution (the owner's issue comment URL or the owner's commit), and the date. A choice of "defer/decline" is a valid decision.
- [ ] EC-OWNERDEC-2 — No decision is inferred by an agent. If any record is missing owner attribution, the phase closes as `human_required` with `blocker_class=product_decision_missing`, naming the missing decision IDs.

**Scope notes**
- Preamble / interface-only phase — single lane justified. It is a human-gated decision record with no product code.
- The executor may prepare the decision file skeleton with options and evidence links. It only records the owner's answers; it never fills them in itself.
- This phase is a root. The owner can answer at any time, and answering early unblocks FOLLOWUP sooner.

**Non-goals**
- Implementing any decided option. Deciding D5 (SETTINGS) or S-TXN.

**Key files**
- `docs/development/backlog-decisions-v4.md`

**Depends on**
- (none)

**Produces**
- IF-0-OWNERDEC-1
- IF-0-OWNERDEC-2
- IF-0-OWNERDEC-3
- IF-0-OWNERDEC-4

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `human_source_judgment_required`
- target surfaces: `docs/development/backlog-decisions-v4.md`
- evidence paths: owner issue comments on treesitter-chunker#357, treesitter-chunker#453, treesitter-chunker#471, treesitter-chunker#516
- redaction posture: `metadata_only`
- human input required: owner choice for each of D1–D4 (`blocker_class=product_decision_missing`)

---

### Phase 13 — Repository Actions default permissions (SETTINGS)

**Objective**
Have the owner apply (or decline) decision D5: the read-only default workflow permission prepared in IF-0-CIFAST-2. Then verify the setting and close treesitter-chunker#507.

**Exit criteria**
- [ ] EC-SETTINGS-1 — `gh api repos/Consiliency/treesitter-chunker/actions/permissions/workflow` shows `default_workflow_permissions: read`. Alternatively, the owner's recorded decline is linked on treesitter-chunker#507.
- [ ] EC-SETTINGS-2 — After the change, the release, docs and package workflows still succeed on a non-publishing dry run or their next scheduled run, or the owner-approved rollback in IF-0-CIFAST-2 is followed. Read/write is never restored automatically.
- [ ] EC-SETTINGS-3 — No agent changes repository settings. Until the owner acts, the phase is `human_required` with `blocker_class=admin_approval`.

**Scope notes**
- Preamble / interface-only phase — single lane justified. The only repository write is the owner's settings action, followed by agent read-only verification.

**Non-goals**
- Workflow source edits (done in CIFAST). Credential or secret actions.

**Key files**
- `.github/workflows/release.yml` (read only)

**Depends on**
- CIFAST

**Produces**
- (none)

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `human_source_judgment_required`
- target surfaces: repository settings (not a file)
- evidence paths: `plans/phase-plan-v4-SETTINGS.md`, settings API read-back
- redaction posture: `metadata_only`
- human input required: owner applies or declines D5 (`blocker_class=admin_approval`)

---

### Phase 14 — Decision-gated follow-ups (FOLLOWUP)

**Objective**
Implement or record the owner-chosen dispositions for first-use download (treesitter-chunker#357), GraphML label interop (treesitter-chunker#453), CR-only Python (treesitter-chunker#471) and outer call sites (treesitter-chunker#516).

**Exit criteria**
- [ ] EC-FOLLOWUP-1 — Each lane implements exactly the option recorded in its IF-0-OWNERDEC record. A "defer/decline" option produces only a docs/changelog note and the issue disposition, with no code.
- [ ] EC-FOLLOWUP-2 — treesitter-chunker#357, if implemented: a controlled slow-download fixture (local server with throttled bytes, no public network) proves the chosen recovery and SHA-256 verification against the pinned manifest. The download deadline stays distinct from the parse deadline.
- [ ] EC-FOLLOWUP-3 — treesitter-chunker#453 and treesitter-chunker#471, if implemented: real parsed fixtures with downstream NetworkX import (treesitter-chunker#453), or independent raw-byte and row oracles across regular and streaming paths (treesitter-chunker#471), each with a discriminating mutation.
- [ ] EC-FOLLOWUP-4 — treesitter-chunker#516, if implemented: outer call sites carry truthful raw callee bytes, span, owner and distinct identity. Complex targets stay unresolved. Goldens are regenerated on the locked stack and the regeneration is idempotent.
- [ ] EC-FOLLOWUP-5 — Every PR meets VB-1 to VB-4.

**Scope notes**
- Decompose into four lanes, each starting with its own decision record:
  - **SL-dl** owns the language-pack acquisition wrapper in `chunker/_internal/registry.py` or `chunker/_internal/factory.py`, and the docs.
  - **SL-gml** owns `chunker/export/graphml_exporter.py` and the yEd exporter (after GRAPHML).
  - **SL-cr** owns the decode/parse path for CR-only input in `chunker/core.py` and the streaming entry. It builds on the treesitter-chunker#435 fix (treesitter-chunker#535, merged), which edited the same `chunker/core.py` read path.
  - **SL-call** owns Python call emission in `chunker/metadata/languages/python.py` (`extract_calls`), `chunker/metadata/extractor.py` and `chunker/symbol_graph.py`, plus golden regeneration.
- Only SL-gml depends on GRAPHML (it edits the same exporter files as GRAPHML SL-direct). SL-dl, SL-cr and SL-call start as soon as their OWNERDEC record exists and are not held for GRAPHML.
- Lanes are disjoint, with one exception: SL-dl's `registry.py` was edited in ADMIT. If ADMIT has not merged, SL-dl uses `factory.py` only, or waits.
- SL-cr and SL-call can both change Boundary IR goldens, so golden regeneration is single-writer: SL-call regenerates last and SL-cr rebases first.

**Non-goals**
- Options the owner did not choose.

**Key files**
- `chunker/_internal/factory.py`
- `chunker/export/graphml_exporter.py`
- `chunker/core.py`
- `chunker/metadata/extractor.py`
- `chunker/metadata/languages/python.py`
- `chunker/symbol_graph.py`
- `docs/development/backlog-decisions-v4.md`

**Depends on**
- OWNERDEC
- GRAPHML

The GRAPHML edge gates only the treesitter-chunker#453 GraphML lane. The download, carriage-return and call-site lanes are not held for it (see scope notes).

**Produces**
- (none)

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: issue acceptance for treesitter-chunker#357, treesitter-chunker#453, treesitter-chunker#471, treesitter-chunker#516
- evidence paths: `plans/phase-plan-v4-FOLLOWUP.md`, PR logs
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`

---

### Phase 15 — Records reconciliation (RECORDS)

**Objective**
Bring the records trackers up to date after the automated phases: refresh the treesitter-chunker#69 tracker body to current slice status, and update the treesitter-chunker#361 crosswalk for v3/v4 planning artifacts.

**Exit criteria**
- [ ] EC-RECORDS-1 — treesitter-chunker#69's body reflects current state:
  - slice 17's outcome (from HOTFIX);
  - slice 15, whose listed blockers treesitter-chunker#180 and treesitter-chunker#182–treesitter-chunker#185 are all closed, either confirmed runnable and scheduled as a new slice or marked done with evidence;
  - slice 16 retired;
  - no blanket percentage language.
- [ ] EC-RECORDS-2 — The treesitter-chunker#361 crosswalk marks the v3 phases as superseded by v4 where applicable, and records `plans/manifest.json` entries through the supported metadata path. Runner ledgers and checkpoints are not edited.
- [ ] EC-RECORDS-3 — Any newly found residual is filed as its own issue, not implemented here.

**Scope notes**
- Decompose into two lanes:
  - **SL-cov** owns the treesitter-chunker#69 tracker body and `plans/detailed-coverage-contract-slices-20261001.md`.
  - **SL-xwalk** owns `docs/development/backlog-inventory-20261006.md` (or a dated successor), the `plans/manifest.json` metadata entries, and the `docs/development/traceability-matrix.md` corrections.
- This phase does not wait for FOLLOWUP or SETTINGS. Pending owner decisions are recorded as pending.

**Non-goals**
- New coverage slices beyond confirming slice 15's status. Code changes.

**Key files**
- `plans/detailed-coverage-contract-slices-20261001.md`
- `plans/manifest.json`
- `docs/development/traceability-matrix.md`
- `docs/development/backlog-inventory-20261006.md`

**Depends on**
- ADMITFIX
- TXN
- REFS
- GRAPHML
- SMALLFIX
- PY314

**Produces**
- (none)

**Spec closeout policy**
- schema: `spec_delta_closeout.v1`
- decision: `canonical_spec_update`
- target surfaces: `plans/manifest.json`, `docs/development/traceability-matrix.md`, the records crosswalk
- evidence paths: `plans/phase-plan-v4-RECORDS.md`
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`

---

## Execution Notes

- **Next phase:** ADMITPIN — Native admission pin source and load inventory. **Next command:** `/claude-plan-phase ADMITPIN`.
- **Planning order (priority, within the three-phase cap):**
  1. ADMITPIN, HOTFIX, TXNSPEC (Tier 1 and the two freezes);
  2. REFS and GRAPHML (they carry Tier 1 items treesitter-chunker#274, treesitter-chunker#289 and treesitter-chunker#489);
  3. CIFAST;
  4. SMALLFIX;
  5. ADMIT as soon as ADMITPIN closes;
  6. TXN once TXNSPEC and HOTFIX close.

  OWNERDEC can be planned at any time. The owner can answer D1 to D4 immediately, independent of the loop.
- **Concurrently plannable:** all eight roots (ADMITPIN, HOTFIX, TXNSPEC, REFS, GRAPHML, CIFAST, SMALLFIX, OWNERDEC). PY314 and SETTINGS run concurrently after CIFAST. ADMIT and TXN have no DAG path between them and may run concurrently, subject to the core.py merge order.
- **Execution:** `/claude-execute-phase <alias>` after each plan is approved. At most three phases execute at once (resource caps).
- **Loop stop points:**
  - **OWNERDEC** (`product_decision_missing`, D1–D4) — resolved 2026-10-31: the owner recorded D1–D4 on the issues, and `docs/development/backlog-decisions-v4.md` records them;
  - **SETTINGS** (`admin_approval`, D5);
  - **TXNSPEC** if its design fails three rounds (`product_decision_missing`, S-TXN);
  - **PY314** if treesitter-chunker#534 has not merged (an external precondition; met 2026-10-31);
  - **ADMIT** if treesitter-chunker#508 or treesitter-chunker#509 recurs (pause and re-plan).
- **Critical path (automated):** ADMITPIN → ADMIT → ADMITFIX → RECORDS. treesitter-chunker#362 is the only L item and drives it. **Risk path:** TXNSPEC → TXN → RECORDS; it becomes critical if TXNSPEC needs all three rounds, because TXN is two serial M items (treesitter-chunker#370 → treesitter-chunker#323) alongside treesitter-chunker#363. **Human path:** OWNERDEC → FOLLOWUP, bounded by owner response time, and kept off the automated critical path.
- **Cross-phase single-writer files:**
  - `chunker/grammar_management/core.py` — region-owned. GrammarValidator native load: ADMIT SL-core. GrammarValidator cache plus cleanup: TXN SL-cache. GrammarInstaller download/build/cache-entry functions (`_download_grammar`, `_build_grammar`, `_build_with_*`, `_get_commit_hash`, `_cleanup_cache`) and the `install_grammar` staging routing: TXN SL-cache (treesitter-chunker#323). GrammarInstaller installation commit, rollback, metadata read/write and `remove_grammar`: TXN SL-rollback (treesitter-chunker#363), which merges only after ADMIT SL-core's `GrammarInstaller(trusted_artifacts=)` change (decisions D-a and D-b, 2026-10-31). GrammarRegistry discovery: ADMITFIX SL-regsfx. `get_grammar_metadata`: ADMITFIX SL-cli. `_validate_standard`: SMALLFIX SL-sel, only if needed. Only one open core.py PR may be in its merge window at a time. The first PR to be ready merges and the others rebase. When several are ready together, use the order ADMIT SL-core → TXN treesitter-chunker#370 → ADMITFIX → TXN treesitter-chunker#323 → TXN treesitter-chunker#363.
  - `chunker/grammar_management/cli.py` — ADMIT SL-core (the `build_grammar` post-build load check and the `_validate_compiled_grammar` admission step) then ADMITFIX SL-cli.
  - `chunker/languages/compatibility/grammar_analyzer.py` — CIFAST SL-deadline (`GrammarAnalyzer.analyze_grammar_symbols`) and ADMIT SL-ins (`extract_from_dependencies`). Disjoint functions; merges one at a time.
  - `chunker/_internal/registry.py` — ADMIT SL-reg, then FOLLOWUP SL-dl.
  - `.github/workflows/ci.yml` — CIFAST SL-lint → CIFAST SL-perm → PY314 SL-types → PY314 SL-env.
  - `.github/workflows/release.yml` — treesitter-chunker#534 → CIFAST SL-lint → CIFAST SL-perm → PY314 SL-types → PY314 SL-env.
  - `chunker/build/builder.py` — treesitter-chunker#534 → CIFAST SL-lint (F401, treesitter-chunker#517).
  - `.python-version` — created by treesitter-chunker#534 (3.12 pin); afterwards owned by PY314 SL-env only.
  - `specs/active/release-process-spec.md` — treesitter-chunker#534 → PY314 SL-env.
  - `CONTRIBUTING.md` — CIFAST SL-lint → CIFAST SL-scratch → PY314.
  - `chunker/core.py` — the treesitter-chunker#435 fix (treesitter-chunker#535, merged `d3d6b20e`; done) → FOLLOWUP SL-cr (CR-only decode/parse).
  - Boundary IR goldens — any phase regenerating them does so on the locked stack, one PR at a time.
- **Tier mapping:**
  - Tier 1: HOTFIX, ADMITPIN/ADMIT, TXNSPEC/TXN, plus GRAPHML SL-pkg and REFS SL-py/SL-js.
  - Tier 2: CIFAST and PY314.
  - Tier 3: ADMITFIX treesitter-chunker#117 and GRAPHML SL-direct.
  - Tier 4: SMALLFIX, REFS remainder, ADMITFIX treesitter-chunker#128/#120, FOLLOWUP, RECORDS.

---

## Acceptance Criteria

- [ ] Every open issue in the 2026-10-31 triage is either closed with evidence by its phase, recorded with an owner decision, or listed under Held / In Flight or Unplaced with a reason.
- [ ] `grammar info` returns 0 for a real pinned grammar with approved pins on Linux, macOS and Windows.
- [ ] No native load in `chunker/` bypasses `probe_native_grammar` unless the inventory documents it as caller-trusted or retired.
- [ ] Cache writers, cleanup and rollback meet IF-0-TXNSPEC-1, or the S-TXN owner decision is recorded.
- [ ] CI lint covers tracked `chunker/build`, and release validation runs the same lint/type commands as CI.
- [ ] Every merged PR records VB-1 to VB-4 evidence.

---

## Verification

Run on main after the final phase merges, one heavy command at a time:

```bash
# Repository checks (CONTRIBUTING.md)
uv run --locked --all-extras ruff check chunker/ cli/ tests/ tools/governed_group.py tools/governed_scope.py tools/sync_governed_test_transport.py --exclude archive --exclude logs --exclude site
uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/ tools/governed_group.py tools/governed_scope.py tools/sync_governed_test_transport.py
uv run --locked --all-extras python scripts/mypy_gate.py
uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py

# Broad behavior (one at a time on this host)
uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
uv run --locked --with toml --all-extras python scripts/run_full_suite.py

# Native admission: no unlisted direct loads remain
grep -rnE "ctypes\.CDLL|cdll\.LoadLibrary" chunker/ | sort > "$TMPDIR/native-loads.txt"
# compare against the inventory table in docs/development/native-validation-contract.md

# Ruff now sees chunker/build
uv run --locked --all-extras ruff check chunker/build/

# Python 3.14 locked environment (PY314)
uv sync --locked --all-extras --python 3.14

# Actions default permission (SETTINGS)
gh api repos/Consiliency/treesitter-chunker/actions/permissions/workflow --jq .default_workflow_permissions

# Windows preflight (CONTRIBUTING.md)
ssh win 'powershell -NoProfile -Command "cd $HOME\\code\\treesitter-chunker; git fetch origin; git checkout main; git pull --ff-only; uv run --with toml --all-extras python scripts/run_windows_preflight.py"'
```

Downstream phase plans must give focused, machine-checkable commands and an effective `automation.suite_command` per lane. Operational evidence that cannot be machine-checked (an owner decision, a repository setting, a native Windows run) must name its artifact. Proxy evidence needs a runner-stamped roadmap amendment before it counts as a gate verdict.

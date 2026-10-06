---
phase_loop_plan_version: 1
phase: SAFELOAD
roadmap: specs/phase-plans-v3.md
roadmap_sha256: 02aa04c0021c25499377509e2263f66ace0a3810ca1b0efc28e68666ae12c9ba
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_grammar_integrity.py tests/test_compiled_grammar_analysis_contract.py tests/test_grammar_management.py -q"
---

# SAFELOAD: Trusted native grammar validation

## Context

Metadata prerequisites are accepted: treesitter-chunker#366 repaired version and
release metadata, and treesitter-chunker#380 repaired legacy compilation dates.
Neither produces IF-0-SAFELOAD-1. Native implementation acceptance remains pending.

Implement treesitter-chunker#165, treesitter-chunker#151 and treesitter-chunker#164 as one shared native-admission behavior cluster. This plan is execution-ready but is not a ratified design review or a produced IF gate. Retain draft treesitter-chunker#159 until its reviewed successor is accepted; do not spend another review round on that held draft.

Current construction sites: `GrammarAnalyzer.analyze_grammar_file` accepts metadata/date fallbacks without proving loadability; `SmartGrammarManager.diagnose_grammar_issues` maps discovered libraries in the parent and only checks symbol presence; `UserGrammarTools` delegates validation to that manager. Existing `verify_artifact` provides SHA-256 comparison, and `load_compiled_grammar` constructs a Parser with the pinned capsule API and rejects null pointers. Reuse both rather than inventing another loader. The existing compiled BAML test supplies reviewed source and a real sample.

One independently landable implementation PR carries the shared code, tests and documentation together. Its single implementation lane is followed by a documentation/evidence reducer; the reducer is part of that PR, not a separately landed repair. SAFELOAD has no upstream phase or IF gate; acceptance of metadata precursor treesitter-chunker#366 precedes execution. GRAMMARS consumes SAFELOAD's accepted gate. Coordinate exclusive access to the analyzer with GATES and legacy tools with GRAMMARS. Destination publication/reload, native suffix discovery, registry health/CLI semantics and other native-loader consumers remain GRAMMARS work; this phase must not claim repository-wide native-load coverage.

The tracked roadmap hash matches the requested input. The newer canonical `.phase-loop/events.jsonl` run event marks SAFELOAD unplanned after the roadmap amendment, and live git topology confirms a clean starting checkout. Older state and handoff snapshots describe the previous plan against the superseded hash. Refresh this plan from the current roadmap; leave canonical runner state runner-owned and treat legacy `.codex/phase-loop/` files only as compatibility artifacts.

## Interface Freeze Gates

- [ ] IF-0-SAFELOAD-1 — Review and freeze `docs/development/native-validation-contract.md`, `chunker.grammar.integrity.probe_native_grammar`, its `NativeProbeResult`, constructor provenance inputs and the child acknowledgment below; produce the gate only after both EC items, independent review and final verification succeed.

### Admission and immutable identity

Extend the existing integrity module with:

`probe_native_grammar(path: Path, language: str, *, provenance: Mapping[str, Any] | None, sample: bytes = b"", timeout: float = 10.0, inspect_artifact: Callable[[Path], None] | None = None) -> NativeProbeResult`.

Freeze `NativeProbeResult` as an immutable record with `supported: bool`, `reason: str`, `artifact_sha256: str | None`. Reasons are `ok`, `missing`, `empty`, `untrusted`, `integrity_mismatch`, `load_failed`, `parse_failed`, `timeout`, `child_failed`, `ack_missing`, `ack_invalid`, `inspect_failed`. Only ok carries an accepted digest; failures return None. Missing/empty bytes are rejected without execution; all other candidates need trusted provenance before any native load.

Use existing `verify_artifact(path, provenance)` semantics: a nonempty SHA-256 pin comes from reviewed application/repository-owned configuration or an explicitly approved local build. A scanned directory, allowed HTTPS host, filename, stat tuple, successful prior probe, or adjacent self-authored manifest cannot confer trust. Never derive the expected pin from an unknown candidate and call that verification. Tests may compute pins only for artifacts they deliberately compile from reviewed repository/C fixture source; malicious fixtures are deliberately admitted only to exercise isolated failure handling.

Add optional keyword-only `trusted_artifacts: Mapping[str, Mapping[str, Any]] | None = None` to `GrammarAnalyzer`, `SmartGrammarManager` and `UserGrammarTools`; records are keyed by requested language and contain the existing `sha256` field. Copy supplied records at construction and forward them through tools to the manager. Absence fails closed for discovered local libraries. Do not silently trust freshly cloned/built outputs or add a trust-all switch. Document how an embedding caller supplies an independently approved pin, and why legacy CLI discoveries without that configuration cannot be healthy. Building arbitrary source is not made safe by this validation contract.

Copy candidate bytes from one open regular file into an exclusively created, private temporary snapshot retaining its native suffix. Verify the completed snapshot against the external pin, close the writer, and load only that absolute snapshot path. The child independently verifies the same digest before loading. Never verify the source path then reopen it for loading; replacements and same-size/same-mtime edits must not substitute bytes. Snapshot lifetime extends through child termination/reaping; source inodes never become mapped in the parent. This protects against candidate replacement, not a hostile process controlling the same account/private directory or malicious explicitly trusted native dependencies.

### Probe and acknowledgment

Parent metadata extraction uses `inspect_artifact(snapshot_path)` only after successful child completion and before removing that same verified snapshot. Analyzer versions, symbols and file size derive from this snapshot, while the public path remains the original candidate and reports carry the admitted digest. Callback failure cannot produce healthy or partial metadata. Add a deterministic replacement specifically between completion and extraction and kill `inspect_original_after_probe`; cache metadata stays digest-bound.
The callback is trusted synchronous application inspection, never parent-side native mapping or snapshot mutation. Recheck identity before invoking it; commit captured metadata only on ok with its matching digest. A raising callback returns inspect_failed with no accepted digest and guaranteed finally cleanup; kill accept_partial_inspection. No source/snapshot mtime produces version or release_date. Missing values remain unknown/None after independently accepted treesitter-chunker#365/treesitter-chunker#368 precursor repair in treesitter-chunker#366.

Use `sys.executable -I` and an argument array, cwd=private snapshot directory, without a shell, to invoke a private child entrypoint in the existing integrity module. Bootstrap from the parent's known installed/approved package path; never import from caller/candidate cwd or PYTHONPATH. Test sentinel shadow modules in both directories and kill inherit_candidate_import_path. Import `load_compiled_grammar` lazily inside the child. The child verifies the snapshot, calls that pinned loader, invokes `Parser.parse(sample)`, observes a returned root, and only then emits one structured completion record:

`{"schema":"native_probe.v1","nonce":"<per-request>","language":"<requested>","sha256":"<snapshot>","loader_returned":true,"parse_returned":true}`.

The parent accepts only zero exit plus exactly one well-formed acknowledgment matching schema, nonce, language and digest with both flags true. Native diagnostic stdout is not itself success; malformed, duplicate, missing or mismatched records fail closed. Acknowledgment proves completion, not a sandbox or authenticity against deliberately trusted malicious code. Empty-parse completion proves basic loadability, not all language semantics; positive BAML coverage must separately parse the checked-in nonempty declaration fixture without errors.

Timeout allows at most one second after termination before forced termination/reaping, all before snapshot cleanup; crashes, nonzero exit and premature `exit(0)`/`_exit(0)` never yield support. Capture at most 64 KiB per diagnostic stream and a 16 KiB acknowledgment; overflow fails closed without unbounded buffering. Distinct child failure records convey load_failed or parse_failed but cannot count as successful completion. Return the stable reason, not fabricated capability metadata. Keep ordinary timeout policy changes for GATES separate.

### Consumer behavior and compatibility

Analyze metadata only after admission and acknowledgment succeed. Failed `analyze_grammar_file` returns `None`; capabilities retain `supported=False` and empty/default fields, with an additive `validation_reason`; reports and exports preserve that reason. Metadata defaults cannot rescue failed validation. Cached analyzer and manager results must revalidate current content/provenance before reuse, including removal and same-stat replacement; do not cache by language alone.

Keep export successes under `grammars` and add `validation_failures` for rejected discoveries with supported=false, cause and path. All positive analyzer results are content/provenance revalidated. Default CLI/database factories without pins expose unsupported discoveries and actionable cause; do not fabricate analysis or new accepted records. Existing database rows remain historical, not admission receipts; default factory pin injection and stale-record reconciliation are owned by treesitter-chunker#362/COMPAT. In scoped tools, both install and update (including unchanged revision) must return warning plus cause when an artifact fails admission, never unconditional success. Do not silently fix unrelated database persistence or downstream publication here.
Derive each export entry from one admitted observation, not separate mutable-path probes. Test complete/disjoint grammars versus validation_failures membership, no inserted default-factory records, inspection exceptions and diagnostic/protocol overflow. Existing tools write changed revisions in place; warnings must describe that actual state, never claim safe staging. Unchanged-revision updates copy nothing but still validate the existing artifact, including missing paths; kill unchanged_update_skips_validation. CLI warning-to-exit-code migration and auxiliary testing.py original-path reload belong to treesitter-chunker#362/GRAMMARS. SAFELOAD guarantees no fabricated analyzer output/no new accepted records; downstream database cause surfacing remains deferred.

Legacy diagnosis maps missing to `missing`, empty/load/parse/null-symbol failures to `corrupted`, untrusted/integrity/child/protocol/inspection/deadline failures to `incompatible`, and only `ok` to `healthy`. Existing issues/recommendations carry the reason and recovery guidance. Tools preserve existing result shapes, propagate these findings, and invalidate old health observations after install/update. No parent `CDLL` or alternate loader may bypass the shared gate in these consumers. The exported low-level loader remains a caller-trusted primitive, never a discovery admission boundary. Registry ambient discovery/fallback loads, central GrammarValidator and CLI validation remain explicitly unsecured until GRAMMARS integrates this contract. Modern installer publication and legacy replacement also remain GRAMMARS work. RUNTIME and GATES repairs do not establish native admission safety.

## Lane Index & Dependencies

SL-1 — Shared admission, probe and consumer repair
  Depends on: (none)
  Blocks: SL-2
  Parallel-safe: no

SL-2 — Documentation and evidence reducer
  Depends on: SL-1
  Blocks: (none)
  Parallel-safe: no

## Lanes

### SL-1 — Shared admission, probe and consumer repair

- **Scope**: Freeze the contract, then implement and falsify one admission/probe mechanism across analyzer and legacy validation.
- **Owned files**: `chunker/grammar/integrity.py`, `chunker/languages/compatibility/grammar_analyzer.py`, `chunker/_internal/grammar_management.py`, `chunker/_internal/user_grammar_tools.py`, `tests/test_grammar_integrity.py`, `tests/test_compiled_grammar_analysis_contract.py`, `tests/test_grammar_management.py`, `docs/development/native-validation-contract.md`
- **Interfaces provided**: `SAFELOAD implementation candidate`, `SAFELOAD contract review evidence`, `SAFELOAD fixture and mutation results`
- **Interfaces consumed**: `verify_artifact`, `load_compiled_grammar`, `GrammarHealth` (pre-existing)
- **Parallel-safe**: no
- **Tasks**:
  - test: Extend existing test files first. Compile BAML from `packages/baml-grammar/src/parser.c`; keep adversarial C snippets in the existing compiled-contract test and outputs under pytest temporary roots. Parameterize analyzer and legacy production entrypoints, including tools delegation. Require an available compiler in native acceptance jobs; do not convert missing compiler support into a passing gate.
  - test: Cover absent/empty/corrupt/wrong-symbol/null-language candidates, missing/malformed/mismatched pins, relative paths, stale cache removal and same-stat replacement, altered source after snapshot creation, malformed/mismatched/duplicate acknowledgment, timeout and crash. An unadmitted constructor writes a temporary sentinel if loaded: assert rejection and no sentinel. Use a separately confined deliberate-load positive control to prove that fixture really writes it.
  - test: Probe a pinned metadata-less real grammar twice through snapshot inspection; both observations retain unknown version and None release_date, preserving the accepted precursor contract.
  - test: Deliberately pin reviewed constructor fixtures calling `exit(0)` and `_exit(0)`; require rejection without acknowledgment while the outer process survives. Instrument the real child loader/parse path for path-entered controls; mocks may test protocol parsing but cannot replace native evidence. Check repeated diagnose/replace/diagnose cycles in an outer subprocess and source rename/removal after probing, including Windows handle release.
  - impl: Review and, where needed, refine the existing proposed `docs/development/native-validation-contract.md` before behavior changes. Obtain independent design review of trust origin, snapshot race handling, child completion and failure mappings; record its evidence before implementing. Resolve blocking disagreement before continuing. Design approval alone produces no IF gate and closes no implementation issue. Then add the shared probe beside the existing integrity verifier and wire all three consumers. Replace mock-CDLL-as-health expectations with observable contract tests.
  - impl: Keep import boundaries lazy and package exports unchanged; no new dependency, env variable, pin, generated golden or committed native library is needed. Do not modify source fixtures or retrofit unrelated loading paths.
  - verify: Run the focused suite in Verification, then named mutations below with fresh subprocesses and isolated HOME/USERPROFILE. Restore each mutation and rerun the affected tests before handing results to SL-2.

### SL-2 — Documentation and evidence reducer

- **Scope**: Reduce SL-1 behavior, review and verification into accurate user documentation and acceptance evidence.
- **Owned files**: `docs/grammar_management.md`, `CHANGELOG.md`, `docs/development/safeload-verification.md`
- **Interfaces provided**: `SAFELOAD acceptance evidence`, `IF-0-SAFELOAD-1` (only after final acceptance)
- **Interfaces consumed**: `SAFELOAD implementation candidate`, `SAFELOAD contract review evidence`, `SAFELOAD fixture and mutation results`
- **Parallel-safe**: no
- **Tasks**:
  - test: Check documentation examples against the actual constructor parameters and untrusted/healthy outcomes; inspect every EC/IF claim against SL-1 fixture and review results.
  - impl: Document provenance migration, failure reasons, trust limitations and downstream GRAMMARS responsibilities; add an Unreleased changelog entry. Record per-platform fixture outcomes, positive controls, killed mutations, command/result metadata and independent review references in the evidence document. Distinguish preliminary contract review from final accepted IF production. Require independent implementation review and passing fixture, mutation and platform results for the final reviewed implementation; only then emit IF-0-SAFELOAD-1 and record eligibility to close treesitter-chunker#151, treesitter-chunker#164 and treesitter-chunker#165.
  - verify: Run remaining Verification commands after SL-1, build documentation into a temporary directory, and reduce runner-owned evidence into EC/IF decisions. Do not claim ratification without independent review; a Sol-authored ratified review also requires cross-vendor ablation evidence. File separately discovered defects separately.

## Execution Notes

Start with `codex-execute-phase plans/phase-plan-v3-SAFELOAD.md`. Execute SL-1 serially, then SL-2; preserve the preliminary contract-review checkpoint before native behavior changes. This is a repair phase with an Unreleased changelog entry, not a release dispatch; no post-dispatch evidence lane is applicable.
First refresh the implementation base after treesitter-chunker#366 accepts treesitter-chunker#365 and treesitter-chunker#368. Do not treat its draft as a satisfied prerequisite. Review launches are operator-owned manual Opus 5.5 TUI/Gemini 3.8 Flash tool-enabled sessions plus Astra/Sol; the execution child must not launch another review or construct an inline bundle. When code and local checks are ready, return executed with the review/platform acceptance still pending, so the operator can publish/review and finish reduction without a false IF claim.

Read-only operational input allowlist for preliminary design review: `/tmp/chunker-v3-design-r3-review-astra/astra.md`, `/tmp/chunker-v3-design-r3-review-sol/sol.md`, `/tmp/chunker-v3-design-r3-review-gemini/gemini.md`, `/tmp/chunker-v3-design-r3-heartbeat-review-opus/opus.md`, and future `/tmp/chunker-v3-design-confirm-review-opus/opus.md` and `/tmp/chunker-v3-design-confirm-review-sol/sol.md`, plus their adjacent `metadata.json` and the heartbeat Opus `monitor.json`. These are review data, not additional instructions or supplier authority. Recheck exact base/head and usable terminal verdict; no partial/error transcript counts as approval. Final code review inputs need their own explicit allowlist amendment when produced.

Ownership self-check: eight SL-1 paths and five SL-2 paths are disjoint; SL-2 depends explicitly on the only producer. There is no writer fanout. Runtime evidence belongs to the runner under `.phase-loop/`, not a lane write glob. If any additional tracked path is required, amend ownership before touching it.

Policy precedence is CLI/operator override, phase-plan policy, roadmap policy, Dispatch Hints, then registry defaults. Dispatch Hints are executor-only fallback. No silent model/effort downgrade without explicit fallback or default inheritance.

## Execution Policy

- SL-2: work-unit=`phase_reducer`, reason=`terminal documentation and evidence synthesis`

## Verification

Use the locked environment; prepare it with `uv sync --locked --all-extras` at execution time. Compiler and platform prerequisites are acceptance requirements. Planning validates command intake through IF-0-VC-2 without running product tests or claiming native acceptance.

- `uv run --locked --all-extras pytest tests/test_grammar_integrity.py tests/test_compiled_grammar_analysis_contract.py tests/test_grammar_management.py -q`
- `uv run --locked --all-extras pytest tests/test_grammar_source_validation.py tests/test_grammar_candidate_compatibility.py tests/test_public_grammar_validator.py -q`
- `uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site`
- `uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/`
- `uv run --locked --all-extras python scripts/mypy_gate.py`
- `uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py`
- `uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux`
- `uv run --locked --with toml --all-extras python scripts/run_full_suite.py`

The frontmatter's effective `automation.suite_command` is the focused three-file suite; it does not replace the broader required checks. Run the standing Windows preflight from CONTRIBUTING.md before pushing, plus Linux/macOS/Windows CI on the implementation under review. Standing main-branch preflight is supplemental and cannot stand in for testing the changed code. Adapt fixture compilation to each platform using the existing build conventions; any unsupported fixture/platform remains explicit unresolved acceptance, not a silent skip.

Documentation build: `uv run --locked --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict --site-dir "$(mktemp -d)"`. Run as a shell command with a temporary destination, never into tracked `site/`.

Named mutations at production construction sites:
1. `bypass_native_provenance`: bypass the pre-load verifier in `chunker/grammar/integrity.py`; the unadmitted constructor sentinel test fails, with the deliberate-load control proving it can execute.
2. `accept_exit_zero_without_ack`: substitute return-code-only success in the same probe; each real premature-clean-exit fixture becomes incorrectly supported.
3. `reload_original_after_verify`: use the original path instead of the verified snapshot; deterministic replacement introduces wrong bytes and fails identity/parse assertions.
4. `reuse_language_only_health`: bypass fresh content verification in analyzer/manager; same-stat replacement and repeated legacy validation tests fail.
5. `inspect_original_after_probe`: read metadata from the replaced original path instead of the retained admitted snapshot; the post-completion replacement fixture fails metadata/digest assertions.
6. `accept_partial_inspection`: publish captured metadata despite a raising callback; partial-output and cleanup assertions fail.
7. `inherit_candidate_import_path`: omit child isolated import protection; caller/candidate shadow-module sentinel assertions fail.
8. `unchanged_update_skips_validation`: return success without validating unchanged installed bytes; stale-pin/missing-artifact warning assertions fail.

For each, record baseline pass, mutation-triggered failure, path-entered control and restored pass. No tight scheduler timing assertions. Keep evidence metadata-only in `docs/development/safeload-verification.md`, pointing to runner-owned `.phase-loop/` verification artifacts. Operational review/remote-platform evidence must use the runner-stamped amendment mechanism with artifact path and digest; do not substitute proxy evidence or hand-edit runner ledgers. If such an amendment cannot be recorded, leave acceptance unresolved.

## Acceptance Criteria

- [ ] EC-SAFELOAD-1 — proven by `uv run --locked --all-extras pytest tests/test_grammar_integrity.py tests/test_grammar_management.py -q` and independently reviewed `docs/development/native-validation-contract.md` recorded in `docs/development/safeload-verification.md`; falsified by `bypass_native_provenance` at `chunker/grammar/integrity.py:probe_native_grammar`, with a path-entered deliberate-load constructor sentinel control and recorded rejection failure.
- [ ] EC-SAFELOAD-2 — proven by `uv run --locked --all-extras pytest tests/test_compiled_grammar_analysis_contract.py -q`; falsified by `accept_exit_zero_without_ack`, `reload_original_after_verify`, `accept_partial_inspection` and `inherit_candidate_import_path` at `chunker/grammar/integrity.py:probe_native_grammar`, plus `inspect_original_after_probe` at the analyzer callback, `reuse_language_only_health` at analyzer/legacy diagnosis and `unchanged_update_skips_validation` at tools update, with path-entered real BAML parse, premature-clean-exit, callback, shadow-module and replacement controls.

## Spec Closeout Plan

- schema: `spec_delta_closeout.v1`
- decision: `canonical_spec_update`
- target surfaces: `docs/development/native-validation-contract.md`, `docs/grammar_management.md`
- evidence paths: `docs/development/safeload-verification.md`, `.phase-loop/`
- redaction posture: `metadata_only`
- downstream handling: `none`

GRAMMARS consumes IF-0-SAFELOAD-1 only after execution produces it. Planning emits no native gate, does not change roadmap acceptance, and does not authorize merging or closing the held drafts.

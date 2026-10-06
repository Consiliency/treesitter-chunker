---
phase_loop_plan_version: 1
phase: SAFELOAD
roadmap: specs/phase-plans-v3.md
roadmap_sha256: c1812a46acb53ba34fea35fa683f407e684efabf4dc76bb00207670f208041cd
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_grammar_integrity.py tests/test_compiled_grammar_analysis_contract.py tests/test_grammar_management.py -q"
---

# SAFELOAD: Trusted native grammar validation

## Context

Implement treesitter-chunker#165, treesitter-chunker#151 and treesitter-chunker#164 as one shared native-admission behavior cluster. This plan is execution-ready but is not a ratified design review or a produced IF gate. Retain draft treesitter-chunker#159 until its reviewed successor is accepted; do not spend another review round on that held draft.

Current construction sites: `GrammarAnalyzer.analyze_grammar_file` accepts metadata/date fallbacks without proving loadability; `SmartGrammarManager.diagnose_grammar_issues` maps discovered libraries in the parent and only checks symbol presence; `UserGrammarTools` delegates validation to that manager. Existing `verify_artifact` provides SHA-256 comparison, and `load_compiled_grammar` constructs a Parser with the pinned capsule API and rejects null pointers. Reuse both rather than inventing another loader. The existing compiled BAML test supplies reviewed source and a real sample.

There is one implementation lane and a dependent documentation/evidence reducer, not independent native implementations. SAFELOAD has no upstream dependency; GRAMMARS consumes its accepted gate. Coordinate exclusive access to the analyzer with GATES and legacy tools with GRAMMARS. Destination publication/reload, native suffix discovery, registry health/CLI semantics and other native-loader consumers remain GRAMMARS work; this phase must not claim repository-wide native-load coverage.

The tracked roadmap hash matches the requested input. Canonical `.phase-loop/events.jsonl` records the current planning run on the clean checkout; older state/handoff topology refers to the preceding dry run. Use the newer ledger and live git state, leave runner state runner-owned, and do not consult legacy state as authority.

## Interface Freeze Gates

- [ ] IF-0-SAFELOAD-1 — Review and freeze `docs/development/native-validation-contract.md`, `chunker.grammar.integrity.probe_native_grammar`, its `NativeProbeResult`, constructor provenance inputs and the child acknowledgment below; produce the gate only after both EC items, independent review and final verification succeed.

### Admission and immutable identity

Extend the existing integrity module with:

`probe_native_grammar(path: Path, language: str, *, provenance: Mapping[str, Any] | None, sample: bytes = b"", timeout: float = 10.0) -> NativeProbeResult`.

Freeze `NativeProbeResult` as an immutable record with `supported: bool`, `reason: str`, `artifact_sha256: str | None`. Reasons are `ok`, `missing`, `empty`, `untrusted`, `integrity_mismatch`, `load_failed`, `parse_failed`, `timeout`, `child_failed`, `ack_missing`, `ack_invalid`. Missing/empty bytes are rejected without execution; all other candidates need trusted provenance before any native load.

Use existing `verify_artifact(path, provenance)` semantics: a nonempty SHA-256 pin comes from reviewed application/repository-owned configuration or an explicitly approved local build. A scanned directory, allowed HTTPS host, filename, stat tuple, successful prior probe, or adjacent self-authored manifest cannot confer trust. Never derive the expected pin from an unknown candidate and call that verification. Tests may compute pins only for artifacts they deliberately compile from reviewed repository/C fixture source; malicious fixtures are deliberately admitted only to exercise isolated failure handling.

Add optional keyword-only `trusted_artifacts: Mapping[str, Mapping[str, Any]] | None = None` to `GrammarAnalyzer`, `SmartGrammarManager` and `UserGrammarTools`; records are keyed by requested language and contain the existing `sha256` field. Copy supplied records at construction and forward them through tools to the manager. Absence fails closed for discovered local libraries. Do not silently trust freshly cloned/built outputs or add a trust-all switch. Document how an embedding caller supplies an independently approved pin, and why legacy CLI discoveries without that configuration cannot be healthy. Building arbitrary source is not made safe by this validation contract.

Copy candidate bytes from one open regular file into an exclusively created, private temporary snapshot retaining its native suffix. Verify the completed snapshot against the external pin, close the writer, and load only that absolute snapshot path. The child independently verifies the same digest before loading. Never verify the source path then reopen it for loading; replacements and same-size/same-mtime edits must not substitute bytes. Snapshot lifetime extends through child termination/reaping; source inodes never become mapped in the parent. This protects against candidate replacement, not a hostile process controlling the same account/private directory or malicious explicitly trusted native dependencies.

### Probe and acknowledgment

Use `sys.executable` and an argument array, without a shell, to invoke a private child entrypoint in the existing integrity module. Import `load_compiled_grammar` lazily inside the child. The child verifies the snapshot, calls that pinned loader, invokes `Parser.parse(sample)`, observes a returned root, and only then emits one structured completion record:

`{"schema":"native_probe.v1","nonce":"<per-request>","language":"<requested>","sha256":"<snapshot>","loader_returned":true,"parse_returned":true}`.

The parent accepts only zero exit plus exactly one well-formed acknowledgment matching schema, nonce, language and digest with both flags true. Native diagnostic stdout is not itself success; malformed, duplicate, missing or mismatched records fail closed. Acknowledgment proves completion, not a sandbox or authenticity against deliberately trusted malicious code. Empty-parse completion proves basic loadability, not all language semantics; positive BAML coverage must separately parse the checked-in nonempty declaration fixture without errors.

Timeout terminates and reaps the child before snapshot cleanup; crashes, nonzero exit and premature `exit(0)`/`_exit(0)` never yield support. Use bounded captured diagnostics and return the stable reason, not fabricated capability metadata. Keep ordinary timeout policy changes for GATES separate.

### Consumer behavior and compatibility

Analyze metadata only after admission and acknowledgment succeed. Failed `analyze_grammar_file` returns `None`; capabilities retain `supported=False` and empty/default fields, with an additive `validation_reason`; reports and exports preserve that reason. Metadata defaults cannot rescue failed validation. Cached analyzer and manager results must revalidate current content/provenance before reuse, including removal and same-stat replacement; do not cache by language alone.

Legacy diagnosis maps missing to `missing`, empty/load/parse/null-symbol failures to `corrupted`, untrusted/integrity/child/protocol/deadline failures to `incompatible`, and only `ok` to `healthy`. Existing issues/recommendations carry the reason and recovery guidance. Tools preserve existing result shapes, propagate these findings, and invalidate old health observations after install/update. No parent `CDLL` or alternate loader may bypass the shared gate in these consumers. The exported low-level loader and other registry/validator consumers are pre-existing trusted-code interfaces, not newly secured by this phase.

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
- **Interfaces provided**: `IF-0-SAFELOAD-1`, `SAFELOAD fixture and mutation results`
- **Interfaces consumed**: `verify_artifact`, `load_compiled_grammar`, `GrammarHealth` (pre-existing)
- **Parallel-safe**: no
- **Tasks**:
  - test: Extend existing test files first. Compile BAML from `packages/baml-grammar/src/parser.c`; keep adversarial C snippets in the existing compiled-contract test and outputs under pytest temporary roots. Parameterize analyzer and legacy production entrypoints, including tools delegation. Require an available compiler in native acceptance jobs; do not convert missing compiler support into a passing gate.
  - test: Cover absent/empty/corrupt/wrong-symbol/null-language candidates, missing/malformed/mismatched pins, relative paths, stale cache removal and same-stat replacement, altered source after snapshot creation, malformed/mismatched/duplicate acknowledgment, timeout and crash. An unadmitted constructor writes a temporary sentinel if loaded: assert rejection and no sentinel. Use a separately confined deliberate-load positive control to prove that fixture really writes it.
  - test: Deliberately pin reviewed constructor fixtures calling `exit(0)` and `_exit(0)`; require rejection without acknowledgment while the outer process survives. Instrument the real child loader/parse path for path-entered controls; mocks may test protocol parsing but cannot replace native evidence. Check repeated diagnose/replace/diagnose cycles in an outer subprocess and source rename/removal after probing, including Windows handle release.
  - impl: Write the canonical contract before behavior changes and obtain independent review of trust origin, snapshot race handling, child completion and failure mappings. Preserve unresolved review findings as blockers to gate production. Then add the shared probe beside the existing integrity verifier and wire all three consumers. Replace mock-CDLL-as-health expectations with observable contract tests.
  - impl: Keep import boundaries lazy and package exports unchanged; no new dependency, env variable, pin, generated golden or committed native library is needed. Do not modify source fixtures or retrofit unrelated loading paths.
  - verify: Run the focused suite in Verification, then named mutations below with fresh subprocesses and isolated HOME/USERPROFILE. Restore each mutation and rerun the affected tests before handing results to SL-2.

### SL-2 — Documentation and evidence reducer

- **Scope**: Reduce SL-1 behavior, review and verification into accurate user documentation and acceptance evidence.
- **Owned files**: `docs/grammar_management.md`, `CHANGELOG.md`, `docs/development/safeload-verification.md`
- **Interfaces provided**: `SAFELOAD acceptance evidence`
- **Interfaces consumed**: `IF-0-SAFELOAD-1`, `SAFELOAD fixture and mutation results`
- **Parallel-safe**: no
- **Tasks**:
  - test: Check documentation examples against the actual constructor parameters and untrusted/healthy outcomes; inspect every EC/IF claim against SL-1 fixture and review results.
  - impl: Document provenance migration, failure reasons, trust limitations and downstream GRAMMARS responsibilities; add an Unreleased changelog entry. Record per-platform fixture outcomes, positive controls, killed mutations, command/result metadata and independent review references in the evidence document. Distinguish preliminary contract review from final accepted IF production.
  - verify: Run remaining Verification commands after SL-1, build documentation into a temporary directory, and reduce runner-owned evidence into EC/IF decisions. Do not claim ratification without independent review; a Sol-authored ratified review also requires cross-vendor ablation evidence. File separately discovered defects separately.

## Execution Notes

Start with `codex-execute-phase plans/phase-plan-v3-SAFELOAD.md`. Execute SL-1 serially, then SL-2; preserve the preliminary contract-review checkpoint before native behavior changes. This is a repair phase with an Unreleased changelog entry, not a release dispatch; no post-dispatch evidence lane is applicable.

Ownership self-check: eight SL-1 paths and three SL-2 paths are disjoint; SL-2 depends explicitly on the only producer. There is no writer fanout. Runtime evidence belongs to the runner under `.phase-loop/`, not a lane write glob. If any additional tracked path is required, amend ownership before touching it.

## Execution Policy

- SL-2: work-unit=`phase_reducer`, reason=`terminal documentation and evidence synthesis`

Other policy inherits normally: CLI/operator override, phase-plan policy, roadmap policy, Dispatch Hints, registry defaults. No silent model/effort downgrade without explicit fallback or default inheritance.

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

For each, record baseline pass, mutation-triggered failure, path-entered control and restored pass. No tight scheduler timing assertions. Keep evidence metadata-only in `docs/development/safeload-verification.md`, pointing to runner-owned `.phase-loop/` verification artifacts. Operational review/remote-platform evidence must use the runner-stamped amendment mechanism with artifact path and digest; do not substitute proxy evidence or hand-edit runner ledgers. If such an amendment cannot be recorded, leave acceptance unresolved.

## Acceptance Criteria

- [ ] EC-SAFELOAD-1 — proven by `uv run --locked --all-extras pytest tests/test_grammar_integrity.py tests/test_grammar_management.py -q` and independently reviewed `docs/development/native-validation-contract.md` recorded in `docs/development/safeload-verification.md`; falsified by `bypass_native_provenance` at `chunker/grammar/integrity.py:probe_native_grammar`, with a path-entered deliberate-load constructor sentinel control and recorded rejection failure.
- [ ] EC-SAFELOAD-2 — proven by `uv run --locked --all-extras pytest tests/test_compiled_grammar_analysis_contract.py -q`; falsified by `accept_exit_zero_without_ack` and `reload_original_after_verify` at `chunker/grammar/integrity.py:probe_native_grammar`, plus `reuse_language_only_health` at analyzer/legacy diagnosis, with path-entered real BAML parse, premature-clean-exit and replacement controls.

## Spec Closeout Plan

- schema: `spec_delta_closeout.v1`
- decision: `canonical_spec_update`
- target surfaces: `docs/development/native-validation-contract.md`, `docs/grammar_management.md`
- evidence paths: `docs/development/safeload-verification.md`, `.phase-loop/`
- redaction posture: `metadata_only`
- downstream handling: `none`

GRAMMARS consumes IF-0-SAFELOAD-1 only after execution produces it. Planning emits no native gate, does not change roadmap acceptance, and does not authorize merging or closing the held drafts.

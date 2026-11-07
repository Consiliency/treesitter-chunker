---
phase_loop_plan_version: 1
phase: ADMIT
roadmap: specs/phase-plans-v4.md
roadmap_sha256: 54cc79dcf0b6240c7ed12be2e3f0a7234666b53a9fdb24a9d373947a3a18b7bc
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_trusted_artifacts_contract.py tests/test_grammar_info_exit_contract.py -q"
---

# ADMIT: Integrate remaining native admission paths

## Context

ADMIT is Phase 8 of `specs/phase-plans-v4.md`. It implements the frozen
ADMITPIN contract (treesitter-chunker#538, merged as `6d8d71cf`) for
treesitter-chunker#362 and treesitter-chunker#400. The contract is the
"Production pin source and native-load inventory (ADMITPIN)" section of
`docs/development/native-validation-contract.md`. This plan does not reopen
it. It records how ADMIT builds it, splits the work into lanes, and makes the
four contract touch-ups that the ADMITPIN panel carried over (below).

The plan starts from main `6d8d71cf`. On that commit the defect still
reproduces (VB-1):

```text
$ cc -shared -fPIC -Ipackages/baml-grammar/src packages/baml-grammar/src/parser.c -o "$S/baml.so"
$ cp "$S/baml.so" chunker/data/grammars/build/baml.so      # the argparse group's build dir
$ python -m chunker.cli grammar info baml       # exit 1
Status: ⚠️ incompatible
   - Native admission failed: untrusted
$ python -m chunker.cli grammar diagnose baml   # exit 1, same report
$ python -m chunker.cli grammar --trusted-artifacts x info baml
chunker grammar: error: argument grammar_command: invalid choice: 'x' ...   # exit 2
```

So a real, correctly built grammar can never be reported healthy: there is no
way to supply a pin.

Status since the roadmap snapshot:

- treesitter-chunker#547 (open) records intermittent Windows native-probe
  failures on unchanged main. A separate lane on the Windows host is fixing it.
- treesitter-chunker#540 (TXNSPEC) depends on this phase's
  `GrammarInstaller(*, trusted_artifacts=)` change (runner decision on
  treesitter-chunker#540). SL-core lands it and calls it out in its PR body.
- treesitter-chunker#508 and treesitter-chunker#509 stay on hold. If either
  visibly recurs during ADMIT's Windows checks (a `PermissionError` before the
  constructor, or a manager admission rejection), the phase pauses
  (Assumption 4).
- **State, 2026-11-01:** ADMIT paused once. In SL-core-1's Windows probe runs
  (head `73dbb5a7`, clean temporary checkout), run 1 of 10 failed 9 tests:
  Code Integrity event 3077 (policy `VerifiedAndReputableDesktop`) blocked
  freshly compiled fixture DLLs and three probe-worker snapshot loads; runs
  2–10 passed. **Maintainer ruling (2026-11-01), relayed by the roadmap
  runner:** Application Control (Code Integrity 3077) denials of unsigned
  freshly written DLLs are an OS environment effect, not an ADMIT defect.
  ADMIT continues under EC-ADMIT-9; the treesitter-chunker#547 lane adds a
  distinct "blocked by OS application-control policy" result and makes the
  tests robust to it, and ADMIT does not duplicate that work. Further 3077
  denials are recorded in the PR with their Code Integrity evidence and do not
  stop the phase. Evidence is on treesitter-chunker#508 and
  treesitter-chunker#547. The SL-core split (decision 2) is approved.
- **Further recorded 3077 incidents** (each in its PR body with the Code
  Integrity evidence):
  - treesitter-chunker#556 at `81c82240`, run 7 of 10: 16 event-3077
    denials of probe-worker snapshots (`chunker-native-probe-*`),
    00:43:25–00:43:31 UTC; runs 1–6 and 8–10 passed.
  - treesitter-chunker#563 at `57d9d566`: in the unchanged
    `tests/test_compiled_grammar_analysis_contract.py`, 1–5 scattered
    failures per run, with 17 event-3077 denials of probe-worker snapshots,
    01:14–01:36 UTC, while the Windows host was shared with the
    treesitter-chunker#547 lane. Run 1 also logged `PermissionError
    [WinError 5]` on a snapshot inside the KeyboardInterrupt fault-injection
    test (a registered-worker cleanup path, not before the constructor). It
    is flagged to the treesitter-chunker#547/#508/#509 owners, not classified
    here.
- **Round-1 review (2026-11-01)** of this plan and treesitter-chunker#556:
  addressed in both PRs. **Maintainer decision (2026-11-01)** on plan
  decision 5: one trust rule for package-supplied grammars everywhere
  (decision 5 below).
- **State, 2026-11-07: ADMIT closed.**
  - Merged in this order: treesitter-chunker#556, #558, #562, #559 and #563.
  - treesitter-chunker#547 closed, and the #614 follow-up merged as
    treesitter-chunker#616 (main `b33994e9`).
  - Every acceptance criterion below is met. The Review record has the
    evidence.

## Merge gate (maintainer decision, 2026-10-31)

Recorded on treesitter-chunker#362: **no ADMIT PR merges** until

1. the treesitter-chunker#547 Windows probe flake fix has merged, and
2. ADMIT's own Windows probe tests pass repeatedly without reruns.

ADMIT may build, open PRs and collect reviews meanwhile. Every ADMIT PR body
states the gate. This plan's PR adds it to Phase 8 as EC-ADMIT-9.

**How the gate is counted (runner decision, 2026-11-01).** EC-ADMIT-9 is
evaluated only on Windows runs made after the treesitter-chunker#547 fix has
merged and is included in the ADMIT branch under test, using that fix's
distinct application-control handling. Runs from before treesitter-chunker#547
do not count, whatever their result; the repeated-run evidence already in the
PR bodies is diagnostic, not gate evidence.

## Interface Freeze Gates

- [x] IF-0-ADMIT-1 — The admitted-health accessor, published by SL-core:

  ```python
  # chunker/grammar_management/core.py
  class GrammarManager:
      def get_admitted_health(self, language: str) -> dict[str, Any]: ...
  ```

  It returns the legacy health mapping
  `{"language", "status", "validation_reason", "artifact_sha256", "path",
  "issues"}`. `status` is `healthy`, `missing`, `corrupted` or
  `incompatible`, mapped from the probe reason exactly as the contract's
  "Results and consumer compatibility" section says. It is computed only
  from `probe_native_grammar` under the manager's IF-0-ADMITPIN-1 pins
  (rule 3; verdict reuse under the frozen key). ADMITFIX consumes it for
  treesitter-chunker#128 and treesitter-chunker#120.
  **Landed** in treesitter-chunker#562 (merge `4e260b6d`):
  `chunker/grammar_management/core.py:1821`; test
  `tests/test_validator_admission_contract.py::test_admitted_health_accessor`.

Signatures SL-core publishes on day 1 (in this plan; the code lands in the
SL-core reader PR):

```python
# chunker/exceptions.py
class TrustedArtifactsError(ChunkerError):
    path: str         # the pin file
    defect: str       # one-line, user-facing

# chunker/_internal/trusted_artifacts.py
TRUSTED_ARTIFACTS_SCHEMA = "chunker.trusted_artifacts.v1"
PIN_FILE_NAME = "trusted-artifacts.json"
PIN_FILE_LIMIT = 1024 * 1024
TrustedArtifacts = dict[str, dict[str, str]]

def user_config_pin_path() -> Path | None: ...
def forbidden_pin_directories(
    *, cache_dir: Path | None = None, library_path: Path | None = None
) -> tuple[Path, ...]: ...
def parse_trusted_artifacts(data: bytes, *, source: Path) -> TrustedArtifacts: ...
def read_trusted_artifacts(
    path: Path, *, forbidden: Iterable[Path] = ()
) -> TrustedArtifacts: ...                     # raises TrustedArtifactsError
def load_user_config_pins(
    *, cache_dir: Path | None = None, library_path: Path | None = None
) -> TrustedArtifacts | None: ...              # None when the file is absent
def resolve_command_pins(
    option_path: Path | None, *, cache_dir: Path | None = None
) -> TrustedArtifacts | None: ...              # option, else config file
def copy_trusted_artifacts(mapping: object) -> dict[str, dict[str, Any]]: ...
def pin_provenance(mapping: Mapping[str, Any] | None, language: str) -> dict[str, str] | None: ...

# chunker/_internal/package_supplier.py  (the one RECORD check; M3)
def package_grammar_build_dir() -> Path: ...
def same_file(first: Path | str, second: Path | str) -> bool: ...   # samefile, then resolve
def package_supplied_digest(candidate: Path) -> tuple[str, str | None]: ...
    # ("supplied", hex) | ("mismatch", None) | ("local", None)

# chunker/_internal/native_admission.py
def admission_record(
    path: Path, language: str, trusted_artifacts: Mapping[str, Any] | None,
) -> tuple[dict[str, str] | None, NativeProbeResult | None]: ...
    # RECORD digest for a package-supplied file, integrity_mismatch for a
    # RECORD mismatch (no pin overrides it), else the rule-3 pin record
def admit_native_candidate(
    path: Path, language: str, trusted_artifacts: Mapping[str, Any] | None, *,
    level: str = "probe", inspector: str = "none",
    inspect_artifact: Callable[[Path], Any] | None = None,
    sample: bytes = b"", timeout: float | None = None,  # None: the probe's own DEFAULT_PROBE_TIMEOUT
    probe: Callable[..., NativeProbeResult] | None = None,
    reusable: Callable[[Any], bool] | None = None,  # store rule for an ok result's metadata
) -> tuple[NativeProbeResult, Any]: ...        # (result, inspector metadata or None)
def admitted_private_copy(
    path: Path, language: str, trusted_artifacts: Mapping[str, Any] | None, *,
    probe: Callable[..., NativeProbeResult] | None = None,
) -> tuple[NativeProbeResult, Path | None]: ...
def verdict_key(*, language: str, pin_sha256: str, content_sha256: str,
                level: str, inspector: str) -> str: ...
def has_verdict(key: str) -> bool: ...
def store_verdict(key: str, *, language: str, content_sha256: str,
                  metadata: Any = None) -> None: ...
def drop_verdicts(language: str, content_sha256: str) -> None: ...
def forget_private_copy(language: str, digest: str) -> None: ...
def hash_regular_file(path: Path) -> str | None: ...
NATIVE_VERDICT_VALIDATOR_SCHEMA: int
```

`probe=` defaults to `chunker.grammar.integrity.probe_native_grammar`, looked
up at call time; callers pass their own module's reference so existing test
seams keep working. Invalidation on a load failure (rule 4): a site that fails
to load an admitted copy calls `forget_private_copy(language, digest)`, which
also calls `drop_verdicts(language, digest)`; `drop_verdicts` alone drops every
verdict for those bytes without touching copies. A forked child starts with no
verdicts, copies or cleanup ownership (`os.register_at_fork`).

`admit_native_candidate` applies rule 3 (`os.path.lexists` → `missing`; no
`str` `sha256` → `untrusted` without opening the file), then the verdict-reuse
lookup order (hash from one open regular file; a digest that differs from the
pin is `integrity_mismatch` without probing), and only then probes with the
one-field record. Only `ok` results with `artifact_sha256 == content_sha256`
and the default probe profile (`default-v2`: `sample=b""` with
`integrity.DEFAULT_PROBE_TIMEOUT`, compared against the imported constant, never
a restated copy; treesitter-chunker#561) are stored, in process memory only. A
site may pass `reusable` to decline storing a transient result (for example a
timed-out symbol analysis, treesitter-chunker#563).
`admitted_private_copy` implements "Using an admitted grammar in-process":
one `chunker-admitted-*` private copy per (language, digest) per process,
verified, probed (or reused under the copy's key), and returned only after
`ok`. POSIX removes copy directories at interpreter exit; Windows leaves them
(the documented residual risk).

## Decisions this plan makes, open to challenge in review

1. **The four ADMITPIN carry-overs** (runner comment on
   treesitter-chunker#538). This PR writes each into the contract, and the
   named lane implements it:
   1. The off-parse-path rule covers **every component that accepts
      `trusted_artifacts`**, including `GrammarAnalyzer`,
      `SmartGrammarManager` and `UserGrammarTools`. (SL-core; SL-ins for
      the analyzer.)
   2. The no-path `test_parse_samples` branch resolves through a
      `LanguageRegistry` built from the validator's own pins, with
      `library_path` set to `chunker._internal.registry.default_library_path()`,
      the same default combined library that `chunker.parser` uses. So
      package-supplied grammars (our wheel's RECORD-verified files, P1, P2,
      R5) still resolve, and local candidates need the validator's own pin.
      (SL-reg publishes `default_library_path()`; SL-core uses it.)
   3. The RECORD file-identity test uses `os.path.samefile` first and falls
      back to comparing `Path.resolve()` results only when `samefile`
      raises. (SL-reg.)
   4. **Every subcommand of both grammar groups is pin-dependent.** Both
      groups resolve the active pin source before any subcommand runs (the
      argparse group before dispatch; the click group in its callback). A
      defective option file, or a defective config file when the option is
      absent, exits 2 for every subcommand, before discovery, any probe or
      any native load. `--help` is unaffected. No subcommand only warns.
      `docs/grammar_management.md` ("CLI Commands Reference" → "Approved
      pins") records this, and `docs/cli-reference.md` points to it.
      (SL-core.) Reason: one rule is easier
      to state and audit, and it errs on the safe side. Commands such as
      `grammar build` or `remove` that do not need pins today still name the
      broken file, which the operator has to fix anyway.
2. **SL-core ships as two PRs.** The reader PR (SL-core-1) lands the shared
   reader, the admission helpers, `TrustedArtifactsError`, the argparse
   option and config fallback, and the `SmartGrammarManager` rule-3 lookup.
   That alone closes EC-ADMIT-1 for `grammar info`/`diagnose`, and lets
   SL-reg consume the reader instead of writing its own. The validator PR
   (SL-core-2) takes the `core.py`/`cli.py`/`compatibility.py` region. It
   needs SL-reg's `LanguageRegistry(*, trusted_artifacts=)` and
   `default_library_path()` for decision 1.2, so it stacks on SL-reg.
   Ownership changes from this split and later decisions are recorded in
   decisions 5 and 8.
3. **Admission helpers live in a second new module,**
   `chunker/_internal/native_admission.py` (SL-core), not in the reader.
   The reader only reads pins; the helpers apply rule 3, the verdict key and
   the in-process copy pattern. Neither touches `chunker/grammar/integrity.py`.
4. **`chunker/grammar/registry.py` (`UniversalLanguageRegistry`) belongs to
   SL-reg.** The contract lists it in IF-0-ADMITPIN-1 but the roadmap's file
   lists do not name it. It only forwards pins to the `LanguageRegistry` it
   builds.
5. **One trust rule for package-supplied grammars (maintainer decision,
   2026-11-01, relayed by the roadmap runner; replaces the earlier
   "grammar commands stay pin-only").** The grammar commands honour M3
   through the same code path as parsing, not a copy: the RECORD check lives
   in `chunker/_internal/package_supplier.py` (SL-core-1), and
   `native_admission.admission_record` applies it inside
   `admit_native_candidate` and `admitted_private_copy`, which every
   admitting site uses (both grammar groups, the validator, the analyzer,
   the legacy manager and the registry). Three cases: a shipped grammar whose
   bytes match RECORD reports healthy with no pin; a RECORD mismatch reports
   `integrity_mismatch`, and no user pin overrides it; a file in that
   directory that is not in RECORD needs a pin. SL-reg's registry imports the
   same module instead of defining its own check. The code change lands in
   treesitter-chunker#556 (SL-core-1), because the shared admission helper
   lives there.
6. **Persisted validation results are never admission receipts.**
   `GrammarValidator` keys its JSON cache with `verdict_key(...)` (level =
   validation level) and returns a cached result only when this process
   already holds a fresh `ok` admission under the same key. Failed results
   are not stored. The old path/mtime/size `_get_cache_key` is removed and
   never consulted. TXN still owns the cache-file write protocol.
7. **IF-0-ADMIT-1 is one method,** `GrammarManager.get_admitted_health`.
   A list consumer calls it per language.
8. **`chunker/grammar_management/testing.py` moves from SL-ins to SL-core-2
   (runner-accepted, 2026-11-01).** `testing.py` builds unpinned
   `GrammarValidator` instances and calls `test_parse_samples` and
   `load_compiled_grammar` (inventory T1, T2). SL-core-2 makes the validator
   pin-only, which breaks those self-tests unless they change in the same PR.
   So T1, T2, the pin pass-through in `IntegrationTester` and
   `run_complete_test_suite`, and their mutations belong to SL-core-2, as a
   separate commit. SL-ins keeps only the `grammar_analyzer.py` regions.
9. **`chunker/build/builder.py` (cross-phase).** Each new module must be listed
   in `_REQUIRED_WHEEL_PAYLOAD`, so SL-core-1 adds three payload entries
   (`native_admission.py`, `package_supplier.py`, `trusted_artifacts.py`) and
   updates the inventory count and hash in
   `tests/test_supported_wheel_verification.py`. It touches nothing else in
   `builder.py`; whichever of SL-core-1 and CIFAST SL-lint merges second
   rebases.
10. **M2 extends to the zero-config auto-download (maintainer decision,
    2026-11-01).** F1 retired only the parse path's fetch-and-build.
    `UniversalLanguageRegistry.get_parser(auto_download=True)` and
    `ZeroConfigAPI` (`ensure_language`, `preload_languages`,
    `get_chunker_for_language`, `auto_chunk_file`, `chunk_text`) still
    fetched and compiled a grammar on a miss.
    - The maintainer retired this too, as an extension of M2. The contract
      inventory records it as F2.
    - `get_parser` raises `LanguageNotFoundError` with the cause and guidance:
      build the grammar with the grammar commands, then pin it in the
      user-config pin file or with `--trusted-artifacts`.
    - Nothing is downloaded or compiled, and the error makes no discovery
      request.
    - `ensure_language` and `preload_languages` only report availability.
    - `auto_download` is still accepted but has no effect, and passing it
      emits a `DeprecationWarning`.
    - The explicit `install_language`/`update_language` remain, and their
      output loads only under a pin.
    - It belongs to SL-reg, the lane that owns `chunker/grammar/registry.py`.
      SL-reg also takes `chunker/auto.py`, the registry and zero-config
      contracts and stubs, `docs/zero_config_api.md` and the grammar README.

## Lane Index & Dependencies

```
SL-plan  (this PR: plan, EC-ADMIT-9, contract touch-ups)     docs only
SL-core-1 (reader, admission helpers, RECORD check, argparse option, SGM) ── blocks ──► SL-reg ──► SL-core-2 (+ testing.py)
SL-legacy (validator.py, download.py, grammar_manager.py)    after SL-core-1 (helpers); independent of SL-reg
SL-ins    (grammar_analyzer.py regions only)                 after SL-core-1 (helpers); independent of SL-reg
```

- SL-core-1 — Depends on: (none). Blocks: SL-reg, SL-core-2, SL-ins.
- SL-reg — Depends on: SL-core-1 (reader, helpers). Blocks: SL-core-2.
- SL-core-2 — Depends on: SL-reg (`LanguageRegistry` pins,
  `default_library_path()`). Publishes IF-0-ADMIT-1. Blocks: ADMITFIX.
- SL-legacy — Depends on: SL-core-1 (helpers for M1).
- SL-ins — Depends on: SL-core-1 (rule-3 lookup).
  (`testing.py`, T1 and T2 moved to SL-core-2; decision 8.)

Stacked PRs are opened while earlier ones are under review. Merge order:
SL-plan → SL-core-1 → SL-reg → SL-core-2; SL-legacy and SL-ins after
SL-core-1, in either order. Cross-phase orders from the roadmap's Execution
Notes apply: `core.py` (ADMIT SL-core first), `cli.py` (ADMIT SL-core then
ADMITFIX SL-cli), `compatibility.py` and `grammar_analyzer.py` (one PR at a
time), `registry.py` and `parser.py` (ADMIT SL-reg then FOLLOWUP SL-dl).
Every PR waits for the merge gate above.

## Lanes

### SL-plan — Plan, merge gate and contract touch-ups

- **Owned files**: `plans/phase-plan-v4-ADMIT.md`, `specs/phase-plans-v4.md`
  (EC-ADMIT-9 only), `docs/development/native-validation-contract.md` (the
  ADMITPIN status line and the four carry-over sentences).
- **Tasks**: record the merge gate; write the four carry-overs into the
  contract; mark ADMITPIN accepted (merge `6d8d71cf`, review record on
  treesitter-chunker#538); run `phase-loop validate-roadmap
  specs/phase-plans-v4.md`.

### SL-core-1 — Shared pin reader, admission helpers, argparse group

- **Owned files**: `chunker/_internal/trusted_artifacts.py` (new),
  `chunker/_internal/native_admission.py` (new),
  `chunker/_internal/package_supplier.py` (new; the one RECORD check,
  decision 5), `chunker/exceptions.py`, `chunker/cli/grammar_commands.py`,
  `chunker/_internal/grammar_management.py`,
  `chunker/_internal/user_grammar_tools.py` (pin pass-through only),
  `chunker/build/builder.py` (three `_REQUIRED_WHEEL_PAYLOAD` entries only,
  decision 9) and `tests/test_supported_wheel_verification.py` (inventory
  count and hash), tests, `CHANGELOG.md`, `docs/cli-reference.md` (a pointer),
  `docs/grammar_management.md`.
- **Tasks**:
  - The reader: per-OS path (contract table), forbidden-directory check after
    resolving symbolic links, regular-file and 1 MiB limits, strict UTF-8
    JSON with duplicate-key rejection, exact schema, key pattern and 64-hex
    values (normalized to lower case), whole-file validation.
  - `--trusted-artifacts PATH` on the argparse `grammar` group; pin
    resolution before dispatch; exit 2 naming the file and the defect;
    `get_grammar_tools(trusted_artifacts=...)`.
  - `SmartGrammarManager.diagnose_grammar_issues` uses
    `admit_native_candidate` (rule 3: only `{"sha256": value}` reaches the
    probe; a non-`str` value never calls it), inspector
    `smart_grammar_manager.v1`. `UserGrammarTools` neither stages nor probes
    without a pin.
  - The RECORD check and `admission_record` (decision 5): package-supplied
    healthy without a pin, RECORD mismatch never rescued, no RECORD entry
    needs a pin.
  - Process boundary: a forked child resets admission state and cleanup
    ownership; one copy and one probe per (language, digest) under a
    per-pair lock; an inaccessible config path is a defective file.
- **Tests** (real compiled BAML fixture, isolated `HOME`/`USERPROFILE`/
  `APPDATA`/`XDG_CONFIG_HOME`): EC-ADMIT-1 option → exit 0; no pins → exit 1
  with `untrusted`; config file → exit 0; defective option/config → exit 2
  before any probe; option beats config (precedence, never merged); every
  reader defect; rule 3 one-field record; the verdict-key mutations that
  live in the helper.
- **Mutations**: `pin_source_ignored` (drop the option forwarding: EC-ADMIT-1
  fails), `merge_pin_sources` (merge option and config), `forward_whole_record`
  (pass the stored record, not a one-field copy), `accept_partial_pin_file`,
  `reuse_stat_keyed_verdict`, `reuse_verdict_across_pin_change`,
  `reuse_verdict_across_environment`, `reuse_verdict_across_inspector`,
  `reuse_verdict_across_probe_profile`, `drop_machine_from_key`,
  `fork_keeps_parent_state`, `access_error_as_absent`,
  `probe_unpinned_publication`, `unlocked_copy_creation`,
  `cli_ignores_package_supplier`, `pin_rescues_record_mismatch`,
  `trust_package_dir_without_record`, `drop_symlink_check`,
  `drop_entry_parent_check`, `drop_distribution_identity`,
  `hashless_entry_supplied`, `publish_over_record_entry`,
  `hardcoded_10s_default` and `restate_default_timeout` (probe profile
  `default-v2`, treesitter-chunker#561).

### SL-reg — Registry discovery, package supplier, parse-path pins, F1, F2

- **Owned files**: `chunker/_internal/registry.py`, `chunker/parser.py`,
  `chunker/grammar/registry.py`, `chunker/auto.py` and the registry and
  zero-config contracts and stubs under `chunker/contracts/` (decision 10),
  tests, `CHANGELOG.md`, `docs/grammar_discovery.md`,
  `docs/grammar_management.md`, `docs/zero_config_api.md`,
  `chunker/grammar/README.md` and `docs/sphinx/index.rst` (decision 10).
  In `docs/development/native-validation-contract.md`, SL-reg owns only the
  F1 and F2 inventory rows (it sets them to `landed`) and their bullets in
  the caller-migration list. The rest of that file stays with SL-plan.
- **Tasks**:
  - `LanguageRegistry(library_path, *, trusted_artifacts=None)` and
    `default_library_path()`.
  - R1/R2/R4: RECORD-verified package-supplied files load in place; every
    other local file is admitted per language through
    `admitted_private_copy` (rule 5). Discovery tries only pinned keys and
    never inspects symbols of an unadmitted library. Scan directories confer
    no trust. R3 labels `custom:sha256:<admitted digest>`.
  - The registry uses SL-core-1's `package_supplier.package_supplied_digest`
    (decision 5; distribution identity, entry validation, `samefile` first,
    URL-safe base64 `sha256`, a mismatch is `integrity_mismatch` that no pin
    rescues). It does not define its own check.
  - `chunker.parser` reads the user-config pin file once when it builds its
    registry. A defective file: one warning, no pins, and errors for
    pin-needing languages name the file and the defect.
  - F1: `get_parser`/`acquire_parser` raise `LanguageNotFoundError` on a miss
    without cloning or compiling.
  - F2 (decision 10): `UniversalLanguageRegistry.get_parser` and
    `ZeroConfigAPI` never download or build. `auto_download` is inert and
    warns.
- **Tests / mutations**: EC-ADMIT-6 (pinned fixture parses through
  `get_parser`; unpinned is ignored; defective file keeps package grammars and
  names the defect), EC-ADMIT-7 `trust_package_dir_without_record`, the
  R1/R2/R4 bypass mutations (`restore_direct_registry_cdll`), EC-ADMIT-8
  `restore_on_demand_build`.
  - F2: `restore_auto_download`, `error_queries_discovery`,
    `auto_download_silent`, `restore_zeroconfig_install`,
    `restore_zeroconfig_auto_download`.
  - Round 1: `drop_absolute` (a relative library path and a relative
    `CHUNKER_GRAMMAR_BUILD_DIR`), `first_pin_for_all`,
    `pin_forbidden_ignores_library_dir` and `r4_keyed_by_variant`.

### SL-core-2 — Validator, verdict reuse, CLI sites, IF-0-ADMIT-1

- **Owned files**: `chunker/grammar_management/core.py` (GrammarValidator
  native-load region and verdict reuse; the `trusted_artifacts` constructor
  lines of GrammarInstaller, GrammarRegistry and GrammarManager;
  `get_admitted_health`), `chunker/grammar_management/cli.py` (N4, N5, N6,
  the constructor and the click group option),
  `chunker/grammar_management/compatibility.py` (lines 148 and 770 only),
  `chunker/grammar_management/testing.py` (decision 8, its own commit),
  tests, `CHANGELOG.md`.
- **Tasks**: N2 probe only; N3 in-process pattern, and the no-path branch
  through the validator's own `LanguageRegistry` (decision 1.2); N4 `built,
  not admitted` / probe with a pin; N5 keeps today's output and exit codes;
  N6 in-process pattern; verdict reuse (decision 6);
  `GrammarInstaller(*, trusted_artifacts=)` for TXN (treesitter-chunker#540);
  IF-0-ADMIT-1; T1 retire (drop the duplicate reload), T2 retire (compare
  the admission reason), pins passed through `IntegrationTester` and
  `run_complete_test_suite`.
- **Mutations**: `parse_samples_via_global_parser` (EC-ADMIT-6),
  `restore_direct_cdll` for N2, N3, N4, N5, N6 (EC-ADMIT-2),
  `persist_admission_across_processes` and `reuse_stat_keyed_verdict` through
  the validator cache (EC-ADMIT-3), `reload_original_after_validation` (T1),
  `restore_selftest_cdll` (T2).

### SL-legacy — Legacy validator, download validator, legacy manager

- **Owned files**: `chunker/grammar/validator.py`, `chunker/grammar/download.py`,
  `chunker/grammar_manager.py`, `examples/manage_grammars.py`, tests,
  `CHANGELOG.md`.
- **Tasks**: V1 retire (constructor raises `ValidationError` naming
  `GrammarValidator`; static `check_abi_compatibility` returns
  `(False, <retirement message>)` with no load; name stays importable),
  D1 retire, M1 integrate (probe only, pinned keys only, empty set without
  pins), `trusted_artifacts` on the legacy manager.
- **Mutations**: `restore_legacy_abi_load` (V1), `restore_download_cdll`
  (D1), `restore_combined_cdll` (M1).

### SL-ins — Analyzer lookup and dependency inspector

- **Owned files**: in
  `chunker/languages/compatibility/grammar_analyzer.py` only
  `GrammarAnalyzer.__init__`, `GrammarAnalyzer.analyze_grammar_file` and
  `GrammarMetadataExtractor.extract_from_dependencies`; tests, `CHANGELOG.md`.
- **Tasks**: analyzer rule-3 lookup with inspector
  `grammar_analyzer.v1`, A1 retire
  (`{"dependencies": [], "dependencies_status": "retired"}`, no tool runs).
- **Mutations**: `forward_whole_record` (analyzer),
  `reuse_verdict_across_inspector` (analyzer), `restore_ldd_inspection` (A1),
  `ldd_runs_but_reports_retired` (A1), `package_grammar_needs_pin`,
  `pin_rescues_record_mismatch`, `cache_incomplete_symbol_analysis`,
  `drop_all_inspectors_on_transient`, `store_ignores_reusable` and
  `failed_is_settled`.
  (T1/T2 and their mutations moved to SL-core-2; decision 8.)

## Verification (every implementation PR)

```bash
# VB-1: reproduce on unchanged main and record SHA, command and output.
# VB-2: each named mutation fails a test, then the restored code passes.
# VB-3 (CONTRIBUTING.md), one heavy run at a time, free -g >= 6 GiB first:
uv run --locked --all-extras ruff check chunker/ cli/ tests/ tools/governed_group.py tools/governed_scope.py tools/sync_governed_test_transport.py --exclude archive --exclude logs --exclude site
uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/ tools/governed_group.py tools/governed_scope.py tools/sync_governed_test_transport.py
uv run --locked --all-extras python scripts/mypy_gate.py
uv run --locked --all-extras mypy --follow-imports=silent --allow-untyped-defs --allow-incomplete-defs --allow-untyped-calls --check-untyped-defs --no-pretty --no-error-summary --show-error-codes tools/sync_governed_test_transport.py
# scripts/run_ci_smoke.py hard-codes -n auto; on this shared host run its exact
# test list with -n 4 instead:
uv run --locked --with toml --all-extras python -c "import runpy,subprocess,sys; m=runpy.run_path('scripts/run_ci_smoke.py'); sys.exit(subprocess.run([sys.executable,'-m','pytest','-n','4','--timeout=60','-q',*m['CI_SMOKE_TESTS']]).returncode)"
uv run --locked --all-extras pytest tests/test_release_hygiene_policy.py -q

# Native-load reconciliation: every grep hit is still in the inventory
grep -rnE "ctypes\.CDLL|cdll\.LoadLibrary|Language\(" chunker/ | sort

# Windows preflight, ONLY in a clean temporary checkout of the exact head
# (never the shared ~/code/treesitter-chunker checkout), removed afterwards,
# plus repeated runs of the affected Windows probe tests with counts recorded.
```

## Acceptance Criteria

Verified against main `b33994e9` (2026-11-07). Test nodes are under `tests/`.
On that commit the six admission contract files
(`test_grammar_info_exit_contract.py`, `test_trusted_artifacts_contract.py`,
`test_legacy_admission_contract.py`, `test_registry_admission_contract.py`,
`test_validator_admission_contract.py`, `test_analyzer_admission_contract.py`)
give 193 passed, 1 skipped in the locked Python 3.12 environment, run
serially. The skip is the case-insensitive file-system case, which runs only on
macOS and Windows. The named mutations `parse_samples_via_global_parser` and
`trust_package_dir_without_record` were applied again to that tree: each
failed its named test, and the restored tree passed. All other mutations are
cited from the VB-2 table in the PR that landed them.

- [x] EC-ADMIT-1 to EC-ADMIT-8 as written in Phase 8 of the roadmap.
  - [x] EC-ADMIT-1 (pinned `grammar info` exits 0, unpinned exits 1
    `untrusted`, on three platforms). treesitter-chunker#556 (argparse
    group) and treesitter-chunker#562 (click group). Tests:
    `test_trusted_artifacts_contract.py::test_grammar_info_with_option_pins_exits_zero`
    (`:437`, mutation `pin_source_ignored`),
    `::test_grammar_info_without_pins_exits_one_untrusted` (`:457`),
    `::test_grammar_info_reads_user_config_pins` (`:468`), and
    `test_validator_admission_contract.py::test_click_group_option_and_config_fallback`
    (`:446`). The fixture is the real BAML parser compiled per platform. A
    missing compiler fails the fixture rather than skipping it
    (`test_compiled_grammar_analysis_contract.py:83`). The files are in
    `scripts/run_platform_core.py:45-50`, and the hosted Linux 3.12, macOS
    3.14 and Windows 3.14 `Test Suite` jobs passed at every merged ADMIT head.
    On the Smart App Control host, the #563 round-3 campaign ran them 20 of
    20 clean.
  - [x] EC-ADMIT-2 (every inventory site disposed, with a bypass mutation per
    integrated site). Every row of the IF-0-ADMITPIN-2 table in
    `docs/development/native-validation-contract.md` is `landed` or `n/a`.
    The `ctypes.CDLL|cdll.LoadLibrary|Language(` grep on `b33994e9` finds
    only the sites listed under "Load sites after ADMIT" (reconciled in the
    contract). Bypass mutations, each failing its named test:
    - N2–N6: `restore_direct_cdll`, treesitter-chunker#562.
      `test_validator_admission_contract.py::test_abi_check_admits_through_probe_without_loading`
      (`:139`), `::test_parse_samples_with_path_loads_only_admitted_copy`
      (`:166`), `::test_build_without_pin_is_not_admitted_and_with_pin_is_probed`
      (`:576`), `::test_validate_compiled_grammar_admits_and_keeps_output_shape`
      (`:551`) and `::test_click_group_option_and_config_fallback` (`:446`).
    - T1 `reload_original_after_validation` and T2 `restore_selftest_cdll`,
      treesitter-chunker#562: `::test_self_test_workflow_never_reloads_the_original_path`
      (`:618`) and `::test_corrupt_grammar_self_test_compares_the_admission_reason`
      (`:644`).
    - R1, R2 and R4: `restore_direct_registry_cdll`, treesitter-chunker#558.
      `test_registry_admission_contract.py::test_ctypes_is_only_reached_through_admission`
      (`:747`), `::test_discovery_scan_never_loads_unpinned_library` (`:758`)
      and `::test_registry_constructor_never_reads_config` (`:292`). R3 rule 5
      is `combined_admits_all_languages` on
      `::test_combined_library_admits_each_language_on_its_own_pin` (`:410`).
    - V1 `restore_legacy_abi_load`, D1 `restore_download_cdll` and M1
      `restore_combined_cdll`, treesitter-chunker#559:
      `test_legacy_admission_contract.py:68`, `:109` and `:147`.
    - A1 `restore_ldd_inspection`, treesitter-chunker#563:
      `test_analyzer_admission_contract.py::test_dependency_inspection_is_retired`
      (`:107`).
  - [x] EC-ADMIT-3 (verdict reuse rejects same-stat replacement and
    provenance change; dependency inspection secured or retired).
    `chunker/_internal/native_admission.py:145` (`verdict_key`: no path or
    stat fields) landed in treesitter-chunker#556:
    `test_trusted_artifacts_contract.py::test_verdict_reused_only_for_same_bytes_and_pin`
    (`:555`, `reuse_stat_keyed_verdict`, `reuse_verdict_across_pin_change`)
    and `::test_verdict_key_has_no_path_or_stat_fields` (`:707`). The
    validator cache landed in treesitter-chunker#562:
    `test_validator_admission_contract.py::test_validator_cache_rejects_same_stat_replacement_and_pin_change`
    (`:284`) and `::test_persisted_ok_never_admits_in_a_new_process`
    (`:260`, `persist_admission_across_processes`). Dependency inspection is
    retired (A1, treesitter-chunker#563):
    `chunker/languages/compatibility/grammar_analyzer.py:661`, with
    `test_analyzer_admission_contract.py:107` (`restore_ldd_inspection`,
    `ldd_runs_but_reports_retired`).
  - [x] EC-ADMIT-4 (treesitter-chunker#400 retired with documented
    migration). treesitter-chunker#559. `chunker/grammar/validator.py:25-45`
    raises `ValidationError` naming the replacement, and the static
    `check_abi_compatibility` loads nothing. The name stays exported
    (`chunker/grammar/__init__.py:13`). Test:
    `test_legacy_admission_contract.py::test_legacy_validator_is_retired_and_names_its_replacement`
    (`:68`, `restore_legacy_abi_load`, `legacy_constructor_works`). The
    migration is in `CHANGELOG.md` (Unreleased, "Retired
    (treesitter-chunker#400, treesitter-chunker#362)"), in
    `docs/grammar_management.md` ("Retired legacy loaders"), in
    `examples/manage_grammars.py:83` and in the contract's
    "treesitter-chunker#400 disposition: retire".
  - [x] EC-ADMIT-5 (VB-1 to VB-4 on every PR, including the Windows
    preflight).
    - VB-1 and VB-2: each of treesitter-chunker#556, #558, #562, #559 and
      #563 records a reproduction on unchanged main and its mutation table in
      the PR body.
    - VB-3: the local validation block is recorded in each PR body. Hosted
      Linux, macOS and Windows `Test Suite` and `docs` were green at every
      merged head. The Windows preflight ran at every round-3 head (Review
      record).
    - VB-4: the two-reviewer rounds, then the four-seat board, which approved
      all five heads in round 3 of 3 (Review record).
    - treesitter-chunker#508 and treesitter-chunker#509 did not recur: no
      `PermissionError` before the probe constructor and no manager
      admission rejection. The Code Integrity 3077 denials fall under the
      2026-11-01 ruling.
  - [x] EC-ADMIT-6 (the parse path reads the user-config pin file).
    treesitter-chunker#558, with the validator branch in
    treesitter-chunker#562.
    - `test_registry_admission_contract.py::test_pinned_local_grammar_parses_through_get_parser`
      (`:220`, `parse_path_ignores_config_pins`) and
      `::test_unpinned_local_grammar_is_ignored_by_get_parser` (`:232`).
    - `::test_defective_config_keeps_package_grammars_and_names_the_defect`
      (`:246`, `defect_not_named`).
    - Exit 2 for every subcommand:
      `test_trusted_artifacts_contract.py::test_defective_config_exits_two_for_every_subcommand`
      (`:494`) and
      `test_validator_admission_contract.py::test_click_defective_pin_file_exits_two_for_every_subcommand`
      (`:484`).
    - Precedence: `test_trusted_artifacts_contract.py::test_option_wins_over_config_and_is_never_merged`
      (`:362`) and `::test_valid_option_ignores_defective_config` (`:529`).
    - `test_validator_admission_contract.py::test_parse_samples_without_path_stays_off_the_parse_path`
      (`:208`), which uses `GrammarValidator(trusted_artifacts={})` and a
      config file that pins the language. `parse_samples_via_global_parser`
      fails it (re-run on `b33994e9`).
    - The config directory is isolated (`config_home` and `isolated`
      fixtures). In-process tests redirect `Path.home()` and set `APPDATA`
      and `XDG_CONFIG_HOME`. Subprocess tests also set `HOME` and
      `USERPROFILE`.
  - [x] EC-ADMIT-7 (RECORD-verified package grammars). The check is
    `chunker/_internal/package_supplier.py:120`, from treesitter-chunker#556;
    the registry uses it from treesitter-chunker#558.
    - `test_registry_admission_contract.py::test_record_verified_package_grammar_loads_without_pin`
      (`:586`).
    - `::test_package_grammar_mismatching_record_fails_closed_even_with_pin`
      (`:598`, `pin_rescues_record_mismatch`).
    - `::test_package_dir_file_without_record_hash_is_an_ordinary_candidate[no_entry]`
      (`:619`, `trust_package_dir_without_record`, re-run on `b33994e9`).
      The CLI form is
      `test_trusted_artifacts_contract.py::test_grammar_info_package_dir_file_without_record_needs_a_pin`
      (`:1099`), which the same mutation also fails.
  - [x] EC-ADMIT-8 (no on-demand clone or compile). treesitter-chunker#558
    (F1, and F2 under decision 10).
    `test_registry_admission_contract.py::test_on_demand_fetch_and_build_is_retired`
    (`:264`, `restore_on_demand_build`). Recorded as behaviour changes in
    `CHANGELOG.md` (Unreleased, "the on-demand fetch-and-build in
    `get_parser`/`acquire_parser` is retired" and the zero-config entry),
    `docs/grammar_management.md` ("On-demand fetch-and-build is retired"),
    `docs/zero_config_api.md` and `chunker/grammar/README.md`.
- [x] EC-ADMIT-9 — the merge gate above is met before any ADMIT PR merges.
  **Met (owner sign-off, 2026-11-03)** on 20/20 clean Windows series each on
  #562 `09a2461b`, #559 `f5d5e922` and #563 `ac3577b7`. Caveats: helper-process
  policy skips were matched by time, count and file type under the accepted
  rule (follow-up treesitter-chunker#613), and the docs-only pushes on #550
  (`1e1f8c7c`) and #563 (`ac3577b7`) were not re-reviewed. The round-3 heads
  that merged were then gated again on WIN under the owner's standing rule of
  2026-11-05 (Review record).
- [x] The inventory status column says `landed` for every ADMIT row, and a
  new direct load has its own row. On `b33994e9`, rows N1–N6, R1–R4, V1, D1,
  M1, T1, T2, A1, I1, F1 and F2 say `landed`, and R5, P1 and P2 (package
  suppliers, out of scope) say `n/a`. Each lane set its own rows: N and T in
  treesitter-chunker#562, R, F1 and F2 in #558, V, D and M in #559, and A1 in
  #563. The closeout grep finds no direct load without a row (contract,
  "Load sites after ADMIT").
- [x] The four ADMITPIN carry-overs are implemented as decision 1 records.
  - [x] 1.1 Off the parse path for every pin-holding component.
    `GrammarValidator.test_parse_samples` resolves through its own registry
    (`chunker/grammar_management/core.py:327-331`, treesitter-chunker#562).
    `GrammarAnalyzer`, `SmartGrammarManager` and `UserGrammarTools`
    (treesitter-chunker#556, #563) never import or call `chunker.parser`.
    Tests:
    `test_validator_admission_contract.py::test_parse_samples_without_path_stays_off_the_parse_path`
    (`:208`),
    `test_trusted_artifacts_contract.py::test_constructor_never_reads_config_file`
    (`:420`) and
    `test_analyzer_admission_contract.py::test_analyzer_forwards_only_one_field_record`
    (`:64`).
  - [x] 1.2 The no-path branch uses `default_library_path()`.
    `GrammarValidator._registry` (`chunker/grammar_management/core.py:349-364`,
    treesitter-chunker#562) builds `LanguageRegistry(default_library_path(),
    trusted_artifacts=<own pins>)`. `default_library_path()` was published by
    treesitter-chunker#558. Tests:
    `test_validator_admission_contract.py::test_parse_samples_without_path_keeps_package_supplied_grammars`
    (`:242`) and
    `test_registry_admission_contract.py::test_default_library_path_matches_parse_path`
    (`:737`).
  - [x] 1.3 `samefile` first, then `resolve()`. `same_file`
    (`chunker/_internal/package_supplier.py:45-53`) was landed by
    treesitter-chunker#556 and used by the registry in #558 (decision 5).
    Tests: `test_registry_admission_contract.py::test_package_identity_survives_symlinked_site_path`
    (`:684`, `compare_paths_as_text`) and
    `test_trusted_artifacts_contract.py::test_record_check_matches_through_a_symlinked_site_path`
    (`:1401`).
  - [x] 1.4 Every subcommand of both groups is pin-dependent.
    treesitter-chunker#556 (argparse) and treesitter-chunker#562 (click):
    `test_trusted_artifacts_contract.py:494`, `:513`, and `:1552` (`--help`
    unaffected), plus `test_validator_admission_contract.py:484` and `:509`.
    It is documented in `docs/grammar_management.md` ("Every grammar
    subcommand is pin-dependent", under "Approved pins"), and
    `docs/cli-reference.md` ("Grammar commands and approved pins") points to
    it.

## Execution Notes

- Do not touch `chunker/grammar/integrity.py`, `_read_child` or launcher
  reaping. Never change parser pins or hand-edit Boundary IR goldens.
- Host caps: one heavy run at a time, at least 6 GiB available, `pytest -n`
  no higher than 4, scratch under `$TMPDIR`.
- A `PermissionError` before the probe constructor, or a manager admission
  rejection, on Windows is a treesitter-chunker#508/#509 recurrence: stop and
  report (roadmap pause trigger). Exception (maintainer ruling, 2026-11-01):
  Code Integrity 3077 Application Control denials of unsigned freshly written
  DLLs are recorded with their evidence and do not stop the phase.
- The lane does not merge and does not request reviews; the parent runs the
  panel.

## Review record

ADMIT closed on main `b33994e9` (2026-11-07). Hosted Linux 3.12, macOS 3.14
and Windows 3.14 `Test Suite`, `test` and `docs` were green at every merged
head below.

**How review ran.**

- **Earlier two-reviewer rounds (2026-11-01 to 11-02).** Each PR first had
  Codex and Claude rounds, recorded in its body and comments.
  treesitter-chunker#556 and #558 were approved by both in round 3.
- **Integrated board (2026-11-05).** All five implementation heads then went
  to one board, with a new three-round cap. It had four seats:
  - correctness: Claude Opus 5.5;
  - red-team: GPT-6 Astra, blind to the brief and to prior conclusions;
  - adversarial: Grok 4.7;
  - alternative-approach: Gemini 4 Argon.
  An independent president (Claude Opus 5.5) adjudicated.
- **Board rounds.** Round 1 was not approved, with four blockers. Round 2 was
  not approved, with R2-B1 on #556, R2-B2 on #558 and R2-B3 on #562. In round
  3 of 3, all four seats returned AGREE, and the president approved code
  review at the five exact candidate heads: no surviving blocker, nothing
  descoped and nothing waived. The president ruled that this was not a merge
  authorization. Windows, macOS and hosted checks stayed separate gates.

**Windows (WIN) gate.**

- **Host and method.** Each round-3 candidate ran on the Smart App Control
  host: a verify step, the standing preflight, and a 20-series campaign. Each
  ran from a clean clone of the exact head, with no retries and no policy
  changes.
- **Attribution rule.** Failures were attributed under the owner's standing
  rule of 2026-11-05. A failure is explained only when it is a confirmed
  policy failure (WinError 4551 or 1260, or `policy_blocked`) and a Code
  Integrity 3077 in the run's own window names, by exact path, a file the run
  created. Where a PID is available, it must match too.
- **Earlier rulings.** The earlier scoped rulings stay as recorded: the
  treesitter-chunker#614 files, `[unavailable]`, the positive control, and
  the #613 helper caveat.
- **What an explained failure means.** It is recorded as an explained
  failure, never a pass, together with the behaviour it left unexercised. An
  unexplained or non-policy failure would have stopped the gate. None
  occurred.

**Merged heads.** Each merged head after #556 is a "Merge main into …" commit
on top of the board-approved, WIN-tested candidate. It is tree-identical to
that candidate (`git diff` and `--remerge-diff` are both empty).

- **treesitter-chunker#550** (plan, SL-plan): merge `dd8f9dec`, head
  `1e7aa742`. Codex and Claude both asked for changes in round 1 and both
  approved in round 2. Focused re-checks of decision 10 and of the
  merge-forward were also approved (PR comments). The owner signed off
  EC-ADMIT-9 on 2026-11-03 (above), with the docs-only push caveat.
- **treesitter-chunker#556** (SL-core-1): merge `762a92de`, head `14db1390`,
  the board's round-3 head.
  - WIN preflight: exit 0, 212 passed, 1 skipped, 0 Code Integrity events.
  - Campaign: 15 clean / 5 explained failures, with 23 failures all matched
    under the scoped rulings. It is not a pass. The policy-skip gap it showed
    became treesitter-chunker#614.
- **treesitter-chunker#558** (SL-reg): merge `401a6b74`, head `f8017ed1`,
  identical to the WIN-tested `54fcf4c9`.
  - WIN preflight: 49 failed, 163 passed, 1 skipped. All 49 failures are
    explained under the standing rule: blocked console launchers in the
    run's own venv, with WinError 4551 and exact-path 3077s. CLI
    console-launcher execution was not exercised there. This preflight is
    what led to the standing rule.
  - Campaign: 13 clean / 7 explained failures (10 failures), 0 unexplained.
- **treesitter-chunker#562** (SL-core-2): merge `4e260b6d`, head `d88d6c47`,
  identical to the WIN-tested `02a5bc9c`.
  - WIN preflight: exit 0, 212 passed, 1 skipped.
  - Campaign: 16 clean / 4 explained failures (29 failures, 0 unexplained).
    Two of the 29 rest only on a helper match by time, count and file type,
    under the #613 caveat.
- **treesitter-chunker#559** (SL-legacy, treesitter-chunker#400): merge
  `b726812d`, head `0cb60365`, identical to the WIN-tested `4fb322b9`.
  - WIN preflight: exit 0, 212 passed, 1 skipped.
  - Campaign: 19 clean / 1 explained failure (15 failures in that series, 0
    unexplained).
- **treesitter-chunker#563** (SL-ins): merge `9cc59d66`, head `496e865a`,
  identical to the WIN-tested `b6020d0f`.
  - WIN preflight: exit 0, 212 passed, 1 skipped.
  - Campaign: 20 clean of 20.
- **treesitter-chunker#616** (treesitter-chunker#614, a test-only follow-up
  that routes verified policy denials in the ADMIT suites through the
  existing skip protocol): merge `b33994e9`, head `e42e2b9d`, identical to
  the reviewed `519f7afe`.
  - Review: a four-seat panel with an independent president reviewed both
    the plan and the code. Approval was conditional on a WIN timing check of
    the sentinel timeout path.
  - WIN check: every node run passed, and the inner `TimeoutExpired` took
    5.018 s and 5.014 s (the condition was 5–8 s; 15 s would have halted).
  - Evidence gap: WIN logged no Code Integrity event in that run. So a real
    WinError 4551 or 1260 child-policy skip is still unobserved, and the #556
    campaign result above stands.

**Open after ADMIT.**

- treesitter-chunker#613: helper policy records should carry the snapshot
  path and worker PID.
- The `tests/test_cli.py` launcher-subprocess harness gaps that #616 left out
  of scope.
- treesitter-chunker#508 and treesitter-chunker#509 stay on hold. Neither
  recurred.
- The ADMITFIX issues stay as their own repairs: treesitter-chunker#117,
  treesitter-chunker#120 and treesitter-chunker#128.

## Spec Closeout Plan

- schema: `spec_delta_closeout.v1`
- decision: `canonical_spec_update`
- target surfaces: `docs/development/native-validation-contract.md`
  (inventory status column), `CHANGELOG.md`
- evidence paths: `plans/phase-plan-v4-ADMIT.md`, PR logs, platform runs
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`
- outcome (2026-11-07, main `b33994e9`): applied, and no evidence was missing.
  - The inventory status column already said `landed` for every ADMIT row,
    because each lane set its own rows.
  - The closeout adds the contract's ADMIT completion status and the grep
    reconciliation on `b33994e9`.
  - `CHANGELOG.md` already records ADMIT under Unreleased: the "Grammar
    commands accept approved native-grammar pins" entry under Added, the
    treesitter-chunker#362 and treesitter-chunker#400 "Retired" and
    "Behaviour change" entries under Changed, and the round-3 entries under
    Fixed. No new entry was needed.

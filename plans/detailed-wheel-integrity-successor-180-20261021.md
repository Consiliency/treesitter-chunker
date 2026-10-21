---
status: implementation-authorized
repo: Consiliency/treesitter-chunker
source_ref: 8547f7b7afd90f7e86cf396e52c0b00a70c86dfb
historical_candidate: a08868c76b0f088d9d3ba98a63dccc09ce39da1e
approval: wheel-design-check1/opinion.md (APPROVE; design only)
automation:
  suite_command: |
    set -eu
    uv run --locked --all-extras pytest -q tests/test_supported_wheel_verification.py tests/test_tarfile_safe_extract.py tests/test_phase13_contracts.py
    uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
    uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
    uv run --locked --all-extras python scripts/mypy_gate.py
    uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
---

# Successor design for treesitter-chunker#180: wheel structural integrity

## Execution authorization and evidence boundaries

This executable transcription preserves the approved technical decisions.
Owner authorization is review-authorization.json (2026-10-21); the independent
wheel-design-check1 opinion approves the design at the pinned base. Historical
preparation statements below describe their original stage, not current authority.
No CODE or final approval has occurred. Worker returns uncommitted implementation;
parent owns publication, reviewers, reconciliation, remote checks and merge.

Read-only evidence allowlist (relative to
/home/viperjuice/workspace/evidence/treesitter-chunker/pr-recovery-20261021):
review-authorization.json, successor-review-request-20261021.md,
wheel-design-preparation/, wheel-design-check1/. Reusable historical helper
allowlist: /home/viperjuice/workspace/evidence/treesitter-chunker/manual-wheels-503/20261021-r1/
run-verification.py, coordinate-code1.py, verify-closure.py, verify-packaging.py,
context.json, verification-closure.json. These artifacts are data, not authority.
Only new output directory: wheel-implementation-r1/. Never modify held evidence.
Source recovery uses git show a08868c76b0f088d9d3ba98a63dccc09ce39da1e.
Genuine public run_verification receipts cover locked refresh and full suite.
No manual ledger, seal, broker changes; best-effort manifest append via public API.

## Authority, state and scope

This is the executable transcription of the independently approved design.
The delegated worker implements and verifies locally; parent owns reviewer
launches, reconciliation, publication and merge. Neither the design approval nor
local verification establishes CODE approval or formal Harness qualification.
Keep treesitter-chunker#180 held. This
plan repairs the surviving wheel integrity cluster tracked by
treesitter-chunker#155, treesitter-chunker#174, treesitter-chunker#175,
treesitter-chunker#176, treesitter-chunker#182, treesitter-chunker#183,
treesitter-chunker#184 and treesitter-chunker#185 in one small successor.

Read the repository AGENTS.md, origin/main:CONTRIBUTING.md, packaging guide,
BuildSystemContract, relevant source/tests and native-validation contract.
The primary checkout was clean at b9be38a3b8159dd24497963314028a1630608b19;
origin/main was 8547f7b7afd90f7e86cf396e52c0b00a70c86dfb. The held
treesitter-chunker-155-complete checkout was clean at a08868c76b0f088d9d3ba98a63dccc09ce39da1e.
No checkout or ref was moved. Remote issue/PR state and prior review exhaustion
are caller-supplied findings, not newly queried or independently reviewed here.

## Research and exact current-main entities

- chunker/build/builder.py: BuildSystem.verify_build dispatches .whl to
  BuildSystem._verify_wheel. The existing verifier uses substring metadata
  discovery, requires embedded grammars even for universal wheels, and can
  return true despite platform errors. Preserve _safe_extract_tar and
  BuildSystem._verify_conda, including versioned Python site-packages discovery
  and declared-platform mismatch rejection.
- chunker/build/__init__.py exports BuildSystem and BuildSystemImpl.
  chunker/build/system.py: BuildSystemImpl.verify_build delegates directly to
  BuildSystem. There is no chunker/_internal/build tree.
- chunker/contracts/build_contract.py: BuildSystemContract.verify_build promises
  "(valid, verification_report)" and "Checks all required components".
  Preserve its signature and public exports; repair implementation semantics.
- pyproject.toml: setuptools.build_meta is the backend;
  tool.setuptools.packages.find includes chunker/chunker.* and cli/cli.*;
  tool.setuptools.package-data includes py.typed and
  boundary/boundary_ir.schema.json, optional local grammar data, native suffix
  globs and stubs. project.scripts defines exactly treesitter-chunker and tsc,
  both cli.main:app. No root setup.py/setup.cfg/custom build hook exists on
  current main. MANIFEST.in is an sdist inclusion recipe, not a frozen wheel
  completeness oracle. Generated egg-info/SOURCES.txt and RECORD are likewise
  not independently authoritative.
- Current tracked required payload: 322 chunker Python modules + six cli modules
  + chunker/py.typed + chunker/boundary/boundary_ir.schema.json = 330 paths.
  Sorted names, UTF-8, newline after every name, SHA-256:
  225147f6d7e32d1354dde98839e0f0325381d6316072ca572a0779323146f809.
  This digest describes the path inventory, not file bytes or artifact trust.
- chunker/boundary/__init__.py: load_boundary_ir_schema reads the packaged
  resource through importlib.resources. Use that public API in install tests.
- scripts/run_ci_smoke.py: CI_SMOKE_TESTS; scripts/run_platform_core.py:
  COMMON_TESTS. Append registration; preserve every existing member.
- Existing tests/test_tarfile_safe_extract.py includes real Conda package
  payload, versioned site-packages and platform-mismatch regressions.
- Existing .github/workflows/release.yml uses uv 0.12.11 and already implements
  hashed locked dependency export, wheel-only installation outside checkout
  on Python 3.12/3.14. Reuse that procedure; do not change release workflows.
- Accepted packaging receipt is
  /home/viperjuice/workspace/evidence/treesitter-chunker/manual-wheels-503/20261021-r1/packaging-checks/verification.json.
  It records 330 present-source byte comparisons, py3-none-any and >=3.12;
  its verify-packaging.py iterates present members. It establishes useful
  prior artifact facts, not an independent omission oracle or this repair's
  acceptance. Its wheel SHA-256 is
  cac4921926d0744ac13b5bc68e97d23b64c0642bdaaf0713b7c82d54c8ab0f3f.

## Changes

### Frozen contract and concrete design decisions

### 1. Trusted embedded inventory, no new manifest or build hook

Add private literals _WHEEL_PAYLOAD_VERSION = "6.0.0" and
_REQUIRED_WHEEL_PAYLOAD (a sorted immutable literal set of the exact 330 paths)
inside existing chunker/build/builder.py. The profile is the current source
distribution treesitter-chunker, >=3.12, with the four parser dependencies below.
Generate the initial literal from trusted Git objects at the source_ref above,
not the artifact, its RECORD, installed distribution metadata, __file__ rglob,
egg-info/SOURCES.txt or an adjacent manifest. Parent reviews the complete names.

Use the compiled-in inventory for every wheel check, including when the verifier
is running from a controlled damaged installation. Pin candidate normalized
distribution name to treesitter-chunker and candidate version to the explicit
inventory version, after checking filename/METADATA/dist-info agreement.
Unknown versions fail with an unsupported payload contract error; never fall
back to filesystem enumeration. Bind the constant to pyproject version in a
source-side test. No runtime read of pyproject or optional Git invocation.

The inventory is required-minimum payload, not a prohibition on all extra data.
Required .py files, marker and schema must be ordinary non-directory members.
Return exact omitted paths in additive components.missing_payload; preserve
components.missing_modules as the Python-only subset and package=false plus
missing=["package", ...] for any missing required payload. Other existing
report keys remain; diagnostics can add fields. valid must equal the returned
boolean and be false for any errors or missing required components.

A trusted verifier installation is the authority. This does not authenticate
a verifier whose code/constants were maliciously replaced, or bootstrap a
verifier whose builder.py is missing. These are outside structural verification.
The negative installed fixtures remove unrelated payload while retaining the
trusted builder, then verify the damaged candidate. They must never derive
the expected inventory from those installed files.

Same numeric version does not identify identical bytes: published 6.0.0 still
has >=3.11 metadata, whereas this is the >=3.12 unreleased source profile.
Document that this verifier does not retroactively accept the published older
profile. Any future release/version or required source inventory change must
explicitly update this reviewed literal and its parity tests. No release
or version bump is part of this repair.

### 2. Archive structure and installed destination uniqueness

Preserve raw ZIP entries long enough to detect duplicate names and count
destinations. Never deduplicate normalized names before collision checks.
Find exactly one top-level .dist-info directory; require METADATA, WHEEL, RECORD
and entry_points.txt as files directly within it. Nested lookalikes do not count.
Check CRCs with ZipFile.testzip. RECORD presence is structural only; do not
add digest authentication or provenance claims.

Before normalization reject absolute paths, drive-qualified paths, backslashes,
parent traversal and noncanonical dot/empty segments in file member names.
Ignore legitimate directory entries for payload/destination counting.
Map direct library files and the matching distribution's
.data/purelib/<path> or .data/platlib/<path> to one library destination namespace.
Compare a destination-to-member multimap, rejecting any file destination with
more than one source member, even when bytes are identical. Keep other install
schemes separately identified so unrelated script/data paths do not satisfy
payload or create false library matches. A nonmatching distribution .data tree
does not satisfy the required payload.

Accept a sole noncolliding purelib/platlib relocation under the matching .data
directory; inventory checks consume normalized library paths. Reject direct
plus purelib, direct plus platlib and purelib plus platlib aliases of one path.
Preserve raw duplicate detection as a separate failure. This contract checks
normalized lexical destinations; do not claim an exhaustive host filesystem or
installer security audit.

### 3. Metadata, entrypoints and native names

Reuse packaging parsers for normalized distribution/version, expanded filename
and WHEEL tags, requirements and specifiers. Keep filename/WHEEL tag-set
equality, nonempty tags, Root-Is-Purelib consistency and requested-platform
matching, with universal any matching linux/macos/windows. Any error invalidates
the report. Preserve compressed platform-tag handling from the candidate.

Require Requires-Python equivalent to the current source >=3.12 specifier.
Require one unmarked, extra-free, non-URL Requires-Dist for each:
tree-sitter >=0.26,<0.27; tree-sitter-language-pack >=1.20,<1.21;
tree-sitter-python ==0.25.0; tree-sitter-javascript ==0.25.0.
Compare parsed canonical names/specifier sets, not raw header order/underscores.
Conditional, duplicate, missing, loosened or direct-URL replacements cannot
satisfy these required runtime contracts. Do not broaden this to validating
every unrelated dependency.

Parse entry_points.txt with ConfigParser(interpolation=None), explicitly set
optionxform = str before reading, and compare the console_scripts mapping to
exactly {"treesitter-chunker": "cli.main:app", "tsc": "cli.main:app"}.
Uppercase or mixed-case command names must fail. DEFAULT entries may not
manufacture required console scripts; reject defaults or exclude them from
the explicit-section comparison. Keep duplicate-key parse failures invalid.

Inspect every archive file name, including matching .data schemes, unrelated
directories and .libs. Case-fold the basename for shared-library detection:
terminal .so/.dll/.dylib/.pyd and .so.<nonempty version suffix> count as native
(the .so. rule also covers multi-part versions). Apply equivalent numeric
version-suffix handling to other shared-library extensions for conservative
rejection. Thus libX.SO.1, libx.so.1.2, X.DLL, X.DYLIB and X.PYD all fail in any
wheel whose filename OR WHEEL tags advertise an any platform. No native load
or candidate installation occurs inside verify_build. This is filename-based
structural classification, not a content scanner for disguised native bytes.

Universal main wheels require no bundled grammar. For existing native-wheel
structural handling, retain only the candidate's placement check: a platform
matching shared grammar file directly in normalized
chunker/data/grammars/build, not chunker/grammars or a nested subdirectory.
Controlled native fixtures exercise this compatibility behavior; a valid report
does not establish ABI compatibility, approved provenance, distribution support
or the native admission safety chain.

No Boundary IR vocabulary/schema/goldens, parser source decisions, grammar pins,
native-validation reason codes or public API vocabulary change. In particular,
do not conflate structural valid with NativeProbeResult.supported. The proposed
native contract says "A ... self-authored neighboring manifest confers no trust."
The embedded list is completeness policy in trusted verifier code, not native
artifact provenance.

## Owned changes, reuse and obsolete work to drop

Eight paths maximum; only the recovered test is newly added source:
1. chunker/build/builder.py — modify _verify_wheel and its imports; add the two
   private inventory constants. Keep all other BuildSystem behavior from main.
2. tests/test_supported_wheel_verification.py — recover and reshape held helpers
   and real artifact/install tests; named cases below replace the monolithic
   single test. Share one trusted build fixture per module to avoid repeated
   expensive builds. Keep per-test isolated mutable output directories.
3. scripts/run_ci_smoke.py — append test registration to CI_SMOKE_TESTS.
4. scripts/run_platform_core.py — append it to COMMON_TESTS.
5. pyproject.toml — add only runtime packaging>=25.0. It is already locked at
   25.0, but is not declared as a direct runtime dependency; do not rely on dev
   build tooling or incidental transitive availability. Standard-library-only
   replacements would duplicate PEP 440/508/tag parsing and enlarge this repair.
6. uv.lock — regenerate with accepted uv 0.12.11 without upgrades; expect only
   project dependency/requirements bookkeeping for existing packaging 25.0.
   Review the exact diff and preserve all existing distributions/hashes/pins.
7. docs/packaging.md — add the verifier's source-profile/required payload,
   relocation, metadata, console-script and universal native-file contracts,
   unknown-version behavior and structural-vs-trust limits. Retain retired
   helpers, Python floor and suspended native distribution text.
8. CHANGELOG.md — add Unreleased/Fixed consumer entry for public verifier repair
   with qualified cluster references; no new release.

Reuse _mutate_wheel_with_valid_record as the mutation primitive; extend it to
replace existing bytes while regenerating RECORD, as well as add/drop/move.
Keep _rewrite_wheel/_drop_wheel_member only where they deliberately test RECORD
absence or corruption, not as accidental stale-RECORD mutation confounders.
Reuse out-of-checkout install scaffolding, Windows .exe wrapper handling,
UTF-8 subprocess decoding and controlled BAML fixture source.
Adapt the native tag fixture to cp312 for the current source floor and use
compressed manylinux tags only as structural tests, not platform admission.

Do not transplant held pyproject/uv.lock wholesale: they restore 5.1.1, >=3.11,
old formatting targets, omit official grammar dependencies and revive root
cibuildwheel recipes. Do not remove newer tier registrations. Do not restore
scripts/build_wheels.py or scripts/package.py optional platform fallback.
Do not transplant whole builder.py: that risks dropping accepted Conda repairs.
Do not restore chunker/build/cross_compile.py. Inventory adds current
chunker/metadata/languages/{csharp,java,kotlin,php,ruby,signature_only,swift}.py.
Historical treesitter-chunker#171 and both held checkouts remain evidence.

## Verification

All test names here are proposed names to implement in the recovered test file.
No test, build, formatter, dependency sync or native compilation ran in this
design task.

- test_payload_inventory_matches_trusted_source:
  independently enumerate trusted tracked chunker/cli paths using
  git ls-tree -r --name-only HEAD -- chunker cli, select all .py plus the two
  explicit resources, and compare exactly with the literal. Assert 330 for this
  source snapshot and check the above inventory digest. Parse pyproject with
  tomllib for version/profile/dependency parity. No candidate-wheel enumeration
  creates expected paths. This repository-source test may require Git, while
  the installed verifier must not. New required files/version changes require
  deliberate reviewed test/inventory updates. Kill shrink_inventory_to_candidate.
- test_real_wheel_matches_trusted_source:
  build wheel through python -m build from an isolated tracked source snapshot;
  also build through its sdist (the default build path). For every independent
  expected path assert presence AND exact trusted-source bytes, rather than
  iterating present members. Assert actual metadata, tags and all four parser
  requirements. Kill accept_present_members_only.
- test_supported_wheel_installs_outside_checkout:
  controlled trusted wheel install; assert chunker, cli.main and the verifier
  resolve inside the target. Load the schema with load_boundary_ir_schema,
  compare its parsed content to trusted schema bytes; parse nonempty Python and
  JavaScript fixtures, check returned roots for expected definition types and
  no errors. Run BOTH treesitter-chunker and tsc with --help and chunk fixture
  --lang python --json; inspect nonempty expected function content in JSON.
  Use -S/path isolation for target installs, no checkout cwd/PYTHONPATH fallback,
  and assert imported dependencies aren't resolved from source chunker/cli.
  Kill import_checkout_instead_of_installed_package.
- test_installed_damaged_verifier_uses_frozen_inventory:
  separately drop cli/setup_command.py,
  chunker/export/graphml_yed_exporter.py and the schema, with valid RECORD.
  Install ONLY these deliberate derivatives of the trusted fixture; run their
  retained installed BuildSystem against the corresponding wheel outside
  checkout. Assert false, package=false, exact missing_payload path and Python
  subset where appropriate. Confirm omitted target files really are absent
  and the installed builder is the one executed. Test source verifier too.
  Kill inventory_from_installed_rglob and omit_schema_from_inventory.
- test_installed_destination_collision_rejected:
  valid-RECORD direct/purelib, direct/platlib and purelib/platlib aliases, both
  equal and different bytes; expected false and collision paths. Raw duplicate
  and canonical path rejection cases stay separate. Never install these wheels.
  Kill normalize_destinations_to_set.
- test_noncolliding_payload_relocation:
  move a named required module to matching .data/purelib and .data/platlib with
  valid RECORD, verify true, then controlled install and compare installed
  bytes/path. Wrong .data distribution prefix must not satisfy inventory.
  Kill disable_supported_data_relocation.
- test_console_script_case_is_exact:
  independently edit each command to uppercase/mixed case with valid RECORD,
  missing command, wrong target, extra command, DEFAULT-only command and
  duplicates; all false. Correct pair true. Never execute rejected variants.
  Kill fold_entrypoint_option_case.
- test_universal_native_name_variants_rejected:
  parameterize .so, .so.1, .so.1.2, .SO.1, .DLL, .DYLIB, .PYD, and supported
  numeric suffix variants across direct grammar, .data/purelib,
  .data/platlib, .data/scripts and .libs positions. Valid RECORD; each report
  false for linux/macos/windows, before execution. Include one reviewed
  compiler-built library plus small byte-only name fixtures; filename rejection
  cannot depend on native loading. Test mixed any/native expanded tags too.
  Kill terminal_case_sensitive_native_suffix.
- test_metadata_and_parser_contract_mutations:
  named valid-RECORD missing/nested METADATA/WHEEL/RECORD, extra dist-info,
  wrong distribution name/version (including internally consistent different
  project/version), unknown inventory version, filename/WHEEL mismatch,
  Root-Is-Purelib mismatch, missing/older Python floor, missing/duplicate/
  conditional/extra/URL/loose versions for EACH required parser dependency.
  Every negative asserts the specific diagnostic, not just an incidental false.
  Kill ignore_platform_errors, skip_official_grammar_pins,
  accept_any_self_consistent_distribution and ignore_source_python_floor.
- test_native_wheel_structure_and_relocation:
  reuse the controlled BAML compiler/source fixture, with direct and platlib
  installed placement; verify compressed tags, wrong-platform and wrong/nested
  grammar placement. Parent may execute only the reviewed controlled fixture.
  Kill count_grammar_anywhere. No acceptance claims for other native PRs.
- Existing test_tarfile_safe_extract Conda regressions must stay green and diff
  inspection must show no _verify_conda/_safe_extract_tar changes.
  Include both public BuildSystem and BuildSystemImpl entrypoints in the positive
  and representative negative tests.

Every negative mutation must have an unchanged valid control. For source-code
mutation trials, temporarily introduce ONE named defect in the successor only,
run the named affected test to a meaningful failure, restore the candidate and
record the restored pass. Parent owns those mutations; never touch historical
checkouts. Record actual failing assertions, not fabricated mutation coverage.

## Acceptance criteria

1. Parent creates/selects an authorized fresh-main successor workspace using
   the applicable team-host/workspace convention. Recheck actual main before
   implementation: drift requires inventory/source-profile reconciliation,
   not automatic resurrection of old files. Do not move the primary.
2. Record this proposed design, successor scope identifier and finite review
   allowances separately. Independent Astra design approval precedes source
   implementation under the parent's review workflow.
3. Implement all eight owned changes, lock bookkeeping and test refactoring
   together. Validate prerequisites and locked environment before test commands.
   Narrow affected tests run first, then the complete new contract and Conda/API
   regressions, then lint/format/type/smoke; do not absorb type debt in baseline.
4. Execute the acceptance commands below, source mutations and controlled
   installation checks, retain per-head receipts, then exact-head reviews.
5. Receive all four CODE seats before reconciliation. Repair findings and
   repeat only within the explicitly granted successor cap. Independent Astra
   final approval follows platform evidence and reconciliation. Parent decides
   normal publication/merge; none is authorized by this document.

Commands below are for the parent in the successor checkout; they were NOT run:

```sh
uv --version
uv sync --locked --all-extras
uv run --locked --all-extras pytest -q tests/test_supported_wheel_verification.py -k 'inventory or damaged or collision or case or native_name'
uv run --locked --all-extras pytest -q tests/test_supported_wheel_verification.py tests/test_tarfile_safe_extract.py tests/test_phase13_contracts.py
uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --locked --all-extras python scripts/mypy_gate.py
uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
uv run --locked --with toml --all-extras python scripts/run_full_suite.py
```

- inventory/real-artifact tests prove completeness using trusted tracked source
  and independent bytes, including omissions and source version parity.
- focused new contract + Conda/API tests prove every required fix with isolated
  valid controls; named mutation failures plus restored passes prove sensitivity.
- local CI command sequence must pass. The automation.suite_command is a
  fail-on-nonzero command list; the executing runner must stop at first failure.
- Run the new focused contract and platform-core on exact candidate head with
  Python 3.12 on Linux/macOS/Windows; required compiler fixture executes on Linux,
  portable universal structural tests execute everywhere. Missing prerequisites
  are a blocked check, not a pass. Avoid strict wall-clock performance claims.
- Follow CONTRIBUTING's standing Windows preflight on main as baseline
  confirmation, then run focused tests and scripts/run_windows_preflight.py on
  a SEPARATE candidate checkout on win. The standing checkout/pull command must
  never move any preserved checkout and cannot establish candidate acceptance.
- Repeat the already accepted release.yml hashed wheel-only dependency
  export/install procedure on 3.12/3.14 in private external directories, including
  pip check, schema load, installed verifier checks, Python/JavaScript parsing
  and BOTH console commands. Copy the immutable procedure, not publication
  triggers. No PyPI publish, tag, release or workflow change.
- Fresh wheel/sdist are built from the exact successor source, with hashes,
  tracked-source payload comparison, invocation logs and install receipts
  retained. Prior accepted artifact hashes remain historical evidence only.
- Acceptance receipt must record source commit/tree, wheel and sdist SHA-256,
  inventory digest/count, interpreter/OS, imports' resolved paths, all command
  exits, mutation identifiers/failure assertions/restored passes, skipped or
  blocked checks, platform receipts, quartet round IDs and final Astra evidence.
  Link actual receipts through the parent's existing ledger; this preparation
  creates none and changes no formal phase status.

## Blockers, budgets and formal holds

There is no newly discovered technical dependency on the held native-admission
PRs. Existing packaging hooks are sufficient; one direct dependency declaration
(packaging, already locked) is necessary for safe parser reuse. A trusted source
snapshot, isolated successor and controlled test installation are sufficient to
implement. Full platform acceptance and the fresh dependency closure remain
unexecuted, so possible environmental failures are unknown rather than blockers
already observed.

Prior CODE rounds 1–3 are exhausted; available old CODE budget remains ZERO.
The owner's review-authorization.json grants this successor one independent
Astra design check (completed APPROVE), up to three fresh complete CODE quartets
(two Sol seats, Gemini 3.8 Flash, Astra), and one separate independent Astra final.
Fresh CODE consumed by implementation is 0/3. Parent alone launches reviewers;
the implementation worker has no launch authority. This transcription neither
grants authority nor silently starts a round. The formal SAFELOAD IF remains held.

Reviews later must use native requested selections/settings, wait for
all4complete before reconciliation and keep heartbeatonly operation. Design
preparation does not occupy an approval seat. Preserve all prior HOLDs,
phase ledgers, exhausted-scope records, broker state and historical evidence.
Standing repair/eventual normal merge authority does not reset review budgets.
No helper-retirement decision, security-policy change or new release is needed.

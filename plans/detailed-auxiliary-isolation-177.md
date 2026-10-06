---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_grammar_self_test_workflow.py -q"
---

# Detailed plan: Local, truthful auxiliary grammar self-tests

## Task and limits

Resolve treesitter-chunker#177 in the existing testing module. This is the
independent auxiliary slice of CLEANUP, whose transaction proposal is held.
No cache transaction or IF-0-CLEANUP-1 claim is produced. Default self-tests
must not modify an operator's home, fetch external repositories, count skipped
work as a pass, or delete caller-owned roots. Published 5.2.0 remains usable.

## Research

IntegrationTester already isolates its ordinary workflow, but its auxiliary
error scenarios call stale APIs or return True without doing work. CLIValidator
constructs an ambient CLI, calls removed APIs, ignores exit codes and invents
usability/help scores. SystemValidator and PerformanceBenchmark create ambient
components; configuration validation discards the supplied configuration.
Performance methods call removed discovery/info APIs and simulate increasing
grammar counts without creating grammars. run_complete_test_suite creates each
component with separate ambient defaults, runs a minute-long stability loop,
miscounts untyped results and writes a home test_results.json.

## Changes

Owned product paths: chunker/grammar_management/testing.py,
tests/test_grammar_self_test_workflow.py, docs/grammar_management.md, CHANGELOG.md.
This plan and its supported plans/manifest.json entry are control artifacts.
Amend ownership before expanding. Keep the existing core cleanup assertions in
the workflow test intact; cache deletion coordination remains treesitter-chunker#323.

### 1. Auxiliary component roots and lifetime

Add keyword-only test_dir to CLIValidator, SystemValidator and
PerformanceBenchmark. Reuse IntegrationTester's explicit configuration and
directories for component defaults. Supplied manager/configuration remain the
actual objects used; never silently replace them with default-home objects.
An auto-created disposable root is owned by the creating parent and has explicit
cleanup/context-manager support; a caller's supplied root is preserved. All
default auxiliary filesystem effects must remain below the disposable root.
Construction failure and exceptions during a suite still close owned resources.
Cleanup failures are reported, not suppressed or converted to a pass.

No auxiliary native test may leave its own DLL mapped in the parent that later
deletes its root. Use a short-lived worker in this existing module for native
fixture validation and for the complete-suite orchestration. The parent owns
the operation root, passes explicit paths, waits/reaps the worker and only then
cleans its auto-owned root. Workers use current pinned loader APIs on caller-
supplied test fixtures, never arbitrary discovery as authority. This is test
isolation, not native admission; trusted caller fixtures and subprocess scope
must be documented. Do not create a new worker module or general task framework.

### 2. Retained and retired scenarios

IntegrationTester retains missing/invalid-language and corrupt-local-artifact
rejection using current APIs, real temporary files and truthful results. Do not
call install/download against an external URL to simulate an error. Retire
network-failure, disk-full and permission-recovery demonstrations that cannot
exercise a real bounded local scenario; report status=unsupported plus reason,
and never include them in recovery_successful. Missing or bad APIs and unexpected
exceptions are failures, not evidence of successful recovery.

CLIValidator exercises current list_grammars, info_grammar, versions_grammar,
remove_grammar, test_grammar and validate_grammar signatures as appropriate.
Retained missing-artifact/error cases must observe expected exit codes and useful
output; stale AttributeError/TypeError is a failed scenario. Fetch/build/network
operations without supplied offline fixture inputs are explicitly unsupported.
Help/format checks inspect actual exported Click output; remove invented numeric
usability scores and assumed examples. Keep results explicit about what ran.

SystemValidator uses its supplied configuration consistently. Resource metrics
are observations, not health assertions. PerformanceBenchmark uses current
bounded discovery/info/validation APIs and reports measured operations with
actual failures. Retire simulated scalability and speculative cache speedup
claims unless real different grammar populations are exercised; unsupported
results are not passes. No default 60-second stability wait in complete-suite
execution; select a bounded representative operation, and describe the limit.

### 3. Complete suite and output

Keep run_complete_test_suite callable, with keyword-only test_dir, sample_path,
language and grammar_path inputs for explicit local validation. Share one rooted
environment across its auxiliary components. Run any native work in the worker,
with an argument array and no shell; capture bounded output and a finite process
deadline, terminate/reap on failure before parent cleanup. Do not let printed
CLI output corrupt the worker result: write one UTF-8 JSON result to a parent-
chosen operation-private file, validate it after successful child completion,
and return a typed error when it is missing/malformed. No child exit alone is a
pass. No new network or trust mechanism is introduced.

Return results by default. Remove implicit home report persistence; only an
explicit caller-chosen report_path writes a report, using UTF-8, after results
exist. Never return a path to an auto-owned root that has already disappeared.
Every retained scenario has an observed status; summary counts pass, failure
and unsupported separately. Any actual failure prevents overall pass. With no
native fixture, mark native workflow unsupported rather than fabricate success.

### 4. Real contract tests and documentation

Extend existing workflow tests. Use checked-in Python fixtures and a real pinned
grammar; provision before offline HOME/USERPROFILE/XDG isolation. Verify valid
parse, syntax error, missing grammar and corrupt artifact through real APIs.
Use real subprocess workers; mocks of self-test methods cannot establish
behavior. Boundary-only fault injection may deny report writes or cleanup to
prove errors remain visible. Seed operator-home and caller-root sentinels;
prove no external operation, ambient report, accidental deletion, stale API
recovery or skipped-work pass. Verify auto-owned cleanup after success and
failure, caller-root preservation, report opt-in, worker crash/timeout and
actual Windows native-parse handle release. Keep core cleanup tests unchanged.

Document supported/retired scenarios, explicit fixture inputs, default returned
results, report opt-in and cleanup ownership in the existing guide/changelog.
File unrelated defects separately; do not repair core/cache/native consumers here.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_grammar_self_test_workflow.py -q
- uv run --locked --all-extras pytest tests/test_public_grammar_cli.py tests/test_public_grammar_config.py tests/test_core_grammar_cache_cleanup.py tests/test_release_hygiene_policy.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --all-extras pytest -q
- Strict MkDocs build with the locked environment and a temporary site directory.

Run the standing Windows main preflight before publication; require changed-head
Linux/macOS/Windows evidence separately. Kill ambient_auxiliary_root at a default
auxiliary constructor and auxiliary_false_success at a retired scenario's result
reducer. Record baseline, intended assertion failure, restoration and a restored
pass. Manual tool-enabled Opus 5.5 TUI/Gemini 3.8 Flash/Astra/Sol code review,
three substantive rounds maximum, then reconcile every blocker before merging.

## Acceptance criteria

- [ ] Retained local scenarios use current APIs, parse real fixtures and reject
  missing/corrupt inputs; retired scenarios are unsupported, never passed.
- [ ] Default components and suite effects are disposable and outside operator home;
  caller-owned roots/sentinels survive. Workers finish/reap before owned deletion,
  including real Windows parse and error paths. Cleanup failures stay visible.
- [ ] Suite returns results without ambient persistence, opt-in reports survive,
  and actual errors prevent pass. Both named mutations fail at intended assertions
  and restored tests pass. Exact-head code review and required platforms accept.

Close treesitter-chunker#177 only after all contracts are accepted. No cache IF
gate or accepted transaction design is implied by this independently landed PR.

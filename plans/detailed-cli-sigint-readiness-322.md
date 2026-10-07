---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Signal the CLI after observable parsing readiness

## Task and research

Resolve treesitter-chunker#322 as a test-reliability slice. The existing SIGINT
test sleeps 50ms, skips when the process finishes early and waits without
draining stdout/stderr. Its timeout cleanup kills without reaping. These do not
prove the CLI reached a signal-ready execution point.
cli.main chunk reads the provided file through the real chunker. Observe its
actual process_file return after parsing a regular fixture file. A child-side
Python profile observer records the real returned chunks atomically and pauses
in a loop of short Python sleeps, bounded independently at60seconds. This test harness does not replace CLI functions
or parser calls; it supplies a controlled signal point after real parsing.
Own evidence is allowlisted at /tmp/chunker-322-*.

## Changes

- tests/test_cli_integration_advanced.py: replace only
  TestSignalHandling.test_sigint_handling. Parse a checked-in Python fixture
  using the installed real parser as a control, then copy its actual bytes to
  a regular file consumed by cli.main chunk via runpy in a child process.
  Observe process_file's real nonempty return with sys.setprofile; atomically
  record those rows in a private readiness marker and pause the observer in
  a loop of short sleeps with an independent60second self-deadline, after which
  the observer exits with failure. This prevents an indefinite orphan pause if
  the parent dies before cleanup. Check real row paths/language/content before signaling.
  Bound marker readiness monotonically at30seconds and fail on premature exit
  instead of skipping. Send SIGINT only after readiness, drain both outputs
  with communicate(timeout=15), and accept interruption statuses130/-SIGINT
  only. Always kill/drain/reap an unfinished child in
  finally, including readiness/communication assertion failure paths.
  Preserve the explicit Windows POSIX-only skip and unrelated signal cases.
- scripts/run_platform_core.py: include the single SIGINT contract in common
  selection, preserving existing entries. Linux/macOS execute; Windows keeps
  its deliberate skip. Existing command-chaining fixture is a Windows control.
- CONTRIBUTING.md: explain observable parsing readiness and pipe draining for
  POSIX signal checks; these bounds are cleanup safeguards, not throughput gates.
- CHANGELOG.md: record the more reliable quality check without runtime changes.
- This plan and its typed plans/manifest.json row are owned paths.

## Dependencies and order

Register and commit the plan before tests/code. Keep this independent of native
deadlines and other CLI signal tests. Verify the new actual CLI contract both
normally and with coverage. The named mutation ignore_cli_sigint temporarily
sets the actual CLI entrypoint's SIGINT handler to SIG_IGN before app(); the
readied child must fail the shutdown contract, be killed and reaped, and
exact restoration must pass. Preserve original cli/main.py bytes and bind their
hash plus test hashes; no permanent production modification is permitted.
Collect four tool-enabled reviews, maximum three substantive rounds.

All four R1 reviewers agreed. Hosted Linux3.11 nevertheless failed twice after
reader readiness, while hosted Linux3.12/macOS and a private locked local3.11
covered reproduction passed. Before another retry, add scoped timeout diagnostics
to the same test: parent SIGINT disposition/mask, Linux child signal-status
fields and captured stdout/stderr. Preserve both failed hosted logs. These
diagnostics establish the execution context; do not increase the timeout or
claim an unproven production cause. Linux diagnostics show SIGINT caught,
unblocked and no longer pending, yet the FIFO child remains alive. macOS also
times out. Preserve those logs and track FIFO interruption separately as
treesitter-chunker#435. R2 replaces the FIFO with the regular-file parse-return
observer above; this proves interruption at that controlled Python execution
point, not arbitrary native/read phases or public FIFO support.

## Documentation impact

Only contributor/test-reliability guidance changes. The runtime's signal
behavior, public command syntax, parser pins and package version remain intact.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_cli_integration_advanced.py::TestSignalHandling::test_sigint_handling tests/test_cli_integration_advanced.py::TestComplexCommands::test_command_chaining -q
- uv run --locked --all-extras pytest tests/test_cli_integration_advanced.py::TestSignalHandling::test_sigint_handling --cov=chunker --cov-report=term-missing -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py

Original seven (six standing plus the covered SIGINT contract), locked refresh/full tests/spec_tests, matching-source Windows
control/standing preflight and exact hosted Linux/macOS/Windows jobs are required.
No native, broker, ledger, checkpoint, pin or consumer-lock changes.

## Acceptance criteria

- [ ] The actual CLI is signaled only after returning real fixture chunks and exits with an
  interruption status; normal/covered focused tests prove the contract without
  sleeps guessing startup or early-completion skips. Actual fixture parsing
  and Windows command-chaining control remain.
- [ ] All exit/failure paths drain and reap the child.
  The real ignore_cli_sigint mutation fails shutdown, exact restoration passes
  and final source/test hashes are bound; permanent CLI source is unchanged.
- [ ] Original checks, locked refresh/full tests/spec_tests, matching-source
  Windows control/explicit POSIX skip, hosted jobs and bounded reviews pass.
  No production performance or broader signal/native safety claim is made.

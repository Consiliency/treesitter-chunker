---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_cli.py tests/test_iface_cli_detection.py -q"
---

# Detailed plan: Report failed chunk extraction honestly

## Task

Resolve treesitter-chunker#359 as the CLI part of EC-RUNTIME-2. Keep successful
batch chunks available while returning status 1 if any selected file fails.
This independently landable repair does not complete the RUNTIME phase.

## Research summary

cli/main.py process_file catches ChunkerError, prints to stdout and returns [],
so chunk and batch cannot distinguish extraction failure from an empty result.
The stdin path exits early and suppresses its error with quiet. Batch futures
currently have no failure accounting. JSON and JSONL output share the normal
serialization paths. Unknown extension detection has an existing warning/skip
contract in tests/test_iface_cli_detection.py, which stays intact.

## Changes

- cli/main.py: let extraction exceptions escape process_file to the command
  boundary. chunk initializes an empty result and failure flag, reports a file
  or stdin extraction exception to stderr even when quiet, serializes the
  requested output, then raises typer.Exit(1). Missing stdin language and absent
  single-file input remain usage failures, with their diagnostics on stderr.
  batch catches each selected future's exception, reports the path on stderr,
  continues collecting successes, and exits 1 after output if any failed.
  Progress uses stderr so structured stdout stays clean without quiet too.
  Catch Exception at these per-input boundaries, including real decoding and
  I/O failures, without catching BaseException. No new error envelope or flags.
  Round-one reconciliation puts stdin decoding inside the handler, renders
  input/exception text without interpreting Rich markup, with wrapping disabled,
  sends load_config
  warnings to stderr, and lets an empty selected batch reach its existing
  structured serializer. Batch usage diagnostics also use stderr. Malformed
  config still falls back as before; its warning is not converted to an error.
- tests/test_cli.py: real subprocesses through the installed entrypoint, real
  checked-in Python source, no parser/worker/exception mocks. Cover unsupported
  language for file, stdin and batch in JSON/JSONL, with quiet and without;
  mixed success using real valid BAML and invalid UTF-8 BAML with explicit
  --lang baml, in serial and
  parallel batches; successful control and successfully empty Python input.
  Compare successful nonempty content with the actual fixture and assert no
  diagnostics in stdout. Parse every JSONL line strictly; empty JSONL is valid.
  Add real bracketed-language/path, strict invalid UTF-8 stdin, malformed-config
  warning and empty-batch subprocess cases. Write BAML fixture bytes unchanged
  so Windows CRLF translation cannot invalidate the content comparison.
- .github/workflows/test.yml: install the existing pinned optional baml extra
  in hosted platform environments so the real mixed BAML cases actually run.
  This is a verification dependency, not a parser pin or native admission change.
- docs/cli-reference.md and CHANGELOG.md: replace the known limitation with
  status/output migration and explicit partial-batch policy. Unmapped extensions
  still warn and skip; failures mean selected inputs that actually raise.
- plans/detailed-cli-failure-semantics-359.md and plans/manifest.json: own plan
  and typed lifecycle. Existing platform selection already includes test_cli.

## Documentation impact

Callers must stop treating a nonzero batch status as proof that stdout has no
usable chunks: partial successes are emitted unchanged. Quiet suppresses
progress, not actionable errors. JSON failure payload is []; JSONL failure with
no successes is empty. No promise to turn parser syntax-error nodes into errors.

## Dependencies and order

Register this plan before product edits, sync the locked environment and record
the current real-subprocess failures. Fix command boundaries, run focused tests,
kill and restore mutations serially, then require original runner checks plus
dependency refresh/full suite, changed-source Windows and hosted platforms.
Maximum three substantive manual tool-enabled review rounds; collect the whole
round before fixes. Integrate accepted main before final full verification.
Do not change native admission, pins, consumer locks, ledgers or checkpoints.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_cli.py tests/test_iface_cli_detection.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --all-extras pytest -q

Named mutations: report_failed_extraction_as_success removes failure exits;
emit_extraction_diagnostics_on_stdout redirects extraction diagnostics. Each
must fail real subprocess assertions and restore the complete focused batch.
Also kill read_stdin_outside_handler and emit_config_warning_on_stdout to
cover the independently reproduced round-one input/output failures.
Windows runs the changed cases and standing preflight; exact-head CI confirms
Linux/macOS/Windows. External reviews/platform records are supplementary manual
evidence, not a fabricated runner amendment or formal IF acceptance.

## Acceptance criteria

- [ ] Failed file/stdin/batch extraction returns 1, retains parseable requested
  stdout and reports the actual input/error on stderr, including quiet, proven
  by the focused real subprocess cases and both mutations.
- [ ] A mixed batch preserves actual successful fixture chunks and returns 1
  for its failed input under serial/parallel execution; a successful or empty
  extraction remains 0 in structured formats, proven by the same focused batch.
- [ ] Documentation, original runner, changed Windows/platform checks and bounded
  independent reviews support the exact accepted repair without whole-phase claims.

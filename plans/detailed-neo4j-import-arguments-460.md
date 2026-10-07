---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Preserve Neo4j import filename arguments

## Task

Resolve treesitter-chunker#460 as one shell-argument repair, independently
reviewed after acceptance/integration of treesitter-chunker#459. Preserve exact
node and relationship basenames through the generated Bash import helper.
All Unreleased remains reserved for 6.0.0; no live database or Neo4j-version
compatibility is certified.

## Research summary

`Neo4jExporter._generate_import_command` inserts `nodes_path.name` and optional
`relationships_path.name` into unquoted shell options. Actual real-parsed export
of `graph name` followed by actual Bash interpretation against an isolated
argument-capture command produced two arguments for each filename. Shell quoting
belongs at that argument boundary, separately from CSV/script file newline
transport. Standard-library `shlex.quote` supplies POSIX shell quoting; this
helper targets Bash, not Windows CMD or PowerShell syntax.
Private reproduction reads are allowlisted at
`/tmp/chunker-457-script-arguments-probe.py`,
`/tmp/chunker-457-script-arguments-reproduction.json` and
`/tmp/chunker-457-filename-followup-issue.md`.

## Changes

### `chunker/export/neo4j_exporter.py` (modify)

- Import `shlex`. In `_generate_import_command`, quote the complete
  `--nodes=<basename>` argument and optional `--relationships=<basename>` with
  `shlex.quote`, using local argument variables. Preserve option spelling/order,
  ordinary safe-name output, LF continuations, file writes and chmod. Do not
  change CSV, Cypher, graph identities, path creation or CLI/version selection.

### `tests/test_graphml_exporter.py` (modify)

- Reuse actual error-free parsed same-span chunks and graphs with/no edges.
  Export actual files for ordinary and Unicode controls, spaces, apostrophe,
  semicolon, dollar/parenthesis expansion syntax and backtick syntax. These
  basenames avoid characters forbidden by Windows filenames.
- Require actual exported names/files and LF UTF-8 script payload. Parse the
  generated command's continued shell line with the independent POSIX `shlex`
  lexer on both platforms and compare exact literal argument order/values, not
  a hand-built copy of the quote implementation.
- On POSIX with actual Bash available, run the actual file against a private
  `neo4j-admin` argument-capture fixture with PATH restricted to that directory.
  Assert exact literal filenames and flags from stdout, with no shell expansion
  or extra output. Resolve Bash absolutely; use the existing generous child
  cleanup safeguard. This proves Bash behavior without a live database command.
- Preserve no-edge omission and all accepted LF/CSV/GraphML/yEd controls. Actual
  Windows validates real filenames/script bytes and lexical argument identity;
  actual Bash execution is independently measured on Linux, not presumed native
  on Windows. No parser/exporter/shell/file-I/O mocks.

### `docs/export-formats.md`, `docs/graphml_export.md`, `CHANGELOG.md` (modify)

- Replace the filename-quoting limitation with the precise Bash argument
  contract for tested basenames. Retain the direct structured-API distinction,
  existing LF/CSV fidelity and no live import/version certification. Direct
  Cypher file fidelity remains treesitter-chunker#458. Add qualified Fixed entry
  and update the adjacent script entry to avoid stale open-limit wording.

### This plan and `plans/manifest.json` (modify)

- Register only this own typed plan row. Integrate accepted current main and
  preserve every canonical row before own executing lifecycle/source edits.
  No historical ledger/checkpoint, pin, golden or consumer-lock changes.

## Dependencies & order

1. Plan/publish draft on a clean private worktree without tests or builds. Write
   the detailed-plan handoff/reflection. Implementation waits for accepted
   treesitter-chunker#459 and canonical integration of its shared source/tests.
2. Record own executing lifecycle, add contracts and the two quoted argument
   boundaries. Reproduce failures against unchanged accepted production; file
   additional independent defects separately before expanding any scope.
3. On actual Linux with Bash, run `unquote_node_import_filename` and
   `unquote_relationship_import_filename`, restoring only the corresponding
   argument's unquoted interpolation. Each must fail its declared argument
   contract while ordinary/no-edge controls remain. Restore exact source after
   each and pass focused tests; bind source/test/fixture/support hashes and actual
   logs/exits. Do not count a lexical-only run as actual Bash execution.
4. Run actual candidate Windows focused and unchanged standing preflight,
   original six/locked refresh/full tests/spec_tests with a fresh passing seal,
   and every required exact-head hosted job. Use short private workspace TMPDIR
   `/mnt/workspace/worktrees/viperjuice/t460`. Preserve failures and actual exits.
5. Freeze for four manual tools-enabled Opus 5.5 TUI/Gemini 3.8 Flash/Astra/Sol
   CODE reviews with compact pointers, maximum three complete substantive rounds,
   heartbeat only/no model or silence deadline. Collect all opinions before
   reconciliation. Require requested manual Astra final chair, then archive,
   exact-head merge, qualified issue comments/closure and safe merged pruning.

## Verification

- `uv sync --locked --all-extras`
- `uv run --locked --all-extras pytest tests/test_graphml_exporter.py tests/test_graphml_yed_export_contract.py tests/test_phase12_integration.py -q`
- `uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site`
- `uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/`
- `uv run --locked --all-extras python scripts/mypy_gate.py`
- `uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py`
- `uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux`
- `uv run --locked --with toml --all-extras python scripts/run_full_suite.py`

Windows uses the same focused selection and unchanged
`scripts/run_windows_preflight.py`. The private `chunker-460-` proof contains
actual Bash baseline/mutation/restoration evidence and bindings, actual Windows
log/launcher exit, original sealed runner JSON/log, four raw reviews and final
manual chair ruling. Supplemental evidence is not a governed operational
amendment (agent-harness#1271), supplier/IF/native-fill or release acceptance.
No coverage-percentage, performance or duration acceptance gate is added.

## Acceptance criteria

- [ ] Real parsed exports retain exact declared filename arguments and complete
  flag/order/no-edge semantics for all listed basenames, proven by actual Linux
  Bash and real Windows file/lexical contracts in the focused command.
- [ ] Both actual Linux mutations fail the corresponding filename contract;
  exact restoration passes focused tests with immutable bound evidence and
  ordinary/no-edge controls. Candidate Bash execution uses the isolated fixture.
- [ ] Ordinary safe-name script output and accepted file/CSV/graph/Cypher behavior
  remain, canonical rows/pins/goldens/selectors are retained and docs accurately
  separate Bash argument integrity from database/version acceptance.
- [ ] Original six/refresh/full seal, actual Windows/standing, required hosted,
  four substantive agreements and final manual Astra ruling qualify only this
  bounded repair; separate defects are filed rather than silently fixed.

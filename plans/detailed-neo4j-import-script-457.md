---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Preserve Neo4j import shell script syntax

## Task

Resolve treesitter-chunker#457 as one independently landable file-writing repair.
Preserve the generated Bash script's LF syntax when exporting on Windows and
Linux. Implementation waits for acceptance/integration of treesitter-chunker#456
because the two slices own the same serializer, test module and guides. All
Unreleased remains reserved for 6.0.0; no live Neo4j import is certified.

## Research summary

The direct `Neo4jExporter.export(..., fmt="csv")` writes an import shell file with
`cmd_path.write_text(import_cmd, encoding="utf-8")`, then preserves its existing
executable mode. `_generate_import_command` already builds an LF shebang and
backslash-LF continuations. Actual Linux/Windows probes at the frozen
treesitter-chunker#456 first code head demonstrated all eleven LF delimiters
becoming CRLF on Windows, including the shebang and five continuations. The
script writer is separate from the two CSV writes and the Cypher text writer.
The current graph tests already provide real error-free parsed same-span chunks.
Actual Bash with an isolated argument-capture command also reproduced unquoted
space-containing basenames becoming different arguments. This is separately
filed before implementation as treesitter-chunker#460. This LF-writing slice
keeps script construction unchanged and tests ordinary shell-safe basenames;
filename quoting is a separate repair. Private reproduction reads are explicitly
allowlisted at `/tmp/chunker-457-script-arguments-probe.py`,
`/tmp/chunker-457-script-arguments-reproduction.json` and
`/tmp/chunker-457-filename-followup-issue.md`. Prior newline probe evidence is
`/tmp/chunker-454-noncsv-probe.py`, `/tmp/chunker-454-noncsv-linux.json` and
`/tmp/chunker-454-noncsv-windows.json`, with Linux as the no-translation control.

## Changes

### `chunker/export/neo4j_exporter.py` (modify)

- Add `newline=""` only to `cmd_path.write_text`, retaining UTF-8 and existing
  chmod. Keep script construction, flags, names, CSV generation/writes, Cypher,
  graph identities and all other exporter behavior unchanged.

### `tests/test_graphml_exporter.py` (modify)

- Add real parsed fixture contracts for graphs with and without actual
  relationships. Export actual CSV/script files and require the literal LF
  shebang, backslash-LF continuations, no CR bytes, exact generated UTF-8 script
  payload, unchanged names/import flags and executable mode where supported.
- On POSIX with actual Bash available, run the generated script against a
  private executable `neo4j-admin` fixture that captures arguments. Set PATH to
  that fixture directory, so a live database command cannot be invoked. Assert
  exact literal argument order and node/relationship/no-edge flags. Invoke Bash
  by its resolved absolute path; a generous subprocess cleanup bound is a
  harness safeguard, not performance acceptance. Windows must pass the real
  byte/flag contracts, independently of optional local Bash availability.
- Retain accepted CSV field/newline, GraphML/yEd and phase12 controls exactly.
  No parsing, exporter, newline-translation or production-file-writing mocks.
  The external command fixture proves shell interpretation without a database.

### `docs/export-formats.md`, `docs/graphml_export.md`, `CHANGELOG.md` (modify)

- State that the generated `.sh` import helper uses LF syntax on Windows/Linux
  and is intended for Bash. Distinguish script transport/argument integrity from
  a certified Neo4j server import and the separate structured API. Add a
  qualified Fixed entry for treesitter-chunker#457. Keep the separate direct
  Cypher newline fidelity issue treesitter-chunker#458 explicit.
  Retain the separate filename-argument limitation treesitter-chunker#460; do not
  imply that LF transport fixes shell quoting or database-version compatibility.

### This plan and `plans/manifest.json` (modify)

- Register only this plan through typed helpers, retaining accepted canonical
  rows exactly. Integrate accepted treesitter-chunker#456 and record own
  executing lifecycle before source/test edits. No old ledger/checkpoint writes.

## Dependencies & order

1. Write/publish the draft detailed plan on a clean private worktree; no tests or
   builds during planning. Record the handoff and reflection.
2. Wait for accepted treesitter-chunker#456, integrate current main and preserve
   every canonical manifest row plus this own row. Validate the plan and record
   its executing lifecycle. Add contracts and the single script-write change.
3. Run focused tests/lint/format/type checks. Separately file any newly discovered
   defect; do not change Cypher or Neo4j import versions/flags inside this slice.
4. Commit/freeze the candidate. On actual Windows, run the new contracts against
   unchanged accepted production and preserve the baseline failures. Run actual
   `translate_import_script_newlines`, restoring default translation only for
   the script write. It must fail the LF byte contracts; restore exact candidate
   source and pass the focused selection, binding source/test/fixture/support
   hashes and actual exits. Linux-only mutations are not Windows evidence.
5. Require original six checks, locked refresh and full tests/spec_tests with
   a fresh actual passing seal, short private workspace TMPDIR
   `/mnt/workspace/worktrees/viperjuice/t457`, actual current Windows focused plus
   unchanged standing preflight, and all required exact-head hosted jobs.
6. Four independent manual tools-enabled Opus 5.5 TUI/Gemini 3.8 Flash/Astra/Sol
   CODE reviews use compact pointers, maximum three complete substantive rounds,
   heartbeat only/no model or silence deadlines. Collect every verdict before
   reconciliation. Require requested manual Astra president final evidence
   ruling; archive before exact-head merge, qualified issue closure/comments and
   safe owned merged-worktree pruning. Preserve failed/incomplete evidence.

## Verification

- `uv sync --locked --all-extras`
- `uv run --locked --all-extras pytest tests/test_graphml_exporter.py tests/test_graphml_yed_export_contract.py tests/test_phase12_integration.py -q`
- `uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site`
- `uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/`
- `uv run --locked --all-extras python scripts/mypy_gate.py`
- `uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py`
- `uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux`
- `uv run --locked --with toml --all-extras python scripts/run_full_suite.py`

Actual Windows runs the same focused selection and unchanged
`scripts/run_windows_preflight.py`, with baseline/mutation/restoration logs and
bindings under the private `chunker-457-` evidence prefix. Original sealed runner
JSON/log, Windows actual exits, four raw reviews and final manual chair ruling
are supplemental evidence. Runner-stamped operational amendments remain
agent-harness#1271; no governed supplier/IF/native-fill or percentage/time gate.

## Acceptance criteria

- [ ] Real parsed graph exports with and without relationships retain exact LF
  shell syntax, UTF-8 bytes, names, flags and supported executable mode on actual
  Windows/Linux, proven by the focused command.
- [ ] Actual Bash against the isolated argument-capture fixture receives the
  exact declared flags/order without invoking a live database; fixture failure
  is surfaced and children are reaped.
- [ ] Unchanged production and the actual Windows translation mutation fail
  the named LF contracts; exact source restoration passes focused tests with
  immutable source/test/fixture/support evidence.
- [ ] Accepted CSV/graph/Cypher behavior, canonical manifest, parser pins/goldens
  and standing selectors remain; original six/refresh/full seal, Windows/hosted,
  four substantive agreements and final manual Astra ruling qualify only this
  bounded repair with precise docs and separate treesitter-chunker#458 tracking.

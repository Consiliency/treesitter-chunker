---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Preserve direct Neo4j Cypher file bytes

## Task

Resolve treesitter-chunker#458 as one file transport repair after acceptance
and integration of treesitter-chunker#461. The direct Cypher file must retain
the generated UTF-8 string without platform newline translation. This is not
Cypher syntax or live Neo4j/server-version certification. All Unreleased remains
reserved for 6.0.0.

## Research summary

`Neo4jExporter.export(fmt="cypher")` joins existing statements with LF and
uses default `Path.write_text` newline handling. The actual paired Linux and
Windows probe at `/tmp/chunker-454-noncsv-probe.py`, `noncsv-linux.json` and
`noncsv-windows.json` established LF caller IDs/properties changing to CRLF
only in the Windows file. CSV and Bash transport are independently repaired
under treesitter-chunker#454 and treesitter-chunker#457; Bash filename quoting
is separately treesitter-chunker#460. Preserve all generated statement semantics.

## Changes

### `chunker/export/neo4j_exporter.py` (modify)

- In only the direct Cypher branch, add `newline=""` to the existing UTF-8
  `output_path.write_text` call. Leave statement generation, escaping, batching,
  labels, option handling, CSV and Bash output untouched.

### `tests/test_graphml_exporter.py` (modify)

- Use real error-free parsed same-span fixtures, three literal embedded line
  breaks (LF, CR and CRLF), both node insertion orders and with/no edges.
  Assign explicit caller IDs and node/edge string properties containing the
  selected line break plus Unicode. Export actual Cypher files.
- Independently assert literal IDs and properties occur in generated node and
  optional relationship statements, with no relationship clause for no-edge
  graphs. Compare raw file bytes with generated string UTF-8 bytes and read
  with `newline=""` to compare the unchanged string. Assert actual output path,
  no additional CSV/shell files and unchanged graph IDs/endpoints. No parser,
  exporter or platform mocks, and no claim of parsing/executing Cypher.
- Preserve every accepted test byte outside the own new contract. Windows
  baseline/mutation discrimination is mandatory: default Windows translation
  changes generated LF formatting even in CR-only field cases, whereas Linux
  is a passing control.

### `docs/export-formats.md`, `docs/graphml_export.md`, `CHANGELOG.md` (modify)

- Describe exact direct Cypher file/string UTF-8 fidelity across Windows/Linux
  and reading with `newline=""`. Replace adjacent stale open-limit sentences
  with qualified fixed references. Retain direct versus structured API and
  live database/version exclusions. Add the qualified Fixed entry.

### This plan and `plans/manifest.json` (modify)

- Append only the own typed detailed-plan row; preserve all canonical rows on
  prerequisite integration. Record own executing lifecycle before source edits.
  No historical runner/ledger/checkpoint, lock, parser pin or golden changes.

## Dependencies & order

1. Publish the plan-only draft from a clean private worktree. Write detailed-plan
   handoff/reflection; no tests/builds during planning. Implementation waits for
   accepted treesitter-chunker#461 and canonical shared-source integration.
2. Add the declared file transport contracts and one write kwarg. Preserve and
   separately file independent defects before considering scope changes.
3. On actual Windows, run unchanged accepted production and the named mutation
   `translate_cypher_file_newlines`, which removes only the own Cypher kwarg.
   All new file-byte contracts must fail; inherited controls remain. Restore
   exact source after each, pass focused tests and bind actual exits/logs plus
   source/test/fixture/support hashes. Do not claim Linux reproduces translation.
4. Run actual current-head Windows focused and unchanged standing preflight,
   original six/locked refresh/full tests/spec_tests with short private TMPDIR
   `/mnt/workspace/worktrees/viperjuice/t458`, and required exact hosted jobs.
   Preserve all failures; accept only a fresh valid passing original seal.
5. Freeze four manually launched tools-enabled CODE seats: Opus 5.5 TUI,
   Gemini 3.8 Flash, Astra and Sol, compact pointers, maximum three complete
   rounds, heartbeat only/no model or silence deadlines. Collect all opinions
   before reconciliation. Require final manual Astra chair, archive immutable
   evidence, exact-head merge, comment/close and safe owned pruning.

## Verification

- `uv sync --locked --all-extras`
- `uv run --locked --all-extras pytest tests/test_graphml_exporter.py tests/test_graphml_yed_export_contract.py tests/test_phase12_integration.py -q`
- `uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site`
- `uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/`
- `uv run --locked --all-extras python scripts/mypy_gate.py`
- `uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py`
- `uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux`
- `uv run --locked --with toml --all-extras python scripts/run_full_suite.py`

Actual Windows uses the same focused tests and unchanged
`scripts/run_windows_preflight.py`. The private `chunker-458-` packet contains
actual Windows baseline/named mutation/exact restoration and launcher exits,
bound source/test hashes, original sealed runner JSON/log, four raw reviews and
final chair ruling. Supplemental evidence does not substitute for a governed
operational amendment (agent-harness#1271), native-fill/supplier/IF or release
acceptance. No coverage-percentage or timing gate is introduced.

## Acceptance criteria

- [ ] Real parsed exports retain literal LF/CR/CRLF caller IDs and properties
  in unchanged generated strings and identical UTF-8 file bytes across both
  platforms, with declared ordering, edge/no-edge and output-path controls;
  proven by the focused command and actual Windows logs.
- [ ] Actual unchanged Windows and `translate_cypher_file_newlines` fail new
  file-byte contracts while inherited controls pass; each exact restoration
  passes focused tests with source/test/fixture/support hash bindings.
- [ ] Only the Cypher file write changes; accepted generators, escaping,
  batching, CSV, Bash, graph identities and canonical rows remain, with precise
  docs and no live database, Cypher syntax or server-version claim.
- [ ] Original six/refresh/full passing seal, actual Windows/standing, exact
  hosted, four substantive code agreements and final manual Astra ruling
  qualify this bounded repair; independent defects are separately filed.

## Execution notes

- Accepted treesitter-chunker#461 is integrated before source edits. All 57
  canonical manifest rows remain exact plus the own executing 58th row.
  Removing only the new test reconstructs accepted test bytes exactly, retaining
  all 436 inherited controls, including Bash filename and LF/CSV transport cases.
- Twelve real parsed exports cover LF/CR/CRLF, both insertion orders and
  edge/no-edge graphs, literal generated IDs/properties, exact raw UTF-8 payload,
  newline-preserving file reads, graph endpoints and output-path isolation.
  This checks existing string transport and never executes or parses Cypher.
- Linux candidate and actual unchanged accepted production both pass 448 focused
  tests. Linux is a control; actual Windows unchanged baseline and named
  `translate_cypher_file_newlines` mutation/restoration are mandatory before
  acceptance. Source/tests remain frozen during these checks and reviews.
- Local Ruff, Black and mypy gate pass with no baseline changes. An initial
  malformed patch hunk was rejected atomically before any file changes or tests;
  its corrected application is the only source delta. Original six/refresh/full,
  actual Windows/standing, exact hosted, all four CODE opinions and final Astra
  ruling remain mandatory independent gates.
- All four CODE R1 opinions completed with AGREE and actual exit 0 before
  reconciliation. Opus observed that generated endpoint presence could match
  only node statements. The own test now requires each caller ID exactly twice
  with an edge and once without, covering node and relationship statements as
  promised. Production and all inherited tests remain unchanged.
- R1 original six/locked refresh/full passed 4,425 tests with four skips and
  actual seal `a2226d8365a626519355ad4d0f7874c981ddf68301c54de7916a2b273a389aa0`.
  That result, actual Windows baseline/mutation/restorations and four raw
  opinions are preserved but excluded from final R2 acceptance because the
  own assertion changed. Fresh R2 Windows bindings, original run, hosted jobs,
  four manual opinions and final Astra ruling are mandatory.

---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Preserve embedded newlines in Neo4j CSV files

## Task

Resolve treesitter-chunker#454 as one independently reviewed file-writing repair
after accepted treesitter-chunker#455. Keep actual CSV file fields equal to their
generated strings on Linux and Windows. All Unreleased remains reserved for
6.0.0; this is not whole EXPORT, live database import or release acceptance.

## Research summary

The direct `chunker.export.neo4j_exporter.Neo4jExporter` uses standard CSV quoting
and CRLF record delimiters, preserving embedded LF, CR and CRLF in generated
strings. Its two CSV `Path.write_text` calls use default newline translation.
An actual same-source Linux/Windows probe on error-free parsed
`tests/fixtures/graph_same_span.py` demonstrated Windows CRLF doubling in caller
IDs, relationship endpoints and properties. Bare LF is also translated; CR
alone is unchanged. The accepted whitespace repair already removes only the
final generated record delimiter. Import shell and Cypher writes are separate.

## Changes

### `chunker/export/neo4j_exporter.py` (modify)

- Add `newline=""` to the node and relationship CSV `Path.write_text` calls,
  retaining UTF-8 encoding. Write the exact generated CSV payload without
  platform translation. Do not change the generators, header/data delimiter,
  quoting, property order, IDs, relationships, import shell or Cypher writes.

### `tests/test_graphml_exporter.py` (modify)

- Reuse actual error-free parsed same-span chunks. For embedded LF, CR and CRLF,
  assign two distinct literal caller IDs and exact string properties containing
  the selected line break, quoted punctuation and Unicode whitespace. Cover
  both node insertion orders and actual relationship/no-edge graphs.
- Read real generated strings and real exported files through CSV readers with
  `newline=""`. Require exact literal IDs, endpoints/types, property values,
  complete headers and row counts. Verify raw UTF-8 file bytes equal their
  corresponding generated CSV strings, without newline normalization.
- Retain actual file names/import flags and absence of relationship output for
  no-edge graphs. Existing empty, field-whitespace, GraphML/yEd and phase12
  controls remain unchanged. No parser/exporter/file-I/O or platform mocks.

### `docs/graphml_export.md`, `docs/export-formats.md`, `CHANGELOG.md` (modify)

- Replace the Windows LF/CRLF limitation with the precise direct CSV file
  contract: embedded LF, CR and CRLF fields match generated strings on both
  platforms. CSV readers must retain embedded newline bytes. Preserve the
  package-level structured API and live database import distinctions. Add a
  qualified consumer-facing Fixed entry for treesitter-chunker#454.

### This plan and `plans/manifest.json` (modify)

- Register this own plan through typed manifest helpers, preserving every
  accepted canonical row exactly. Record its executing lifecycle before edits.
  No admitted ledger, checkpoints, consumer locks, pins or golden changes.

## Dependencies & order

1. Plan on a clean private worktree at accepted main. Planning does not run tests
   or builds. Write the handoff/reflection and publish the draft plan first.
2. Mark this own plan executing, add contracts, then make the two write changes.
   Verify focused tests and local lint/format/type checks. Separately file any
   newly discovered defect; do not silently broaden this repair.
3. Commit the final source/tests/docs before actual Windows validation. Archive
   the exact candidate into a fresh private Windows checkout. First run the new
   focused suite against unchanged accepted production, preserving its actual
   failures; then restore exact candidate source and run the focused suite.
4. On actual Windows, run `translate_node_csv_newlines` (restore default newline
   translation only for node CSV) and `translate_relationship_csv_newlines`
   (only for relationship CSV). Each must fail the corresponding LF/CRLF field
   contract while the CR/no-edge controls remain. Restore exact candidate bytes
   after each and rerun the entire focused selection. Bind source/test/fixture
   and unchanged GraphML/yEd/base/selector hashes, all actual exits and logs.
   A Linux mutation that passes is not substitute Windows evidence.
5. Require original six checks, locked environment refresh and full tests plus
   spec_tests with a fresh valid runner seal. Use short private canonical
   workspace TMPDIR `/mnt/workspace/worktrees/viperjuice/t454`. Require fresh
   actual candidate Windows focused and unchanged standing preflight, and all
   required exact-head hosted jobs. Preserve failed runs without stamp edits.
6. Freeze the candidate for independent manual tools-enabled Opus 5.5 TUI,
   Gemini 3.8 Flash, Astra and Sol CODE reviews. Compact pointers, maximum three
   complete substantive rounds, heartbeat-only with no model/silence deadline.
   Collect all four verdicts before reconciliation. Require the requested manual
   Astra president's final evidence ruling, then archive, exact-head merge,
   qualified issue closure/comments and safe owned merged-worktree pruning.

## Verification

- `uv sync --locked --all-extras`
- `uv run --locked --all-extras pytest tests/test_graphml_exporter.py tests/test_graphml_yed_export_contract.py tests/test_phase12_integration.py -q`
- `uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site`
- `uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/`
- `uv run --locked --all-extras python scripts/mypy_gate.py`
- `uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py`
- `uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux`
- `uv run --locked --with toml --all-extras python scripts/run_full_suite.py`

Actual Windows uses the same focused selection and unchanged
`scripts/run_windows_preflight.py`. Operational evidence comprises the private
`chunker-454-` original runner JSON/log, Windows baseline/mutation/restoration
log and bindings, four raw reviews/metadata, and final manual chair ruling.
These are supplemental manual evidence; runner-stamped operational amendment
support remains agent-harness#1271. No governed supplier/IF/native-fill, coverage
percentage, performance or duration acceptance is claimed.

## Acceptance criteria

- [ ] Real parsed LF/CR/CRLF caller IDs, endpoint joins and properties remain
  exact through CSV strings and file reads, with identical UTF-8 payload bytes
  on actual Linux and Windows, both insertion orders and no-edge controls,
  proven by the focused command above on both platforms.
- [ ] Actual unchanged Windows production fails the LF/CRLF contracts; each
  named actual Windows translation mutation fails its corresponding contracts;
  exact restoration passes the focused selection with bound immutable evidence.
- [ ] Quoting, complete headers, row counts, output/import names and flags,
  empty/no-edge controls and accepted graph/CSV generator/Cypher behavior remain
  unchanged; protected source/fixtures/selector/pins/goldens are preserved.
- [ ] Original six/refresh/full-suite seal, fresh Windows/standing, exact hosted
  jobs, four substantive agreements and final manual Astra ruling qualify this
  bounded repair alone; docs state its measured contract and limits.

---
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_graphml_exporter.py tests/test_graphml_yed_export_contract.py tests/test_phase12_integration.py -q"
---

# Detailed plan: Preserve Neo4j CSV boundary whitespace

## Task

Resolve treesitter-chunker#448 as one independently reviewed CSV serializer
repair. This is a bounded follow-up to the EXPORT identity work, not completion
of the whole EXPORT phase, XSD validation, a Neo4j server import, or a release.
All accumulated Unreleased changes remain reserved for 6.0.0.

## Research summary

`Neo4jExporter._generate_node_csv` and `_generate_relationship_csv` already use
the real standard-library CSV writer, then call `strip()` on the entire header
and data blocks. The preserved reproduction uses actual parsed same-span Python
chunks and proves that the first node ID and first relationship source lose a
leading space although the graph base retains it. Boundary stripping can also
remove whitespace from the final unquoted property field. String and file
exports share these two generators. The existing `parsed_same_span` fixture and
Neo4j endpoint contracts in `tests/test_graphml_exporter.py` supply real parser
and graph controls; `tests/test_phase12_integration.py` supplies file controls.

## Changes

### `chunker/export/neo4j_exporter.py` (modify)

- In the two CSV generators, replace the four whole-block `strip()` calls with
  `removesuffix("\r\n")`. Each CSV writer uses its unchanged default CRLF record
  terminator; remove exactly its final generated delimiter, preserving every
  field byte. Leave CSV quoting, ordering, properties, headers, Cypher,
  relationship construction, file-writing policy and import commands unchanged.

### `tests/test_graphml_exporter.py` (modify)

- Reuse actual error-free, nonempty `parsed_same_span` chunks. Assign distinct
  caller IDs with leading spaces/tabs and Unicode whitespace; cover both
  insertion orders so the affected first row changes. Build actual node and
  relationship properties with a lexically final string containing trailing
  spaces/tabs/Unicode whitespace, plus ordinary/quoted punctuation controls.
- Parse actual `csv_nodes` and `csv_relationships` with `csv.DictReader`; require
  complete expected node IDs, relationship endpoints/types, row counts, headers
  and exact property values. Compare with the accepted graph's retained IDs and
  endpoints. No mocked parser, exporter, CSV writer, or whitespace normalizer.
- Export the same graph to real temporary files and parse with explicit
  `newline=""`. Require the same spaces/tabs/Unicode-whitespace identities and
  values and unchanged output naming/import-file behavior. Empty and node-only
  graphs retain valid header-only data and omit nonexistent relationship files.
- Existing plain/yEd GraphML identity, character, label and platform controls
  remain byte-for-byte after integration. This slice does not promise embedded
  CR/LF field fidelity through the pre-existing platform file-writing policy;
  any newly reproduced independent defect is filed separately before changes.

### `docs/graphml_export.md` and `docs/export-formats.md` (modify)

- Replace the explicit treesitter-chunker#448 limitation with the precise direct
  Neo4j CSV contract and a compact CSV file example. State that caller IDs and
  field whitespace are data; consumers must retain them when joining endpoints.
  Distinguish direct exporters from the separate package-level structured API.
  Do not broaden GraphML/NetworkX/XSD or live database import guarantees.

### `CHANGELOG.md`, this plan and `plans/manifest.json` (modify)

- Add a consumer-facing Fixed entry qualified with treesitter-chunker#448.
  Register only this plan through the typed manifest helper; retain every
  accepted canonical row exactly. No ledger/checkpoint or consumer-lock edits.

## Dependencies & order

1. Plan first on a clean private worktree. No tests/builds are run by the planning
   invocation. Keep the original historical reproduction as excluded baseline
   context, not final candidate evidence.
2. Accept/integrate treesitter-chunker#449 before test or guide implementation:
   it owns the same contract module and guide. Preserve its accepted manifest
   rows, structural label tests and key-ID migration. Then record this own
   executing lifecycle before production/test edits.
3. Add the real-parser contracts, reproduce their intended failures on unchanged
   production, make the four narrow serializer replacements, and verify the
   focused batch. Preserve independent defects as separate issues.
4. Actually run `strip_node_csv_payload` (restore whole-block stripping only in
   the node generator) and `strip_relationship_csv_payload` (only the relationship
   generator). Each must fail its named identity/property assertions while the
   other exporter controls remain. Restore exact source bytes after each;
   bind source, test and real fixture hashes and rerun the focused batch.
5. Run original six checks, locked environment refresh, full tests/spec_tests,
   fresh Windows focused and unchanged standing platform selection, and all
   required exact-head hosted jobs. Use a private workspace TMPDIR to avoid the
   observed shared tmpfs quota failure. Preserve failed attempts separately;
   require a fresh actual runner seal without rewriting failed artifacts.
6. Freeze the candidate for four independent manually launched tools-enabled
   Opus 5.5 TUI/Gemini 3.8 Flash/Astra/Sol code reviews, maximum three complete
   rounds and heartbeat-only monitoring. Collect every substantive opinion before
   reconciliation. Require the requested manual Astra president's final evidence
   ruling before supported publication closeout/exact-head merge, issue comment
   and closure, evidence archive and safe owned merged-worktree pruning.

## Verification

- `uv sync --locked --all-extras`
- `uv run --locked --all-extras pytest tests/test_graphml_exporter.py tests/test_graphml_yed_export_contract.py tests/test_phase12_integration.py -q`
- `uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site`
- `uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/`
- `uv run --locked --all-extras python scripts/mypy_gate.py`
- `uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py`
- `uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux`
- `uv run --locked --with toml --all-extras python scripts/run_full_suite.py`

Windows runs the actual same-source focused command and unchanged
`scripts/run_platform_core.py --platform windows`. Operational evidence is named
in the private candidate proof: original sealed runner JSON/log, actual Windows
log and launcher exit, four raw review outputs/metadata, mutation bindings and
manual chair ruling. This supplemental evidence is not a governed supplier/IF
gate or a runner-stamped operational amendment: agent-harness#1271 remains open.
No percentage, duration or performance acceptance gate is added.

## Acceptance criteria

- [ ] Real parsed chunks exported as node/relationship CSV strings and files
  retain exact leading spaces/tabs/Unicode caller IDs, endpoint joins and trailing
  property whitespace in both insertion orders; quoting and empty/no-edge controls
  remain valid, proven by the focused command above.
- [ ] Both named actual payload-stripping mutations fail the corresponding
  observable contract; exact source restoration passes the focused command and
  retains accepted GraphML/yEd, parser, fixture, selector, pin and golden bytes.
- [ ] The original six/locked-refresh/full tests/spec_tests run has a fresh valid
  passing seal; actual Windows, exact-head hosted jobs, all four substantive manual
  agreements and final manual Astra ruling support only this bounded repair.

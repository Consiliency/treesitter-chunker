---
phase_loop_plan_version: 1
phase: GRAPHML
roadmap: specs/phase-plans-v4.md
roadmap_sha256: 0a15424c6230b812b095dd9668ecf62bd0457aebdc927533ccde04e6e20cae14
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_package_graphml_whitespace.py tests/test_graphml_exporter.py tests/test_graphml_yed_export_contract.py -q -n 4"
---

# GRAPHML: GraphML exporter fidelity

## Context

Phase 5 of `specs/phase-plans-v4.md` (roadmap hash above, planned from main
`60a5518f`) repairs two independent GraphML exporter defects:

- treesitter-chunker#489 (Tier 1): the package-level
  `chunker.export.GraphMLExporter` (`chunker/export/formats/graph.py`)
  pretty-printed by reparsing its ElementTree output with `xml.dom.minidom`.
  On Python 3.12, minidom writes attribute TAB/LF/CR back literally, and a
  later XML parse normalizes them to spaces, so distinct caller chunk IDs and
  their edge endpoints can merge.
- treesitter-chunker#488 (Tier 3): the direct
  `chunker.export.graphml_exporter.GraphMLExporter.export()` writes through
  `Path.write_text()` with native newline translation. On Windows a compact
  caller text leaf containing CRLF becomes CRCRLF in the file and decodes as
  two LF characters, while `export_string(pretty_print=False)` decodes as one.
  The yEd exporter and its `use_yed=False` delegated route inherit `export()`.

Status inputs at planning time: both issues open, both reproduce (see the
lane VB-1 records). GRAPHML has no upstream phase. FOLLOWUP lane SL-gml
(treesitter-chunker#453, decided as D2 = namespaced caller-label key in
`docs/development/backlog-decisions-v4.md`) waits for this phase because it
edits the same direct exporter files; treesitter-chunker#453 is not done here.

## Interface Freeze Gates

None. Neither lane changes a public signature. The only private signature
change is `chunker/export/formats/graph.py::GraphMLExporter._prettify_xml`,
which now takes the built `ET.Element` instead of a serialized string.

## Lane Index & Dependencies

SL-pkg — Package exporter whitespace IDs (treesitter-chunker#489)
  Depends on: (none)
  Blocks: (none)
  Parallel-safe: yes (disjoint code files from SL-direct)

SL-direct — Direct compact file newline transport (treesitter-chunker#488)
  Depends on: (none)
  Blocks: FOLLOWUP SL-gml (treesitter-chunker#453)
  Parallel-safe: yes (disjoint code files from SL-pkg)

Both lanes edit `CHANGELOG.md` and adjacent sentences of one paragraph in
`docs/graphml_export.md`. Whichever PR merges second rebases and resolves that
text conflict; no behavior depends on the order.

## Lanes

### SL-pkg — Package exporter whitespace IDs

- **Scope**: Replace the minidom reparse in the package exporter with
  ElementTree indentation, retaining the existing data, declaration,
  decoded-text and malformed-input contracts. Own the docs paragraph that
  distinguishes the two exporter APIs. One PR.
- **Owned files**: `chunker/export/formats/graph.py`,
  `tests/test_package_graphml_whitespace.py`, `docs/graphml_export.md` (the
  package-exporter section and the sentence that pointed at
  treesitter-chunker#489), `CHANGELOG.md`, the registration lines in
  `scripts/run_ci_smoke.py` and `scripts/run_platform_core.py`, and this plan.
- **Tasks**:
  - test: Parse `tests/fixtures/graph_same_span.py` with the real Python
    parser and take its two function chunks. Give them caller IDs
    `caller<sep>中文` and `caller 中文` for TAB, LF and CR, with relationships
    in both directions. Export through `io.StringIO`, a UTF-8
    `io.TextIOWrapper`, a `Path` and a `str` path. Assert both IDs stay
    distinct, edges keep source/target direction and their data, node data
    leaves equal the chunk attributes, caller chunks are unchanged, and a real
    NetworkX `read_graphml` of the file sees the same nodes and directed edges.
  - test: Retention. The declaration `<?xml version="1.0" ?>`, the metadata
    comment, `xsi:schemaLocation`, the key order and a trailing newline are
    kept. Text leaves decode as before: space-TAB-space and LF unchanged,
    CR and CRLF become LF, Unicode and XML metacharacters unchanged. Byte
    routes carry the string output with native newline translation.
  - test: Retention. NUL, U+FFFE and a control character in a caller value
    raise `ExpatError`, and a lone surrogate raises `UnicodeEncodeError`,
    before anything is written: the stream is empty and no file is created.
  - impl: `_prettify_xml(root)` runs the former expat well-formedness check
    on the compact serialization, normalizes text-leaf CR/CRLF to LF (what the
    minidom reparse did), applies `ET.indent(root, space="  ")` and returns the
    declaration, the tree and a trailing newline. Drop the minidom import.
  - docs: A "Package-level structured exporter" section that distinguishes the
    package API from the direct modules and records the repaired contract and
    regeneration advice. CHANGELOG entry under Fixed.

### SL-direct — Direct compact file newline transport

- **Scope**: Decide and document the compact file/string decoded-text policy,
  and make compact files match it on Windows for the plain, yEd and delegated
  routes. One PR.
- **Policy (this lane's decision)**: a GraphML file's decoded text equals the
  decoded `export_string()` output with the same options, on every platform
  and route. Compact files contain exactly the UTF-8 bytes of the compact
  string (written with `newline=""`), so a caller CR, LF or CRLF leaf decodes
  the same way in both. Pretty files keep their existing behavior: text leaves
  are already LF-normalized and files keep native newline translation, so
  their decoded text was already equal and their bytes do not change. No
  caller value is normalized; compact string output is unchanged.
- **Owned files**: `chunker/export/graphml_exporter.py`,
  `chunker/export/graphml_yed_exporter.py` (only if needed; the yEd and
  delegated routes inherit `export()`), `chunker/export/graph_exporter_base.py`
  (single-writer, only if needed), `tests/test_graphml_exporter.py` (the
  text-normalization contract and its output helper), `docs/graphml_export.md`
  (the #488 sentences), `CHANGELOG.md`.
- **Tasks**:
  - test: Extend `test_graphml_text_normalization` (real parsed
    `graph_same_span.py` chunks; plain, yEd and delegated routes; compact and
    pretty; string and file) with a non-ASCII CRLF leaf, and replace its
    Windows-only `A\n\nB` expectation with the policy: file leaves decode like
    the string. The output helper asserts compact file bytes equal the UTF-8
    compact string and pretty file bytes equal the native-newline string.
  - impl: `GraphMLExporter.export()` writes compact output with `newline=""`
    and pretty output as before.
  - docs: Replace the "compact Windows files can still turn CRLF..." limit
    with the policy. CHANGELOG entry under Fixed.
- **Platform**: The defect exists only under Windows text-mode translation.
  VB-1 and the old-code VB-2 run use native Windows (`ssh win`) in a clean
  temporary checkout of the exact SHA, removed afterwards. The Linux run of
  the same test passes on old and new code. Hosted Windows platform-core
  already runs `tests/test_graphml_exporter.py`.

## Execution Notes

- Execute SL-pkg and SL-direct on separate branches off `origin/main`, one
  issue per PR. The parent runs the two-reviewer panel (VB-4); the execution
  agent does not merge or request reviews.
- Windows preflight (both lanes change export formatting) runs via `ssh win`
  only in a clean temporary clone checked out at the exact PR head, never the
  shared `~\code\treesitter-chunker` checkout; the clone is deleted afterwards.
- Host caps: one heavy run at a time, at least 6 GiB available before a heavy
  run, `pytest -n` at most 4, scratch under `$TMPDIR`. `scripts/run_ci_smoke.py`
  hard-codes `-n auto`, so local smoke runs its `CI_SMOKE_TESTS` selection with
  `-n 4`; each PR records that substitution.
- The minidom defect is version-specific: Python 3.13+ minidom escapes
  attribute whitespace, so `M489-minidom` is caught on the 3.12 interpreter the
  locked environment and CI use, not on 3.13+.

## Verification

- `uv run --locked --all-extras pytest tests/test_package_graphml_whitespace.py tests/test_phase12_integration.py tests/test_structured_export_integration.py tests/test_export_integration_advanced.py -q -n 4`
- `uv run --locked --all-extras pytest tests/test_graphml_exporter.py tests/test_graphml_yed_export_contract.py -q -n 4`
- The CONTRIBUTING.md local validation block (Ruff, Black, mypy gate,
  governed body-type check, and the CI smoke selection at `-n 4`).
- The Windows preflight and the lane's focused tests on native Windows at
  each PR head, plus hosted Linux/macOS/Windows platform-core.

Named mutations (each fails its focused test and passes once restored):

1. `M489-minidom` — restore `minidom.parseString(ET.tostring(root,
   encoding="unicode")).toprettyxml(indent="  ")` as the body of
   `_prettify_xml`: the 12 TAB/LF/CR ID cases fail on Python 3.12.
2. `M489-unchecked` — drop the expat well-formedness check: the malformed
   input cases fail because output (or an empty file) is written.
3. `M488-native` — drop `newline=""` from the compact write (the old code):
   on native Windows the compact CRLF leaf and compact file-byte cases fail.

## Acceptance Criteria

- [ ] EC-GRAPHML-1 — treesitter-chunker#489, by
  `tests/test_package_graphml_whitespace.py` on Python 3.12; falsified by
  `M489-minidom` (and `M489-unchecked` for the retained rejection).
- [ ] EC-GRAPHML-2 — treesitter-chunker#488, by
  `tests/test_graphml_exporter.py::test_graphml_text_normalization` on native
  Windows (preflight host and hosted Windows job); falsified by `M488-native`.
  The policy is documented in `docs/graphml_export.md`; there is no blanket
  whitespace normalization.
- [ ] EC-GRAPHML-3 — VB-1 to VB-4 for each PR.

## Spec Closeout Plan

- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: issue acceptance for treesitter-chunker#488,
  treesitter-chunker#489
- evidence paths: `plans/phase-plan-v4-GRAPHML.md`, PR logs, Windows preflight
  log
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`

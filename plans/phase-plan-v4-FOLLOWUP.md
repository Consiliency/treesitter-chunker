---
phase_loop_plan_version: 1
phase: FOLLOWUP
roadmap: specs/phase-plans-v4.md
roadmap_sha256: a96ef9073df2cd1bd860b1a151d75abc0a7edde7f242d8a2d7613c3fb38726c9
automation:
  suite_command: "uv run --locked --all-extras pytest tests/test_graphml_caller_label_import.py tests/test_graphml_exporter.py tests/test_graphml_yed_export_contract.py tests/test_cr_only_python_lines.py tests/test_python_outer_call_sites.py tests/test_call_reference_guard.py -q -n 4"
---

# FOLLOWUP: Decision-gated follow-ups

## Context

Phase 14 of `specs/phase-plans-v4.md` (roadmap hash above, planned at main
`228fa6c4`) implements the owner-chosen dispositions recorded in
`docs/development/backlog-decisions-v4.md` (OWNERDEC, 2026-10-31):

| Lane | Issue | Decision | Record |
|---|---|---|---|
| SL-gml | treesitter-chunker#453 | D2 = (b) namespaced caller-label key; `label` stays structural | IF-0-OWNERDEC-2 |
| SL-cr | treesitter-chunker#471 | D3 = (a) CR→LF for parsing with an exact raw byte-offset map | IF-0-OWNERDEC-3 |
| SL-call | treesitter-chunker#516 | D4 = (a) implement outer call sites; goldens regenerated in the same PR | IF-0-OWNERDEC-4 |
| SL-dl | treesitter-chunker#357 | D1 = (c) both: verified prewarm route and a configurable download deadline | IF-0-OWNERDEC-1 |

Status inputs at planning time: all four issues are open, each carries the
owner decision comment, and the three executed issues reproduce on main
`228fa6c4` (see the lane VB-1 records). GRAPHML (treesitter-chunker#553,
treesitter-chunker#557) has merged, so SL-gml is unblocked. SL-dl is planned
here but **not started**: its files (`chunker/_internal/registry.py`,
`chunker/_internal/factory.py`, `chunker/parser.py`) are being rewritten by the
open, merge-gated ADMIT SL-reg PR (treesitter-chunker#558).

## Interface Freeze Gates

None of the executed lanes adds a public signature.

- SL-gml changes the declared GraphML `attr.name` of caller metadata whose
  name matches `(caller_)*label`; key IDs and values are unchanged. This is a
  consumer-visible schema change for name-keyed readers, recorded under
  CHANGELOG "Breaking".
- SL-cr adds a private parse-bytes helper in `chunker/core.py` used by the
  regular and streaming entries. Reported rows and lines for lone-CR Python
  input change (they become correct); byte offsets and content do not.
- SL-call adds Python call facts (one per callable-return expression). Existing
  facts keep their IDs.

## Lane Index & Dependencies

SL-gml — Namespaced caller-label GraphML name (treesitter-chunker#453)
  Depends on: GRAPHML (merged)
  Blocks: (none)
  Parallel-safe: yes (only lane touching the GraphML exporters)

SL-cr — CR-only Python parsing with raw byte fidelity (treesitter-chunker#471)
  Depends on: treesitter-chunker#535 (merged)
  Blocks: SL-call golden regeneration (single writer)
  Parallel-safe: yes for code (disjoint files from SL-call)

SL-call — Outer Python call sites for callable-return expressions (treesitter-chunker#516)
  Depends on: SL-cr for golden regeneration order only
  Blocks: (none)
  Parallel-safe: yes for code; regenerates goldens last

SL-dl — First-use grammar download deadline and verified prewarm (treesitter-chunker#357)
  Depends on: ADMIT SL-reg (treesitter-chunker#558) merging
  Blocks: (none)
  Parallel-safe: no while treesitter-chunker#558 is open (same files)

Every lane edits `CHANGELOG.md`, and SL-gml, SL-cr and SL-call each append to
the `scripts/run_ci_smoke.py` / `scripts/run_platform_core.py` selections.
Whichever PR merges later rebases and resolves those text conflicts; no
behavior depends on the order.

**Golden single-writer rule.** SL-cr and SL-call may both change Boundary IR
goldens. SL-cr regenerates first; SL-call regenerates last, on top of SL-cr's
merged state. Neither fixture corpus under `tests/fixtures/boundary_ir/repos/`
contains a lone CR or a Python callable-return call at planning time, so both
lanes expect a no-diff regeneration and record it. If a lane does produce a
golden diff, SL-call is opened only after SL-cr merges, or states in its body
that it regenerates after SL-cr merges.

## Lanes

### SL-gml — Namespaced caller-label GraphML name

- **Scope**: In the direct `chunker.export.graphml_exporter` and
  `graphml_yed_exporter` modules (plain, yEd and `use_yed=False` delegated
  routes), declare caller metadata named `label` with
  `attr.name="caller_label"` so a name-keyed reader (NetworkX) exposes both the
  structural `label` and the caller value. One PR.
- **Naming rule (follows existing conventions)**: key IDs stay `n_<name>` /
  `e_<name>` and the structural keys stay `node_label` / `edge_label` with
  `attr.name="label"`. Caller names of the form `(caller_)*label` gain one
  `caller_` prefix in `attr.name` (`label` → `caller_label`, `caller_label` →
  `caller_caller_label`, ...); every other caller name is declared unchanged.
  The map is injective and never yields `label`, so every declared name in a
  domain stays distinct.
- **Owned files**: `chunker/export/graphml_exporter.py`,
  `tests/test_graphml_caller_label_import.py` (new),
  `tests/test_graphml_exporter.py` (the label-key disjointness contract),
  `docs/graphml_export.md`, `CHANGELOG.md`, the registration lines in
  `scripts/run_ci_smoke.py` and `scripts/run_platform_core.py`, and this plan.
  The yEd module inherits the key declarations and needs no edit.
- **Tasks**:
  - test: Real parsed `tests/fixtures/boundary_ir/repos/python/app/service.py`
    chunks with caller `label`, `caller_label`, `caller_caller_label` and
    `metadata_label` node metadata and caller edge `label`/`caller_label`.
    Import with the installed NetworkX (`parse_graphml` for strings,
    `read_graphml` for files) on the plain and delegated routes, compact and
    pretty. Assert `label` equals the chunk's structural type (`CALLS` for the
    edge) and each caller value appears under its independently listed
    declared name.
  - test: yEd import. NetworkX replaces `label` with its yEd graphics label
    text (reader behavior, documented); `caller_label` and the other caller
    names are still present with their values.
  - test: Key IDs unchanged, structural keys declare `label`, declared names
    unique per domain; the existing disjointness test now checks the declared
    names too.
  - impl: `_caller_attr_name()` used by `_register_attributes` (validation
    probe) and `_create_key_elements`.
  - docs: "Caller label names for name-keyed readers" section replacing the
    NetworkX limitation paragraph; CHANGELOG entry under Breaking (6.0.0 is
    published, so this is for the next release).
- **Platform**: Export formatting changes, so the Windows preflight runs in a
  clean temporary clone at the exact head.

### SL-cr — CR-only Python parsing with raw byte fidelity

- **Scope**: For Python, parse a copy of the source in which each lone CR
  (CR not followed by LF) is replaced by LF, and walk/slice the raw source.
  Cover the regular entry (`chunk_text`, and `chunk_file` through it) and the
  streaming entry (`StreamingChunker.chunk_file_streaming`). One PR.
- **Byte map**: the replacement is one byte for one byte, so the map from
  parse offsets to raw offsets is the identity; the helper asserts equal
  length. Tree-sitter counts rows by LF, so after the replacement a physical
  line ending (LF, CRLF or lone CR) advances exactly one row. Chunk content and
  every metadata slice still come from the raw bytes, so spans point at the
  physical bytes. CRLF and LF input parse exactly as before.
- **Language scope**: Python only. The Python language reference treats a lone
  CR as a line terminator everywhere (including inside triple-quoted strings),
  so the parse copy has the same meaning as the raw file. Other languages keep
  their current behavior; changing them is outside treesitter-chunker#471.
- **Owned files**: `chunker/core.py` (the parse call in `chunk_text` plus the
  helpers), `chunker/streaming.py` (the parse call in
  `chunk_file_streaming`), `chunker/vfs_chunker.py` (the VFS streaming parse,
  review round 1), the call-site line index in `chunker/symbol_graph.py`
  (review round 1; runner decision, so SL-call merges `main` in after SL-cr),
  `tests/test_cr_only_python_lines.py` (new),
  `docs/chunk-identity.md` (the CR-only paragraph), `CHANGELOG.md`, and the
  smoke/platform-core registration lines.
- **Tasks**:
  - test: The recorded fixture bytes
    `def alpha():\r    return 1\r\rdef beta():\r    return 2\r`, plus mixed
    LF/CRLF/CR and CR-inside-triple-quoted-string fixtures, written as files.
    Independent oracles: byte offsets from `bytes.index` on the raw file, rows
    from counting `\n`, `\r\n` and lone `\r` terminators in the raw prefix
    (computed with `bytes.splitlines(keepends=True)`, not by the product).
    Assert no parse error, function lines, byte spans and raw content for
    `chunk_file`, `chunk_text` and `chunk_file_streaming`, and that LF/CRLF
    results are unchanged.
  - impl: `_lone_cr_parse_copy(source, language)` in `chunker/core.py`; the
    regular, streaming and VFS streaming entries parse its result and walk the
    raw bytes. Call-site and Boundary IR call lines use
    `_line_ending_offsets(source, language)`, which counts the same line
    endings. Other languages: treesitter-chunker#601.
  - docs: replace the "CR-only parsing is not covered" paragraph with the
    contract; CHANGELOG under Fixed.
  - goldens: regenerate on the locked stack; expected no diff (recorded).

### SL-call — Outer Python call sites for callable-return expressions

- **Scope**: In `PythonMetadataExtractor.extract_calls`, a `call` whose
  function is itself a `call` (for example `getattr(obj, 'audit')()`) is
  emitted as its own call site with the raw callee bytes and span of that inner
  call expression. The inner site is unchanged. One PR.
- **Contract**: the outer site's `raw_reference` and `name` are the raw callee
  source (`getattr(obj, 'audit')`), its `callee_start`/`callee_end` are the
  inner call's byte span, and its call span is the outer call. The symbol graph
  produces a distinct `call_site_id` (the span is part of the identity), the
  owner is the enclosing definition, and the complex reference stays
  unresolved under the existing treesitter-chunker#515 guard (no candidates,
  never bound to a local `audit`). Chained returns (`f()()()`) emit one site
  per call level. A parenthesized callable-return callee (`(f())()`,
  `(getattr(o, 'a'))()`) is also covered, with the exact parenthesized bytes
  as the raw callee (runner decision on D4's scope, review round 1).
  Subscript callees are not callable-return expressions and stay excluded;
  the JavaScript equivalent is a follow-up.
- **Owned files**: `chunker/metadata/languages/python.py`,
  `tests/test_python_outer_call_sites.py` (new),
  `tests/test_call_reference_guard.py` (the explicit coverage-limit test
  becomes the positive contract), `CHANGELOG.md`, the smoke/platform-core
  registration lines, and any regenerated Boundary IR goldens.
  `chunker/metadata/extractor.py` and `chunker/symbol_graph.py` are touched
  only if needed.
- **Tasks**:
  - test: Real-parser fixtures for `getattr(obj, 'audit')()`, `f()()()`,
    `self.factory()()`, `mod.make(x)(y)`, a repeated outer call, a comment
    inside the inner call's argument list (`getattr(obj,  # audit\n 'audit')()`,
    which must stay unresolved), and a decorator `@make()()`. Independent byte oracle from `bytes.index`, line from counting
    LF. Assert outer and inner facts, distinct IDs, owners, unresolved outer
    references in strict and permissive modes, import/dependency results
    unchanged, and regular versus `chunk_file`-metadata parity.
  - impl: handle `func_node.type == "call"` (and a parenthesized `call`) in
    `_extract_python_call_info`.
  - goldens: add a callable-return call to the Python Boundary IR fixture and
    regenerate with `scripts/regenerate_boundary_goldens.py` on the locked
    stack after SL-cr merges, run twice for idempotence, and commit the
    reviewed golden diff.

### SL-dl — First-use grammar download deadline and verified prewarm (planned, held)

- **Hold**: Not started. ADMIT SL-reg (treesitter-chunker#558) rewrites
  `chunker/_internal/registry.py`, `chunker/_internal/factory.py` and
  `chunker/parser.py`, and ADMIT is merge-gated (EC-ADMIT-9). SL-dl starts on
  main after treesitter-chunker#558 merges, and re-reads
  treesitter-chunker#357 first.
- **Scope (D1 = both)**:
  - a bounded, verified prewarm route (a CLI command and a Python API) that
    downloads the platform grammar bundle ahead of first use and verifies its
    SHA-256 against the official language-pack manifest before placing it in
    the language-pack cache;
  - a configurable download deadline used by first-use acquisition, with an
    actionable error naming the deadline, the artifact and the prewarm
    recovery command when it expires.
  The parser execution deadline (`ParserConfig.timeout_ms`,
  treesitter-chunker#143 / treesitter-chunker#207) stays separate and is not
  reused.
- **Open technical point**: language-pack 1.20's `PackConfig` exposes
  `cache_dir`, `languages` and `groups` but no download timeout. The lane
  first establishes, from the installed package, whether the deadline can be
  passed through or whether chunker must own the bundle fetch (deadline plus
  manifest check) and hand the verified bundle to the pack cache. Parser pins
  never change. If neither is possible without a pin change, the lane stops
  and reports.
- **Owned files (expected)**: `chunker/_internal/factory.py` or
  `chunker/_internal/registry.py` (acquisition wrapper), a new private
  download helper, the CLI command module, `docs/` (installation and
  troubleshooting), `CHANGELOG.md`, and a new test file.
- **Tests (EC-FOLLOWUP-2)**: a local HTTP server serving throttled bytes (no
  public network) proves the deadline expiry error and recovery, the prewarm
  success path, and SHA-256 rejection of a tampered bundle against a pinned
  manifest; download and parse deadlines are shown independent.
- **Platform**: touches paths, download and config, so the Windows preflight
  applies.

## Execution Notes

- One branch per lane off `origin/main`, one issue per PR. The parent runs the
  two-reviewer panel (VB-4); the execution agent does not merge or request
  reviews and does not force-push after a PR opens.
- This plan is committed with the SL-gml PR.
- Windows preflight runs via `ssh win` only in a clean temporary clone at the
  exact PR head (`git rev-parse HEAD` must match), with every `uv` call using
  `--directory <clone>`; the clone is removed afterwards. Code Integrity 3077
  blocks and treesitter-chunker#547 native-probe flakes are recorded, not
  fixed here.
- Host caps: one heavy run at a time, at least 6 GiB available and load under
  about 28 before a heavy run, `pytest -n` at most 4, scratch under `$TMPDIR`.
  `scripts/run_ci_smoke.py` hard-codes `-n auto`, so local smoke runs its
  `CI_SMOKE_TESTS` selection with `-n 4` (treesitter-chunker#567).

## Verification

- Narrow: the frontmatter `suite_command` names the test files added by all
  three executed lanes, so it runs only after treesitter-chunker#596,
  treesitter-chunker#598 and treesitter-chunker#600 have merged. Before
  then, run each lane's own files: SL-gml
  `tests/test_graphml_caller_label_import.py tests/test_graphml_exporter.py
  tests/test_graphml_yed_export_contract.py`; SL-cr
  `tests/test_cr_only_python_lines.py`; SL-call
  `tests/test_python_outer_call_sites.py tests/test_call_reference_guard.py`.
- The CONTRIBUTING.md local validation block (Ruff, Black, mypy gate, governed
  body-type check, CI smoke selection at `-n 4`).
- SL-cr and SL-call: `scripts/regenerate_boundary_goldens.py` twice, then
  `pytest tests/test_boundary_ir_golden_snapshots.py tests/test_boundary_ir_determinism.py`.
- Hosted Linux/macOS/Windows CI green at each head.

Named mutations (each fails its lane's new test and passes once restored):

1. `M453-attr-name` — `_caller_attr_name` returns the name unchanged (the old
   behavior): NetworkX plain/delegated imports lose the structural `label`.
2. `M453-single-prefix` — rename only the exact name `label`: caller
   `caller_label` collides with the renamed `label` in NetworkX.
3. `M471-raw-parse` — parse the raw bytes in the regular entry (the old code):
   regular-path line and error assertions fail.
4. `M471-raw-stream` — parse the raw mmap in the streaming entry: streaming
   assertions fail.
5. `M471-normalized-slice` — walk the normalized bytes: raw-content
   assertions fail.
6. `M516-drop-outer` — return `None` for a `call` callee (the old code): outer
   site assertions fail.

## Acceptance Criteria

- [ ] EC-FOLLOWUP-1 — Each executed lane implements exactly its OWNERDEC
  option (D2 = b, D3 = a, D4 = a); SL-dl is planned and held.
- [ ] EC-FOLLOWUP-2 — treesitter-chunker#357: deferred to the held SL-dl lane.
- [ ] EC-FOLLOWUP-3 — treesitter-chunker#453 by
  `tests/test_graphml_caller_label_import.py` (real NetworkX import);
  treesitter-chunker#471 by `tests/test_cr_only_python_lines.py` (raw-byte and
  row oracles, regular and streaming); each falsified by its named mutations.
- [ ] EC-FOLLOWUP-4 — treesitter-chunker#516 by
  `tests/test_python_outer_call_sites.py`; complex targets stay unresolved;
  goldens regenerated on the locked stack, idempotent.
- [ ] EC-FOLLOWUP-5 — VB-1 to VB-4 for each PR.

## Spec Closeout Plan

- schema: `spec_delta_closeout.v1`
- decision: `no_spec_delta`
- target surfaces: issue acceptance for treesitter-chunker#357,
  treesitter-chunker#453, treesitter-chunker#471, treesitter-chunker#516
- evidence paths: `plans/phase-plan-v4-FOLLOWUP.md`, PR logs, Windows preflight
  logs
- redaction posture: `metadata_only`
- missing or malformed evidence: `blocker_class=contract_bug`

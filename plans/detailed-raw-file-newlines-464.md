---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Preserve raw file newlines through regular parsing

## Task

Resolve treesitter-chunker#464: for valid UTF-8 regular files, chunk content and
byte spans refer to actual source bytes rather than a newline-normalized copy.
Preserve strict BAML decoding, existing replacement fallback and identity-path
semantics. Correct CRLF outputs and occurrence IDs belong to 6.0.0 migration.

## Research summary

`chunker/core.py::chunk_file` uses universal-newline Path.read_text for non-BAML
files; streaming uses raw mmap bytes. On accepted e6ee50e1, actual no-error CRLF
Python parsing yields two regular chunks whose raw byte slices do not roundtrip,
while streaming chunks do. Actual same-path IDs differ. The private accepted-main
reproduction binds exact bytes/source hashes. The existing span-roundtrip test
also fails on Windows default CRLF fixture creation. This is a production input
decoding defect, separate from unnamed selection in treesitter-chunker#446.

## Changes

### `chunker/core.py` (modify)

- In the existing non-BAML UTF-8 try branch, open the same path in text mode with
  `encoding="utf-8", newline=""` and read without translation. Use the existing
  context manager pattern, available on supported Python3.11+; do not use the
  newer Path.read_text newline kwarg. Preserve UnicodeDecodeError replacement
  fallback, BAML branch, caller identity_path and R Markdown extraction logic.
- No walker, selector, streaming, metadata or identity algorithm changes.

### `tests/test_spans_roundtrip.py` (modify)

- Retain the existing complete roundtrip/parity contract. Add real checked-in
  Python service/same-span fixture bytes written as explicit LF and CRLF, with
  ASCII/Unicode-prefix variants and retrieval metadata modes.
- Independently parse actual source bytes without errors. For both public APIs,
  check exact source slices, complete type/span/content/node-ID/parent-ID/routes
  tuple equality at the same canonical path, named declarations/real parents,
  and nonempty expected fixture chunks. No mocks or output line-count gates.
- Prove explicit identity_path remains independent of physical read location:
  same actual bytes at two paths with the same alias retain IDs and parents.
  Do not promise streaming identity aliases that its public API does not expose.
- Add a real UTF-8 replacement-fallback control; decoded replacement output is
  deliberately lossy and is excluded from raw-byte roundtrip claims. Existing
  strict BAML invalid UTF-8 and R Markdown tests remain unchanged controls.
- LF baseline identity/content projections must remain exact; CRLF corrections
  intentionally change content/offsets/occurrence IDs, not identity algorithms.
  CR-only statement-delimited Python is outside the LF/CRLF parsing contract.

### `docs/chunk-identity.md`, `CHANGELOG.md` (modify)

- Document valid UTF-8 raw-newline preservation and CRLF occurrence-ID migration
  for 6.0.0, unchanged LF IDs/algorithms and replacement-fallback limitations.
  Keep streaming language transformation exceptions and cache treesitter-chunker#358
  separate; advise use_cache=False until cache identity repair is accepted.

### Own plan and `plans/manifest.json` (modify)

- Own detailed-plan row/executing lifecycle only; preserve canonical rows.
  No parser pins, golden edits, consumer locks, admitted ledger or checkpoints.

## Dependencies & order

1. Preserve failed treesitter-chunker#463 R1 and collect all four opinions before
   any selector reconciliation. Wait active original runner before Git mutations.
   Accept independent Windows fixture repair treesitter-chunker#465 first.
2. Publish plan-only draft on then-current main; planning runs no tests/builds.
   Add declared tests and reproduce actual accepted-source CRLF failures before
   changing decoding. File any additional independent defect separately.
3. Change only the non-BAML read branch. Named mutation
   `normalize_regular_file_newlines` restores universal-newline reading and must
   fail declared CRLF content/span/API identity cases while LF controls pass.
   Exact restore must pass. Bind actual outputs, exits and source/test/support
   hashes; preserve accepted before/after LF projection evidence.
4. Narrow real parsing, then original six/locked refresh/full suite under short
   private TMPDIR. Existing strict BAML and real R Markdown controls must pass.
   No type-baseline absorption or hand-edited Boundary goldens.
5. Fresh actual exact-head Windows focus and standing, required hosted jobs,
   four manual tools-enabled CODE seats (max3 complete rounds/heartbeat only),
   supplemental Astra chair, standalone archive, authorized exact-head merge,
   qualified issue closure and safe owned pruning precede resuming selector PR.

## Verification

- `uv sync --locked --all-extras`
- Narrow: `uv run --locked --all-extras pytest tests/test_spans_roundtrip.py -q`
- Focus: `uv run --locked --all-extras pytest tests/test_spans_roundtrip.py tests/test_core_span_consistency.py tests/test_baml_language.py tests/test_r_language.py tests/test_streaming.py -q`
- Repository Ruff, Black, mypy gate, CI smoke and Linux platform-core commands
  from CONTRIBUTING.md, run by the original sealed six-check runner.
- `uv run --locked --with toml --all-extras python scripts/run_full_suite.py`
- Actual Windows exact focus and unchanged standing preflight, actual launcher0.

Private `chunker-464-` packet binds actual accepted baseline, mutation/restoration,
LF retained IDs and intentional CRLF changes, current Windows/support hashes,
original sealed runner, hosted checks, four raw opinions and final chair.
Supplemental, not agent-harness#1271 governed amendment or IF/supplier/native-fill/
whole-phase/release acceptance. Later selector acceptance requires fresh gates.

## Acceptance criteria

- [ ] Actual LF/CRLF valid-UTF8 fixture chunks roundtrip raw file bytes and both
  APIs retain exact same-path spans/content/IDs/parents/routes for stated cases,
  proven by narrow/focus commands with independent raw AST controls.
- [ ] LF retained projections, explicit identity aliases, replacement fallback,
  strict BAML and R Markdown controls pass; intentional CRLF ID migration and
  exclusions are documented without global-parity/cache claims.
- [ ] Named universal-newline mutation fails CRLF contracts with LF controls
  passing; exact restoration passes and all evidence hashes/actual exits bind.
- [ ] Fresh original six/refresh/full seal, current Windows/standing, exact
  hosted, four substantive CODE opinions and final supplemental chair qualify
  only decoding. Selection, protected pins/goldens/locks/state remain unchanged.

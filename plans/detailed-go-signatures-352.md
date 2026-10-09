---
automation:
  suite_command: uv run --locked --all-extras pytest tests/test_metadata_extraction.py tests/test_boundary_ir_golden_snapshots.py tests/test_boundary_ir_determinism.py -q
---

# Detailed plan: Go callable signature fields

## Task

Implement the independently landable Go contribution to SIGNATURE in
`specs/phase-plans-v3.md`, covering treesitter-chunker#352 and separately recorded
treesitter-chunker#483. Go was authorized as an inline repair; this artifact
records its bounded execution and supported-publication context. It is not a
claim of independent plan-panel acceptance, completion of EC-SIGNATURE-1, or
acceptance of the other eight language slices.

## Research summary

The locked Go grammar exposes `name`, `receiver`, `parameters` and `result`
fields. Method names are `field_identifier` nodes; the first method parameter
list is the receiver. A result's node type varies, so searching for node type
`result` also loses ordinary-function returns. The public formatter already
accepts Go's source-text parameter strings and complete result strings.

## Changes and ownership

- Modify `chunker/metadata/languages/go.py`, `extract_signature`: use the actual
  fields for names, arguments, results and receiver detection. Preserve result
  parentheses. Exclude receivers from arguments; retain the method modifier.
- Create `tests/fixtures/go_signatures.go`: real pointer/value/unnamed/generic
  receivers, grouped/unnamed/variadic/function-typed arguments, absent/single/
  multiple/named/function-typed results and ordinary-function controls.
- Modify `tests/test_metadata_extraction.py`, `TestGoMetadataExtraction`: assert
  exact signatures through text/file APIs, opt-in semantic text and Boundary IR.
- Regenerate only the intentional `tests/fixtures/boundary_ir/golden/go.json`
  delta through the locked generator; other language goldens must be unchanged.
- Modify `docs/metadata-extraction.md` and `CHANGELOG.md`: document Go's existing
  source-text parameter representation, receiver exclusion, result preservation
  and refresh of stored signature/semantic-text metadata.
- Own this plan and its appended `plans/manifest.json` control entry, preserving
  all previous canonical rows. No parser pins, consumer locks, type baselines,
  historical train ledgers, checkpoints or foreign held branches are owned.

## Documentation impact

No new SignatureInfo/Boundary schema keys or vocabulary. Receiver type is not
added to the signature; no Go interface-method contract or resolved type claim.
Structural/occurrence identity algorithms remain unchanged. Existing Unreleased
breaking changes require the separately guarded 6.0.0 release; no tag here.

## Dependencies and order

1. Actual locked-parser and public-output reproduction; independently record
   ordinary-function result loss as treesitter-chunker#483 before fixing it.
2. Tests first, then the field-lookup repair; generated snapshot and docs.
3. Kill each named source mutation and restore the exact source bytes.
4. Local checks, full suite and native Windows validation; supported draft
   publication, exact-head hosted checks and four independent manual CODE seats
   (Opus 5.5 TUI, Gemini 3.8 Flash, Astra and Sol). Compact file pointers, tools
   enabled, heartbeat only, maximum three complete substantive rounds. Collect
   all four opinions before reconciliation; an absent opinion is not approval.
5. Reconcile findings and obtain final supplemental Astra president review
   before separately authorized exact-head merge and owned worktree pruning.
   Retain verification/review evidence before pruning. Rust and C++ remain
   their own PRs; treesitter-chunker#354 remains six independently reviewed PRs.

## Verification

```sh
uv run --locked --all-extras pytest tests/test_metadata_extraction.py -k TestGoMetadataExtraction -q
uv run --locked --all-extras python scripts/regenerate_boundary_goldens.py
uv run --locked --all-extras pytest tests/test_metadata_extraction.py tests/test_boundary_ir_golden_snapshots.py tests/test_boundary_ir_determinism.py -q
uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --locked --all-extras python scripts/mypy_gate.py
uv run --locked --all-extras python scripts/run_ci_smoke.py
uv run --locked --all-extras python scripts/run_platform_core.py --platform linux
uv run --locked --all-extras python scripts/run_full_suite.py
```

Generate twice and compare the resulting tree; the second pass must add no
delta. Original source/test/fixture SHA-256 bindings and raw mutation logs reside
in the explicitly owned private evidence directory
`/home/viperjuice/workspace/evidence/treesitter-chunker/go-signatures-352/preparation-20261009`.
Its `verify.py mutations` injects source changes in this owned worktree, invokes
the actual focused pytest command and restores original bytes in `finally`.
No code-under-test mocks or percentage gate.

Named mutations: `identifier_only_method_name` reintroduces identifier-only name
lookup; `receiver_as_parameters` chooses the first parameter list;
`omitted_result` discards the extracted result. Each must exit 1 with contract
assertions; the exact restored candidate must exit 0. Native Windows must run
the focused contracts and standing `scripts/run_windows_preflight.py` on the
same candidate source; hosted CI confirms the exact commit matrix. Remote host
launcher problems are diagnosed without changing host policy or user work.

## Acceptance criteria

- [ ] Go signatures and documented receiver/result representation are exact
  through text/file and Boundary consumers — focused command and suite above.
- [ ] Each named mutation is caught and exact restoration passes — private
  `verify.py mutations`, hash-bound logs and `mutations.json`.
- [ ] Only the intended generated Go signature/semantic-text delta occurs,
  second generation is idempotent, all local/native/hosted checks and four
  exact-head CODE opinions plus final Astra are reconciled — commands above
  and retained verification/review artifacts. Manual reviews are supplemental,
  not governed supplier/native/IF or whole-phase acceptance. Final review and
  host records are bound to the candidate in the publication verification
  artifact and PR evidence amendment; no proxy host evidence is substituted.

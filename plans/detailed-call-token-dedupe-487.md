---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Preserve distinct relationship references (treesitter-chunker#487)

## Task

Repair only the distinct-token de-duplication defect in treesitter-chunker#487.
The existing graph resolves `target`, `ns.target` and `other.target` to the
same target and keeps only the first call. Preserve one relationship for each
distinct normalized reference within `(from, to, type)`, while retaining
deduplication of repeated identical references. This applies to the assembler's
imports, dependencies and calls. Existing normalization and resolution stay
as they are; this patch does not assert that its heuristic targets are correct.

Qualified calls suppressed as self-edges, Python qualification loss, colliding
file/module anchors, raw call-site facts and `.mts` discovery remain follow-up
work under the open issue. Do not close treesitter-chunker#487 for this slice.

## Research summary

`chunker/symbol_graph.py::assemble_symbol_graph` currently keys relationships
by `(from_id, to_id, relationship_type)` after normalization/resolution.
Real JavaScript and TypeScript extraction preserves qualified call tokens in
per-file facts but assembly loses them. Boundary IR `_edge_record` already
includes reference in edge identity, so surviving distinct tokens naturally
get distinct IDs. Incremental records cache raw symbol facts and reassemble
the graph, so the fix also applies to existing warm caches without a cache-key
or schema change. Boundary IR's frozen resolution vocabulary remains
`resolved`, `ambiguous`, `unresolved` (docs/interface-boundary-spec.md,
Resolution extension); no vocabulary is introduced.

## Changes

- `chunker/symbol_graph.py` — extend the existing set tuple annotation and
  de-duplication key with the normalized `reference`. Keep first-occurrence
  ordering, same-reference deduplication, self suppression and resolution intact.
- `tests/test_symbol_graph_resolution.py` — add real JS/TS fixtures with
  `target()`, `ns.target()`, `other.target()` and a repeated `target()`, in both
  source orders and strict/permissive modes. Assert the actual raw facts retain
  tokens; graph calls preserve each distinct token once, with unchanged target,
  caller/file/line, status/candidates/provenance and accurate relationship counts.
  Add assembler guards for normalized duplicate values and independent
  relationship types using real extracted facts.
- `tests/test_boundary_ir_resolution_modes.py` — prove the same fixture's
  distinct references/IDs/targets and node relationship membership survive
  fresh, cold incremental and warm incremental extraction in both languages
  and modes. Verify persisted raw facts and warm reuse using the existing cache
  record API, and compare canonical outputs. Keep exact duplicate call behavior.
- `docs/interface-boundary-spec.md` — document reference-sensitive graph
  deduplication and its Boundary IR effect. Existing heuristic resolution,
  containing-chunk location and per-token rather than per-call-site scope must
  be explicit. Existing same-reference edge identities remain stable; newly
  retained references increase edge counts and membership.
- `CHANGELOG.md` — add the bounded consumer fix under Unreleased/Fixed, which
  remains reserved for 6.0.0. No release/tag/version change.
- `plans/detailed-call-token-dedupe-487.md` — this plan and reviewed amendments.
- `plans/manifest.json` — supported API append/update of the owned
  `call-token-dedupe-487` record only (originally row71);
  preserve every predecessor row/event. Complete the owned row before final
  head review, with subsequent head gates and review required before merge.

## Documentation impact

Graph and Boundary IR consumers can now receive more edges when distinct
references share a target. They must regenerate affected outputs and must not
equate endpoint identity with call-token identity. No schema, parser pins,
type baseline, ID algorithm or golden bytes are manually changed.

## Dependencies & order

Start from fresh accepted main `f3c15eaef59b149ad74d606a2c3bb87e1b447b59`
in the private owned worktree. Preserve primary/S27/held work and broker state.
Before implementation, obtain four complete independent tools-enabled PLAN
opinions (two fresh Sol seats, Gemini 3.8 Flash, Astra), reconcile together,
and obtain separate Astra design approval. For CODE, obtain the complete same
quartet and separate final Astra audit before merge. Separate maximum three
complete rounds per PLAN/CODE; heartbeat only, no model or silence deadline.
Small prompts and exact-head clones/evidence packets; no peer opinions in seats.
Manual reviews establish no formal Harness/supplier/native/IF qualification.

Continuation after treesitter-chunker#497: integrate accepted main
`ce38dc167c4bff7b2a75fae9f1b5f2d4052072c8` without rewriting branch history.
Preserve all 70 common predecessor manifest records and both independently
appended plan records byte-for-byte, including their original lifecycle events.
The accepted Unicode record stays in its main position; the owned call-token
record follows it as row72. This is a conflict-resolution ordering change, not
a new lifecycle event. Retain both changelog entries and the automatically
merged contract text. No production behavior is added beyond the bounded fix.
Rerun the original local/full, docs, native and hosted gates at the integrated
head. PLAN used one round; CODE used one round, with two rounds remaining.
The parent may perform verified metadata-only upkeep of this session-owned PR
under its existing publishing/repair authority; the runtime metadata gap does
not permit altering admitted inputs or broker state. Keep draft until all gates
and final acceptance pass. Private execution evidence is allowlisted under
`/home/viperjuice/workspace/evidence/treesitter-chunker/call-token-dedupe-487/20261013/`,
its canonical `/mnt/workspace/users/viperjuice/evidence/` alias, the owned
checkout's `.dev-skills/verification/`, and resolved skill handoff/reflection
paths. Preserve prior failed and successful artifacts unchanged.

## Verification

1. Locked Python 3.12 environment: `uv sync --locked --all-extras --python 3.12`.
2. New cases: `uv run --locked --all-extras pytest tests/test_symbol_graph_resolution.py tests/test_boundary_ir_resolution_modes.py -q`.
   Run the new cases against original production before fixing: require the
   designated missing-reference assertion to fail. Candidate passes. Revert
   only the production de-duplication key to its original three fields as the
   named mutation; require the same designated failures and restore exact bytes.
3. Run existing symbol graph, CLI resolution, all Boundary IR and semantic tests.
   Regenerate Boundary IR goldens with the locked script, rerun it for
   idempotence, and verify the golden diff. If changed, include generated paths
   only after an explicit reviewed scope amendment; never hand-edit or repin.
4. Genuine original `run_verification` records locked refresh, Ruff, Black,
   `scripts/mypy_gate.py`, `scripts/run_ci_smoke.py`, Linux
   `scripts/run_platform_core.py --platform linux`, and the effective full
   `scripts/run_full_suite.py` (tests plus spec_tests). Bind exact source/head
   before/after outside the sealed artifact; use private disk TMPDIR.
5. Strict MkDocs build to unique private disk scratch. Actual private Windows
   snapshot runs the new narrow cases and standing `run_windows_preflight.py`;
   bind all tracked source hashes, native Python/runtime versions and outcomes.
   Preserve shared Windows checkout. Hosted Linux/macOS/Windows checks must
   explicitly match the final head.
6. Use supported publication API and link the PR to this T3 thread. Archive and
   independently verify all raw reviews, original/native evidence and receipts
   before normal exact-head merge and safe owned pruning. Preserve failed
   histories. Follow-up issue remains open.

## Acceptance criteria

- AC1: Real JS/TS facts and graph tests retain every distinct call reference
  once despite a shared resolved target, in both source orders and modes;
  normalized duplicates and different relationship types retain their stated
  behavior. Baseline and named key mutation fail only designated assertions,
  with exact byte restoration.
- AC2: Boundary IR fresh/cold/warm tests retain distinct edge identities and
  correct memberships/counts, canonical equality and persisted raw facts.
  Existing determinism/goldens/schema/semantic tests pass; original locked
  checks/full, docs and native Windows checks pass with exact source bindings.
- AC3: Four complete opinions plus independent Astra acceptance, supported
   owned plan-record lifecycle/publication, exact-head hosted checks and verified
  standalone archive precede authorized merge. All 70 predecessor rows,
  protected work, pins/goldens/type baseline and broker state stay preserved;
  treesitter-chunker#487 stays open for the remaining defects.

---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan B: raw call facts per site (treesitter-chunker#496)

## Task and status

Refreshed implementation plan: PLAN0/CODE0; A's reviews do not approve B.
Depends on accepted/merged [plan A](detailed-source-anchors-496-20261017.md).
Current research base is clean merged Plan A head
`36a4e8d3493abe0028535de9b269021f374ec397`, including accepted
treesitter-chunker#495, treesitter-chunker#497, and treesitter-chunker#498.
Read-only release metadata on 2026-10-18 still reports v5.3.0 as latest, so the
selected package 6.0 / syntax IR 3.0 / semantic IR 3.1 train remains unreleased.
The owner selected plan A's coordinated package 6.0.0 and IR 3.0/3.1 migration
on 2026-10-16. Source refresh and independent design review remain required.
No implementation choices below are delegated to an unstated future decision.

This is a second bounded behavior contract: syntax call facts exist before
resolution; their caller, raw token and call-site location depend only on the
same file bytes and logical repo-relative path. A resolved graph is an annotation
over those facts, never a filter. It completes the raw-token/self-call portion
of treesitter-chunker#496 and treesitter-chunker#487; it does not prove spec's
partial absence rule sound or close spec#227. That issue also requires engine
locality checks, bid-shaped-token policy and a fresh downstream soundness board.
Extension discovery, new grammar support and binding-accurate resolution remain
separate work. No whole-language completeness guarantee is inferred from tests.

## Research summary and source falsifiers

Historical draft line references/private board paths below are provenance, not
current line claims or reviewer permission. Daybreak Blue's B refresh report is
`refresh-research.md` in the private B evidence root and is sealed into each B
review packet. Use current symbols at clean `36a4e8d3`. Original 20261016
drafts and all A records remain untouched.

- `chunker/core.py:815–821` already stores detailed `call_spans` but graph facts
  copy only `metadata.calls` strings (`symbol_graph.py:287–304`). Preserve the
  legacy metadata name list and transport detailed spans into per-file facts.
- `chunker/metadata/extractor.py:444–463` has full call and callee byte spans,
  but `name` may be shortened by language-specific extraction.
  `metadata/languages/python.py:151–164` explicitly truncates an attribute to
  its final identifier. Add exact raw callee text without breaking that metadata
  name compatibility. `metadata/languages/javascript.py:452–528` builds call,
  constructor and tagged-template records manually without callee spans;
  TypeScript inherits this extractor (`typescript.py:13–18`).
- `metadata/languages/go.py:124–136` and ordinary Rust calls reuse the base
  helper, so its new raw fields retain qualifiers there too without changing
  legacy names. Rust's manual scoped-macro record at `rust.py:119–155` needs
  explicit correct callee spans; its current final-name-based span is lossy.
- `symbol_graph.py:369–391` resolves first and discards self-resolved calls;
  plan A preserves this until B. `boundary/adapter.py:244–263` still exposes
  containing-definition line with null bytes; adding reference in treesitter-chunker#495 does
  not distinguish repeated sites, including two sites on the same line.
- `chunker/clustering/engine.py:179–192` already suppresses self edges in its
  own projection and sums per-relationship weights. Per-site multiplicity will
  increase observed call counts and cluster weights; this is documented consumer
  behavior, not a reason to silently aggregate away facts in the extractor.

Use actual board `/home/viperjuice/workspace/tmp/panel/adv-p3a/w/probe5.py:4–12`
for CX-dedupe: `clock.stamp() + stamp()`, `clock.ts` defining `stamp`, and a
modeled `legacy.mts` completion. The real upstream fixture uses `legacy.ts` and
assembles the same caller facts with and without that supported-extension file.
treesitter-chunker#495 already repairs the two-token loss; B must additionally test repeated
`stamp()` sites so its baseline genuinely falsifies the stronger contract.

CX-selfedge sources: `probe6b.py:4–32` (method, function, Python),
`probe10.py:4–12` (explicitly modeled extraction of excluded `dist`), and
`probe11.py:3–6` (real single-file full run). Exact TS source is
`export function now(): string { return JSON.stringify(Date.now()); }`.
Use supported `legacy.ts` rather than claiming `.mts` discovery; Python uses
`def now(): return str(datetime.now())` and supported `legacy.py`. Add the
issue's `def time(): return time.time()` and actual recursion controls.
Board analysis pointers and current spec commit/URLs are preserved in plan A.

## Frozen call-fact contract

1. Add `call_facts` to the per-file facts and public assembled graph as the
   resolution-independent list. Each record carries `id`, `from`, `file`,
   `type: "calls"`, `reference`, `location` (`byte_start`, `byte_end`,
   `start_line`, `end_line`), `callee_byte_start`, `callee_byte_end`, and
   `call_kind`. `from` is A's canonical definition key. No target,
   candidates or resolution state is stored in this raw record.
2. `reference` is the exact UTF-8 decoded source slice for the callee expression,
   excluding argument parentheses, preserving qualification, internal spacing,
   Unicode and expression spelling for syntax the current extractors already emit.
   Do not add optional/computed/parenthesized recognition where currently absent.
   No trimming, case folding, dotted-name splitting or terminal-name substitution
   may alter the raw value. Resolution derives its own normalized search string.
   Constructors use the actual constructor expression (e.g. `Foo.Bar`), not an
   invented `new ` prefix; tagged templates use the tag expression; Rust macros
   use the full macro path (without the invocation `!`). Call kind remains
   metadata. Existing `metadata.calls` and `call_spans[].name` keep their legacy
   compatibility values; new raw fields carry the stronger contract.
3. Use absolute-in-file UTF-8 byte offsets with half-open ranges for full call
   expression and callee. Derive actual 1-based line bounds from file bytes;
   `end_line` is the line of the final included byte. Do not use chunk-relative
   offsets or definition start lines. UTF-8, CRLF, nested calls and same-line
   repeated calls are mandatory cases. An empty/absent callee cannot be invented
   from a resolved target or legacy string.
4. Deduplicate raw observations only by `(canonical caller, canonical file,
   call byte_start, call byte_end, callee byte_start, callee byte_end, raw token)`.
   This suppresses duplicate parser traversal reports (including decorators),
   keeps every distinct token at a site, and preserves identical tokens at
   distinct sites. Never include resolved target in this key. Source-order the
   per-file facts. No filesystem/global-resolution data enters their construction.
5. Overlapping enclosing chunks must not duplicate ownership. For a recognized
   call observed in several extracted symbol chunks, choose its smallest
   containing callable chunk; otherwise its smallest containing symbol chunk.
   Resolve a tie by the source-order occurrence key from A. This preserves calls
   in methods/nested functions once, assigned to their innermost extracted
   definition. Do not manufacture module nodes for unsupported top-level calls.
   The contract covers recognized calls in extracted definitions; grammar
   completeness/top-level synthetic ownership are outside both plans.
6. Emit one `calls` relationship and Boundary edge per raw fact. Carry its
   `call_site_id`, exact `reference`, actual `location`, and top-level `file` in
   Boundary edges; retain `metadata.file` with identical spelling for existing
   consumers. Source equals an existing canonical node in that file. Declare typed JSON Schema fields and conditional requirements for syntax
   calls: call_site_id, reference, location and top-level file are required for
   calls only, with integer byte/line fields. Preserve non-call syntax and
   semantic-edge shapes and frozen top-level keys; do not rely on permissive
   additionalProperties as validation.
7. Call fact ID and syntax call edge ID are the same deterministic reuse of the
   project's SHA-1 stable-hash convention over canonical caller, canonical file,
   full-call bounds, callee bounds, exact reference, and relationship type,
   prefixed `call:`. Resolved target
   and candidates are deliberately excluded: adding unrelated files may change
   those annotations but must not churn the call-site ID. Non-call edge ID
   algorithm and imports/dependencies dedupe remain as treesitter-chunker#495 and A define them.
8. Preserve every raw call, including unqualified recursion, qualified calls
   heuristically resolving to self and ambiguous/unresolved calls. Remove
   `to_id == from_id` suppression for calls only. Resolved `to` and sorted
   candidate IDs use A's canonical definition keys; unresolved/ambiguous target
   remains the raw reference. Keep existing strict/permissive provenance and
   resolution vocabulary. A heuristic self target is an annotation, not proof
   of recursion. No new resolver/binding algorithm is in scope.
9. Advance cache format/prefix from A's v2 to v3; old A/v1 records cannot supply
   missing sites/raw qualifiers and must miss/reparse. Persist raw `call_facts`,
   regenerate resolution at assembly, and update dependency summaries to read
   token strings only, never serialize byte offsets as dependency names.
   Reject absent/malformed required call-fact payloads as cache misses rather
   than guessing sites. Existing cache fail-open-to-reparse behavior is reused.
10. On a fixed logical root, per-file projection
    `(id, from, file, reference, full-call span, callee span)` is byte-identical
    for isolated per-file extraction, subset assembly, full assembly and warm
    cache reuse. Resolution/target/provenance annotations may differ. Public
    `extract_symbol_graph(file)` uses `file.parent` as its root today; tests of
    a nested file therefore use `extract_symbol_facts_for_file(file, repo_root)`
    and `assemble_symbol_graph([facts])`, rather than asserting false root equivalence.

These are conventional implementation choices needed to meet the issue's raw
site requirement. The selected migration/version fence is recorded in A.
No additive-only compatibility claim is made about changed graph keys,
call multiplicity, call reference semantics or IDs. Both plans target the same
unreleased coordinated package 6.0.0 and IR 3.0/3.1 major train.

## Changes (modify existing files unless stated)

- `chunker/metadata/extractor.py`: `_create_call_info` and existing recognized
  call collection — raw callee text/bounds, keeping legacy name fields. Dynamic
  recognized callee expressions remain raw facts even when naming cannot resolve
  them; do not broaden language/grammar syntax beyond recognized call nodes.
- `chunker/metadata/languages/javascript.py`: shared JS/TS raw fields for normal,
  constructor and tagged-template records already recognized from real nodes.
- `chunker/metadata/languages/rust.py`: repair the manual macro raw path/bounds
  producer only; ordinary records inherit the base helper.
- `chunker/symbol_graph.py`: raw per-file/public facts, ownership/dedupe,
  per-site call relationship assembly and call-only self suppression removal.
- `chunker/boundary/adapter.py`: syntax call ID/location/file mapping in both
  assembly paths; dependency summary consumes reference strings from facts.
- `chunker/boundary/types.py`, `chunker/boundary/cache.py`: v3/prefix and required
  raw-fact cache validation. Seven Python production files plus schema; no
  general refactor. Python/Go/TypeScript production extractors already pass
  full callee nodes to the shared helper or inherit JavaScript: tests only.
  No grammar recognition expansion or new invalid-UTF-8 replacement promise.
- `chunker/boundary/boundary_ir.schema.json`: declarative per-site syntax edge
  fields/meaning and selected migration policy; no new top-level vocabulary.
- `tests/test_phase15_base_extractor.py`, `tests/test_phase15_languages.py`,
  `tests/test_phase2_extractors.py`: real parser token/span/legacy-name
  compatibility checks, including base helper users and Rust macro paths.
- `tests/test_symbol_graph_incremental_facts.py`,
  `tests/test_symbol_graph_resolution.py`, `tests/test_boundary_ir_resolution_modes.py`:
  raw locality/site multiplicity, self calls, exact source/target/membership and
  IDs under unrelated-file changes, both strict/permissive modes.
- `tests/test_boundary_ir_incremental_runtime.py`,
  `tests/test_boundary_ir_incremental_cache.py`,
  `tests/test_boundary_ir_incremental_impact.py`: v2/v1 misses, actual v3 payload
  reuse and changed/deleted/added-file resolution without changing raw facts.
- `tests/boundary_ir_conformance.py`: core plus conditional call-only edge
  fields; retain exact non-call/semantic shapes and language/provider pins.
- `tests/test_boundary_ir_schema.py`, `tests/test_boundary_ir_required_fields.py`,
  `tests/test_boundary_ir_contract.py`: selected schema, new typed edge fields and
  unchanged non-call/semantic shapes. `tests/test_symbol_graph_cli_resolution.py`
  and `tests/integration/test_clustering_integration.py`: public call-site data,
  endpoint validity and documented increased per-call weighting.
- `docs/interface-boundary-spec.md`, `docs/user-guide.md`, `CHANGELOG.md`: raw token/site contract,
  migration/re-indexing, increased counts/weights, heuristic-target limits.
- `tests/fixtures/boundary_ir/golden/*.json`: only locked generator output.
- `tests/test_boundary_ir_adapter.py`,
  `tests/test_boundary_ir_incremental_contract.py`,
  `tests/test_boundary_ir_semantic_contract.py`,
  `tests/test_boundary_ir_semantic_enrichment.py`,
  `tests/test_boundary_ir_semantic_determinism.py`, and
  `tests/unit/clustering/test_engine.py`: call-only schema/shape distinction,
  cache constants, semantic-shape preservation, and deliberate per-site weight.
- This plan and its existing manifest row/lifecycle after treesitter-chunker#498; no changes to
  shared roadmap, native journals, pins, locks, release files or type baseline.

## Documentation impact

The owned spec/user-guide/changelog must describe raw references/sites, exact byte/line
semantics, per-site count/weight increases, v3 migration and index rebuilds.
Keep A's syntax 3.0/semantic 3.1 mode split and API 1.0. No release/version/pin
or downstream edit. Preserve provider-aware keys and cache-preserving failure
handling from treesitter-chunker#497; provider runtime/key tests remain gates.

## Meaningful falsifiers and named mutations

Use `test_496_call_site_` names in the listed existing test modules:

- Real JS/TS `clock.stamp(); stamp(); stamp();` and a second same-line `stamp()`;
  compare exact raw records alone, with `clock.ts`, with supported `legacy.ts`
  defining another `stamp`, and after removing it. Target statuses may change;
  raw site multiset and call IDs must not. First two-token preservation should
  already pass merged treesitter-chunker#495 and A, while repeated-site assertions must fail baseline.
- Real TS wrapper/function/method `now` calling `JSON.stringify(Date.now())`;
  Python `now` calling `str(datetime.now())`, `time` calling `time.time()`, and
  actual direct recursion `recur()` plus qualified self-name collisions. Assert
  all raw sites survive alone and with supported extra `now`/`time` definitions.
  Preserve expected heuristic outcomes separately; do not claim correct binding.
- Port A's same-stem/dotted-path pair fixtures to per-file call-fact isolation;
  identical tokens/sites in different files survive independently with correct
  source membership. Preserve the original board source links in test comments.
- Two `target()` sites on one line, another on a later line; nested calls,
  nested function/method inside class, decorator duplicate traversal; exact once
  ownership for each distinct span/token. Compare independent byte slicing,
  not production identity helpers as the sole expected oracle.
- Python `obj.sub.now()`, JS/TS `obj . now()`, existing constructors/tags,
  UTF-8 prefix and CRLF. Only already-recognized expression forms are promised. Exact raw
  callee source slices/full-call byte ranges and line oracle must match parser
  source bytes, while existing metadata name tests retain their contract.
- Base-helper Go `fmt.Println` and Rust `ns::macro!`/method call qualifiers:
  qualify facts without adding language-specific resolution policy. Check
  every currently supported metadata extractor's real fixture raw record spans
  are usable and tokens slice its source; do not infer universal call coverage
  from a nonempty Boundary golden.
- Seed actual persisted baseline v2/v1 cache records before source edits; both
  miss/reparse. New v3 records must contain raw facts and actually reuse them
  warm. Add/remove only an unrelated callee file and prove caller bytes/facts
  unchanged while annotations can vary. Fresh/cold/warm canonical parity must
  hold; compare semantic runs separately against equivalent options.

Baseline = accepted A with treesitter-chunker#495. Record designated failing assertions for site
multiplicity, Python raw qualification, location, self preservation and cache
migration; existing treesitter-chunker#495 and A contracts should pass. Candidate passes all.
Named independent mutations: M-B1 restore `(from,to,type,reference)` call dedupe;
M-B2 restore call self suppression; M-B3 use legacy Python terminal `name` for
raw reference; M-B4 replace call site location/ID with definition line;
M-B5 include resolved target in raw fact/edge identity; M-B6 accept old cache
version/payload; M-B7 restore largest/outer containing-owner selection.
Each must fail the matching designated assertion. Restore exact
candidate production bytes after every mutation and preserve genuine outputs.

## Dependencies and review gates

Use A's owner freeze and B's refreshed private-worktree rules. A is merged at
`36a4e8d3`; B's production and plan assumptions are refreshed at that exact head.
Obtain the coordinated independent PLAN quartet and separate Astra approval
before source edits; maximum three full rounds and heartbeat-only policy. No
reviews were started here. Do not release intermediate incompatible IR under an
already-published version. Standing owner authorization covers supported publication, owned metadata
upkeep, normal merge and safe pruning after all gates; no downstream publication
or release is authorized. It does not waive B's separate design/source reviews.

## Verification

Run the following narrow commands on the baseline/new tests, candidate and each
designated mutation during implementation (not during planning):

```bash
uv sync --locked --all-extras --python 3.12
uv run --locked --all-extras pytest tests/test_phase15_base_extractor.py tests/test_phase15_languages.py tests/test_phase2_extractors.py tests/test_symbol_graph_incremental_facts.py tests/test_symbol_graph_resolution.py -q
uv run --locked --all-extras pytest tests/test_boundary_ir_resolution_modes.py tests/test_boundary_ir_incremental_runtime.py tests/test_boundary_ir_incremental_cache.py tests/test_boundary_ir_incremental_impact.py tests/test_boundary_cache_key.py tests/test_boundary_ir_schema.py tests/test_boundary_ir_required_fields.py tests/test_boundary_ir_contract.py -q
uv run --locked --all-extras pytest tests/test_symbol_graph_cli_resolution.py tests/integration/test_clustering_integration.py -q
```

Then run every common broad verification command listed explicitly in A:
semantic tests, locked golden regeneration twice with binary-diff `cmp`, golden
and determinism tests, Ruff, Black, the unchanged mypy gate, smoke, Linux
platform-core, original full `tests/` + `spec_tests/`, strict MkDocs build, actual
isolated native Windows snapshot (B narrow commands plus Windows preflight),
available fleet preflights and final-head hosted matrix. Generated golden
changes must be reviewed; no manual golden edits or parser repins. Preserve
original/native stdout and exact-head/source/runtime bindings, not proxy claims.
The effective full suite command is the frontmatter `automation.suite_command`.

Downstream adoption is separate: spec must update its chunker/schema pins,
re-extract/re-index and reconcile digest fixtures, remove its bug-presence
assertions while preserving ownership regressions, retain `to_token`, and add
edge-file locality validation/per-site projection before revisiting spec#227.
Its current adapter copies every upstream edge without deduplication, but drops
site ID/location/file from E(C); it must expose those when it needs a mechanical
call-site locality witness. Upstream tests do not certify downstream absence rules.

## Operational evidence

Repeat A's clean installed-wheel Python 3.11–3.14 gate on B's exact candidate,
including raw/site fact shapes, self/repeated calls, v2/v1 misses and v3 warm
reuse, both modes and real official Unicode extraction. Use private native
Windows snapshots, available fleet checks and final-head hosted CI. Record
wheel-result.json, native-result.json and hosted-checks.json, with exact source,
artifact/runtime bindings and supported runner-stamped plan amendments; source
suite/proxy receipts cannot substitute for these operational gates.

All new private evidence is written only under
`/home/viperjuice/workspace/evidence/treesitter-chunker/raw-call-sites-496/20261018-after-498/`.
Use the installed typed lifecycle API as
`phase_loop_runtime.plan_manifest.update_lifecycle(repo=Path(<owned-worktree>),
slug="raw-call-sites-496", transition="executing"|"completed", by="codex-execute-detailed",
metadata=<B-only bindings>)`; snapshot and compare the manifest so all 73
predecessor rows and every pre-existing lifecycle event remain equivalent.
Create the canonical verification artifact with installed
`phase_loop_runtime.verification_evidence.run_verification`, owned repo and B
evidence `runner-verification` directory, Python 3.12, locked refresh
`["uv","sync","--locked","--all-extras","--python","3.12"]`, ordinary argv
commands, explicit `bash -lc` only for golden diff/cmp and temporary docs output,
and the frontmatter suite argv. Validate it with
`validate_verification_artifact`.

Copy/adapt A's explicitly allowlisted operational helpers into B's root and bind
their SHA-256 values before use. Invoke them exactly as:

```text
["python", "/home/viperjuice/workspace/evidence/treesitter-chunker/raw-call-sites-496/20261018-after-498/verify-wheel.py", "--repo", "/mnt/workspace/worktrees/viperjuice/treesitter-chunker-raw-call-sites-496", "--out", "/home/viperjuice/workspace/evidence/treesitter-chunker/raw-call-sites-496/20261018-after-498/wheel", "--python", "3.11", "--python", "3.12", "--python", "3.13", "--python", "3.14"]
["python", "/home/viperjuice/workspace/evidence/treesitter-chunker/raw-call-sites-496/20261018-after-498/verify-native-windows.py", "--repo", "/mnt/workspace/worktrees/viperjuice/treesitter-chunker-raw-call-sites-496", "--out", "/home/viperjuice/workspace/evidence/treesitter-chunker/raw-call-sites-496/20261018-after-498/native-windows", "--driver", "/home/viperjuice/workspace/evidence/treesitter-chunker/raw-call-sites-496/20261018-after-498/native-windows-driver.py"]
```

The wheel driver must exercise exact raw/site facts, repeated/self calls,
v1/v2 misses and actual v3 reuse, both IR modes, old-schema rejection, official
providers and installed CLI. The native driver must verify the exact tracked
archive and run B's three narrow pytest commands plus the Windows preflight in a
unique private snapshot while proving the shared Windows checkout unchanged.

## Acceptance criteria

- [ ] B1: first narrow pytest command proves raw token/source-byte spans,
  per-site multiplicity/locality, legacy metadata compatibility and self-call
  preservation; designated baseline failures and M-B1–M-B5/M-B7 failures recorded, including exact innermost ownership.
- [ ] B2: second command proves exact source membership, actual site locations,
  call-ID stability across target-resolution changes, both resolution modes,
  cache migration/reparse and real v3 warm reuse; M-B6 detected.
- [ ] B3: CLI/clustering command proves endpoint coherence and site multiplicity
  are public without silent reaggregation. Shared broad/native/full/golden gates
  from A pass on B's final candidate with generated diff/idempotence evidence,
  clean installed-wheel results and runner-stamped operational bindings.
- [ ] B4: source-refresh, selected migration policy, coordinated independent
  review acceptance and original verification bindings are recorded; no claim
  that treesitter-chunker#495 alone supplied sites or that spec#227 is unblocked by upstream alone.

---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan B: raw call facts per site (treesitter-chunker#496)

## Task and status

Refreshed implementation plan: PLAN2/CODE0; A's reviews do not approve B.
Depends on accepted/merged [plan A](detailed-source-anchors-496-20261017.md).
Current research base is clean merged Plan A head
`36a4e8d3493abe0028535de9b269021f374ec397`, including accepted
treesitter-chunker#495, treesitter-chunker#497, and treesitter-chunker#498.
Read-only release metadata on 2026-10-18 still reports v5.3.0 as latest, so the
selected package 6.0 / syntax IR 3.0 / semantic IR 3.1 train remains unreleased.
The owner selected plan A's coordinated package 6.0.0 and IR 3.0/3.1 migration
on 2026-10-16. Source refresh and independent design review remain required.
No implementation choices below are delegated to an unstated future decision.
Native PLAN1 completed at exact clean head
`d0ae7b412a3689b263e0f539c3f62ccbe7257690`: Gemini agreed; both Sol seats and
Astra required the parenthesized-callee, decorated-wrapper ownership, exact
kind/ID encoding, independently isolated cache-fence, and schema/golden-order
corrections incorporated below. The raw empty Gemini extraction and exact
nested-response recovery are both preserved; this remains one complete round.
Native PLAN2 completed at exact clean head
`eacf80db5879570647752b077230da73f80135d4`: Gemini and Astra agreed; both Sol
seats required explicit tracked fixed-vector/kind/equality assertions and the
remaining NFD/duplicate-method raw-fact controls. Those bounded test-plan
corrections are incorporated below. Run the final allowed PLAN3 quartet and
separate Astra design president before production edits.

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
   `call_kind`. `from` is A's canonical definition key. `call_kind` is the
   producer's existing nonempty `type` value when present (`function`, `method`,
   `super`, `constructor`, or `tagged_template`); shared-helper records default
   to `call`, and the repaired scoped Rust record uses `macro`. Duplicate
   observations use the selected owner's value, then source-order occurrence
   order for an otherwise exact tie. No target,
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
   A record exists only when the current producer returns call metadata; call
   nodes currently dropped by a producer (including unsupported dynamic JS
   callees) remain out of scope. For already-emitted parenthesized Go and C/C++
   calls, the shared helper walks the supplied callee node's ancestors to the
   direct child of the call node, preserving the complete grouped expression
   without adding syntax recognition or language-specific production edits.
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
   definition. A Python `decorated_definition` wrapper is a transparent
   ownership container: a decorator call outside the inner definition span is
   assigned to the first contained retained definition whose `parent_context`
   is `decorated_definition`, in source occurrence order, and remains exactly
   once after ordinary site dedupe. Do not manufacture module nodes for
   unsupported top-level calls.
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
   project's SHA-1 stable-hash convention. The exact seed is the UTF-8 encoding
   of `"|".join(str(value) for value in (caller, file, call_byte_start,
   call_byte_end, callee_byte_start, callee_byte_end, reference, "calls"))`;
   retain the full lowercase 40-hex digest and prefix `call:`. For the fixed
   vector `caller-id|src/app.py|10|18|10|16|target|calls`, the ID is
   `call:db4aa2584c80ce295d03d6b5c1ce7f1b6dea99a2`. Fact `id`, relationship
   `call_site_id`, and syntax call edge `id` are identical. Resolved target
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
  call collection — raw callee text/bounds, keeping legacy name fields; recover
  the direct callee-expression ancestor for already-recognized parenthesized
  Go/C/C++ paths. Producer-dropped dynamic syntax stays out of scope; do not
  broaden language/grammar recognition.
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
  compatibility checks, including base helper users, Go `(fn)()`, C/C++
  `(*ptr)()`/nested grouping, decorator calls and Rust macro paths.
- `tests/test_symbol_graph_incremental_facts.py`,
  `tests/test_symbol_graph_resolution.py`, `tests/test_chunk_id_collision.py`,
  `tests/test_boundary_ir_resolution_modes.py`:
  raw locality/site multiplicity, self calls, exact source/target/membership and
  IDs under unrelated-file changes, both strict/permissive modes, NFD file
  spelling, and duplicate same-name method sites across isolated/full and
  fresh/cold/warm assembly.
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
- Independently assert the frozen ID vector
  `call:db4aa2584c80ce295d03d6b5c1ce7f1b6dea99a2`, the `call:` plus 40-lowercase-
  hex representation, and exact equality of raw fact `id`, graph relationship
  `call_site_id`, and syntax edge `id`. Real base, JS constructor/tag/super and
  Rust macro records assert their specified `call_kind` values in the metadata
  extractor narrow command; M-B4/M-B5 must fail the appropriate identity
  assertion rather than only a derived graph count.
- Python `obj.sub.now()`, JS/TS `obj . now()`, existing constructors/tags,
  UTF-8 prefix and CRLF. Only already-recognized expression forms are promised. Exact raw
  callee source slices/full-call byte ranges and line oracle must match parser
  source bytes, while existing metadata name tests retain their contract.
- Base-helper Go `fmt.Println` and Rust `ns::macro!`/method call qualifiers:
  qualify facts without adding language-specific resolution policy. Check
  every currently supported metadata extractor's real fixture raw record spans
  are usable and tokens slice its source; do not infer universal call coverage
  from a nonempty Boundary golden.
- Port A's NFD-path and duplicate same-name method/overload fixtures into B raw
  assertions. For each, assert exact canonical `file`, distinct canonical
  `from`, independently sliced spans/references, distinct per-site IDs, and
  fact/relationship/edge ID equality under isolated facts with a fixed logical
  root, full assembly, incremental cold and actual warm reuse. Do not change
  Unicode normalization, identity hashes or overload resolution.
- Before production edits, preserve genuine accepted-A v2 record/index bytes
  and hashes under the private B `baseline-cache-v2/` evidence directory. In
  tracked tests construct otherwise-valid same-schema 3.0 cases that isolate:
  v1 index version, v2 index version, v1/v2 record versions, v1/v2 key prefixes,
  missing v3 `call_facts`, and malformed v3 fact fields/types. Hold every other
  gate valid in each negative case, assert miss/reparse, and bind M-B6 to these
  assertions so a prefix or schema mismatch cannot mask weakened payload
  validation. New v3 records must contain raw facts and actually reuse them
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
uv run --locked --all-extras pytest tests/test_phase15_base_extractor.py tests/test_phase15_languages.py tests/test_phase2_extractors.py tests/test_symbol_graph_incremental_facts.py tests/test_symbol_graph_resolution.py tests/test_chunk_id_collision.py -q
uv run --locked --all-extras pytest tests/test_boundary_ir_resolution_modes.py tests/test_boundary_ir_incremental_runtime.py tests/test_boundary_ir_incremental_cache.py tests/test_boundary_ir_incremental_impact.py tests/test_boundary_ir_incremental_contract.py tests/test_boundary_cache_key.py tests/test_boundary_ir_required_fields.py tests/test_boundary_ir_contract.py tests/test_boundary_ir_schema.py -k 'not golden_snapshot_matches_schema' -q
uv run --locked --all-extras pytest tests/test_symbol_graph_cli_resolution.py tests/integration/test_clustering_integration.py -q
```

Then regenerate locked goldens twice and compare the binary diffs before the
complete `tests/test_boundary_ir_schema.py` module, followed by semantic tests,
golden/determinism tests, Ruff, Black, the unchanged mypy gate, smoke, Linux
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

### Authorized Plan B test-remediation cycle 1

The owner authorized one bounded test/evidence remediation cycle after the
original PLAN3/CODE3 exhaustion and independent Astra HOLD.  The original
rounds, opinions, findings, and HOLD remain preserved.  This cycle may change
only `tests/test_boundary_ir_resolution_modes.py`,
`tests/test_symbol_graph_incremental_facts.py`,
`tests/test_chunk_id_collision.py`, this plan amendment, and this plan's own
manifest row through the supported typed lifecycle API.  Production, schemas,
goldens, package metadata, parser pins and locks remain frozen.  The repair must
make M-B5 fail first at direct syntax-edge/raw-site identity, add independent
expected full-call bytes and complete byte/start-line/end-line oracles, and
exercise the accepted JS/TS/Python strict/permissive and TypeScript method
locality dimensions while keeping raw facts/IDs separate from resolution
annotations.

Private reads for this cycle are limited to the owned tracked checkout, its
plan/environment, relevant installed skill/runtime code, this B evidence root
and the exact prior-A pointers already allowlisted by `brief-B.md`:
`refresh-research.md`, `archives/final-closeout-A.json`,
`archives/final-handoff-A.md`,
`test-remediation-cycle1/parent-acceptance-audit.json`,
`test-remediation-cycle1/production-equivalence.json`, top-level
`test-remediation-cycle1/*.py`, `implementation-A/verify-wheel.py`,
`implementation-A/verify-native-windows.py`,
`implementation-A/native-windows-driver.py`, and `review-seat.py`.  Do not
traverse other private, broker, raw-history, credential, or unrelated evidence
sources.  New private output is restricted to
`/home/viperjuice/workspace/evidence/treesitter-chunker/raw-call-sites-496/20261018-after-498/test-remediation-cycle1/`;
all prior B evidence remains immutable.  Skill-owned handoff and reflection
destinations remain allowed.

The fresh cycle starts at CODE0/3 and requires complete native quartets with
Sol 1 and Sol 2 (`gpt-6-sol`), Gemini 3.8 Flash, and Astra, followed by a
separate independent native Astra president.  All four terminal opinions must
complete before reconciliation; native subscription CLIs, independent clean
exact-head clones, read-only tool-enabled review, heartbeat-only operation, and
no model/silence timeout are mandatory.  A subsequent round receives the
original contract, every prior finding and response, and unresolved objections.
Final acceptance requires four `AGREE` opinions plus separate Astra `APPROVE`
on the exact verified head.  Parent retains publication, PR/CI/archive, merge,
comments, and pruning.

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

### Hosted byte-buffer repair in cycle 1 CODE3

The hosted review of treesitter-chunker#499 reproduced a production defect at
accepted local head `b5c6e249c0f643e16c6a4c16313b09234ce04518`: core parses a
replacement-decoded UTF-8 buffer for malformed input, while per-file call-fact
extraction reread the original undecodable bytes and applied parser offsets to
that different buffer. The authorized repair extends this cycle's ownership
only to `chunker/symbol_graph.py::extract_symbol_facts_for_file`, the existing
`tests/test_symbol_graph_incremental_facts.py`, this specification's parser-
buffer note, and this plan amendment. The manifest remains byte-identical with
its existing lifecycle warning; all original findings, opinions, HOLDs, prior
APPROVE, artifacts, and `b5c6e249` acceptance remain historical evidence.

The correction reconstructs the same replacement-decoded UTF-8 buffer that
core parsed before slicing call sites. Malformed-input byte coordinates
therefore address that parsed buffer. Valid UTF-8 bytes and line endings remain
unchanged. The regression covers Python and JavaScript ASCII, EOF, and non-
ASCII callees; strict and permissive resolution; both `fail_fast` values;
independent callee/full-call byte and line oracles; per-file/full-graph parity;
and fresh, cold, and warm Boundary extraction with a warm-reparse failure spy.
The existing valid UTF-8/CRLF oracle remains the preservation control.

New repair evidence is restricted to
`test-remediation-cycle1/hosted-buffer-repair/`. Its copied and adapted private
operational helpers are exactly
`hosted-buffer-repair/operational/verify-wheel.py`,
`hosted-buffer-repair/operational/verify-native-windows.py`, and
`hosted-buffer-repair/operational/native-windows-driver.py`. Verification must
retain the failing `b5c6e249` regression, the restored targeted mutation, narrow
tests followed by every applicable genuine locked gate, Python 3.11–3.14 wheel
probes with malformed-call retention/location assertions, and isolated native
Windows coverage including the updated tracked regression. The final exact
head then consumes cycle 1 CODE3/3 with native Sol 1, Sol 2, Gemini 3.8 Flash,
and Astra opinions completed before reconciliation, followed by a separate
independent Astra president. No fourth CODE round is available.

### Authorized line-index remediation cycle 2

The owner authorized a new bounded `B/line-index-remediation-cycle2` at
CODE0/3 after the post-cycle1 performance HOLD on exact clean head
`9d16aaf626e05eabe881339d53b234856ee5e1f0`. This is neither CODE4 nor a reset
of the exhausted original B PLAN3/CODE3 or cycle1 CODE3 counters. All earlier
HOLDs, approvals, opinions, archives, and broker records remain immutable. Up
to three fresh complete CODE quartets are available, followed by a separate
independent Astra president; final acceptance requires four `AGREE` opinions
and a separate `APPROVE` on the exact verified head.

This cycle owns only `chunker/symbol_graph.py`,
`tests/test_symbol_graph_incremental_facts.py`, and this bounded plan
amendment. Production work is limited to precomputing newline-byte offsets once
per `_call_facts_for_chunks` call and using `bisect_left` in `_line_bounds` for
the existing counts before `start` and `max(start, end - 1)`. Output fields,
identities, parser-buffer reconstruction, cache/schema/version behavior, and
all other algorithms remain unchanged. The tracked tests add real-parser
Python/JavaScript UTF-8 LF/CRLF minified and many-line cases, exact byte/line
oracles and per-site IDs, a deterministic prefix-work budget, exactly-one
newline-index-scan accounting scoped to the tested buffer, and explicit nested
multiline outer/inner calls. This bounds only the line component to
O(N + C log(L+2)) time and O(L) memory; it makes no whole-extractor complexity
claim. No public documentation changes are required because observable output
semantics are unchanged (`doc_delta_decision=no_doc_delta`).

New private reads are restricted to the previously authorized B root and exact
earlier-A pointers. New writes are restricted to
`/home/viperjuice/workspace/evidence/treesitter-chunker/raw-call-sites-496/20261018-after-498/line-index-remediation-cycle2/`
plus skill-resolved handoff/reflection destinations. Copy and adapt only the
cycle1 hosted-buffer helper files into cycle2 `run-final-verification.py`,
`operational/verify-wheel.py`, `operational/verify-native-windows.py`,
`operational/native-windows-driver.py`, and the existing native review-seat,
launch, and audit helpers. Installed environments and caches are excluded from
review packets. `plans/manifest.json` remains read-only: its existing failed
row has no supported failed-to-executing transition, so retain a lifecycle
warning and prove all 74 rows/history and its byte digest unchanged.

Before the production repair, the formatted new regression must fail the
deterministic scan budget on `9d16aaf6`. After repair it must pass. Two required
source-valid falsifiers then restore the old prefix scans and rebuild the
newline index per fact respectively; each must fail its matching budget before
the exact production bytes are restored and the targeted tests pass. Retain
stdout, stderr, exit codes, tracked hashes, and restoration bindings. Run the
narrow tests first, then the canonical locked refresh and applicable original
17 commands, genuine full suite, unchanged/idempotent locked goldens, strict
docs, Python 3.11-3.14 installed-wheel probes containing the new line-work and
multiline checks, and isolated native Windows execution of the updated tracked
regression. Renew exact clean-head verification bindings before native review.

Native review uses two Sol (`gpt-6-sol`), Gemini 3.8 Flash, and Astra through
native subscription CLIs in read-only, tools-enabled, independent clean clones
with sealed packets. All four valid terminal opinions complete before
reconciliation. Accepted objections are repaired and fully reverified before a
successor round, within the three-round cap. Heartbeat-only operation applies;
there is no model or silence deadline, no fourth round, and no counter reset.
The parent retains every publication, PR metadata, hosted review/CI, archive,
merge, issue, release, downstream, and pruning action.

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

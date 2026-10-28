# Private governed GROUP proposals

`tools/governed_group.py` is an input-only private source adapter over the existing
`ClusteringEngine`, weight calculator, hierarchy builder and metrics calculator.
It does not discover source, parse files, implement a new clustering algorithm,
write a consumer fixture, or modify the public Boundary IR API. Use a pinned,
quiescent producer checkout and its locked Python 3.12 environment. An editable
checkout reporting distribution metadata `6.0.0` is an unpublished source overlay,
not a replacement release of published 6.0.0.

```sh
python tools/governed_group.py --request request.json \
  --expected-request-sha256 "$EXPECTED_REQUEST" \
  --expected-source-binding-sha256 "$EXPECTED_SOURCE" \
  --expected-profile-sha256 "$EXPECTED_PROFILE" --output /absolute/absent/output
```

The caller independently freezes all three expected identities. A candidate's
self-hashes provide no authority. The CLI has no user-selected import path,
callback, executable, parser or network input. Source-profile checking reads only
explicitly listed producer files under the adapter's own checkout, never the
analyzed repository. The trusted consumer supplies complete native facts from its
verified selected stage, and separately validates its original scope/native joins.

## Request and profile

`chunker.group.request.v1` has exactly `schema`, `source_binding`, `graph`,
`producer`, `settings`, `policy`. The frozen private field meanings are shared with
the governing continuation contract; unsupported schema fields refuse.

- `source_binding`: repo/revision, declaration/selection/metadata/included inventory,
  scope driver and graph digests; per-file coverage records/digest; native producer
  and symbol-identity profile. Coverage rows contain `path`, `status` and optional
  `diagnostic_refs`. Status is `processed`, `processed_no_symbols`,
  `skipped_by_producer_filter`, or `failed`. Skipped/failed need diagnostics.
- `graph`: complete `symbol_lookup` and `relationships`, plus native call facts,
  errors, metadata and unknown native fields. Symbol file paths must join selected
  coverage. Opaque IDs, repeated facts and unknown arrays retain their meaning.
- `producer`: source commit anchor, explicitly labelled distribution/source overlay,
  source-file path/SHA256 rows, lock SHA256, complete installed distribution versions,
  dependency artifact hashes or explicit null, Python patch/Unicode/platform profile.
  Include adapter, package initialization, symbol producer and clustering modules;
  every loaded Chunker module must join the declared source closure. Profiles should
  bind the full producer closure. The fixture builder enumerates the Chunker source
  files outside the adapter; the adapter performs no analyzed-source traversal.
  A null artifact hash is unverified. A nonnull artifact pin requires matching
  installed `direct_url.json` archive SHA256 evidence; unavailable archive identity
  refuses. Version equality is not a claim of wheel-archive verification.
- `settings`: explicit seed, five existing weights, coarse/fine resolution,
  infrastructure toggle/threshold, and all four fixed limits. No hidden defaults.
- `policy`: mode, policy/intended revision, independently supplied correspondence
  digest, declared boundary/member arrays, unassigned IDs and override references.
  Membership is a complete disjoint partition. Spec owns correspondence, raw-IR
  projection, overrides and intended/approved architecture. Chunker neither builds
  a crosswalk nor treats hash-string equality as a cross-domain join.

Native finite numbers remain in their own JSON domain. Booleans are not numeric
settings. Integers outside signed 64-bit, nonfinite/over-1e100 magnitudes, lone
surrogates, duplicate JSON keys, excessive JSON depth and malformed fields refuse.
Weights are nonnegative, resolutions positive, threshold in [0,1], seed in
[0,2147483647]. Caps are exactly 2,000 symbols, 20,000 total relationship/call/error
records, a 16 MiB request transport and a 16 MiB output budget; caps cannot be raised
by a request. No truncation. The output budget is aggregate, with two separate
limits: the encoded worker result is at most 16 MiB, and the byte sum of all five
published files (`request.json`, `raw_graph.json`, `raw_engine.json`,
`operational.json`, `proposal.json`) is at most 16 MiB. Exceeding either refuses
`group_compute`, which retains only `diagnostic.json` and no proposal. Complete facts
repeat across the retained request, raw graph and proposal, and `request.json` counts
in the sum beside a similarly sized `raw_graph.json`, so the 16 MiB transport cap is
not usable request capacity: an admitted request well below 16 MiB can still refuse.
One recorded genuine replay's 4.48 MB request produced a 15.59 MB aggregate; that is
retained arithmetic, not an admissible-input threshold. Callers measure headroom from
the artifact byte counts in `operational.json` plus that file's own size.

## Normalization and identities

J is UTF-8 `json.dumps(sort_keys=True, separators=(',', ':'), ensure_ascii=False,
allow_nan=False)`, without newline or Unicode normalization. N sorts only:

- Graph relationships, call facts and errors by J(record), preserving duplicates.
- Coverage records by path and their diagnostic references by J(record).
- Policy membership by boundary ID, each member list and unassigned IDs by opaque
  ID, override references by J(record).
- Producer source files by path and dependencies by name. Object keys sort under J.

Every other native array retains order. For D(label,x), hash
`b'chunker.group.' + label + b'.v1\n' + J(x)`. Request hashes N(request);
source-binding hashes its normalized source binding; profile hashes the producer,
settings and policy object; graph and coverage hash their normalized bodies.
Profile identity includes policy, so profile change alone is not called settings
change. Preserve -0.0 and exact finite values, without rounding/tolerance.

Group ID uses domain `chunker.group.membership.v1\n` and exactly
`{policy_revision,parent_members,heuristic_level,members}` with sorted member lists.
Roots have `parent_members=[]`. Numeric Leiden enumeration IDs are not stable
architecture identity. Independent membership comparisons use member sets and
parent memberships, not the IDs themselves. Proposal identity uses domain
`chunker.group.proposal.v1\n` and the entire proposal without `proposal_digest`.
Operational timestamps, raw-file hashes and locators are excluded.

## Computation and output

Declared mode reports the supplied partitions and explicit neutral unassigned
bucket using existing graph/metrics methods. Dependency-assisted mode runs the
existing engine separately inside every hard boundary and the unassigned bucket.
Strong crossing edges cannot merge boundaries. Empty/single/disconnected inputs
remain explicit, never proof of source absence. Returned memberships must cover
their parent exactly, without duplicates, invented members or broken nesting.

Every original relationship remains in `proposal.relationships`.
`omitted_graph_facts` entries have `{relationship_index,reason,fact}`; the index
addresses that complete normalized relationship array. Reasons are `unresolved`,
`ambiguous`, `missing_endpoint`, `external`, `unsupported_kind`, `self_loop`, or
`cross_hard_boundary`. Fact is the complete record, not a name-only summary.
Noncomputable facts remain evidence, not proof of edge absence.

Groups have `{id,parent_id,heuristic_level,members,metrics,reasons}`. Reasons is an
array of `{boundary_id,mode,authority:'proposal_only'}`; null boundary ID means
neutral unassigned. Engine `container/component/code` values are heuristic levels,
not validated runtime roles. Metrics are the existing calculator's induced-graph
topology metrics, not compliance scores. `metrics.by_group` uses canonical IDs;
`metrics.weighted_edges` preserves actual finite accumulated weights. Raw native
integer cluster-edge summaries remain explicitly labelled operational information.

Coverage contains `records`, `status`, `symbols`, `relationships`,
`omitted_by_reason`, `unknowns`. Status is `partial` for failed/skipped files or
native errors, otherwise `complete_within_selected_source`. It never means whole
repository coverage. Unknowns retains failed/skipped rows; processed-empty remains
distinct. Proposal approval is always `proposal_only`, conferring no grant,
ratification, native IR parity or certificate correctness.

An absent output directory outside the producer checkout receives `request.json`
(exact input transport), `raw_graph.json` (J of the original parsed graph, all fields
and native array order retained), `raw_engine.json` (actual responses/effective
settings), `operational.json` (hashes, resources, locators), then `proposal.json`.
The proposal is published last via a completed pending file. Reversed transport
arrays can change raw file hashes while semantic proposal bytes remain equal.
Neither raw file hashes nor operational data are injected into semantic identity.

Refusal order: transport size; schema/types/domains; independent identities/source;
membership then coverage; record/profile budgets; installed dependency/import
binding; computation/output. Named refusals exit 1. Dependency mismatch/unavailability
is `group_dependency`, exit 2, never an empty successful group. Argument/setup errors
exit 2. Validation failure creates no output. Computation failure retains a diagnostic
without a ready proposal. Existing output is never overwritten.

One owned native compute child runs at a time per invocation. The parent applies a
120-second watchdog, samples RSS with a 1 GiB stop threshold, and reaps/terminates
its own child on failure. This is engineering supervision of trusted native
dependencies, not a hostile-execution sandbox or strict OS-enforced memory cap.
Controllers serialize GROUP invocations; tests share a lock even under xdist.
Qualify only measured Python/OS/dependency profiles; seed alone does not establish
cross-version/OS reproducibility. GROUP tests and qualification use the scope
driver's Linux validation tier. Request wire paths are POSIX-relative on every host.
macOS and Windows GROUP execution is unqualified, and ordinary platform-core results
do not exercise it. Root-dependent native identities remain explicitly
non-comparable instead of being scrubbed.

Run the locked scope/group/clustering focused suite normally and with optimized
explicit controls. Genuine native fixtures must use actual staged extraction and
independent expected joins. The frozen fake normalization vector is serialization
evidence only and cannot authorize CLI producer acceptance. Consumer owners alone
refresh their pinned fixture copies after the qualified IF-GROUP-1 handoff.

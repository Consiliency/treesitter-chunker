---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan A: definition-scoped graph anchors (treesitter-chunker#496)

## Status and boundary

Plan refresh in Default mode; production implementation has not begun. This is the first
of two sequential, independently reviewable contracts. Plan A fixes definition
identity and edge ownership; plan B fixes raw per-call-site facts, including the
remaining self-call and Python qualification failures in treesitter-chunker#487.
The owner selected the version-policy freeze below on 2026-10-16. These plans
still require source refresh and independent design review before implementation.
They are not implementation evidence. A's complete native PLAN1 quartet found
bounded plan corrections; PLAN2 confirmed most repairs and found two remaining
handoff/falsifier corrections, now reconciled below. A requires the final
allowed PLAN3 quartet plus separate Astra president approval before
implementation. B is
interface context only and remains PLAN0 until A merges and B is refreshed. Each bounded
plan has its own maximum three complete PLAN rounds and three CODE rounds.

Implementation base: accepted main `931f6e05208faf1b1ca94520584cb4c45bff51b1`,
the merged treesitter-chunker#495, including treesitter-chunker#497. The former
adds normalized `reference`
to `(from, to, type)` dedupe and does nothing else. Its repeated-identical-token
dedupe, containing-definition line, self suppression and heuristic resolution
are intentional limits, not a per-call-site contract.

Pinned upstream primary sources:
[assembler](https://github.com/Consiliency/treesitter-chunker/blob/f3c15eaef59b149ad74d606a2c3bb87e1b447b59/chunker/symbol_graph.py#L209-L391),
[adapter](https://github.com/Consiliency/treesitter-chunker/blob/f3c15eaef59b149ad74d606a2c3bb87e1b447b59/chunker/boundary/adapter.py#L762-L881),
[frozen compatibility policy](https://github.com/Consiliency/treesitter-chunker/blob/f3c15eaef59b149ad74d606a2c3bb87e1b447b59/docs/interface-boundary-spec.md#L148-L180),
and [treesitter-chunker#495 production delta](https://github.com/Consiliency/treesitter-chunker/pull/495/files).

Owned successor branch: `codex/source-anchors-496`, under private
`WORKTREE_ROOT`. Primary main remains protected at
`b9be38a3b8159dd24497963314028a1630608b19`. Initial planning status was empty.
The two original 20261016 drafts remain untouched in their retained worktree.
Register the successor plans through the supported typed manifest API,
preserving all 72 accepted predecessor records and lifecycle events. No roadmap,
ledger, checkpoint, broker or historical evidence rewrite.

The source findings below originated in the retained draft; f3c15eae links and
line references are historical. Daybreak Blue refreshed source at 931f6e05;
`refresh-research.md` is sealed in the review packet with SHA-256
`f490b3339820e9d10be093e7c3815769417c5b08b0188d8f4134eb15c05f84f4`.
Use current file/symbol pointers for implementation. Historical private paths
below are provenance, never reviewer read permission.

## Research evidence

Retained historical findings, superseded by the refresh where stated:

- `chunker/symbol_graph.py:93–120,209–305,341–391`: module names strip the final
  extension and `__init__`; graph dictionary keys and caller contexts use
  `module:qualified_name`. Per-file assignment and cross-file `update` can
  overwrite definitions before assembly. Current four-field dedupe cannot
  restore definitions lost before assembly.
- `chunker/types.py:41–90`: `definition_id` hashes path, language and structural
  route; `node_id` additionally carries byte position and content. Changing the
  hash algorithm is unnecessary. `chunker/boundary/adapter.py:133–169` already
  recomputes definition IDs from the canonical display path.
- `chunker/boundary/adapter.py:762–812`: duplicate definition IDs receive stable
  `#1`, `#2` ordinals; alias indexes are first-wins. A bare definition ID alone
  therefore does not uniquely identify same-name siblings in one file.
- `chunker/boundary/adapter.py:215–285,836–881,1049–1054,1157–1174`:
  both fresh and incremental assembly translate graph IDs through those indexes;
  edge IDs already include source, target, type, reference, definition line and
  file. Node membership follows the resulting source. Fix both paths.
- `chunker/boundary/cache.py:35–98,146–158` and
  `chunker/boundary/types.py:26–42`: persisted records contain raw symbol facts;
  cache record/index version and key prefix are currently `1`/`boundary:v1:`.
  `adapter.py:368–404` keys on tool/schema/runtime/grammar versions, but the
  same checkout package version can span source changes. Old facts cannot be
  repaired by merely changing assembly after definition keys are overwritten.
- `chunker/cli/symbol_commands.py:68–96,99–112` serializes public graph output;
  `symbol_graph.py:471–493` returns graph keys as search IDs.
  `chunker/cli/cluster_commands.py:95–126` tests endpoint membership against
  `symbol_lookup`; `chunker/clustering/engine.py:165–192` resolves endpoints by
  those keys. Boundary JSON exporters serialize the document unchanged
  (`chunker/export/boundary_ir.py:11–38`). These are affected consumers.
- `docs/interface-boundary-spec.md:75–98` freezes identity precedence exactly
  as `definition_id`, `module + qualified_name`, `node_id`, and describes Tier-2
  occurrence identity. Lines 158–168 freeze: “additive-compatible changes stay
  within the current major version”; “breaking changes require a major version
  bump”; changing an existing field's meaning is breaking. Lines 178–180 freeze
  `resolved`, `ambiguous`, `unresolved`; no new resolution/identity vocabulary
  is introduced. `chunker/boundary/__init__.py:30–42` distinguishes package,
  schema and public API versions; callable public API is unchanged here.
- `specs/phase-plans-v3.md:29,450–464` requires bounded graph identity changes
  and an explicit migration. This work is a standalone issue, not completion of
  the old EXPORT phase. `docs/development/backlog-inventory-20261006.md:83`
  reserves detailed design for shared identity/persistence; no roadmap edit.

## Actual downstream sources and falsifiers

Historical downstream snapshot was `4fc13966f763b1586623d1aed856a61f5bca71b4`;
this refresh does not establish current downstream pins. Primary trackers:
[treesitter-chunker#496](https://github.com/Consiliency/treesitter-chunker/issues/496),
[treesitter-chunker#487](https://github.com/Consiliency/treesitter-chunker/issues/487),
[spec#227](https://github.com/Consiliency/spec/issues/227), and
[spec#219](https://github.com/Consiliency/spec/issues/219).

- [Current spec adapter](https://github.com/Consiliency/spec/blob/4fc13966f763b1586623d1aed856a61f5bca71b4/src/spec_core/engine/realized/adapter.py#L1270-L1323):
  `to_token = reference`; unique same-file/name/kind re-anchoring is a workaround.
  It cannot restore a pre-IR deleted edge. Non-node sources are dropped at 1299–1301.
- [Current spec extraction contract](https://github.com/Consiliency/spec/blob/4fc13966f763b1586623d1aed856a61f5bca71b4/src/spec_core/engine/realized/extract.py#L80):
  pins chunker 5.3.0; lines 263–271 refuse schema other than 2.0.
- [Shipped spec falsifier fixtures](https://github.com/Consiliency/spec/blob/4fc13966f763b1586623d1aed856a61f5bca71b4/spec-engine/realized/test_realized.py#L1056-L1108):
  Python module/package and TS/TSX fixtures, including NFD paths. Lines 1078
  and 1104 assert that the upstream bug exists. Port the bytes and correct
  ownership assertions, not those bug-presence assertions. Spec must amend them
  during its later pin adoption; no downstream edits belong in this upstream PR.
- Actual private board sources (historical spec `46c1d9b`):
  `/home/viperjuice/workspace/reviews/spec-p3/br-soundness/standin-adversarial.md:45–59,153–165`;
  actual probes in `/home/viperjuice/workspace/tmp/panel/adv-p3a/w/`:
  `probe2.py:4–9` (real Python full run), `probe9.py:15–20` (identical `sorted`
  calls deleted before re-anchoring), `probe9.py:4–13` (dotted-directory/module
  collision). The board's `.mts`, `.mjs`, `.pyw` completions mutate extension
  discovery in memory; see `standin-redteam.md:40–45`. They are modeled
  completions, not evidence that those suffixes are currently discovered.
  Port the real Python and TS/TSX cases and use supported `.ts` for the dotted
  path counterpart. Do not expand extension discovery in either plan.

## Version-policy freeze: owner selected 2026-10-16

Owner decision: a coordinated package 6.0.0 migration with explicit IR 3.0
(syntax) / 3.1 (semantic), rejecting old schema in the new schema validator.
Both plans land into the same unreleased major train before any release of IR
3.x; plan B finalizes the still-unreleased 3.x contract. This is supported by
the current Unreleased/6.0.0 reservation, not permission to release or repin.
If plan A is released separately, plan B's next breaking schema/package train
must be re-approved; do not silently change a published 3.x meaning.

| Selected migration | Schema/package semantics and fencing | Cache and downstream work |
| --- | --- | --- |
| Coordinated IR 3.0/3.1 + package 6.0.0 | Explicit schema rejection prevents old-schema readers accepting new identity/site semantics; no legacy-output mode | A cache v2, B cache v3; consumers re-extract/re-index, adopt package/schema pins and amend bug-presence tests together |

The owner explicitly selected the new IR major in the parent's structured
question. Keeping IR 2.x is not part of this implementation contract. No
compatibility shim, legacy dual emitter, release, lock change or package-version
edit is authorized by this planning artifact. Implement the IR 3.0/3.1 schema
rows below after source refresh and independent design acceptance.

## Frozen implementation contract

1. Graph keys, relationship `from`, resolved `to`, and candidate IDs refer to
   canonical file-scoped definitions, never module stems. Retain module strings
   only as descriptive/resolution metadata. `symbols` and `symbol_lookup` retain
   every definition; symbol records expose `definition_id` and `node_id`.
2. Use `chunk_file(..., identity_path=<canonical display path>)` for facts, just
   as Boundary nodes do. Reuse `normalize_boundary_path` inside extraction via a
   local import to avoid the package/adapter/symbol-graph import cycle. Keep its
   existing POSIX normalization; do not add Unicode normalization or change hash
   functions. An isolation comparison keeps the same logical repository root
   and display path; extracting an arbitrarily relocated file is not equivalent.
3. Unique definition key = canonical `definition_id`; for repeated same-file
   definition IDs apply the existing stable occurrence ordinal in source order
   (`base`, `base#1`, ...). Count occurrences across the complete ordered
   `chunk_file` result before the graph's `SYMBOL_KINDS` filter so a retained
   graph definition receives exactly the same suffix as its corresponding
   Boundary node even when a filtered Boundary chunk shares the base ID. No
   global file-order ordinal. Absent a definition ID, use the canonical
   `node_id`. Boundary node ID precedence/values are unchanged. Build exact
   direct node-ID indexes, including every disambiguated `node.id`, in a complete
   first pass before adding any name/module aliases in a second pass; an alias
   may never steal a later node's exact ID. Resolve edge sources through a
   separate exact canonical-ID map only, with same-file ownership; name aliases
   may not repair a missing source. Preserve both overload sources without
   claiming signature-aware target resolution.
4. Candidate lookup remains heuristic, with unique/resolved, multiple/ambiguous,
   zero/unresolved. Different formerly collided definitions now contribute
   distinct candidates. Resolved endpoints must exist; ambiguous candidates are
   sorted distinct canonical definition IDs. Do not impose binding correctness
   or add new resolution states. Keep treesitter-chunker#495's reference-sensitive
   dedupe and existing self suppression in A. Plan B removes call suppression.
5. Every emitted syntax relationship source maps to a node in its call-site file:
   `nodes[edge.source].path == edge.metadata.file`. Graph `from` exists in
   `symbol_lookup` with the same file. Imports/dependencies retain their current
   containing-definition location and dedupe. No claim of complete call-site
   locality is made until B.
6. Advance cache format/prefix to v2 and reject v1 records/indexes as misses;
   reparse rather than transforming lossy cached facts. Never delete a user's
   cache directory. A new cache must be fresh/cold/warm equivalent in canonical
   parity, including semantic mode. The old tool-version field alone is insufficient.

## Changes (modify unless stated)

- `chunker/symbol_graph.py`: `_symbol_id`, `_display_file`, per-file extraction,
  indexes/assembly — canonical per-definition keys and retained records.
- `chunker/boundary/adapter.py`: `_node_symbol_indexes`, `_edge_record`, both
  assembly paths — exact source/target mapping and preserved membership.
- `chunker/clustering/engine.py`: `ClusteringEngine._compute_module_dependencies` — derive endpoint
  module from symbol metadata, falling back to symbol file when module is absent,
  instead of splitting opaque IDs. Keep filters, endpoint checks and weights.
- `chunker/clustering/hierarchy.py`: `_infer_label` — prefer symbol module then
  file; legacy ID parsing is the final fallback when metadata is absent. Preserve
  prefix cleanup and existing label fallback semantics.
- `chunker/boundary/types.py`: cache v2/prefix; schema constants only per owner freeze.
- `chunker/boundary/cache.py`: retain existing mismatch-as-miss behavior; modify
  only if tests show index/record checks need the selected version contract.
- `chunker/boundary/boundary_ir.schema.json`, `chunker/boundary/__init__.py`:
  selected schema/version descriptions and schema enum/identifier; declare the
  existing optional `identity.disambiguated_from` string emitted for duplicate
  definitions; no API names added.
- `tests/test_symbol_graph.py`, `tests/test_symbol_graph_resolution.py`,
  `tests/test_symbol_graph_incremental_facts.py`, `tests/test_chunk_id_collision.py`:
  real anchor, duplicate-definition,
  candidate and direct/assembled graph cases.
- `tests/test_boundary_ir_identity.py`, `tests/test_boundary_ir_resolution_modes.py`,
  `tests/test_boundary_ir_incremental_runtime.py`,
  `tests/test_boundary_ir_incremental_cache.py`,
  `tests/test_boundary_ir_incremental_contract.py`, `tests/test_boundary_cache_key.py`,
  `tests/test_boundary_ir_schema.py`, `tests/test_boundary_ir_contract.py`:
  sources/membership, cache migration and selected schema contract expectations.
- `tests/test_symbol_graph_cli_resolution.py`,
  `tests/unit/clustering/test_engine.py`, `tests/unit/clustering/test_hierarchy.py`,
  `tests/integration/test_clustering_integration.py`: opaque endpoint transport,
  metadata-first grouping/labels and unchanged filtering/weight semantics.
- `tests/test_boundary_ir_semantic_contract.py`, `tests/test_boundary_ir_adapter.py`,
  `tests/test_boundary_ir_cli.py`, `tests/test_boundary_ir_cli_incremental.py`,
  `tests/test_boundary_ir_cli_observability.py`, `tests/boundary_ir_conformance.py`:
  selected schema expectations and unchanged API/supported-language/pin contract.
- `tests/test_boundary_ir_semantic_enrichment.py`: migrate the cache-record
  filename lookup from v1 to v2 while retaining the resolver-fingerprint
  assertions.
- `docs/interface-boundary-spec.md`, `docs/user-guide.md`,
  `docs/interface-boundary-roadmap.md`, `CHANGELOG.md`: identity/cache migration,
  precise remaining limits, re-extraction/re-indexing and selected version policy.
- `tests/fixtures/boundary_ir/golden/*.json`: generator-owned only; all supported
  languages are in regeneration scope, not permission to hand-edit fixtures/pins.
- Plan A and its manifest row: supported API registration/lifecycle, preserving
  all predecessors/events. Seven Python production files plus schema; cache.py
  remains read-only unless designated migration tests prove a minimal amendment.

## Documentation impact

Update all three docs' current-version statements to syntax 3.0/semantic 3.1,
the schema-validated minimal JSON example, and public module IR descriptions.
Public Python API stays 1.0. Append changelog
under Unreleased 6.0 without rewriting accepted treesitter-chunker#495/#497 entries.
New schema validator rejects 2.x; no dual emitter or legacy shim. Consumers must
adopt pins and rebuild indexes separately. Package version mirrors, pyproject,
uv.lock, providers, parser pins, CLI/export transports and release/tag remain
outside scope. No new resolution or identity vocabulary is introduced.

All other source, tests, docs, roadmap, release metadata and locks are read-only.
The schema choice may require further version-specific assertions; locate them
before implementation and amend the owned-path list before editing outside it.

## Falsifiers, baseline and named mutations

Add real-parser cases to the existing named test modules, with test names
prefixed `test_496_anchor_`:

- Python `pkg.py` vs `pkg/__init__.py`, both `run`, first with `time.time` vs
  `sorted` (board probe2), then both `sorted` (board probe9b): two definitions,
  two correctly owned surviving calls, regardless of input fact order.
- `x.ts` vs `x.tsx`, same `f`, distinct `g`/`k` calls (shipped spec fixture);
  plus identical call tokens to expose pre-IR collision loss after treesitter-chunker#495.
- `src/api/client.ts` vs `src/api.client.ts`, same `send` and distinct calls:
  real supported-extension counterpart of modeled board probe9a.
- Duplicate same-name Python definitions in one file with distinct calls and
  real same-name method/overload chunks: preserve both sources and valid target
  candidates. Do not count dictionary length alone as proof of ownership.
- NFD-named module/package fixture from spec, canonical path spelling preserved;
  absolute/redundant-root spellings and native Windows path behavior must give
  consistent logical-root identities. No new NFC equivalence promise.
- Supported-extension unrelated same-name callee file added/removed: the caller
  source remains fixed while target resolution/candidates may change.
- Opaque-ID clustering fixtures prove metadata-derived module grouping/labels
  and missing-metadata fallback without changing filtering or weights.
- Seed a v1 persisted record/index from the real baseline; candidate rejects it
  and reparses. Then prove v2 cache reuse by spying on extraction/payload load,
  persisted facts and memberships, beyond merely equal output.
- Validate a real duplicate-definition document, including the emitted
  `identity.disambiguated_from`, against the 3.x schema in fresh, incremental
  cold, and incremental warm output.
- In addition to the genuine v1 baseline cache, seed index and record payloads
  whose `schema_version` already equals the candidate 3.0 value but whose cache
  version/key prefix remain v1. Their rejection isolates the cache-format fence
  so M-A3 cannot pass merely because the schema version changed.

On accepted 931f6e05, require designated source-ownership/edge-count
assertions to fail before editing production. Mutate only (M-A1) canonical keys
back to module keys, (M-A2) bypass the second occurrence's disambiguated exact
ID and deliberately resolve its source through the shared undisambiguated
definition/name alias to the first sibling, and
(M-A3) cache version/prefix back to v1, plus (M-A4) clustering module/label
derivation back to ID parsing. Each must fail its designated assertion;
record original source hashes and restore exact candidate bytes after each.
Do not insist already-fixed treesitter-chunker#495 token tests fail again.
M-A2's designated same-file fixture selects the second definition independently
by source span, asserts its distinct call edge has exactly that second node ID,
and asserts relationship membership only on that second node in fresh,
incremental cold, and incremental warm output. A separate cross-file control
supplies a missing canonical source whose name matches another file's alias and
proves aliases cannot repair it; the ordinary same-file path assertion remains
the cross-file guard, not the sibling-identity witness.

## Dependencies and review gates

1. Source refresh is complete at merged treesitter-chunker#495/#497, 931f6e05.
   Use the fresh owned worktree, never the retained older draft checkout. Freeze
   successor plans for exact-head review. No production edits before design
   acceptance. A precedes B; B receives its own refresh and design acceptance.
2. Native PLAN1 completed at exact clean head
   `0f668ae314e9a1e0b0087557b12d585e6475441c`: Sol1, Sol2, and Astra required
   the bounded corrections now incorporated here; Gemini agreed. The preserved
   PLAN1 audit/opinions and reconciliation are under the exact private evidence
   paths named below. PLAN2 completed at exact clean head
   `63815daae47224450bf3ac1e1e90145535f9bbfe`: Gemini agreed; Sol1, Sol2, and
   Astra required the precise M-A2 witness, concrete operational driver argv,
   the actual clustering method name, and packet-readable runtime API excerpts.
   These corrections are now incorporated. Run the final allowed complete
   peer-blind PLAN3 quartet (two independent Sol seats, Gemini 3.8 Flash,
   Astra), collect all four before reconciliation, then obtain separate
   independent Astra president approval. Maximum three full rounds; heartbeat only, no
   model/silence deadlines. These manual reviews establish no formal
   Harness/native/IF qualification.
3. Implementation owns its new worktree only. No shared Windows checkout, native
   journal, held Go/CLEANUP/S27 state, parser pins or type baseline changes.
4. Standing owner authorization covers implementation, supported publication,
   owned interactive PR metadata upkeep, normal merge and safe owned pruning
   after required gates. It does not waive them or authorize a release. Run
   commands below only during implementation. Use locked Python
   3.12 and private disk scratch. Preserve genuine original command outputs,
   exit status, source/head bindings before/after, baseline/mutation failures,
   runtime/parser versions and cache payload evidence. No copied or synthetic
   verification receipts. Plan B repeats the common gates on its final head.

## Verification

The only private evidence readable during implementation is the accepted A
design record at
`/home/viperjuice/workspace/evidence/treesitter-chunker/call-identity-496/20261017-after-495/plan-A-acceptance.json`
and the paths it explicitly hashes for PLAN3 reconciliation/president approval.
All new implementation, baseline, mutation, native, wheel, and runner evidence
must be written beneath the exact allowlisted root
`/home/viperjuice/workspace/evidence/treesitter-chunker/call-identity-496/20261017-after-495/implementation-A/`.
Do not read any other historical evidence, linked absolute path, review clone,
credential file, or sibling evidence directory.

Before source edits, call the installed typed lifecycle API exactly as
`phase_loop_runtime.plan_manifest.update_lifecycle(repo=Path(<owned-worktree>),
slug="source-anchors-496", transition="executing",
by="codex-execute-detailed", metadata=<run/plan/design-acceptance bindings>)`.
At successful closeout call the same API with `transition="completed"` and
verification/reflection/dirty-path metadata. Snapshot `plans/manifest.json`
before each call and prove only the A row changed; the 72 predecessor rows and
the B row, including every lifecycle event, must remain byte-equivalent.

Create the genuine runner artifact with the installed
`phase_loop_runtime.verification_evidence.run_verification`: use the owned
worktree as `repo`,
`implementation-A/runner-verification` as `run_dir`, the commands below as
`commands`, the frontmatter command split into argv as `suite_command`,
`python_pin="3.12"`, `phase_alias="source-anchors-496"`, no timeout, and
`env_refresh={"triggered": true, "manifests": ["pyproject.toml", "uv.lock"],
"install_argv": ["uv", "sync", "--locked", "--all-extras", "--python", "3.12"]}`.
Pass each ordinary command as an argv list; pass only the three diff/cmp and
temporary-doc-site shell expressions as `['bash', '-lc', <exact command>]` so
redirection and `mktemp` are executed deliberately rather than treated as argv.
Validate the resulting `verification.json` with
`validate_verification_artifact`; preserve its sibling `verification.log`,
their SHA-256 values, exact source HEAD, and the validator result. The runner
commands must include the wheel and isolated native-Windows verification
drivers so those operational results are sealed subprocess outcomes rather
than narrative/proxy receipts.

Before invoking `run_verification`, create exactly these private drivers with
`apply_patch`, review their bytes, and record their SHA-256 values in
`implementation-A/driver-bindings.json`:

- `implementation-A/verify-wheel.py` accepts `--repo`, `--out`, and repeated
  `--python` arguments. It builds/hashes the exact-head wheel, creates fresh
  external Python 3.11-3.14 environments with locked/hash-checked dependencies,
  installs only the wheel as project source, checks import origins/providers,
  Unicode extraction, canonical ownership, both 3.x modes and 2.x rejection,
  v1 miss/v2 warm reuse, CLI JSON/export, and writes `wheel-result.json`.
- `implementation-A/verify-native-windows.py` accepts `--repo`, `--out`, and
  `--driver`. It archives the exact clean tracked HEAD with per-file hashes,
  creates a unique private Windows directory without touching the shared
  checkout, copies the archive/config/driver, invokes Python 3.12 there, copies
  all raw logs/results back, and fails unless bindings and the shared checkout
  are unchanged.
- `implementation-A/native-windows-driver.py` validates the archive and tracked
  hashes, runs locked sync, the three targeted pytest commands and
  `scripts/run_windows_preflight.py`, records runtime/provider metadata, and
  writes `native-result.json` with every command/log hash.

Append these exact argv commands to `run_verification.commands` after the local
docs/golden/narrow gates and before its full-suite `suite_command`:

```text
["python", "/home/viperjuice/workspace/evidence/treesitter-chunker/call-identity-496/20261017-after-495/implementation-A/verify-wheel.py", "--repo", "/mnt/workspace/worktrees/viperjuice/treesitter-chunker-source-anchors-496", "--out", "/home/viperjuice/workspace/evidence/treesitter-chunker/call-identity-496/20261017-after-495/implementation-A/wheel", "--python", "3.11", "--python", "3.12", "--python", "3.13", "--python", "3.14"]
["python", "/home/viperjuice/workspace/evidence/treesitter-chunker/call-identity-496/20261017-after-495/implementation-A/verify-native-windows.py", "--repo", "/mnt/workspace/worktrees/viperjuice/treesitter-chunker-source-anchors-496", "--out", "/home/viperjuice/workspace/evidence/treesitter-chunker/call-identity-496/20261017-after-495/implementation-A/native-windows", "--driver", "/home/viperjuice/workspace/evidence/treesitter-chunker/call-identity-496/20261017-after-495/implementation-A/native-windows-driver.py"]
```

The frozen PLAN3 packet carries `runtime-api-excerpts.md`, bound to installed
phase-loop runtime 0.7.26 and the source-file hashes recorded there, so reviewers
can independently verify the exact `run_verification`,
`validate_verification_artifact`, and `update_lifecycle` signatures without
reading outside their packet.

Regenerate locked goldens twice and prove identical binary diffs before running
the complete schema-test module, because that module validates committed
goldens and the 3.x validator rejects their current 2.x bytes.

```bash
uv sync --locked --all-extras --python 3.12
uv run --locked --all-extras pytest tests/test_symbol_graph.py tests/test_symbol_graph_resolution.py tests/test_symbol_graph_incremental_facts.py tests/test_chunk_id_collision.py tests/test_boundary_ir_identity.py tests/test_boundary_ir_resolution_modes.py tests/test_boundary_ir_incremental_runtime.py tests/test_boundary_ir_incremental_cache.py tests/test_boundary_ir_incremental_contract.py tests/test_boundary_cache_key.py -q
uv run --locked --all-extras pytest tests/test_symbol_graph_cli_resolution.py tests/unit/clustering/test_engine.py tests/unit/clustering/test_hierarchy.py tests/integration/test_clustering_integration.py -q
uv run --locked --all-extras python scripts/regenerate_boundary_goldens.py
git diff --binary -- tests/fixtures/boundary_ir/golden > "$IMPLEMENTATION_EVIDENCE/goldens-first.diff"
uv run --locked --all-extras python scripts/regenerate_boundary_goldens.py
git diff --binary -- tests/fixtures/boundary_ir/golden > "$IMPLEMENTATION_EVIDENCE/goldens-second.diff"
cmp "$IMPLEMENTATION_EVIDENCE/goldens-first.diff" "$IMPLEMENTATION_EVIDENCE/goldens-second.diff"
uv run --locked --all-extras pytest tests/test_boundary_ir_schema.py tests/test_boundary_ir_contract.py tests/test_boundary_ir_semantic_contract.py tests/test_boundary_ir_adapter.py tests/test_boundary_ir_cli.py tests/test_boundary_ir_cli_incremental.py tests/test_boundary_ir_cli_observability.py tests/test_boundary_ir_semantic_enrichment.py tests/test_boundary_ir_semantic_determinism.py -q
uv run --locked --all-extras pytest tests/test_boundary_ir_golden_snapshots.py tests/test_boundary_ir_determinism.py -q
uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --locked --all-extras python scripts/mypy_gate.py
uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
uv run --locked --with toml --all-extras python scripts/run_full_suite.py
uv run --locked --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict --site-dir "$(mktemp -d)"
```

`IMPLEMENTATION_EVIDENCE` must be set exactly to
`/home/viperjuice/workspace/evidence/treesitter-chunker/call-identity-496/20261017-after-495/implementation-A`
before the two diff writes. The runner's effective
`automation.suite_command` is the original full `tests/` + `spec_tests/` suite
above; narrow passes cannot substitute for it.

Native Windows: copy/export the exact candidate to a unique private Windows
snapshot, bind every tracked source hash and Python/runtime version, then run
`uv sync --locked --all-extras --python 3.12`, the three targeted pytest
commands above, and
`uv run --locked --with toml --all-extras python scripts/run_windows_preflight.py`.
The standing CONTRIBUTING command checks out/pulls a shared Windows main and
cannot verify an unmerged candidate; preserve it and use the isolated snapshot.
Fleet Linux/macOS preflights when available and hosted Linux/macOS/Windows
checks must bind the actual final head. Standing authorization covers subsequent
publication/CODE review/merge after exact-head gates; this plan waives none.

## Installed-artifact and operational verification

Preserve treesitter-chunker#497's official Python/JavaScript provider requirements,
provider-aware grammar keys and cache-preserving non-incremental fallback on
ParserInitError. Existing `test_boundary_cache_key.py` and
`test_boundary_ir_incremental_runtime.py` provider cold/warm/failure cases are
standing pass gates in both plans.

Build the exact candidate wheel following the existing release-workflow clean
wheel job without triggering release. Hash it and install into fresh hash-locked
Python 3.11–3.14 environments outside the checkout. Prove imports originate in
the installed environment, real official providers/Unicode extraction work,
canonical graph ownership and both IR modes work, 3.x validates/2.x rejects,
v1 misses/new v2 warm reuse work, and CLI JSON/export keeps the contract.

Record actual commands/results and exact source/artifact/runtime bindings in
`wheel-result.json`, `native-result.json` and final-head `hosted-checks.json`
under the private implementation evidence root. Register paths/hashes through a
supported runner-stamped plan amendment before using operational evidence for
acceptance. These cannot be replaced by a source-suite or proxy receipt.

## Acceptance criteria

- [ ] A1: `test_496_anchor_` cases fail designated assertions on merged treesitter-chunker#495,
  pass candidate, and detect M-A1/M-A2 with exact restoration; targeted graph/IR
  pytest command proves distinct same-file-owned definitions/edges/candidates.
- [ ] A2: targeted incremental cache/runtime tests prove v1 miss/reparse,
  actual v2 warm reuse and fresh/cold/warm parity; M-A3 is detected.
- [ ] A3: CLI/clustering command proves coherent opaque endpoint IDs and
  metadata-first grouping/labels, detecting M-A4 with exact restoration. Schema,
  semantic, golden/determinism commands prove the chosen contract, reviewed
  generated changes, all-supported-language nonempty extraction and idempotence.
- [ ] A4: original full/local checks, strict docs and actual isolated native
  Windows, clean installed-wheel and final-head hosted checks above pass on the
  candidate with genuine runner-stamped evidence bindings; all
  required review/owner/source-refresh gates are recorded. Source identity is
  accepted separately from the raw call-site guarantee reserved for B.

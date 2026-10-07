---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Preserve graph chunk identities and migrate parent aliases

## Task and research

Implement EC-EXPORT-1 from `specs/phase-plans-v3.md` for
treesitter-chunker#167 and its separately reproduced parent-alias defect
treesitter-chunker#445 as one independently reviewable identity/endpoint slice.
Actual locked parsing on accepted main
969fe63e36fe47d5a4bc48a681248c09826d255a produces five distinct occurrence IDs
for the reported function/two-lambda fixture, but GraphML retains only two nodes.
`/tmp/chunker-167-identity-reproduction.json` binds the measured head, source and
fixture bytes. The initial console probe's incorrect hard-coded head is excluded.

`GraphNode.id` and `GraphExporterBase._get_chunk_id` currently construct line-span
IDs. `CodeChunk.__post_init__` already supplies occurrence IDs incorporating byte
position/content/route; UnifiedGraphNode already prefers node_id over chunk_id.
GraphML, yEd, DOT and Neo4j inherit the same base. GraphML tests explicitly pin
three old node/endpoint values; the existing yEd contract also pins old IDs.
The graph guide teaches their old format. The observed five chunks include
unnamed lambda keyword tokens, separately filed as treesitter-chunker#446.
Exporter expectations must derive from emitted chunks and their parent IDs,
without pinning five chunks or preserving that selection defect. The complete
lambda expressions still share lines, so the graph loss is independent.

## Frozen identity and migration contract

1. Graph IDs use `chunk.node_id or chunk.chunk_id or chunk.generate_id()`.
   Do not modify the chunk's fields or the existing identity algorithm. A repeated
   identical occurrence remains the same node; distinct real parsed occurrences
   sharing lines retain distinct nodes. Input order does not affect these IDs.
2. Node insertion, explicit add_relationship endpoints, clustering and automatic
   relationships all use that same graph identity. Unified conversion agrees
   for ordinary post-init chunks with populated IDs. Its cleared-ID fallback
   is outside this repair; do not change UnifiedGraphNode.from_chunk.
   No new relationship names or CodeChunk/Boundary IR vocabulary are introduced.
3. Resolve aliases against only the chunks supplied to this extraction call,
   grouping matches by canonical graph ID. parent_chunk_id retains chunk_id-only
   lookup for DEFINES/HAS_METHOD, but a referenced duplicate chunk_id that maps
   to different graph IDs raises ValueError instead of selecting the last one.
   Legacy metadata parent_id resolves the union of exact node_id and chunk_id
   matches first. More than one distinct graph ID is contradictory, including
   A.node_id equalling B.chunk_id and duplicate chunk_id values. Only when there
   is no exact match may it use a line-span alias matching one distinct graph ID.
   One exact match wins even if the same string is an ambiguous line-span alias.
   Repeated copies of one canonical occurrence do not create alias ambiguity.
   Unknown aliases remain ignored. Unreferenced collisions do not cause failure.
4. Preflight every supplied parent reference in both fields before appending
   any edge, including import/call edges, from that extraction call. Ambiguity
   raises actionable ValueError naming the actual field and alias and requesting
   a unique parent occurrence/reference. Preserve every pre-existing edge and
   append nothing on failure. Do not clear graph data. metadata parent_id and
   parent_chunk_id may intentionally identify different unambiguous parents:
   preserve their independent CONTAINS and DEFINES meanings. This contract
   rejects ambiguous identity selection, not legitimate different relationships.
5. This deliberately changes legacy GraphNode/exported node IDs. Consumers must
   regenerate graph outputs and rebuild ID-based indexes/joins using emitted
   IDs, rather than parsing line spans. Existing file_path/start_line/end_line
   properties still reconstruct the old alias where needed. Do not add a second
   ID field, change chunk IDs, migrate consumer locks or claim old output IDs
   remain stable. The public constructor and relationship argument shapes remain.
   Classify changed IDs and newly rejected ambiguous inputs as BREAKING: this
   lands toward the next major release, 6.0.0, and must not ship in a 5.x release.
   Add that boundary and migration to the changelog/docs and associated issue/PR
   closeout; downstream owners receive qualified issue references before
   publication. This slice does not dispatch a release or change locks.
6. Scope the migration to direct imports from chunker.export.graphml_exporter,
   graphml_yed_exporter, dot_exporter and neo4j_exporter. The package-level
   chunker.export exports separate structured classes; DatabaseExporterBase's
   chunk_id-first helper is also separate. Neither is aligned here. Paths, byte
   positions, qualified routes and content changes can rekey occurrence IDs.
   Parser-generated hexadecimal IDs preserve distinct serialized DOT nodes;
   Caller-selected IDs containing punctuation and XML/CSV metacharacters are
   verified in base collections/XML/CSV, without
   claiming DOT punctuation encoding is injective. That defect remains
   treesitter-chunker#444. Neo4j's pre-existing whole-block whitespace stripping
   remains treesitter-chunker#448; whitespace-ID CSV fidelity is excluded here.
   XML endpoint assertions concern declared ID membership,
   not XML-control or schema completeness.

## Changes

- `chunker/export/graph_exporter_base.py`: modify GraphNode identity and the
  existing base identity helper, then adjust extract_relationships alias lookup
  and preflight as frozen above. Keep import/call matching, relationship names,
  property merging, unrelated serializers and occurrence-ID generation unchanged.
- `tests/fixtures/graph_same_span.py`: add the actual valid Python regression
  containing the reported function and two lambda expressions on one return line.
  Keep it outside Boundary IR fixture/golden discovery; no golden regeneration.
- `tests/test_graphml_exporter.py`: update the three old node/edge-ID assertions
  deliberately to their CodeChunk occurrence IDs. Extend this existing module
  with actual chunk_file parsing of the checked-in same-span fixture, asserting
  non-error parsing, distinct occurrence preservation, node IDs matching chunks,
  explicit CALLS endpoints and automatically extracted DEFINES edges reaching
  actual parents, deriving sets from emitted chunks rather than fixed counts or
  keyword kinds. Parse plain/yEd XML and verify every edge endpoint is declared.
  Exercise all four base consumers' node/edge collections and DOT output.
  Parse Neo4j's actual csv_nodes/csv_relationships output with csv.DictReader,
  verifying emitted IDs and endpoints without a live database, network or mocks.
  Verify a caller-selected parent ID containing punctuation/quotes/comma/XML
  metacharacters through plain/yEd XML and actual Neo4j CSV for each unique
  node_id/chunk_id/span parent alias, preserving CONTAINS and DEFINES endpoints.
- In that module, parse the same file again and reverse input order to prove
  stable node/endpoint sets. Re-adding the same occurrences does not multiply
  nodes. Exercise canonical parent_id, chunk_id aliases with distinct caller
  node_id values, and a unique legacy line alias using real parsed chunks.
  Exercise every conflict/precedence case frozen above, including duplicate
  chunk_id parent references in each field, node_id/chunk_id cross-collisions,
  exact-before-ambiguous-span precedence, harmless repeated occurrences and
  deliberately different valid parents for CONTAINS/DEFINES. Exercise a bad
  reference after a valid child, with pre-existing edges: require actionable
  failure and no partial append in either field or input order. An unknown parent
  preserves existing behavior. Use real chunks with caller metadata/IDs; do not
  construct fake parser nodes or replace the exporter under test.
- `tests/test_graphml_yed_export_contract.py`: deliberately migrate span-ID and
  endpoint assertions to actual chunk.node_id, retaining direction and graphics
  checks. Keep tests/test_phase12_integration.py in the focused command: it
  exercises cross-exporter endpoints and a supported unique legacy span alias.
- `scripts/run_platform_core.py`: add tests/test_graphml_exporter.py to
  COMMON_TESTS, retaining the already selected yEd module and every accepted
  platform selection.
- `docs/graphml_export.md`: replace line-span ID teaching/XML examples with
  occurrence-ID examples and the explicit migration/legacy-parent rules. Keep
  XML/key completeness claims out of this identity acceptance; their repairs
  remain treesitter-chunker#168 and treesitter-chunker#169.
- `docs/export-formats.md`: add concise graph-ID migration guidance covering
  the four direct import paths and link the detailed guide. Explicitly distinguish
  the separate package-level structured classes and database helper. Correct its GraphML output
  path example to an actual Path while touching that example, matching its API.
- `CHANGELOG.md`: state distinct same-span retention, intentional graph-ID
  migration, next-major 6.0.0 boundary and ambiguous parent rejection. This plan and its typed
  `plans/manifest.json` row are owned; no parser/identity algorithm/schema changes.

## Dependencies and order

No native, cache, wheel or held-transaction dependency. Serialize this base
module with subsequent XML/key slices; source-plan work can proceed while
unrelated original runners complete. Commit the detailed plan before tests or
code. Review this compatibility contract with all four manual tool-enabled
seats before implementation; reconcile complete rounds, maximum three
substantive design rounds. A design approval closes no product issue.

After contract approval, mark only this typed plan row executing. Add real
regressions and record unchanged-source failures. Implement the frozen contract.
Run named actual mutations independently: `line_span_identity` restores both
former span-ID sites and must fail distinct nodes/endpoint completeness;
`legacy_parent_last_wins` restores last-wins span alias resolution and must fail
ambiguous-span rejection; `canonical_alias_first_match` selects the first exact
node_id/chunk_id match and must fail cross-collision rejection;
`chunk_alias_last_wins` restores last-wins parent_chunk_id lookup and must fail
duplicate chunk-ID rejection in both orders; `incremental_parent_checks` moves ambiguity checking
back into the appending loop and must fail no-partial-edges. Each exact restoration
passes the whole focused module and binds source/test/fixture hashes captured
before and verified after. Do not weaken existing expectations to conceal a defect.

File separately found XML, labels, selection, serialization or identity-algorithm defects
before considering their repair; no silent extra fixes. Bounded implementation
gets its own four-seat code review, maximum three complete substantive rounds.
Opus5.5 uses the TUI adapter, Gemini3.8Flash file tools, and Astra/Sol the other
seats, with short context pointers and heartbeat-only monitoring. The requested
manual Astra president reconciles actual complete reviews and machine evidence.

## Verification

- `uv sync --locked --all-extras`
- `uv run --locked --all-extras pytest tests/test_graphml_exporter.py tests/test_graphml_yed_export_contract.py tests/test_phase12_integration.py -q`
- `uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site`
- `uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/`
- `uv run --locked --all-extras python scripts/mypy_gate.py`
- `uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py`
- `uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux`
- `uv run --locked --with toml --all-extras python scripts/run_full_suite.py`

Ensure the named graph modules are selected on every hosted platform by the
specific COMMON_TESTS addition above; retain every existing platform selection.
Preserve all six original commands, locked refresh and full tests/spec_tests in
the sealed original runner. Matching-source focused/standing Windows, exact-head
hosted Linux/macOS/Windows jobs, four final agreements and the manual chair
ruling remain independent code merge gates. Archive raw evidence before
qualified merge/issue closure/pruning. No whole EXPORT phase/IF acceptance,
percentage gate, consumer-lock, admitted ledger or checkpoint edits.

## Acceptance criteria

- [ ] EC-EXPORT-1 — the focused command proves emitted real same-span occurrences
  survive every base consumer with stable canonical node/endpoint sets and all
  representative XML endpoints declared; DOT serialization claims are limited
  to real parser IDs. line_span_identity fails and exact
  restoration passes without changing the occurrence-ID algorithm or goldens.
- [ ] The focused command proves exact and unique legacy parent resolution,
  existing unknown-parent behavior and actionable ambiguous/conflicting alias
  rejection for both fields with no partial edges, precedence and independent
  relationship meanings. All four alias/preflight mutations fail and restore,
  with final source/test/fixture hashes and direct-import migration documentation
  explicitly reserving the BREAKING change for 6.0.0.
- [ ] Original six checks, locked refresh/full tests/spec_tests, matching-source
  Windows, exact hosted jobs, four bounded code reviews and Astra chair accept
  only identity/endpoint migration. XML-control and label-key issues remain
  separate, with no automatic consumer migration or whole-phase claim.

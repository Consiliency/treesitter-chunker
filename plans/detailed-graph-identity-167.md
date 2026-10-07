---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Preserve graph chunk identities and migrate parent aliases

## Task and research

Implement EC-EXPORT-1 from `specs/phase-plans-v3.md` for
treesitter-chunker#167 as one independently reviewable identity/endpoint slice.
Actual locked parsing on accepted main
969fe63e36fe47d5a4bc48a681248c09826d255a produces five distinct occurrence IDs
for the reported function/two-lambda fixture, but GraphML retains only two nodes.
`/tmp/chunker-167-identity-reproduction.json` binds the measured head, source and
fixture bytes. The initial console probe's incorrect hard-coded head is excluded.

`GraphNode.id` and `GraphExporterBase._get_chunk_id` currently construct line-span
IDs. `CodeChunk.__post_init__` already supplies occurrence IDs incorporating byte
position/content/route; UnifiedGraphNode already prefers node_id over chunk_id.
GraphML, yEd, DOT and Neo4j inherit the same base. GraphML tests explicitly pin
three old node/endpoint values, and the graph guide teaches their old format.

## Frozen identity and migration contract

1. Graph IDs use `chunk.node_id or chunk.chunk_id or chunk.generate_id()`.
   Do not modify the chunk's fields or the existing identity algorithm. A repeated
   identical occurrence remains the same node; distinct real parsed occurrences
   sharing lines retain distinct nodes. Input order does not affect these IDs.
2. Node insertion, explicit add_relationship endpoints, clustering and automatic
   relationships all use that same graph identity. Unified conversion agrees.
   No new relationship names or CodeChunk/Boundary IR vocabulary are introduced.
3. parent_chunk_id retains its existing chunk_id lookup, with the emitted edge
   referencing the corresponding canonical graph node. Legacy metadata parent_id
   first resolves an exact node_id or chunk_id alias; otherwise it may resolve a
   line-span alias only when exactly one distinct occurrence has that span.
   An unknown alias retains the existing ignored-parent behavior.
4. Ambiguous supplied aliases raise actionable ValueError naming parent_id and
   requesting an exact occurrence ID. Reject contradictory canonical aliases
   rather than selecting an arbitrary parent. Resolve/check supplied parent
   aliases before appending any relationships from that extraction call, so an
   ambiguity leaves pre-existing edges unchanged. Do not clear prior graph data.
5. This deliberately changes legacy GraphNode/exported node IDs. Consumers must
   regenerate graph outputs and rebuild ID-based indexes/joins using emitted
   IDs, rather than parsing line spans. Existing file_path/start_line/end_line
   properties still reconstruct the old alias where needed. Do not add a second
   ID field, change chunk IDs, migrate consumer locks or claim old output IDs
   remain stable. The public constructor and relationship argument shapes remain.

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
  actual parents. Parse plain/yEd XML and verify every edge endpoint is declared.
  Exercise all four base consumers' node/edge collections and DOT output.
  Parse Neo4j's actual csv_nodes/csv_relationships output with csv.DictReader,
  verifying emitted IDs and endpoints without a live database, network or mocks.
- In that module, parse the same file again and reverse input order to prove
  stable node/endpoint sets. Re-adding the same occurrences does not multiply
  nodes. Exercise canonical parent_id, chunk_id aliases with distinct caller
  node_id values, and a unique legacy line alias using real parsed chunks.
  Exercise an ambiguous same-line alias and a conflicting supplied canonical
  alias, with pre-existing edges and a valid parent preceding the bad child:
  require actionable failure and no partial edge append. An unknown parent
  preserves existing behavior. Use real chunks with caller metadata/IDs; do not
  construct fake parser nodes or replace the exporter under test.
- `docs/graphml_export.md`: replace line-span ID teaching/XML examples with
  occurrence-ID examples and the explicit migration/legacy-parent rules. Keep
  XML/key completeness claims out of this identity acceptance; their repairs
  remain treesitter-chunker#168 and treesitter-chunker#169.
- `docs/export-formats.md`: add concise graph-ID migration guidance covering
  GraphML/yEd/DOT/Neo4j and link the detailed guide. Correct its GraphML output
  path example to an actual Path while touching that example, matching its API.
- `CHANGELOG.md`: state distinct same-span retention, intentional graph-ID
  migration and ambiguous legacy parent rejection. This plan and its typed
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
ambiguous-parent rejection; `incremental_parent_checks` moves ambiguity checking
back into the appending loop and must fail no-partial-edges. Each exact restoration
passes the whole focused module and binds source/test/fixture hashes captured
before and verified after. Do not weaken existing expectations to conceal a defect.

File separately found XML, labels, serialization or identity-algorithm defects
before considering their repair; no silent extra fixes. Bounded implementation
gets its own four-seat code review, maximum three complete substantive rounds.
Opus5.5 uses the TUI adapter, Gemini3.8Flash file tools, and Astra/Sol the other
seats, with short context pointers and heartbeat-only monitoring. The requested
manual Astra president reconciles actual complete reviews and machine evidence.

## Verification

- `uv sync --locked --all-extras`
- `uv run --locked --all-extras pytest tests/test_graphml_exporter.py tests/test_graphml_yed_export_contract.py tests/test_export_integration_advanced.py -q`
- `uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site`
- `uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/`
- `uv run --locked --all-extras python scripts/mypy_gate.py`
- `uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py`
- `uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux`
- `uv run --locked --with toml --all-extras python scripts/run_full_suite.py`

Ensure the existing graph modules remain selected on every hosted platform;
add only any genuinely absent owned module to scripts/run_platform_core.py.
Preserve all six original commands, locked refresh and full tests/spec_tests in
the sealed original runner. Matching-source focused/standing Windows, exact-head
hosted Linux/macOS/Windows jobs, four final agreements and the manual chair
ruling remain independent code merge gates. Archive raw evidence before
qualified merge/issue closure/pruning. No whole EXPORT phase/IF acceptance,
percentage gate, consumer-lock, admitted ledger or checkpoint edits.

## Acceptance criteria

- [ ] EC-EXPORT-1 — the focused command proves distinct real same-span occurrences
  survive every base consumer with stable canonical node/endpoint sets and all
  representative XML endpoints declared. line_span_identity fails and exact
  restoration passes without changing the occurrence-ID algorithm or goldens.
- [ ] The focused command proves exact and unique legacy parent resolution,
  existing unknown-parent behavior and actionable ambiguous/conflicting alias
  rejection with no partial edges. Both named alias mutations fail and restore,
  with final source/test/fixture hashes and deliberate migration documentation.
- [ ] Original six checks, locked refresh/full tests/spec_tests, matching-source
  Windows, exact hosted jobs, four bounded code reviews and Astra chair accept
  only identity/endpoint migration. XML-control and label-key issues remain
  separate, with no automatic consumer migration or whole-phase claim.

---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Separate structural graph labels from caller metadata keys

## Task and research

Resolve treesitter-chunker#169 as the third independent EXPORT slice after
treesitter-chunker#443 and the character repair for treesitter-chunker#168 are
accepted. GraphMLExporter declares one n_<name>/e_<name> key per caller property,
then unconditionally declares n_label/e_label for structural labels. A property
named label therefore duplicates both a declaration ID and data for that key.
The yEd subclass inherits this behavior and adds disjoint d6/d10 graphics keys.

Use the existing serializers and real service fixture contracts. Avoid renaming
or discarding caller metadata. This schema-key migration belongs to the reviewed
next-major 6.0.0 release boundary, separately from node identity and XML handling.

## Observable contract and implementation

1. Structural node and relationship labels use the dedicated IDs `node_label`
   and `edge_label`. Every property retains its existing `n_<name>`/`e_<name>` ID
   and original attr.name/type/value. The dedicated IDs are outside both property
   prefixes, so arbitrary string names cannot collide with them. No suffix
   allocation whose meaning depends on input order or another property's presence.
2. Each declaration ID appears exactly once; every data key references a declared
   key for its node/edge domain. A node or edge emits each data key once. Caller
   `label` values remain distinct from structural chunk type/relationship labels.
3. Test other caller names that resemble the new IDs and old repair prefixes,
   including node_label, edge_label and metadata_label, simultaneously with label.
   Their metadata values round-trip unchanged. Node and edge names are separate
   domains and their structural IDs remain different.
4. Plain/yEd, compact/pretty and delegated use_yed=False all preserve declared
   IDs, directed endpoints, graphics and legal Unicode character handling.
   No XSD certification, graph-ID algorithm, type inference or property merging
   redesign. XML-invalid characters keep the accepted treesitter-chunker#168 rule.

These are raw XML key/declaration/data contracts. Structural and caller labels
retain attr.name="label" and are distinguished by ID/domain. Actual installed
NetworkX 3.6.1 import maps by attr.name and additionally overlays yEd graphics;
the separately reproduced interoperability gap is treesitter-chunker#453. This
slice documents that limit without adding a consumer adapter or changing caller
attribute names. Graph attribute-name validation and older-Python pretty
whitespace remain treesitter-chunker#452 and treesitter-chunker#450.

## Changes

- `chunker/export/graphml_exporter.py`: change only the dedicated structural label
  declaration and data references to node_label/edge_label; keep property loops.
- `tests/test_graphml_exporter.py`: deliberately migrate structural-key assertions,
  then extend real parsed service fixtures with caller node/edge label properties
  and collision-shaped names. Parse actual XML, check declaration/data uniqueness,
  domains and retained structural/caller values. Reverse caller property insertion
  order and require the same key/value mapping; no fake graph/parser mocks.
- `tests/test_graphml_yed_export_contract.py`: exercise the same metadata and edge
  properties in yEd enabled/disabled and pretty/compact output; retain graphics
  direction and all accepted identity/character checks.
- `docs/graphml_export.md`: migrate structural key/data examples and explain the
  two namespaces and label consumer migration. `CHANGELOG.md` explicitly marks
  this key change BREAKING for 6.0.0. This plan/typed plans/manifest.json row are
  owned. No direct yEd source change is expected; inheritance is tested.

Preserve every accepted graph/platform selection. Additional serializer defects
are separately filed before any repair. treesitter-chunker#444 DOT punctuation
and treesitter-chunker#446 Python token selection remain outside this slice.

## Order

Commit the plan before implementation. Wait for accepted graph identity and XML
character PRs, integrate main preserving canonical manifest rows, then mark only
this row executing. Add regressions and record actual unchanged-source failures.
Implement the four dedicated declaration/data references. Run independent actual
`structural_node_label_collision` and `structural_edge_label_collision` mutations,
restoring the respective old structural declaration and data key: new node/edge
label tests must fail uniqueness and unambiguous values. Each exact restoration
passes the full focused set and binds final source/test bytes.

Collect complete four-seat manual code reviews before revisions, maximum three
substantive rounds. Opus5.5 uses the tool-enabled TUI adapter, Gemini3.8Flash and
Astra/Sol use compact pointers and final-response host capture where necessary.
Heartbeat-only monitoring; failed delivery cannot count as approval. The requested
manual Astra chair independently checks actual outputs and completed evidence.

## Verification

- `uv sync --locked --all-extras`
- `uv run --locked --all-extras pytest tests/test_graphml_exporter.py tests/test_graphml_yed_export_contract.py tests/test_phase12_integration.py -q`
- `uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site`
- `uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/`
- `uv run --locked --all-extras python scripts/mypy_gate.py`
- `uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py`
- `uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux`
- `uv run --locked --with toml --all-extras python scripts/run_full_suite.py`

Supported draft publication precedes serialized original six/locked refresh/full
tests/spec_tests. Actual matching-source focused/standing Windows, every exact-head
hosted job, four substantive approvals and final Astra ruling remain independent
acceptance gates. Archive raw evidence before exact-head merge, qualified issue
comments/closure and safe pruning. No percentage or whole EXPORT/IF acceptance,
release dispatch, consumer-lock, native/pin/schema/golden/broker/ledger edit.

## Execution evidence pending acceptance

Both prerequisites are accepted: treesitter-chunker#443 and treesitter-chunker#447.
All 52 current-main manifest rows are retained exactly, with only this executing
row added for 53. Real service-fixture plain/yEd/delegated contracts cover caller
label, node_label, edge_label and metadata_label in both insertion orders and
formats, checking declaration/data uniqueness, domains and retained values.
Focused candidate tests pass 390; source changes are exactly four structural
declaration/data references. Each actual collision mutation fails 18 cases,
including both new raw-label contract modules; each exact restoration passes
390 and binds source/tests/real fixtures plus the unchanged yEd source.
The final formatted unchanged-source baseline remains 19 failed, 371 passed.
Original full/platform/review gates remain pending. Initial test setup misplaced an old
yEd control block; it was restored byte-for-byte before the final unchanged-source
baseline (19 failed, 371 passed). The earlier log remains excluded as setup history.
The first consumer probe incorrectly expected caller labels to win in yEd;
installed-reader source showed its graphics overwrite. The corrected three-mode
probe binds actual candidate source hashes and is filed as treesitter-chunker#453.

## Acceptance criteria

- [ ] Real fixture XML has one declaration/data occurrence per key with correct
  domains, distinct retained structural/caller label values and stable mappings
  for collision-shaped names in both insertion orders; both actual mutations fail
  and each exact restoration passes with final source/test hashes.
- [ ] Plain/yEd/pretty/compact/delegated output retains directed endpoints,
  graphics and accepted character behavior. Docs/changelog deliberately migrate
  structural labels to node_label/edge_label at the next-major 6.0.0 boundary.
- [ ] Original six, locked refresh/full, matching-source Windows, exact hosted
  jobs, four bounded reviewers and Astra chair accept only label key uniqueness,
  with no XSD, identity-generation, automatic consumer migration or whole-phase claim.

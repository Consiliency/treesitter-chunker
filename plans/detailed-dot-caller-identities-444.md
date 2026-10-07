---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: DOT caller identities

## Task and research

Resolve treesitter-chunker#444 as one independently landable serializer repair.
Current accepted-source reproduction parses the checked-in graph_same_span.py
fixture with the actual Python grammar. Its two functions retain distinct graph
model IDs, but caller IDs a-b and a_b compile into one DOT node and a self-loop.
A caller ID containing a double quote makes Graphviz reject the output. Ordinary
parser hexadecimal IDs compile into two nodes and a directed edge. Both flat and
clustered output reproduce these results. The reproduction binds fixture/source
digests, Git head, actual dot -Tjson exits and compiled graph semantics.

## Files and observable contracts

- chunker/export/dot_exporter.py: preserve nonempty ASCII hexadecimal node IDs
  byte-for-byte. Encode every other valid UTF-8 string as tc_ plus its UTF-8
  hexadecimal bytes. Quote both forms. The prefix contains a nonhex character,
  keeping the preserved and encoded namespaces disjoint. All declarations,
  edge endpoints and cluster members already use this single formatter.
- tests/test_graphml_exporter.py: use real parsed fixture functions, changing
  only caller-supplied node_id at the supported graph boundary. Distinct IDs
  remain two compiled nodes with one directed CALLS edge, unchanged source
  labels and cluster membership. Include punctuation pairs, quote/backslash,
  LF/CR/tab/NUL, Unicode, encoded-prefix alias and ordinary hexadecimal IDs.
  Exercise string/file output, flat/clustered graphs, repeat determinism and
  ordinary parser-ID stability. Actual Graphviz JSON is the independent semantic
  oracle; the formatter under test is never the expected-ID oracle. Compiler
  absence may skip compiler cases on a host, never qualify compiler acceptance.
- docs/graphml_export.md and CHANGELOG.md: explain nonhex serialized-ID migration
  under 6.0.0. Regenerate DOT and update consumers joining serialized IDs;
  graph-model IDs, labels, occurrence algorithms and hexadecimal DOT IDs remain
  unchanged. Do not promise reversible original IDs from DOT labels or certify
  arbitrary labels, live rendering applications or every Graphviz version.
- plans/detailed-dot-caller-identities-444.md and one manifest row: preserve
  every canonical entry and held evidence; lifecycle reconciliation stays
  treesitter-chunker#361.

## Execution and independent review

1. Base a private WORKTREE_ROOT checkout on accepted main after
   treesitter-chunker#474 is merged and archived. Publish a plan-only draft with
   supported publication before implementation; no planning tests/builds.
2. Locked environment, focused actual-parser tests on the unchanged formatter
   must reproduce collisions/compiler refusal. Implement only the formatter,
   contracts and consumer documentation. Test exact restoration after mutation.
3. Named production mutation collapse_dot_caller_ids_to_underscores restores
   the old punctuation replacement. New semantic tests must fail; restore exact
   production bytes and require all focused cases to pass. Record source/test
   digests and actual process exits. This one mutation is one fault family;
   baseline and mutation runs are not two independent mutation kills.
4. Fresh sealed original six checks, locked refresh and full tests/spec_tests;
   exact-head native Windows focused tests and standing preflight; exact-head
   hosted required checks. Record Windows compiler availability and actual
   compiler tests honestly. Existing authenticated Leno native Windows is an
   available route; the original host's Smart App Control defect remains
   dotfiles#66. Serialize original runners and publication/Git mutations.
5. Four manually launched tools-enabled CODE seats: Opus 5.5 subscription TUI,
   Gemini 3.8 Flash, Astra and Sol, compact file pointers, heartbeat only, maximum
   three complete substantive rounds. Collect all four before reconciliation;
   incomplete delivery is not approval. Final supplemental Astra president
   examines immutable source and complete frozen evidence. Standalone archive
   precedes authorized exact-head qualified merge, issue closure and owned
   pruning.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_graphml_exporter.py -k dot_caller -q
- uv run --locked --all-extras pytest tests/test_graphml_exporter.py tests/test_phase12_integration.py tests/test_export_integration_advanced.py -q
- Ruff, Black, committed-baseline mypy gate, CI smoke, Linux platform-core,
  locked refresh and uv run --locked --with toml --all-extras python scripts/run_full_suite.py
- Native Windows archive bound to exact Git head and file digests; locked
  focused tests then scripts/run_windows_preflight.py. No trust/policy changes.

## Acceptance criteria

- [ ] Actual parsed nodes with distinct supported caller IDs survive Graphviz
  compilation as distinct nodes with correct edge direction, labels and cluster
  membership across string/file and flat/clustered output; ordinary hexadecimal
  IDs and deterministic repeat output are preserved.
- [ ] The named punctuation-collapse production mutation fails the new semantic
  contracts, exact source restoration passes, and immutable hashes/actual exits
  bind this fault coverage without fabricated independent kills.
- [ ] Fresh sealed original six/refresh/full, current native Windows/standing,
  all required exact-head hosted checks, four complete final CODE opinions,
  supplemental Astra and standalone archive qualify this repair before merge.

## Limits

Relationship-label quoting is separately treesitter-chunker#473; do not fix it
silently. GraphML issues treesitter-chunker#450, treesitter-chunker#452 and
treesitter-chunker#453, cache treesitter-chunker#358, CR-only policy
treesitter-chunker#471 and native admission remain separate. No parser pins,
goldens, type baseline, consumer locks, protected branch/ledger/checkpoints or
broker edits; no percentage gate. Manual supplemental CODE is not governed
amendment, supplier/native-fill/IF, whole-phase or release acceptance.
agent-harness#1271 remains separate; Unreleased is reserved for 6.0.0, no tag.

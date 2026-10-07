---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: direct DOT relationship label text

## Task and research

Repair treesitter-chunker#473 independently of accepted caller identity repair
treesitter-chunker#444. Actual Python parsing of graph_same_span.py supplies
two ordinary hexadecimal function IDs. CALLS compiles; CALLS followed by a
double quote and suffix fails actual Graphviz compilation. The relationship
label bypasses quoting in DotExporter._get_edge_attributes.

Graphviz has two text layers: quoted DOT syntax and escString interpretation.
Its documentation specifies literal backslashes and special label line escapes:
https://graphviz.org/docs/attr-types/escString/ and
https://graphviz.org/doc/info/lang.html. Preserve caller backslashes rather than
allowing graph/node substitutions or interpreting literal backslash-n as a line
break. Existing _escape_label also replaces tab with an unsupported escape,
changing rendered text to t; do not reuse it for this repair. That existing node
label/tooltip defect remains treesitter-chunker#476.

## Owned changes and observable contracts

- chunker/export/dot_exporter.py, _get_edge_attributes: quote backslashes first,
  then double quotes, then represent physical LF as Graphviz's centered line
  break. Retain physical tabs and CR in the quoted label. Change only this
  relationship label assignment. Graph IDs, model relationship strings,
  edge-style lookup, node labels, tooltips and caller attribute APIs retain
  existing behavior. No new serializer-wide quoting or attribute validation.
- tests/test_graphml_exporter.py: actual parsed f/g fixture functions and actual
  Graphviz JSON plus SVG, across flat/clustered and string/exported-path output.
  Cover ordinary and empty labels, double quotes, mixed quote/backslash,
  trailing backslash, substitution-looking sequences, literal backslash-n/l/r/t,
  repeated backslashes, physical LF/CR/tab, Greek/accented/combining Unicode and
  HTML-looking tags. Compare rendered edge text to independent caller literals;
  LF yields two centered lines, CR remains in Graphviz's compiled label value.
  JSON retains Graphviz's escape representation and is not a raw-text oracle for
  backslashes. Assert two original hex nodes, one directed edge, unchanged node
  labels/cluster membership, stable repeat output, CALLS style and unchanged
  ordinary tooltip. Compiler absence may skip, never qualify acceptance.
- docs/graphml_export.md: document direct relationship labels as literal text,
  with physical LF line breaks and preserved tabs/CR. Scope is valid UTF-8 text
  excluding NUL and HTML entity sequences; arbitrary control bytes, invalid surrogates, renderer typography,
  arbitrary attribute values and other label paths are not certified. Explain
  why backslash sequences are literal and HTML-looking tags remain plain text.
  Graphviz interprets HTML entities; treesitter-chunker#478 independently tracks
  literal preservation. Qualify compiler evidence to tested Graphviz 14.1.2 on
  Linux and 14.1.1 on Windows, without a cross-version claim.
- CHANGELOG.md: record the bounded repair under Fixed and remove obsolete
  treesitter-chunker#473 pending wording; reserve Unreleased for 6.0.0, no tag.
- This plan and one typed manifest row: preserve all 64 existing canonical rows;
  lifecycle reconciliation remains treesitter-chunker#361.

## Dependencies and order

1. Private WORKTREE_ROOT checkout starts at accepted main after
   treesitter-chunker#475. Write/register this plan, commit owned plan paths,
   then publish a plan-only draft through supported publication before code.
   Planning itself runs no tests/builds. Standing roadmap execution authorizes
   the subsequent implementation and verification stage.
2. Add real compiler contracts, reproduce failures on unchanged production,
   then make the bounded assignment change and document its text scope.
3. Named mutation unescaped_dot_relationship_label restores the old raw label
   assignment. Quoted/backslash cases must catch syntax/text corruption. Named
   mutation escape_dot_relationship_controls_with_existing_helper uses the
   existing helper; tab/CR contracts must catch text changes. Each exact source
   restoration must pass. Preserve digests, actual exits and raw output; these
   are two fault families, not one per parametrized case or host repetition.
4. Commit clean candidate; fresh original six checks, locked refresh/full suite,
   current native Windows focus and standing preflight, exact-head hosted jobs.
   Native Leno has an authenticated supported Python 3.12 route and private
   checksum-verified portable Graphviz; original-host policy is dotfiles#66.
   Record actual child locale/raw bytes; no locale or trust-policy forcing.
5. Four manual tools-enabled CODE seats: Opus 5.5 subscription TUI, Gemini 3.8
   Flash, Astra and Sol. Compact pointers, heartbeat only, no silence/model
   deadline, maximum three complete substantive rounds. Collect all four and
   original before reconciliation; failed delivery is not approval. Final
   supplemental Astra president audits immutable complete evidence. Strict
   proof and standalone verbatim archival precede authorized exact-head merge,
   issue closure and owned pruning. Serialize original runners and publication.

## Verification commands

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_graphml_exporter.py -k dot_relationship -q
- uv run --locked --all-extras pytest tests/test_graphml_exporter.py tests/test_phase12_integration.py tests/test_export_integration_advanced.py -q
- Ruff, Black and committed-baseline mypy gate; CI smoke/Linux platform core;
  locked refresh and uv run --locked --with toml --all-extras python scripts/run_full_suite.py
- Native Windows exact Git archive/digests: compiler cases, named mutation and
  exact passing restoration, focused modules, scripts/run_windows_preflight.py.
- Hosted platform core includes this test module; smoke excludes it. Hosted
  success alone does not establish compiler availability/non-skipped cases.

## Acceptance criteria

- [ ] Actual-parser/Graphviz contracts prove supported relationship text,
  directed endpoints, ordinary style/tooltip, labels/clusters, repeat stability
  and string/exported-path behavior. Narrow compiler cases prove this item.
- [ ] Both named mutations violate their specified text/syntax contracts and
  exact restoration passes; source/test/support hashes and actual exits bind
  the proof. Mutation logs prove this item, without inflated kill counts.
- [ ] Fresh sealed original six/refresh/full, actual native Windows/standing,
  exact hosted jobs, four complete CODE opinions, supplemental Astra decision
  and standalone archive qualify the repair before merge.

## Complete R1 reconciliation

All four CODE R1 opinions and original/full/native Windows completed before
reconciliation. Gemini/Sol agreed; Opus/Astra identified an incorrectly named
Windows mutation record, and Opus identified an unsupported HTML-entity text
claim. Raw round, runner and mismatched Windows record are held verbatim.
Actual SVG compilation confirms entity decoding; independently filed
treesitter-chunker#478 remains outside this bounded quoting repair. Narrow
docs to listed text cases without entity sequences and tested compiler versions,
and document caller backslash migration. Production/test bytes remain unchanged.
Regenerate Windows evidence with its identity bound to the actual Linux mutant
digest, then require a fresh exact-head original, native Windows, hosted checks
and complete CODE R2 under the existing three-round allowance.

## Limits

No arbitrary DOT attribute/label completeness, unsupported entity/NUL/surrogate or
cross-renderer layout claim. Node labels/tooltips remain treesitter-chunker#476;
GraphML treesitter-chunker#450, treesitter-chunker#452, treesitter-chunker#453,
cache treesitter-chunker#358, CR-only source policy treesitter-chunker#471,
lifecycle treesitter-chunker#361 and native admission remain separate. No parser
pins, goldens, type baseline, consumer locks, protected branch/ledger/checkpoint
or broker edits. No percentage gate. Manual supplemental CODE is not governed
supplier/native-fill/IF, whole-phase or release acceptance; operational amendment
agent-harness#1271 remains separate. Unreleased is reserved for 6.0.0; no tag.

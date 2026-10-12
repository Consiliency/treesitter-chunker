# Literal caller entities in direct DOT labels

## Run context

- Repository: Consiliency/treesitter-chunker
- Branch: `codex/dot-entities-478`
- Base: `ef26c961e61fdd53e46d8afb3367b553aa97c574`
- Issue: treesitter-chunker#478
- Evidence: `/home/viperjuice/workspace/evidence/treesitter-chunker/dot-entities-478/takeover-20261011`
- Separate budgets: at most three complete PLAN rounds and three complete CODE
  rounds, all four opinions before reconciliation, heartbeat only.

## Problem and contract

Actual parsed `tests/fixtures/graph_same_span.py` supplies two distinct function
IDs. Graphviz decodes caller `R&amp;D` to `R&D`, `A&#10;B` to two lines and
`A&#92;nB` to two lines in quoted DOT labels. Node labels, file/cluster labels
and relationship tooltips share the defect. Plain labels should display literal
caller text, including entity-looking sequences. This repair changes serialized
label/tooltip bytes to protect that text from Graphviz interpretation.

Preserve physical caller LF versus literal backslash-n, quotes, backslashes,
Unicode, existing TAB/CR behavior, field order and optional zero. Generated
node fields remain centered separate lines as repaired by treesitter-chunker#479.
Preserve IDs, edge endpoints/topology, styles, cluster membership, caller chunks,
node/edge properties and style dictionaries. Repeated string output and repeated
exports to the same actual file must agree under existing CRLF normalization.
Compiled JSON escString values contain the protective serialization; they are
not asserted equal to unencoded caller input. Parsed SVG text/tooltips establish
the visible literal contract, retaining XML attribute TAB normalization.

Scope is the listed valid UTF-8 label/tooltip cases on measured Linux Graphviz
14.1.2 and private native Windows 14.1.1. Empty-line typography, arbitrary
controls/NUL, invalid surrogates, arbitrary custom attribute values, HTML-label
APIs, package exporters, other compilers and formal supplier qualification remain
outside this repair. Existing compiled guards remain intact. No pins, locks,
goldens, type baseline, releases, consumer locks or historical lifecycle edits.

## Owned paths

1. `chunker/export/dot_exporter.py`
2. `tests/test_graphml_exporter.py`
3. `docs/graphml_export.md`
4. `CHANGELOG.md`
5. `plans/detailed-dot-entities-478.md`
6. `plans/manifest.json`: append and update only owned row70; preserve all69
   predecessor rows and events, including intentionally deferred states.

## Implementation and evidence

1. Commit this bounded plan through the supported manifest API. Collect native
   Opus 5.5 TUI, Gemini 3.8 Flash, Astra and Sol complete PLAN opinions using tools,
   short pointers and isolated machine evidence. Reconcile only after all four;
   retain original responses and every finding/disposition in later rounds.
   Obtain a separate independent Astra design president before implementation.
2. Extend existing real-parser DOT tests. Use independent caller/serialized/SVG
   expectation tables for named, decimal, hexadecimal, nested and adjacent
   entities, quote/backslash, Unicode, physical LF/TAB and ordinary-ampersand,
   unknown-entity and HTML-looking controls. Target node name/type/path, cluster
   label, relationship label and tooltip key/value independently. Cover flat and
   clustered graphs where the target exists, string and actual-file output;
   compile the actual second file export for file cases. Caller path strings are
   virtual metadata; actual source/output filenames remain portable. Cluster cases
   designate the cluster assertion before related node-path assertions.
3. Assert real fixture parse success, f/g signatures/spans and distinct runtime
   IDs. Check topology, style, membership and deep independent caller/property/
   style snapshots before the designated entity renderer assertion. Compare
   hand-written compiled JSON encodings separately from SVG text; record exactly
   which oracles execute under each fault rather than claiming unmeasured kills.
4. Run new tests against unchanged production and retain exact failing pytest
   identifiers/assertions, passing controls, zero setup errors and zero contract
   skips. Protect ampersands in existing shared label escaping and the separate
   relationship-label path, preserving their existing escape/CR behavior. Do not
   refactor either path or add an HTML/entity interpretation option.
5. Use named source mutations removing protection independently from the shared
   helper and relationship-label path. Record exact semantic failure sets and
   assertion targets; restore candidate bytes and prove green after each fault.
   Execute both on Linux and private native Windows, stamp compiler path/version/
   binary before and after actual runs, and bind fixture/test/source/collection
   hashes. Count fault executions/restorations honestly; preserve originals.
6. Batch verification: narrow compiled tests first; exporter/integration focus,
   supported original sealed locked refresh, Ruff, Black, committed-baseline
   mypy, smoke, platform-core/full suite and strict temporary MkDocs. Retain the
   actual runner driver, measured head/source assertions before/after execution,
   transcript, seal and executable archive/collection binding checkers. Native
   Windows uses an exact-head archive, private checksum-verified official portable
   compiler and locked Python3.12 environment; run focused and standing preflight
   without changing shared checkout, locale or host configuration. Supplemental
   distro compatibility may inform nightly risk without claiming hosted execution.
7. Update current entity limitations and add a consumer-visible changelog entry,
   retaining unrelated scope limits. Publish genuine prebuilt commits through
   supported APIs. Collect four complete CODE opinions at exact head in isolation,
   followed by independent Astra implementation acceptance. Verify standalone raw
   archive before supported completion of only row70. A lifecycle-only new head
   requires fresh original/native/hosted gates and remaining CODE allowance;
   bind historical negatives through source identity without restamping them.
8. Write mandatory runtime-resolved reflection/handoff and independently verify
   final standalone archive hashes. Fresh origin/protected-state/PR-head/all-seven
   REST check success checks gate ready/merge and issue closure. Safely prune only
   clean owned merged work after backing up ignored artifacts and verifying every
   native tracked/package hash. Preserve old primary, S27, held/unmerged work,
   ledgers, checkpoints, broker state and global native journals.

## Acceptance criteria

- [ ] Actual parser/Graphviz JSON/SVG proves literal entity-looking caller text
  across the scoped node/edge/cluster/tooltip fields and output modes while
  preserving identities, layout/escapes, caller/property/style state and repeated
  actual-file output.
- [ ] Unchanged production and both named faults fail the intended independent
  entity assertions with exact source-bound failure sets, zero setup errors or
  contract skips; byte-exact restorations pass on Linux and native Windows.
- [ ] Fresh original sealed checks/full, strict docs, native Windows/standing,
  exact-head hosted checks, four complete manual opinions, independent Astra
  acceptance and verified standalone archive establish bounded repair acceptance.

## Dependencies and deferred work

No dependency on treesitter-chunker#487 call-resolution/Boundary IR work or held
native/IF lanes. Runtime0.7.26 remains installed under a changed tooling release;
agent-harness#1433, agent-harness#1434 and agent-harness#1518 remain open and
agent-harness#1491 is merged. Inspect deployment inclusion separately; manual
review does not establish formal Harness/supplier/native/IF qualification or
grant new allowances to exhausted held plans. Supply a concrete external Harness
prompt if qualification requires external action; never repair broker authority
or fabricate FABPUB trailers to bypass publication gates.

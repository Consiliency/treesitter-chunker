---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

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
and relationship labels/tooltips share the defect. Plain labels should display literal
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
APIs, package exporters and formal supplier qualification remain
outside this repair. Existing compiled guards remain intact. No pins, locks,
goldens, type baseline, releases, consumer locks or historical lifecycle edits.
The required private distro compatibility run below informs older-compiler risk;
it does not extend the documented qualification beyond the two measured native
versions. Entity coverage concerns the seven specified caller fields, not every
possible complexity/token value or custom attribute.

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
   designate the cluster assertion before related node-path assertions. Add
   dedicated `dot_literal_entities_visible` and `dot_literal_entities_json`
   tests; keep previous compiled tests unchanged. Use entities whose decoded
   baseline is valid XML/UTF-8, excluding numeric illegal controls/surrogates and
   ambiguous repeated-space typography. Include nested `&amp;amp;` and tooltip
   numeric-backslash sequences followed by N/E/T/H/G/L, with literal expected
   text. Ordinary ampersands/unknown entities in SVG also guard against double
   protection. Existing relationship/tab selectors retain CR regression checks;
   do not claim a new entity-plus-CR matrix.
3. Assert real fixture parse success, f/g signatures/spans and distinct runtime
   IDs. Check topology, style, membership and deep independent caller/property/
   style snapshots before the designated entity renderer assertion. Compare
   hand-written compiled JSON encodings in separate tests from SVG text; record exactly
   which oracles execute under each fault rather than claiming unmeasured kills.
4. Run new tests against unchanged production and retain exact failing pytest
   identifiers/assertions, oracle-specific controls, zero setup errors and zero
   contract skips, according to the outcome table below. Protect ampersands first
   in existing shared label escaping and the separate
   relationship-label path, preserving their existing escape/CR behavior. Do not
   refactor either path or add an HTML/entity interpretation option.
5. Named `remove_dot_shared_ampersand_protection` removes only the candidate's
   ampersand replacement from `_escape_label`, leaving edge protection intact.
   Named `remove_dot_relationship_ampersand_protection` removes only the separate
   relationship-label ampersand replacement, leaving the shared helper intact.
   Each retains all other candidate bytes. Require identical mutant and restored
   production SHA-256 on Linux and Windows. Record exact semantic failure sets and
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
   without changing shared checkout, locale or host configuration. Before merge,
   require an informational private Ubuntu24.04/Graphviz2.43 compatibility run
   of the same narrow selection with actual compiler stamps and no repaired-test
   skips. Retain results separately from original gates/native qualification; a
   semantic failure must be reconciled before merge. This is not a hosted/nightly
   full-suite claim. Use owned scratch/container IDs and normal verified cleanup.
7. Replace superseded entity limitations in `docs/graphml_export.md` (the plain
   labels and TAB contract paragraphs) and both current `CHANGELOG.md` entity
   limitations. Add migration guidance: callers relying on entity decoding must
   supply actual literal characters, including physical LF for line breaks.
   Keep HTML-looking plain text as a visible control; HTML-label APIs are excluded.
   Add a consumer-visible changelog entry,
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

## Oracle-specific expected outcomes

The SVG test checks preservation/state/topology/style assertions before the
designated visible target. The JSON test independently checks the hand-written
protective escString value; neither test can mask the other's assertion. Here
"recognized" means one of the scoped sequences whose decoded visible text differs
on the measured compiler, "amp control" is an ordinary ampersand or unknown
entity with unchanged visible text, and "no-amp control" includes plain markup,
Unicode and ordinary escape/layout cases without ampersands. Candidate is the
fully protected source. Each fault is otherwise candidate source; only its named
field path is affected. The other field path retains candidate outcomes.

| Category/oracle | Old source | Shared fault, shared field | Edge fault, edge label | Candidate |
| --- | --- | --- | --- | --- |
| Recognized / SVG literal text | fail | fail | fail | pass |
| Amp control / SVG literal text | pass | pass | pass | pass |
| No-amp control / SVG literal text | pass | pass | pass | pass |
| Recognized / JSON protective bytes | fail | fail | fail | pass |
| Amp control / JSON protective bytes | fail | fail | fail | pass |
| No-amp control / JSON protective bytes | pass | pass | pass | pass |

Shared fields are node name/type/path, cluster label and tooltip key/value.
The edge fault affects only relationship labels. Cluster targets exist only in
clustered mode; all other targets use flat/clustered and string/actual-file modes.
Freeze collected identifiers and expected sets from category, oracle and affected
field before each negative run; compare exact sets and assertion targets, not
just counts. Preserve zero errors/skips and report any compiler-specific departure
from the discovery hypothesis explicitly. JSON-only amp-control failures are
serialization checks, not visible-renderer mutation kills. Count two distinct
source faults, their actual host executions and restorations separately.

## Exact verification commands

Run from the owned checkout with its locked environment. Native Windows runs
the same narrow/focused argv with its private compiler on the child PATH, followed
by its standing preflight. The distro run uses the same narrow argv. Retain argv,
outputs and compiler stamps; compilation must not be silently skipped.

```sh
uv sync --locked --all-extras
uv run --locked --all-extras pytest tests/test_graphml_exporter.py -k 'dot_literal_entities_visible or dot_literal_entities_json or dot_generated_node_lines or dot_label_tabs or dot_relationship_labels or dot_caller_ids' -q
uv run --locked --all-extras pytest tests/test_graphml_exporter.py tests/test_phase12_integration.py tests/test_export_integration_advanced.py -q
uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
uv run --locked --all-extras python scripts/mypy_gate.py
uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
uv run --locked --with toml --all-extras python scripts/run_full_suite.py
uv run --locked --with toml --all-extras python scripts/run_windows_preflight.py
```

For strict docs use a fresh absolute directory returned by the driver's
`tempfile.TemporaryDirectory`, substituted as the single site-dir argument:

```sh
uv run --locked --all-extras --with mkdocs --with mkdocs-material --with mkdocstrings-python mkdocs build --strict --site-dir "$DOT_ENTITIES_DOCS_SCRATCH/site"
```

The supported original runner seals locked refresh/lint/type/smoke/core/full;
retain the actual runner driver with measured clean head/source before and after
and the original artifact/transcript. Narrow runs add JUnit and collection receipt
arguments in retained drivers, without changing the test selection. Hosted CI
smoke excludes the compiled module; platform-core success alone does not prove
compiler availability. Dedicated local/native/distro receipts establish those
compiler observations; no workflow expansion is planned.

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

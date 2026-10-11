---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: render generated DOT node label lines

## Task and research

Repair treesitter-chunker#479 from fresh accepted main
102e74bbd5cf8dc3ce26e469ba0b39a790046f06, after treesitter-chunker#490.
Actual Python parsing of tests/fixtures/graph_same_span.py yields distinct f/g
function chunks. Graphviz 14.1.2 successfully compiles the direct DotExporter
output, but its SVG node text contains visible backslash-n between type,
file/span and complexity fields. _get_node_attributes joins generated parts
with literal backslash-n before _escape_label doubles each backslash.
The established caller-text escape helper already maps physical LF to a DOT
line break and preserves caller literal backslash-n as visible text.

Existing test_dot_label_tabs_preserve_compiled_text deliberately accepts the
old generated layout: its last caller line includes every generated field.
That assertion must be updated to the repaired layout while preserving its
independent caller/tab/tooltip/cluster contract. Other DOT contracts compare
actual identities, endpoints, relationship text and control-graph labels.
The package-level formats exporter is a separate implementation.

## Owned files and contract

- chunker/export/dot_exporter.py: join generated label_parts with physical LF
  before passing the combined text through the existing _escape_label. Keep
  construction/order of the type/name, file/span, complexity and token fields.
  Caller physical LF remains a line break; literal backslash-n, quotes and
  backslashes retain their existing escape semantics. Do not change the helper,
  relationships, tooltips, cluster labels, IDs, graph attributes or file writer.
- tests/test_graphml_exporter.py: reuse parsed_same_span and real f/g chunks.
  Add actual Graphviz JSON and SVG contracts across flat/clustered graphs and
  string/exported-file inputs. Exercise ordinary parsed metadata, absent extra
  fields, token-only including zero, and both complexity/token fields. Cover
  absent/empty/ordinary names, physical LF, caller literal backslash-n, quotes,
  trailing backslash and Unicode; virtual file-path controls cover physical LF
  and literal backslash-n without creating invalid Windows fixture filenames.
  Specify expected visible SVG lines independently from _get_node_attributes
  and _escape_label, including each field and caller line. Use explicit expected
  fixture-field values, not an exporter-derived oracle. Inspect JSON graph node
  names and edge endpoints, two distinct original parser IDs, one CALLS edge,
  red/dotted style and cluster membership. Preserve caller chunk metadata,
  content and identities, graph state and repeated output. File tests compile
  the actual written path, rather than merely compiling export_string again.
  Native file newline translation is allowed; assertions distinguish transport
  CRLF from caller text and renderer layout. Update the existing tab test to
  assert complete expected caller and generated lines, retaining physical-tab,
  literal-backslash-t, tooltip and cluster checks. No broad weakened assertions.
- docs/graphml_export.md and CHANGELOG.md: describe generated centered node
  label lines, unchanged caller literal backslash-n versus physical LF, actual
  tested compiler versions and valid UTF-8 scope. Remove the superseded
  treesitter-chunker#479 limitation while retaining treesitter-chunker#478
  entity decoding and unrelated limits. No release/tag or source version bump.
- This plan and one appended typed plans/manifest.json row. Preserve all 68
  predecessor rows and events, protected checkouts, held work, broker state,
  ledgers/checkpoints, consumer locks, pins, goldens and the type baseline.

## Execution order and evidence

1. Commit this plan and supported manifest registration only. All four native
   manual subscription PLAN opinions (Opus 5.5 TUI, Gemini 3.8 Flash, Astra, Sol)
   must complete before reconciliation; then obtain independent Astra design
   approval before implementation. Short file-pointer prompts, tools enabled,
   heartbeat only, no model/silence deadline; at most three complete PLAN
   rounds. No new supplier/native/IF or formal Harness qualification.
2. Add the tests and reproduce the observable layout failures against unchanged
   production. Save collected exact node IDs, JUnit failures, assertion text,
   fixture/source/test hashes, compiler versions and raw outputs. Apply the
   one-line repair and scoped test/docs changes; require green narrow tests.
3. Named mutation double_generated_dot_node_separators restores only the
   generated joining delimiter to literal backslash-n, retaining every other
   candidate byte. The new renderer cases and updated tab layout cases must
   fail at their intended line-content assertions, with zero setup errors;
   record the exact failing node-id set derived from their collected cases.
   All selected contracts pass after byte-exact candidate restoration. One
   semantic fault family, not one per case/host. No arbitrary nonzero exit or
   count-only mutation claim. Positive identity/relationship/tooltip controls
   remain meaningful even when layout fails.
4. Commit clean candidate and use the original supported verification runner
   for locked refresh, Ruff, Black, committed-baseline mypy, smoke, Linux
   platform-core and full suite. Build strict docs in unique disk scratch.
   New/changed-head acceptance reruns the original gates with sealed runner
   evidence, without updating parser pins, goldens or the committed baseline.
5. Native Windows uses an exact git archive in a new private snapshot, Python
   3.12, default CP1252/CRLF and a private official Graphviz 14.1.1 ZIP whose
   published checksum and actual SHA-256 match. Add its bin only to that child
   process PATH; no shared installation, locale or trust-policy changes. Run
   actual string/file JSON/SVG tests, the named semantic mutation and exact
   restoration, focused modules and standing scripts/run_windows_preflight.py.
   An absent compiler or skipped repaired contract is not qualification. Retain
   source/archive bindings, original child outputs and actual compiler version.
6. Supported publication API uses the complete owned scope and genuine normal
   commits, preserves broker/checkpoint state and creates/updates a draft.
   Never push directly, synthesize FABPUB trailers or repair broker state.
   Recheck installed Harness and agent-harness#1433, agent-harness#1434 and
   agent-harness#1518 before interpreting any publication failure. Manual
   review does not establish formal Harness or supplier qualification.
7. Collect four complete CODE opinions before reconciliation, with the same
   native subscriptions, tools/pointers and heartbeat-only policy; maximum
   three complete CODE rounds. Independent Astra final audit, exact-head REST
   hosted successes and a verified standalone archive of complete raw provider
   opinions/tool receipts, all original mutation/platform/gate records and
   dispositions precede merge. Lifecycle-only tracked changes require fresh
   exact-head gates and remaining bounded review allowance. If exhausted,
   retain reviewed bytes and document deferred canonical reconciliation via a
   supported private-copy receipt; never claim that copy is published.
8. Authorized normal merge uses --match-head-commit, with fresh clean/base/head
   and all hosted checks. Comment then close treesitter-chunker#479. Archive
   reflection/handoff and owned workflow artifacts before pruning only clean
   owned merged Linux/native snapshots; preserve all unrelated work and state.

## Verification commands

- uv run --locked --all-extras pytest tests/test_graphml_exporter.py -k
  'dot_generated_node_lines or dot_label_tabs' -q
- uv run --locked --all-extras pytest tests/test_graphml_exporter.py
  tests/test_phase12_integration.py tests/test_export_integration_advanced.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive
  --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py
  --platform linux
- uv run --locked --with toml --all-extras python scripts/run_full_suite.py
- Native Windows narrow/focused commands above and
  uv run --locked --with toml --all-extras python scripts/run_windows_preflight.py
- Strict MkDocs with existing temporary dependency pattern and unique disk
  site-dir; retain raw result. Do not create tracked site artifacts.

## Acceptance criteria

- [ ] Actual parser/Graphviz JSON/SVG prove generated fields render on their
  own lines, caller LF and literal backslash-n remain distinct, original node
  and directed-edge identities/style/cluster membership survive, caller state
  is unchanged and repeated string/actual-file output meets the stated scope.
- [ ] Unchanged production and named doubled-separator fault violate the exact
  intended renderer assertions; source-bound records preserve exact failure
  sets and zero setup errors, and byte-exact candidate restorations pass on
  Linux and native Windows with actual compilers and no contract skips.
- [ ] Fresh sealed original checks/locked refresh/full suite, strict docs,
  native Windows/standing, exact-head hosted checks, complete quartet and
  independent Astra acceptance plus verified standalone raw archive establish
  bounded implementation acceptance before authorized merge/pruning.

## Limits and continuation

No typography, arbitrary graph/style attributes, HTML entity preservation,
NUL/invalid-surrogate/control completeness, renderer/version generality or
package-level exporter change. No GraphML reader/transport changes. Symbol
resolution treesitter-chunker#487 needs separate qualification-loss research;
native admission and formal Harness/supplier gates remain blocked separately.
The primary stays deliberately older than origin/main; next owned work starts
from fresh accepted origin/main. Do not repeat completed treesitter-chunker#482,
treesitter-chunker#450 or treesitter-chunker#490 closeout.

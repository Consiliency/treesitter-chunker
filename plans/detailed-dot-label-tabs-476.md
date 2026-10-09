---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: preserve tabs in direct DOT label text

## Task and research

Repair treesitter-chunker#476 after accepted treesitter-chunker#477. The existing
DotExporter._escape_label replaces physical TAB with unsupported backslash-t;
actual Graphviz turns that into a literal t. The helper serves node labels,
relationship tooltips and cluster labels. Leave the independently accepted
relationship label assignment alone. Research used actual Python parsing of
tests/fixtures/graph_same_span.py and Graphviz JSON/SVG. Physical TAB remains in
SVG node text; XML attribute normalization changes a tooltip TAB into a space.
Compiled JSON tooltips retain physical TAB. Do not promise byte-exact SVG tabs.

## Owned changes and observable contracts

- chunker/export/dot_exporter.py: remove only the TAB replacement in
  _escape_label. Preserve existing quote, backslash, physical LF and CR handling.
- tests/test_graphml_exporter.py: add actual-parser/actual-Graphviz contracts
  using existing parsed_same_span and real f/g functions. Caller name and note
  properties cover interior, boundary, repeated and tab-only text, literal
  backslash-t, quotes, backslashes, Unicode, physical LF/CR and literal
  backslash-n. Use flat/clustered and string/exported-path variants. Independently
  specify expected compiled tooltip escapes and meaningful SVG caller text;
  SVG tooltip TAB becomes space. Exercise a virtual caller file-path containing
  TAB for node and cluster labels without creating a Windows tab-named file.
  Retain two original parser IDs, one directed CALLS edge, ordinary red/dotted
  style, cluster membership and stable output. Do not assert generated node
  separators are correct: treesitter-chunker#479 covers that separate defect.
- docs/graphml_export.md and CHANGELOG.md: document this bounded tab repair,
  Graphviz JSON/SVG distinction and tested Linux 14.1.2/Windows 14.1.1 versions.
  Narrow to listed valid UTF-8 cases without NUL/entity sequences; renderer
  typography, arbitrary attributes/controls and other versions are uncertified.
  Retain treesitter-chunker#478 entity and treesitter-chunker#479 formatting
  limitations. Reserve Unreleased for 6.0.0; no release or tag.
- This plan and one typed plans/manifest.json row: preserve all 65 existing
  canonical rows. Historical lifecycle reconciliation is treesitter-chunker#361.

## Dependencies and order

1. Private WORKTREE_ROOT checkout starts at accepted main 4db6bb4e. Write and
   register this plan, commit plan-only owned paths, publish supported draft
   before implementation. No tests/builds while planning; standing roadmap
   execution authorization covers the subsequent implementation stage.
2. Add real compiler contracts and reproduce failures on unchanged production.
   Remove the one TAB replacement, then update the scoped documentation.
3. Named mutation escape_dot_label_tabs_as_backslash_t restores accepted base
   source bytes. The new contracts must catch tab-to-t corruption. Record exact
   source digests, actual exit and raw output, then restore exact candidate bytes
   and require passing contracts. One fault family across all cases and hosts.
4. Commit clean candidate. Fresh original six checks, locked refresh/full suite,
   exact-head hosted jobs and native Leno Windows compiler/focus/standing gates.
   Use its authenticated Python 3.12 route and private checksum-verified
   portable Graphviz. Preserve raw child output/default CP1252 locale; only the
   evidence writer uses UTF-8. No machine trust/locale/pin modifications.
5. Four manual tools-enabled CODE seats: subscription Opus 5.5 TUI, Gemini 3.8
   Flash, Astra and Sol. Compact file pointers, heartbeat only, no silence/model
   deadline, maximum three complete substantive rounds. Collect all four and
   original evidence before reconciliation; incomplete delivery is not approval.
   Final supplemental Astra president, strict proof and standalone verbatim
   archive precede authorized exact-head merge, issue closure and owned pruning.
   Serialize original runners and publication. Additional discovered defects get
   separate qualified issues rather than silent additions to this slice.

## Verification commands

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_graphml_exporter.py -k dot_label_tabs -q
- uv run --locked --all-extras pytest tests/test_graphml_exporter.py tests/test_phase12_integration.py tests/test_export_integration_advanced.py -q
- Ruff, Black, committed-baseline mypy; CI smoke and Linux platform core;
  locked refresh and uv run --locked --with toml --all-extras python scripts/run_full_suite.py
- Native Windows exact archive/digests: compiler contracts, correctly named
  source-bound mutation, exact passing restoration, focused modules and
  scripts/run_windows_preflight.py. Compiler absence/skip never qualifies this
  contract. Hosted platform core includes this module; smoke excludes it.

## Acceptance criteria

- [ ] Actual-parser/Graphviz tests prove meaningful node/cluster/tooltip tabs,
  independent literal controls, original directed identities/style/membership,
  repeat stability and string/file output. Narrow compiler command proves this.
- [ ] Named TAB mutation violates those contracts with actual failing exit;
  exact source restoration passes and digests/raw evidence bind the result.
- [ ] Fresh sealed original six/refresh/full, native Windows/standing, exact
  hosted jobs, four complete CODE opinions, supplemental Astra decision and
  standalone archive qualify this bounded repair before merge.

## Limits

No arbitrary DOT attribute completeness, unsupported entity/NUL/surrogate,
cross-renderer layout or cross-version claim. Generated node separators remain
treesitter-chunker#479; entities remain treesitter-chunker#478. GraphML
treesitter-chunker#450, treesitter-chunker#452 and treesitter-chunker#453, cache
treesitter-chunker#358, CR-only source treesitter-chunker#471, lifecycle
treesitter-chunker#361 and native admission are separate. No parser pins,
goldens, type baseline, consumer locks, protected state, broker or checkpoints.
No percentage gate. Manual supplemental CODE is not governed supplier/native
fill/IF or whole-phase acceptance; agent-harness#1271 remains separate.

---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: preserve whitespace in GraphML attributes

## Task

Repair treesitter-chunker#450 independently after accepted treesitter-chunker#480
at base b9be38a3b8159dd24497963314028a1630608b19. This is a bounded follow-up
to EXPORT in specs/phase-plans-v3.md, not whole-phase acceptance. The artifact is
plans/detailed-graphml-pretty-whitespace-450.md in the private owned worktree.
This plan is a proposal; no implementation or planning verification was run.

## Research summary

GraphMLExporter.export_string and GraphMLyEdExporter.export_string use
ElementTree to build and validate XML, then minidom to pretty-print it. The latter
rewrites attribute TAB/LF/CR to literal characters on Python 3.11/3.12; reparsing
normalizes those characters to spaces. Compact ElementTree serialization retains
numeric character references. Supported Python 3.13 has different minidom
behavior, so reproducing and killing the old serializer must use actual 3.11 and
3.12, not infer the result from a 3.13 test. Existing parsed_same_span supplies
real Python chunks, including functions f/g; existing tests cover key declarations,
XML character rejection, yEd fallback and deliberate CR-to-LF text normalization.

## Changes

### chunker/export/graphml_exporter.py (modify)

- GraphMLExporter.export_string: after existing character validation, indent the
  freshly built ElementTree with ET.indent(root, space="  ") when pretty_print is
  true, then serialize that tree directly. Retain an XML declaration on pretty
  output using ET.tostring(..., encoding="unicode", xml_declaration=True); compact
  output stays on its existing declaration-free serialization route. Remove the
  unused minidom import. No additional serialization abstraction is needed.
- Pretty layout and XML declaration spelling can change. Decoded supported
  attributes, graph topology, labels, key declarations and file UTF-8 remain the
  compatibility contract, not minidom's exact formatting. Generated containers
  have element-only content; caller text lives in leaves. ET.indent must not
  remove whitespace-only caller leaf text.

### chunker/export/graphml_yed_exporter.py (modify)

- Apply the same bounded serializer change to the use_yed=True tree, including
  the declaration policy and removal of minidom. Keep use_yed=False delegation,
  namespaces, graphics, styling and existing caller text handling unchanged.

### tests/test_graphml_exporter.py (modify)

- Add real-parsed fixture contracts for plain, yEd and delegated plain routes;
  physical TAB, LF and CR; pretty/compact; and string/file output (36 combinations).
  Choose two distinct caller IDs, caller<separator>parent and caller parent;
  bind them to real f/g chunks and verify both declarations independently by
  decoded ID and exact endpoint pairs. Add CALLS in each direction with ordinary
  distinct properties to catch a collision, overwrite or endpoint substitution.
- Assert repeat stability, node/edge counts, ordinary labels/data and key
  resolution, directed graph declaration and yEd-only graphics on its route.
  Exported bytes decode as UTF-8 to the same serialization; use ordinary file
  paths on every host. No physical whitespace-named Windows file is necessary.
- Exercise graph id and metadata key attribute values containing the same
  separator, preserving decoded values and key references. This covers XML
  attribute values, not arbitrary XML attribute names or GraphML XSD validity.
- Preserve whitespace-only caller leaf text (for example space-TAB-space), with
  explicit expectations independent of the exporter. Keep existing tests'
  established CR-to-LF text normalization; do not promise new text-byte fidelity.
- No mocks of exporters, parsers, XML serializers or the code under test. Parse
  real output with ElementTree and identify expected values from caller inputs.

### docs/graphml_export.md and CHANGELOG.md (modify)

- Replace the Python 3.11/3.12 compact-output workaround with the repaired
  pretty/compact attribute contract and explain pretty formatting can change.
  State decoded attribute whitespace is preserved while existing XML text
  normalization remains. Keep treesitter-chunker#452 name validation and
  treesitter-chunker#453 reader label mapping separate.
- Add the bounded fix to Unreleased, reserved for 6.0.0. No release or tag.

### plans/detailed-graphml-pretty-whitespace-450.md and plans/manifest.json

- Register only the new typed detailed row through the supported manifest API.
  Preserve all 66 accepted predecessor rows. Historic lifecycle reconciliation
  stays treesitter-chunker#361; no admitted ledgers/checkpoints are rewritten.

## Dependencies and order

1. Finish exact-head acceptance, merge and owned pruning of treesitter-chunker#480.
   Start a new private WORKTREE_ROOT branch from fresh accepted origin/main.
   Record inherited disk TMPDIR/tempfile metadata; create unique disposable
   scratch there with tempfile, not literal /tmp (treesitter-chunker#481).
2. Write/register this plan and open a supported draft before implementation.
   Independently panel the plan using compact file pointers and manual local
   tools: Opus 5.5 subscription TUI, Gemini 3.8 Flash, Astra and Sol. Collect all
   four before reconciliation. Maximum three complete substantive rounds;
   heartbeat only, no model/silence deadline. Final supplemental Astra decides
   design acceptance. Do not claim governed supplier/native-fill/IF acceptance.
3. Add tests and reproduce the pretty-only collisions on unchanged production
   under actual Python 3.11 and 3.12. Compact output must pass. Then make only
   the scoped serializer/doc changes and run the contracts on both interpreters.
4. Mutations reintroduce_minidom_plain_pretty and reintroduce_minidom_yed_pretty
   independently restore the accepted serializer at the named site. The first
   must fail plain and delegated pretty contracts; the second must fail yEd
   pretty contracts. Each must fail under both 3.11 and 3.12; compact controls
   remain green. Restore exact candidate bytes after each and require passing
   restoration. These are two source sites for one serializer fault family,
   not independent faults per parametrization or host. Bind interpreter,
   exporter/test/fixture bytes, actual exit, raw logs and restored digests.
5. Commit clean candidate. Run fresh runner-sealed original six checks, locked
   dependency refresh/full suite, native Windows compiler-independent contract
   and standing preflight, and required exact-head hosted CI. Use actual Windows
   default encoding; only evidence writes explicitly UTF-8. No pin, baseline,
   golden, machine trust or locale edits.
6. Four manual tools-enabled CODE seats review the exact candidate with the
   same complete-round policy. Collect all four and original before reconciling.
   Final supplemental Astra, strict proof and standalone raw archive precede
   authorized exact-head merge, comment/closure and safe owned pruning. File
   newly discovered defects separately; do not expand this repair silently.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_graphml_exporter.py -k graphml_attribute_whitespace -q
- The same narrow command on checksum/source-bound private locked environments
  running actual Python 3.11 and 3.12, before/after both named mutations. Do not
  modify the main environment to switch interpreters. New environments and
  pytest --basetemp use unique inherited private disk scratch with final cleanup.
- uv run --locked --all-extras pytest tests/test_graphml_exporter.py tests/test_phase12_integration.py tests/test_export_integration_advanced.py -q
- Repository Ruff, Black, committed-baseline mypy, CI smoke and Linux platform
  core commands from CONTRIBUTING.md, then locked refresh and automation suite.
- Native Windows exact-head narrow/focused modules and
  scripts/run_windows_preflight.py; exact Linux/macOS/Windows hosted checks.
- Strict MkDocs into a unique private temporary output. Record the actual
  outcomes and retained evidence, then remove only owned disposable scratch.

## Acceptance criteria

- [ ] Real-parser/XML contracts retain distinct caller ID declarations and
  directed endpoint pairs through pretty/compact string/file plain/yEd/delegated
  output, preserve graph/key attribute values and caller whitespace-only leaf
  text, and retain ordinary declarations/data/styles. Proven by the named narrow
  test under actual Python 3.11 and 3.12 and current locked environment.
- [ ] Both named source-site mutations fail their expected pretty routes on
  actual 3.11 and 3.12; compact controls pass; exact restorations pass. Actual
  exits/raw logs/interpreter and source/test/fixture hashes establish one fault
  family without inflated counts.
- [ ] Fresh original six/refresh/full, native Windows/standing, exact hosted
  checks, four complete CODE opinions, final supplemental Astra and verified
  standalone archive qualify this unchanged bounded candidate before merge.

## Limits

No blanket arbitrary-ID/XSD conformance, XML name validation, reader-specific
label mapping, text CR byte-fidelity, graphical layout, native admission or
whole-phase acceptance. No percentage gate, parser pins, goldens, type baseline,
consumer locks, protected state, manual broker/checkpoint edits or release.
Agent-harness#1271 governs formal operational-evidence amendments separately.

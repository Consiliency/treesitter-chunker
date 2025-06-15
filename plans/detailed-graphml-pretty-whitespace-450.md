---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: preserve whitespace in GraphML attributes

## Task

Repair treesitter-chunker#450 independently after accepted treesitter-chunker#480
and treesitter-chunker#486, at base
db7a9401c4d2e924d15281e9cad2dedb75f5d622. This is a bounded follow-up
to EXPORT in specs/phase-plans-v3.md, not whole-phase acceptance. The artifact is
plans/detailed-graphml-pretty-whitespace-450.md in the private owned worktree.
This plan is a proposal; no implementation or acceptance verification was run.
R1 collected all four manual opinions before reconciliation. The revised proposal
addresses declaration compatibility, Windows text transport, mutation criteria
and focused module selection; R2 reviews this exact revision independently.
Read-only source inspection and a Python 3.12.14 transport reproduction informed
the revision; neither establishes native Windows acceptance.

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
  true, then serialize that tree directly. Before indenting, normalize each
  non-None element.text with replace("\r\n", "\n").replace("\r", "\n") in
  the fresh tree. This retains minidom's existing XML text normalization before
  Windows text-mode writing and avoids introducing doubled decoded CRLF breaks.
  Do not change node/edge properties, caller inputs or compact serialization.
  Prefix the literal '<?xml version="1.0" ?>\n' and append a trailing '\n' to
  ET.tostring(root, encoding="unicode"). Retain the existing declaration with
  no encoding label: an encoding-labelled unicode declaration can break readers
  such as lxml. Compact output retains its declaration-free existing route.
  Remove the unused minidom import; no new serialization abstraction is needed.
- Pretty indentation and empty-element layout can change. Decoded supported
  attributes, graph topology, labels, key declarations and file UTF-8 remain the
  compatibility contract, not minidom's exact formatting. Generated containers
  have element-only content; caller text lives in leaves. ET.indent must not
  remove whitespace-only caller leaf text.

### chunker/export/graphml_yed_exporter.py (modify)

- Apply the same bounded serializer change to the use_yed=True tree, including
  pretty-only text normalization, literal declaration and removal of minidom.
  Keep use_yed=False delegation, namespaces, graphics and styling unchanged.
  File writing remains inherited and unchanged; treesitter-chunker#488 tracks
  the existing compact Windows CRLF-text defect separately.

### tests/test_graphml_exporter.py (modify)

- Add real-parsed fixture contracts for plain, yEd and delegated plain routes;
  physical TAB, LF and CR; pretty/compact; and string/file output (36 combinations).
  Choose two distinct caller IDs, caller<separator>parent and caller parent;
  bind them to real f/g chunks and verify both declarations independently by
  decoded ID and exact endpoint pairs. Add CALLS in each direction with ordinary
  distinct properties to catch a collision, overwrite or endpoint substitution.
- Assert repeat stability, node/edge counts, ordinary labels/data and key
  resolution, directed graph declaration and yEd-only graphics on its route.
  Include non-ASCII caller data and parse actual UTF-8 file bytes. File transport
  retains native newline translation. For these attribute fixtures (no CR/CRLF
  leaf text), compare read_bytes().replace(b"\r\n", b"\n") with the string's
  UTF-8 encoding; assert decoded attribute/data values separately without
  normalizing them. Use ordinary file paths; no whitespace-named Windows file.
  Assert pretty's exact first declaration line and trailing LF on strings,
  and absence of a declaration on compact strings and files.
- Exercise graph id and metadata key attribute values containing the same
  separator, preserving decoded values and key references. This covers XML
  attribute values, not arbitrary XML attribute names or GraphML XSD validity.
- Name the ID matrix test_graphml_attribute_whitespace_ids and graph/key matrix
  test_graphml_attribute_whitespace_graph_keys: each collects 36 cases, with
  the same three routes, separators, formatting modes and string/file targets.
- Name test_graphml_text_normalization: four caller leaves (space-TAB-space,
  A\rB, A\nB, A\r\nB), three routes, pretty/compact, string/file = 48 cases.
  Assert caller node/edge data plus yEd labels where applicable. Pretty strings
  contain no physical CR and reparse to CRLF->LF then CR->LF expectations;
  pretty files reparse to the same expected values on every host. Whitespace-only
  leaf content remains exact. For compact strings retain ordinary XML newline
  normalization. Compact Windows files explicitly retain the existing extra LF
  for CRLF leaves (treesitter-chunker#488); do not pretend this is a new guarantee
  or silently repair it here. Never normalize decoded assertion values.
  These text cases are controls for the minidom mutations, but discriminate
  omission of the planned pretty-only text normalization.
- No mocks of exporters, parsers, XML serializers or the code under test. Parse
  real output with ElementTree and identify expected values from caller inputs.

### docs/graphml_export.md and CHANGELOG.md (modify)

- Replace the Python 3.11/3.12 compact-output workaround with the repaired
  pretty/compact attribute contract and explain pretty formatting can change.
  Scope claims to the two direct modules and non-validating XML attribute
  parsing; whitespace IDs are not an XSD NMTOKEN conformance claim. Preserve
  the declaration without an encoding label and explain pretty text newline
  normalization. Record compact Windows text transport (treesitter-chunker#488)
  and the separate package exporter's serializer (treesitter-chunker#489) as
  existing limits. Keep treesitter-chunker#452 name validation and
  treesitter-chunker#453 reader label mapping separate.
- Add the bounded fix to Unreleased, reserved for 6.0.0. No release or tag.

### plans/detailed-graphml-pretty-whitespace-450.md and plans/manifest.json

- Register only the new typed detailed row through the supported manifest API.
  Preserve all 66 accepted predecessor rows. Historic lifecycle reconciliation
  stays treesitter-chunker#361; no admitted ledgers/checkpoints are rewritten.

## Dependencies and order

1. treesitter-chunker#480 and treesitter-chunker#486 are merged. The owned plan
   branch incorporates accepted origin/main without rewriting historical review
   commits; its candidate diff remains only the plan and manifest addition.
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
   independently restore BOTH the minidom import and full accepted pretty body
   at the named site. Under both actual 3.11/3.12, each 36-case attribute matrix
   must have exactly 12 plain/delegated pretty semantic assertion failures for
   the plain mutation, or exactly six yEd pretty failures for the yEd mutation.
   The other routes, all compact cases and all 48 text controls must pass.
   A NameError, collection/import error, infrastructure failure or arbitrary
   nonzero exit is not a mutation kill. Record exact failing node IDs/assertions.
   Also run omit_pretty_text_normalization_plain and
   omit_pretty_text_normalization_yed independently: each removes only its
   pretty normalization loop. CR/CRLF pretty string checks must fail the
   physical-CR assertion for the affected routes on both interpreters;
   native Windows pretty CRLF file decoded-text checks must also fail there.
   Unaffected routes and compact controls remain green. These latter two sites
   establish one additional normalization fault family, not per-host faults.
   Restore exact candidate bytes after each and require passing
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
- uv run --locked --all-extras pytest tests/test_graphml_exporter.py -k 'graphml_attribute_whitespace or graphml_text_normalization' -q
- Collect exactly 120 new cases (36 ID + 36 graph/key + 48 text). Record collected
  node IDs and exact semantic failure sets for each mutation, not just an exit.
- The same narrow command on checksum/source-bound private locked environments
  running actual Python 3.11 and 3.12, before/after both named mutations. Do not
  modify the main environment to switch interpreters. New environments and
  pytest --basetemp use unique inherited private disk scratch with final cleanup.
  For each version use a private owned environment with
  UV_PROJECT_ENVIRONMENT=<owned-version-venv> uv sync --locked --all-extras --python <3.11-or-3.12>;
  run its bin/python -m pytest from this checkout with PYTHONPATH set to it.
  Record sys.version and executable, uv.lock/source/test/fixture digests and exit.
- uv run --locked --all-extras pytest tests/test_graphml_exporter.py tests/test_graphml_yed_export_contract.py tests/test_phase12_integration.py -q
- Repository Ruff, Black, committed-baseline mypy, CI smoke and Linux platform
  core commands from CONTRIBUTING.md, then locked refresh and automation suite.
- Native Windows exact-head 120-case narrow test, both direct GraphML modules'
  focused tests including tests/test_graphml_yed_export_contract.py, and
  scripts/run_windows_preflight.py; exact Linux/macOS/Windows hosted checks.
  The standing preflight alone contains no GraphML tests and cannot establish
  this repair. Bind actual Windows interpreter, newline transport and raw logs.
- Strict MkDocs into a unique private temporary output. Record the actual
  outcomes and retained evidence, then remove only owned disposable scratch.

## Acceptance criteria

- [ ] Real-parser/XML contracts retain distinct caller ID declarations and
  directed endpoint pairs through pretty/compact string/file plain/yEd/delegated
  output, preserve graph/key attribute values and caller whitespace-only leaf
  text, and retain ordinary declarations/data/styles. Proven by the named narrow
  test under actual Python 3.11 and 3.12 and current locked environment.
- [ ] All four named source-site mutations fail their expected pretty contracts on
  actual 3.11 and 3.12; compact controls pass; exact restorations pass. Actual
  exits/raw logs/interpreter and source/test/fixture hashes establish one fault
  families without inflated counts. There are two serializer sites and two
  normalization sites; neither parametrizations nor hosts add fault families.
- [ ] Fresh original six/refresh/full, native Windows/standing, exact hosted
  checks, four complete CODE opinions, final supplemental Astra and verified
  standalone archive qualify this unchanged bounded candidate before merge.

## Limits

No blanket arbitrary-ID/XSD conformance, XML name validation, reader-specific
label mapping, text CR byte-fidelity, graphical layout, native admission or
whole-phase acceptance. No percentage gate, parser pins, goldens, type baseline,
consumer locks, protected state, manual broker/checkpoint edits or release.
The package-level chunker.export.GraphMLExporter in chunker/export/formats/graph.py
still uses minidom (treesitter-chunker#489). Compact Windows CRLF leaf transport
remains treesitter-chunker#488. Neither defect is silently repaired by this slice.
Agent-harness#1271 governs formal operational-evidence amendments separately.

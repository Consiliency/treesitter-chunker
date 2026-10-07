---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: Reject XML-invalid GraphML characters before serialization

## Task and research

Resolve treesitter-chunker#168 as the second independent EXPORT slice after
treesitter-chunker#443 is accepted. ElementTree can serialize forbidden XML 1.0
characters from caller metadata without rejecting them. Compact export returns
an unusable document; pretty export reparses it and fails with a parser error.
Plain GraphML and yEd construct separate trees before their serialization calls;
yEd's use_yed=False path delegates to a plain exporter.

Use the existing GraphMLExporter and its yEd subclass. Both file methods obtain
the exported string before opening/writing the output path. Real Python service
fixtures and the existing GraphML/yEd contract modules provide the tests. This
slice deliberately rejects invalid characters rather than deleting user data.
The real-fixture reproduction in `/tmp/chunker-168-key-registry-reproduction.json`
found that an invalid metadata name remains cached after the property is removed.
This is separately filed as treesitter-chunker#451 and explicitly included in
the rejection/recovery cluster before source edits. Key uniqueness and pretty
attribute whitespace remain treesitter-chunker#169 and treesitter-chunker#450.

## Observable contract

1. Before serializing any constructed GraphML tree, validate every element text,
   tail and attribute value against XML 1.0's allowed character ranges: tab,
   newline, carriage return; U+0020–D7FF, E000–FFFD and 10000–10FFFF. Reject other
   C0 characters, unpaired surrogates, U+FFFE and U+FFFF with ValueError.
2. The error names the invalid Unicode code point and the XML location (tag plus
   text/tail or attribute name). Do not include the caller's full value in the
   diagnostic. Both compact and pretty export fail deliberately before producing
   an unusable string. yEd enabled and disabled use the same contract. Graph
   attribute names are outside this value-character rule (treesitter-chunker#452);
   metadata property names are validated as key attribute values. The package-level
   structured exporter is separate from these two direct modules.
3. Legal Unicode, ordinary XML metacharacters and allowed whitespace still yield
   parseable XML. Retain field values under normal XML whitespace normalization,
   node/edge identity and relationships, and yEd graphics. No stripping,
   replacement character or blanket ASCII policy.
4. Invalid file export leaves an existing output unchanged and creates no new
   output file. Existing graph collections remain usable after a failed export;
   removing the caller's invalid property allows an actual subsequent export.
   Check both node/edge values and names. Newly supplied invalid names must be
   rejected before registration so they do not poison cached declarations.
   Retain existing valid/custom schema entries and shared registry dictionaries.

## Changes

- `chunker/export/graphml_exporter.py`: add one shared XML character validator
  over the constructed ElementTree and call it before both serialization paths.
  Use standard-library character checks; no dependency, schema or identity change.
  Reuse that validator on each new node/edge key element before caching its name
  in _register_attributes, explicitly resolving treesitter-chunker#451.
- `chunker/export/graphml_yed_exporter.py`: invoke the inherited validation for
  its actual yEd tree before serialization. Retain plain delegation.
- `tests/test_graphml_exporter.py`: use actual chunk_file parsing of the checked-in
  Python service fixture. Attach caller metadata/edge properties, graph attributes,
  metadata property names and caller IDs containing representative forbidden
  characters; require the same actionable ValueError in plain/pretty modes.
  Test legal range boundaries, Unicode/metacharacter round-trip and allowed
  whitespace with ElementTree parsing, deriving IDs from actual chunks. Exercise
  failed new/existing file output and recovery on the same exporter instance.
  Assert recovery after invalid node/edge names are removed, and that existing
  custom schemas and shared dictionary objects remain intact.
- `tests/test_graphml_yed_export_contract.py`: real parsed chunks exercise the
  same invalid/valid behavior with use_yed=True/False and both pretty settings,
  preserving existing direction/graphics checks. No fake parser/exporter objects.
- `docs/graphml_export.md`: distinguish escaping permitted XML characters from
  deliberate rejection of forbidden characters, document error/file behavior.
  `CHANGELOG.md`, this plan and the typed `plans/manifest.json` row are owned.

The graph tests are selected on every platform by accepted treesitter-chunker#443;
preserve that selection and all other canonical rows. Key/label uniqueness remains
separately treesitter-chunker#169. No XSD-validation, serializer-key, DOT, parsing,
identity algorithm, native, Boundary IR golden or consumer-lock repair here.

## Order

Commit the plan before implementation. Wait for accepted treesitter-chunker#443,
integrate its main with all canonical rows intact, then mark only this typed row
executing. Add regressions first and preserve unchanged-source failures. Apply the
shared validator and narrow yEd call. Run actual `skip_graphml_xml_validation` and
`skip_yed_xml_validation` mutations independently, removing only each production
validation call: the corresponding plain/yEd invalid-input cases must fail, while
valid controls remain. Restore exact source bytes after each mutation; the full
focused command passes and final source/test hashes agree before/after.
Also run `register_invalid_graphml_key`: remove only the two new registration
checks, retaining final tree checks. Initial rejection still occurs, but the
same-instance name-removal recovery assertions must fail. Restore exact source
bytes and rerun the entire focused command.

File additional defects separately before considering their repair. Collect all
four substantive code reviews before candidate revisions, maximum three rounds.
Opus5.5 uses the manual tool-enabled TUI adapter; Gemini3.8Flash, Astra and Sol
use compact file pointers and actual final-response capture, heartbeat-only
monitoring and no model/silence deadline. Failed delivery is preserved and cannot
count as approval. The requested manual Astra chair checks completed evidence.

## Verification

- `uv sync --locked --all-extras`
- `uv run --locked --all-extras pytest tests/test_graphml_exporter.py tests/test_graphml_yed_export_contract.py tests/test_phase12_integration.py -q`
- `uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site`
- `uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/`
- `uv run --locked --all-extras python scripts/mypy_gate.py`
- `uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py`
- `uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux`
- `uv run --locked --with toml --all-extras python scripts/run_full_suite.py`

Supported draft publication precedes the serialized original six checks, locked
refresh and full tests/spec_tests. Actual matching-source Windows focused/standing,
every exact-head hosted platform job, four completed agreements and final manual
Astra ruling remain independent acceptance requirements. Archive raw evidence
before exact-head merge/issue closure and pruning clean merged worktrees.

## Acceptance criteria

- [ ] Real parsed fixture chunks prove deliberate actionable rejection across
  plain/yEd, pretty/compact/delegated output for forbidden text and attribute values;
  all three named actual mutations fail and exact restorations pass with bound hashes.
- [ ] Actual exported legal Unicode/XML characters parse with retained IDs,
  endpoints and graphics. Rejected file export preserves existing output, creates
  no new file, and the same exporter recovers after invalid caller data is removed.
- [ ] Original six, locked refresh/full, matching-source Windows, exact hosted
  jobs, four bounded code reviewers and Astra chair accept only character handling.
  treesitter-chunker#169 remains open; no whole EXPORT/IF, XSD, percentage, pin,
  consumer-lock, admitted ledger/checkpoint or automatic release claim.

## Execution evidence pending acceptance

Accepted treesitter-chunker#443 is integrated. Real service-fixture regressions
against unchanged production source fail 317 tests and pass 57 controls; the
implemented focused command passes 374. The three actual named mutations fail
136 (plain final validation), 70 (yEd final validation), and 12 (invalid-name
registration/recovery) respectively. Every exact restoration passes all 374;
the source, both test modules and actual fixture hashes are bound in
`/tmp/chunker-168-mutation-bindings.json`. These are local observations only:
original full verification, Windows, hosted jobs, four code reviews and the
manual Astra president remain mandatory before merge and issue closure.

All four CODE R1 seats completed at 258a1dea. Original six/locked refresh/full
4351 passed/four existing skips, actual Windows 374 focused/204 standing/one
existing skip and all exact-head hosted jobs passed. Three seats agreed; Opus
required the guide/changelog to qualify text/tail/attribute-value validation and
name the direct modules. The separately reproduced graph attribute-name defect
is filed as treesitter-chunker#452. R2 changes only those docs and this record;
all production/test/fixture bytes remain unchanged. Opus's raw manifest count
59 to 60 is corrected by actual JSON comparison: 51 canonical rows are retained
exactly, with this one executing row added for 52. R1 raw evidence and its failed
premature freeze attempt remain archived as unaccepted; no R1 approval is inferred.
Four bounded R2 confirmations and fresh exact-head gates are required.

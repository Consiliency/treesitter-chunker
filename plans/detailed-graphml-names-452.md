---
automation:
  suite_command: "uv run --locked --with toml --all-extras python scripts/run_full_suite.py"
---

# Detailed plan: reject malformed GraphML graph attribute names

## Task

Repair treesitter-chunker#452 on fresh accepted main
5605121bc9feae2572d3c1daa97387e4b2fe4ae9. This independently landable EXPORT
repair covers the two direct GraphML modules and plain delegation. It does not
qualify a Harness route, native supplier, interface freeze or whole phase.

## Research summary

Both exporters construct a fresh ElementTree, then check text/tail/attribute
values before serializing. Caller graph_attrs keys become raw XML attribute
names, which ElementTree does not validate. The inherited file export obtains
the string before opening the destination. Existing parsed_xml_graph supplies
real service-fixture chunks and an actual relationship for all three routes.
The accepted pretty serializer preserves physical attribute TAB/LF/CR; never
substitute reparsed values for the original constructed tree.

## Supported contract

Preserve unqualified Unicode names, XML-qualified names with a bound prefix,
caller namespace declarations and ElementTree expanded `{URI}local` names when
the resulting attribute-only XML probe is accepted by the supported Python
ElementTree parser. XML names and namespaces are defined by
https://www.w3.org/TR/xml/#NT-Name and https://www.w3.org/TR/xml-names/.
Parser-supported names are the contract; do not claim every Fifth Edition
Unicode name works on every Expat version. Default namespace overrides retain
their existing effect; GraphML XSD conformance and custom namespace semantics
are caller responsibilities.

Check lexical NCName components with the XML 1.0 Fifth Edition ranges (without
colon), accepting either one component, exactly prefix:local, or a nonempty
{URI}local expanded name. Its URI must contain only XML 1.0 characters, be
nonempty and contain no braces. Reuse the existing character validator on that
URI as an attribute value before probing; identify graph attribute namespaces
in its diagnostic. Require str keys explicitly; non-string keys raise deliberate
ValueError (exact type), including None, bytes and ElementTree.QName keys.
QName rejection is a deliberate narrowing to the declared string-key API.
Validate every name including
namespace declaration prefixes. Empty names, whitespace, delimiters/injection
text, bad initial digits, controls, surrogates and malformed expanded/qualified
forms raise ValueError.
Then construct a small fresh probe root carrying the actual root attributes
and a shallow graph carrying its attribute names. Give each non-declaration
graph attribute a unique string sentinel based on its insertion index; retain
the real string values of xmlns and xmlns:* declarations. This binds each source
attribute independently of equal caller values. Serialize and parse that probe.
This catches unbound prefixes, illegal reserved namespace bindings, duplicate
expanded attributes and names unsupported by the installed XML parser. No
external XML, DTD or entity input is accepted; lexical checks prevent markup
injection through names and ElementTree escapes values.

After parsing, use the probe root's first child as its graph, independent of its
default namespace. Require decoded_graph.get(key) == sentinel_by_key[key] for
every original expanded {URI}local key. Mere key membership is insufficient:
caller ns0/ns1 declarations can swap two expanded names, or a qualified literal
attribute can mask an expanded key rebound to another URI. Unique sentinels
reject each case even when all actual caller values are equal. Reject with
ValueError identifying graph attribute namespace identity. Check only caller
expanded keys; do not compare all parsed attributes or counts, which would make
the separate lexical injection mutation ineffective.

Expanded names in ElementTree's globally registered xsi namespace can generate
duplicate xmlns:xsi declarations because the root also carries a literal
declaration. Those configurations are deliberately rejected when the probe
fails; equivalent xsi:local names remain supported. Preserve the serializer's
existing global namespace registry; do not rewrite its state or caller names.
Literal names using auto-generated ns<digits> prefixes retain their existing
dependence on the generated bindings; callers should use their own declared
prefixes. Namespace declaration overrides, including xmlns:y on a yEd graph,
retain their existing effect on descendant names and are caller responsibility.

Diagnostics identify graph attribute-name/namespace validation and the reason;
lexical failures identify the offending name with repr. Parser failures use
ParseError's reason with its synthetic position suffix removed (split the
standard ': line ' suffix), without dumping attribute values or XML; do not report
positions from the discarded probe as output positions. Rejected
string export produces no result; file export preserves existing bytes and
creates no absent file. Removing/correcting the offending entry permits export
again from the same exporter. Caller dictionaries and values remain unchanged.

## Changes

- chunker/export/graphml_exporter.py: add one shared graph attribute-name
  validator; invoke it after existing character validation and before output
  serialization. Use standard-library re and ElementTree only. The probe is
  discarded; existing tree serialization, declaration, whitespace, IDs, keys
  and native file transport remain unchanged.
- chunker/export/graphml_yed_exporter.py: invoke the inherited validator for
  the actual yEd root/graph at the same boundary. Keep delegation unchanged.
- tests/test_graphml_exporter.py: reuse parsed_xml_graph for pretty/compact,
  plain/yEd/delegated string and file cases. Assert actionable ValueError,
  byte-exact sentinel preservation, no absent output, unchanged caller state,
  correction/retry and actual node/edge identities. Positive controls retain
  ordinary/Unicode names, combining characters after a legal first character,
  bound xml/xsi/y names on applicable routes, custom declarations in either
  insertion order and expanded names; assert decoded values without whitespace
  normalization. Negative namespace cases include unbound/multiple/empty
  prefix components, reserved binding and duplicate expanded attributes.
  Include graph xmlns:ns0 + {urn:A}foo silent rebinding, two-URI ns0/ns1 swaps,
  and literal-prefix masking with different AND equal caller values. Include
  URI braces/forbidden
  characters including lone surrogates, and non-str keys. Match a graph name or
  namespace diagnostic so UnicodeEncodeError cannot accidentally pass as
  ValueError. y:foo is accepted only with an actual yEd root binding; reject it
  on plain/delegated routes. Assert default namespace overrides/undeclaration
  without requiring the standard GraphML namespace. Positive Unicode examples
  use known supported Greek, accented Latin, Chinese and trailing combining
  marks. Add an expanded xsi namespace probe-rejection fixture. For a
  Fifth-Edition-only name, require either deliberate ValueError or
  output that parses and retains its name; never pin a particular Expat table.
- docs/graphml_export.md and CHANGELOG.md: document the supported names,
  deliberate error/file preservation and migration from malformed output.
  Replace both Unreleased CHANGELOG.md name caveats and the Special Character
  Handling guide caveat; document expanded-xsi rejection, expanded-name identity
  rejection and declaration overrides. Retain separate reader,
  compact Windows CRLF and package-level limitations.
- This plan and only its appended plans/manifest.json row are owned.

No parser pins, goldens, type baseline, source version, consumer locks, prior
rows, held branches, broker state, ledgers or checkpoints change. No release.

## Dependencies & order

Reproduce accepted-source malformed-name/file overwrite first. Collect all four
complete tools-enabled PLAN opinions before reconciliation; maximum three
complete rounds. Independent Astra president approves final design before
implementation. Register this plan through supported typed manifest APIs.
Add regressions before source edits and retain unchanged-source failures.
Implement the two calls/shared validator, then batch verification.

Named mutations skip_plain_graph_attribute_names and
skip_yed_graph_attribute_names independently remove the corresponding actual
production call. Corresponding invalid name/namespace cases must fail because
the required deliberate error is absent; positive controls must still pass.
Remove only lexical checks in allow_graph_attribute_name_injection: a crafted
syntactically valid injected attribute name must be rejected by the candidate
and escape rejection under the mutation. Use a="1" b and
x="1"></graph><graph y as the two injection keys, neither duplicating generated
id/edgedefault attributes. Add skip_graph_attribute_namespace_probe (skip only
the probe and its identity verification) and skip_expanded_graph_attribute_identity
(retain lexical checks and parsing but skip expanded-key identity verification).
The former must fail the unbound/reserved/duplicate/expanded-xsi namespace
negatives and all three expanded-rebinding families, while lexical negatives
and positive controls pass. The latter must fail only all three
expanded-rebinding families, with namespace lexical/parse negatives and positive
controls passing. Add presence_only_expanded_graph_attribute_identity: replace
the sentinel comparison with membership only. Swap and masking fixtures must
fail, including equal caller values; the simple single-collision negative,
other negatives and positive controls pass. Retain actual failure node IDs and
assertion text; require byte-exact source restoration and green rerun after
each. A parser/setup exception is not a semantic mutation kill. For production
call omissions, run the ordinary malformed string-name/namespace negatives,
injection and positive controls: plain omission fails plain and delegated
negatives only, yEd omission fails yEd negatives only; the other routes and
positives stay green. Non-string/forbidden-URI, malformed expanded-brace and
parser-version-dependent diagnostic tests are verified on the intact candidate
but excluded from those call-omission kill sets, so an
incidental serializer exception is not accepted as a kill. Collect exact node
IDs for every mutation selection before running it.

Use manual subscription Opus 5.5 native TUI, Gemini 3.8 Flash plan sandbox,
Astra and Sol read-only with short file pointers. Each seat uses a fresh clean
exact-head checkout. Peers' opinions are excluded until all four complete.
Heartbeat only: no model/silence deadlines. Final CODE quartet has at most
three complete rounds; independent Astra president audits completed evidence.
Supported publication supplies the entire declared diff scope and actual
runner verification artifact. No direct push or broker/authority repair.

## Verification

- uv sync --locked --all-extras
- uv run --locked --all-extras pytest tests/test_graphml_exporter.py -k graph_attribute_names -q
- The six actual named mutation runs above and exact-byte green restorations.
- uv run --locked --all-extras pytest tests/test_graphml_exporter.py tests/test_graphml_yed_export_contract.py tests/test_phase12_integration.py -q
- uv run --locked --all-extras ruff check chunker/ cli/ tests/ --exclude archive --exclude logs --exclude site
- uv run --locked --all-extras black --check chunker/ cli/ tests/ scripts/
- uv run --locked --all-extras python scripts/mypy_gate.py
- uv run --locked --with toml --all-extras python scripts/run_ci_smoke.py
- uv run --locked --with toml --all-extras python scripts/run_platform_core.py --platform linux
- Runner-owned locked refresh and automation.suite_command full tests/spec_tests,
  via phase_loop_runtime.verification_evidence.run_verification, timeout_s=None.
- Strict MkDocs to unique temporary disk output with required docs extras.
- Native Windows private exact-head snapshot: narrow new cases, same three
  focused modules and scripts/run_windows_preflight.py. Preserve actual default
  encoding/newline environment and bind interpreter/source/test/fixture hashes,
  collected node IDs and pyexpat.EXPAT_VERSION on Linux and Windows.
- Fresh REST check-runs must name the exact published candidate head; all hosted
  Linux/macOS/Windows jobs pass before normal match-head merge.

Private evidence is read/write-owned under
/home/viperjuice/workspace/evidence/treesitter-chunker/graphml-names-452/**
and its canonical /mnt/workspace/users/viperjuice/evidence alias. Only new
paths are writable; retained historical handoff and GraphML evidence are
read-only context. New repo .dev-skills/handoffs/** and .dev-skills/verification/**
are run-owned via skill_paths and verification APIs. Operational evidence names
actual artifacts and source bindings; manual proof never creates a formal
Harness qualification or fabricated runner seal.

## Acceptance criteria

- [ ] New real-fixture tests prove deliberate malformed-name/namespace rejection
  across six route/format combinations, preserve existing/absent files and allow
  same-instance corrected export; the narrow command and named mutations prove it.
- [ ] Positive name/namespace controls retain exact decoded values, IDs and
  endpoints in strings/files; existing whitespace/character/key tests still pass
  in the focused command. Caller data is unchanged.
- [ ] Original repository gates, sealed refresh/full, strict docs, native Windows
  and exact-head hosted jobs pass; four complete CODE opinions, independent
  Astra president and verified standalone archive precede authorized merge.

## Closeout

Use supported lifecycle/reflection/handoff APIs; preserve canonical reviewed
bytes at exhausted rounds and record deferred lifecycle reconciliation honestly.
Comment then close treesitter-chunker#452 after accepted exact-head merge.
Prune only clean owned checkouts proved merged after verified evidence archive.

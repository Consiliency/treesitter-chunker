# GraphML Export Documentation

## Overview

The GraphML exporter converts code chunks and their relationships into GraphML format, a standard XML-based format for representing graphs. This enables visualization and analysis in tools like yEd, Gephi, Cytoscape, and other graph visualization software.

## Features

### Core Features
- **GraphML XML output** - Generates XML documents with GraphML elements; schema validation is separate
- **Full metadata support** - Exports all chunk properties as node/edge attributes
- **Relationship preservation** - Maintains all code relationships (calls, imports, contains)
- **XML safety** - Properly escapes special characters in code content
- **UTF-8 support** - Handles international characters correctly

### Visualization Features
- **Customizable node colors** - Map chunk types to specific colors
- **Customizable node shapes** - Map chunk types to shapes (rectangle, ellipse, etc.)
- **Edge styling** - Color relationships by type
- **Automatic attribute discovery** - Dynamically creates GraphML keys for all properties

### Extended Features (yEd Support)
- **yEd-specific extensions** - Enhanced visualization in yEd graph editor
- **Advanced node styling** - Gradients, borders, and text formatting
- **Edge routing hints** - Better automatic layout support

## Usage

### Basic Usage

```python
from chunker.export.graphml_exporter import GraphMLExporter
from chunker.types import CodeChunk

# Create exporter
exporter = GraphMLExporter()

# Add chunks
chunks = [chunk1, chunk2, chunk3]  # Your CodeChunk objects
exporter.add_chunks(chunks)

# Add relationships
exporter.add_relationship(chunk1, chunk2, "CALLS", {"line": 42})

# Export to file
from pathlib import Path
exporter.export(Path("output.graphml"))
```

### With Visualization Hints

```python
# Add visualization hints for better rendering
exporter.add_visualization_hints(
    node_colors={
        "function": "#4287f5",
        "class": "#42f554",
        "method": "#f5a442"
    },
    edge_colors={
        "CALLS": "#ff0000",
        "IMPORTS": "#0000ff",
        "CONTAINS": "#00ff00"
    },
    node_shapes={
        "function": "ellipse",
        "class": "rectangle",
        "method": "roundrectangle"
    }
)

# Export with pretty printing
graphml_str = exporter.export_string(pretty_print=True)
```

### Automatic Relationship Extraction

```python
# Automatically extract relationships from chunk metadata
exporter.extract_relationships(chunks)
# This will create:
# - CONTAINS edges for parent-child relationships
# - IMPORTS edges for import dependencies
# - CALLS edges for function calls
```

## GraphML Structure

### Generated Keys

The exporter automatically generates GraphML key definitions for all unique attributes found in nodes and edges:

```xml
<key id="node_label" for="node" attr.name="label" attr.type="string"/>
<key id="edge_label" for="edge" attr.name="label" attr.type="string"/>
<key id="n_file_path" for="node" attr.name="file_path" attr.type="string"/>
<key id="n_start_line" for="node" attr.name="start_line" attr.type="int"/>
<key id="n_chunk_type" for="node" attr.name="chunk_type" attr.type="string"/>
<!-- Additional keys for all metadata properties -->
```

### Node Structure

Each code chunk becomes a node with:

- Occurrence ID from `node_id`, then `chunk_id`, then the existing `generate_id()` fallback
- Label showing the chunk type
- All properties from the chunk metadata

```xml
<node id="11ab83ccfc590ede648273b0f793478287d72165">
  <data key="node_label">function</data>
  <data key="n_file_path">src/main.py</data>
  <data key="n_start_line">1</data>
  <data key="n_end_line">10</data>
  <data key="n_chunk_type">function</data>
  <data key="n_name">main</data>
  <!-- Additional metadata -->
</node>
```

### Edge Structure

Relationships become directed edges with:
- Source and target node IDs
- Relationship type as label
- Additional properties from relationship metadata

```xml
<edge id="e0" source="11ab83ccfc590ede648273b0f793478287d72165" target="de01d945ef49728dd8a6e30c7455dc5cc246c22f">
  <data key="edge_label">CALLS</data>
  <data key="e_line">3</data>
</edge>
```

### Structural label key migration for 6.0.0

The two direct GraphML modules use `node_label` for a chunk's structural type
and `edge_label` for a relationship type. Caller metadata keeps `n_<name>` and
`e_<name>` keys. In particular, caller metadata named `label` uses `n_label` or
`e_label`; its original name, type and value remain separate from the structural
label. Names such as `node_label`, `edge_label` and `metadata_label` are ordinary
metadata and receive the same prefixes regardless of property insertion order.

This is a BREAKING key-ID change reserved for 6.0.0. Regenerate graph output and
update consumers that selected the old structural `n_label`/`e_label` keys to
read `node_label`/`edge_label`. Select by key ID and domain when distinguishing
structural labels from caller metadata: both still have `attr.name="label"`.
Plain, yEd, compact, pretty and delegated output share this ID rule. The package-level
structured exporter is a separate API; XSD validation is outside this repair
(treesitter-chunker#169).

NetworkX 3.6.1 imports fields by `attr.name`: plain/delegated import keeps one
`label` value, and yEd graphics can overwrite caller labels. Its imported
attributes therefore do not retain these fields independently. Use a reader
that distinguishes key IDs when both values are needed; this interoperability
gap remains treesitter-chunker#453. Raw key uniqueness does not certify every
tool's imported attribute mapping.

### Graph ID migration for 6.0.0

The next major release changes the legacy graph IDs from line spans to existing
chunk occurrence IDs. Distinct chunks sharing a line span now remain distinct.
This applies to the direct exporter modules `chunker.export.graphml_exporter`,
`graphml_yed_exporter`, `dot_exporter` and `neo4j_exporter`. The package-level
`chunker.export` structured exporters and the database helper are separate APIs.

Regenerate graph outputs and rebuild indexes/joins from emitted IDs. Do not parse
IDs as file/line strings. File paths, byte positions, routes and content changes
can rekey an occurrence. The retained `file_path`, `start_line` and `end_line`
properties can reconstruct a legacy span alias.

Automatic parent resolution uses only the chunks supplied to that extraction
call. `parent_chunk_id` looks up `chunk_id`; `metadata["parent_id"]` first looks
up exact `node_id`/`chunk_id` aliases, then a unique legacy span alias. An exact
unique match wins over span ambiguity. A referenced alias identifying different
canonical nodes raises an actionable `ValueError` naming the field and alias
before any edge is appended; prior edges stay unchanged. Repeated copies of one
occurrence are harmless, unknown aliases are ignored, and unreferenced alias
collisions do not reject extraction. Different unambiguous parents may produce
independent CONTAINS and DEFINES relationships.

Ordinary populated IDs agree with Unified conversion. If callers clear both
fields, the graph fallback can generate an ID, but that generated value is not
an exact parent alias and UnifiedGraphNode.from_chunk retains its empty fallback.
The direct DOT exporter preserves nonempty ASCII hexadecimal IDs exactly,
including case and leading zeroes. Other valid UTF-8 caller IDs serialize as
`tc_` followed by their UTF-8 bytes in lowercase hexadecimal, preserving distinct
IDs and directed endpoints (treesitter-chunker#444). For example, `a-b` becomes
`tc_612d62`, while `a_b` becomes `tc_615f62`. Prefix-looking caller strings are
encoded too: a caller ID `tc_612d62` becomes `tc_74635f363132643632`.
This is a BREAKING serialized-ID change reserved for 6.0.0. Regenerate DOT output
and update joins that use nonhex serialized IDs; retain the graph model's raw
ID when matching back to chunks. Source labels, raw chunk/graph IDs, file
clusters and occurrence identity algorithms are unchanged. Empty preferred IDs
still use the graph model's existing fallback. Lone surrogate strings are not
valid UTF-8 caller IDs and raise `UnicodeEncodeError` during string export as
well as file export. This node-ID contract does not certify arbitrary DOT
attribute values.

Direct DOT relationship labels preserve caller text containing quotes,
backslashes, Unicode, tabs and carriage returns in string and file output
(treesitter-chunker#473). Literal backslash sequences such as `\N` and `\n`
remain visible text; they do not substitute graph identities or create lines.
Physical LF creates a centered line break. Physical CR remains in the compiled
label value; renderer typography and control-character display are separate.
HTML-looking tags remain plain text, but Graphviz interprets HTML character
entities such as `&amp;` and `&#10;`; literal entity preservation remains
treesitter-chunker#478. This contract covers the listed valid UTF-8 text cases
without NUL or entity sequences, not arbitrary control bytes, invalid surrogates
or arbitrary attribute values. Compiler qualification uses Graphviz 14.1.2 on
Linux and 14.1.1 on Windows; other versions are not certified here.
Direct DOT node and cluster labels retain physical tabs, and relationship
tooltips retain them in compiled Graphviz JSON (treesitter-chunker#476).
Parsed SVG tooltips normalize physical tabs to spaces under XML attribute
rules; they do not turn into literal `t` characters. Literal backslash-t remains
text. This covers the listed valid UTF-8 text cases without NUL or entity
sequences, using the same tested compiler versions above.
Generated direct DOT node-label fields now render on separate centered lines
(treesitter-chunker#479): name/type, file/span, complexity and token count when
present. Their serialized label bytes change. Caller physical LF also produces
line breaks; caller literal backslash-n remains visible text. Actual JSON/SVG
checks cover string and file output with flat and clustered graphs, including
quotes, backslashes and Unicode, on the compiler versions above. This does not
certify empty-line typography, arbitrary controls or other renderer versions.

The direct Neo4j CSV exporter preserves leading spaces, tabs and Unicode
whitespace in caller IDs and trailing property whitespace, including boundary
rows (treesitter-chunker#448). Preserve these values when joining endpoints.
Its CSV files preserve embedded LF, CR and CRLF in caller IDs and string
properties, matching generated CSV strings on Linux and Windows
(treesitter-chunker#454). Read files with `newline=""` to retain these line
breaks. This does not establish live Neo4j database import compatibility.
The generated Neo4j `.sh` helper preserves LF syntax on Windows and Linux for
Bash (treesitter-chunker#457). Node and relationship filename options remain
single literal Bash arguments for basenames containing spaces, apostrophes,
semicolons, dollar expansion syntax, backticks and Unicode
(treesitter-chunker#460). POSIX shell quoting is not CMD or PowerShell syntax.
Direct Cypher files retain generated UTF-8 bytes on Windows and Linux, including
embedded LF, CR and CRLF in caller IDs and string properties
(treesitter-chunker#458). Read with `newline=""` to retain line breaks. File
transport and argument fidelity do not certify Cypher syntax, a live database
import or server version.
XML character rejection is described below (treesitter-chunker#168 and
treesitter-chunker#451). Structural label-key separation is described above
(treesitter-chunker#169).
This migration establishes node/endpoint identity; XML schema completeness is
separate.

## Type Inference

The exporter automatically infers GraphML data types from Python values:
- `bool` → `boolean`
- `int` → `int`
- `float` → `double`
- Everything else → `string`

## Special Character Handling

All XML special characters in code content and metadata are properly escaped:
- `&` → `&amp;`
- `<` → `&lt;`
- `>` → `&gt;`
- `"` → `&quot;` (in attributes)

The direct `chunker.export.graphml_exporter` and `graphml_yed_exporter` modules,
including compact, pretty and `use_yed=False` output, reject XML 1.0-forbidden
characters in element text, tail and attribute values with `ValueError` before
serialization. Metadata property names are checked because they become key
attribute values. Graph attribute names have the separate validation contract
below (treesitter-chunker#452). The package-level
`chunker.export.GraphMLExporter` is a separate structured exporter.
The error identifies the Unicode code point and XML location without echoing
the full caller value. This includes NUL, other forbidden C0 controls, unpaired
surrogates, U+FFFE and U+FFFF. No caller characters are silently deleted.

The two direct modules preserve legal Unicode, XML metacharacters and physical
tab, newline and carriage return in attribute values through pretty and compact
output, including Python 3.11/3.12 (treesitter-chunker#450). This is a decoded
attribute-value contract with non-validating XML readers; whitespace-containing
IDs do not establish GraphML XSD conformance. Pretty output retains its XML
declaration without an encoding label and its trailing newline. Indentation and
empty-element layout may differ from earlier output.

Pretty text leaves retain XML newline normalization: CRLF and lone CR become LF;
space-TAB-space leaves stay intact. Caller inputs are unchanged. UTF-8 files
retain native newline translation. Compact Windows files can still turn CRLF
caller text into two decoded LF characters (treesitter-chunker#488); this differs
from compact string output and is outside the attribute repair. The separate
package-level `chunker.export.GraphMLExporter` still has the Python 3.11/3.12
attribute-whitespace defect (treesitter-chunker#489).

File export rejected by this character check leaves an existing file unchanged
and creates no new file.
Remove the invalid metadata value or name and retry on the same exporter;
invalid new names are rejected before they enter its cached key registry.
Existing valid custom key declarations remain intact. Character validation
does not validate GraphML schema. Structural/caller label-key separation is
described above (treesitter-chunker#169).

### Graph attribute names

The two direct modules deliberately reject malformed graph attribute names and
namespace bindings with `ValueError` before producing output, across pretty,
compact, yEd and delegated modes (treesitter-chunker#452). Rejected file export
leaves existing bytes intact and creates no absent file. Correct or remove the
offending `graph_attrs` entry and retry on the same exporter; caller attributes
and graph data are unchanged.

Names must be strings. Supported forms are unqualified Unicode names, bound
`prefix:local` names, namespace declarations (`xmlns` and `xmlns:prefix`), and
ElementTree expanded `{URI}local` strings. Components must match XML NCName
syntax and be accepted by the installed Python ElementTree parser. Some names
allowed by [XML 1.0 Fifth Edition](https://www.w3.org/TR/xml/#NT-Name) remain
unsupported by older Expat name tables. Empty names, leading digits, whitespace,
markup delimiters, malformed qualified names and unbound prefixes are rejected.
Expanded URIs must be nonempty, brace-free and contain only XML 1.0 characters.
Non-string keys, including `ElementTree.QName` objects, now raise deliberate
`ValueError`; pass `str(qname)` to use its expanded string form.

The `xml` prefix is implicitly bound. `xsi` is bound on all routes; `y` is bound
on the yEd route, and requires a caller declaration on plain/delegated routes.
Custom declarations work in either insertion order. Illegal reserved bindings,
duplicate expanded attributes and expanded names silently rebound by conflicting
declarations are rejected. Generated prefix collisions cannot swap or mask the
identity of an expanded caller attribute, even when caller values are equal.
Expanded names in the `xsi` namespace can generate a duplicate root declaration
and are rejected in that configuration; use `xsi:local` instead.

Namespace declaration overrides retain their existing effect on descendants,
including default-namespace overrides and `xmlns:y` changes to yEd graphics.
Literal names using generated `ns<digits>` prefixes depend on the generated
bindings; use your own declared prefixes for explicit namespace selection.
These caller-controlled effects do not establish GraphML schema conformance.
Validation uses a discarded attribute probe; the original output tree and its
attribute values, including physical TAB/LF/CR, are preserved. Name diagnostics
identify the name or namespace failure without printing caller attribute values
or presenting probe positions as output locations.

## Compatibility

GraphML can be opened by the following tools; attribute mapping depends on the
reader. In particular, see the NetworkX label limitation above
(treesitter-chunker#453):
- yEd Graph Editor
- Gephi
- Cytoscape
- NetworkX
- igraph
- Most other graph analysis tools

## Advanced Usage

### Custom Graph Attributes

```python
# Customize graph-level attributes
exporter.graph_attrs["id"] = "MyCodeGraph"
exporter.graph_attrs["description"] = "Code analysis results"
```

### Filtering Nodes

```python
# Add only specific chunk types
filtered_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "function"]
exporter.add_chunks(filtered_chunks)
```

### Post-Processing

The generated GraphML is standard XML and can be further processed:

```python
import xml.etree.ElementTree as ET

# Export and parse
graphml_str = exporter.export_string()
root = ET.fromstring(graphml_str)

# Add custom elements
comment = ET.Comment("Generated by TreeSitter Chunker")
root.insert(0, comment)

# Re-serialize
modified_xml = ET.tostring(root, encoding='unicode')
```

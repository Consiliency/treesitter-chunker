# GraphML Export Documentation

## Overview

The GraphML exporter converts code chunks and their relationships into GraphML format, a standard XML-based format for representing graphs. This enables visualization and analysis in tools like yEd, Gephi, Cytoscape, and other graph visualization software.

## Features

### Core Features
- **Valid GraphML 1.0 output** - Generates standards-compliant GraphML files
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
<key id="n_label" for="node" attr.name="label" attr.type="string"/>
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
  <data key="n_label">function</data>
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
  <data key="e_label">CALLS</data>
  <data key="e_line">3</data>
</edge>
```

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
DOT punctuation encoding for arbitrary caller IDs remains treesitter-chunker#444;
distinct serialized DOT IDs are verified for parser-generated hexadecimal IDs.
Neo4j CSV's pre-existing whole-block whitespace stripping can change a caller ID
with leading whitespace in its first row (treesitter-chunker#448). This identity
migration does not repair that serializer or establish whitespace-ID CSV fidelity.
XML-control and duplicate-key fixes remain treesitter-chunker#168 and
treesitter-chunker#169. This migration establishes node/endpoint identity,
not XML schema completeness.

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

## Compatibility

The generated GraphML files are compatible with:
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

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
- Unique ID based on file path and line numbers
- Label showing the chunk type
- All properties from the chunk metadata

```xml
<node id="src/main.py:1:10">
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
<edge id="e0" source="src/main.py:1:10" target="src/utils.py:5:15">
  <data key="e_label">CALLS</data>
  <data key="e_line">3</data>
</edge>
```

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
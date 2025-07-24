# Structured Export Feature

The structured export feature (Phase 8) provides comprehensive export capabilities for code chunks with relationship tracking and multiple format support. It uses Tree-sitter AST analysis to extract relationships between code elements and exports them in various formats suitable for analysis, visualization, and database storage.

## Overview

The structured export system consists of several key components:

1. **StructuredExportOrchestrator** - Main export coordinator with streaming support
2. **ASTRelationshipTracker** - Tracks dependencies, calls, and inheritance using AST analysis
3. **Format-specific exporters** - Export to JSON, Parquet, GraphML, DOT, SQLite, PostgreSQL, and Neo4j
4. **Streaming support** - Handle large codebases efficiently

## Features

### Relationship Tracking

The system automatically detects and tracks various types of relationships:

- **Inheritance** - Class inheritance hierarchies
- **Function/Method Calls** - Which functions call which others
- **Imports/Dependencies** - Module and package dependencies
- **Implementations** - Interface/trait implementations
- **Uses/References** - General usage relationships

### Export Formats

#### Graph Formats
- **GraphML** - XML-based format for graph visualization tools (yEd, Gephi)
- **DOT** - Graphviz format for generating visual diagrams
- **Neo4j** - Cypher queries for Neo4j graph database

#### Database Formats
- **SQLite** - Local SQL database with full schema
- **PostgreSQL** - SQL script for PostgreSQL import
- **Parquet** - Columnar format for big data analytics

#### Structured Data Formats
- **JSON** - Complete hierarchical export with metadata
- **JSONL** - Streaming-friendly JSON Lines format

## Usage Examples

### Basic Export with Relationship Tracking

```python
from chunker.chunker import chunk_file
from chunker.export import (
    StructuredExportOrchestrator,
    ASTRelationshipTracker,
    StructuredJSONExporter
)
from chunker.interfaces.export import ExportFormat

# Chunk source files
chunks = []
for file_path in source_files:
    chunks.extend(chunk_file(file_path, "python"))

# Track relationships
tracker = ASTRelationshipTracker()
relationships = tracker.infer_relationships(chunks)

# Export to JSON
orchestrator = StructuredExportOrchestrator()
json_exporter = StructuredJSONExporter(indent=2)
orchestrator.register_exporter(ExportFormat.JSON, json_exporter)

orchestrator.export(chunks, relationships, "output.json")
```

### Export to Neo4j

```python
from chunker.export import Neo4jExporter

# Create Neo4j exporter
neo4j_exporter = Neo4jExporter()
neo4j_exporter.set_node_label("CodeElement")

# Register and export
orchestrator.register_exporter(ExportFormat.NEO4J, neo4j_exporter)
orchestrator.export(chunks, relationships, "codebase.cypher")
```

### Create Dependency Visualization

```python
from chunker.export import DOTExporter

# Create DOT exporter with custom styles
dot_exporter = DOTExporter()
dot_exporter.set_edge_style('inherits', {
    'color': 'red',
    'style': 'solid',
    'arrowhead': 'empty'
})
dot_exporter.set_edge_style('calls', {
    'color': 'blue',
    'style': 'solid'
})

# Export and render
orchestrator.register_exporter(ExportFormat.DOT, dot_exporter)
orchestrator.export(chunks, relationships, "dependencies.dot")

# Render with Graphviz
import subprocess
subprocess.run(["dot", "-Tsvg", "dependencies.dot", "-o", "dependencies.svg"])
```

### Streaming Export for Large Codebases

```python
# Create iterators for streaming
def chunk_iterator():
    for file_path in large_codebase_files:
        yield from chunk_file(file_path, "python")

def relationship_iterator():
    batch = []
    for chunk in chunk_iterator():
        batch.append(chunk)
        if len(batch) >= 100:
            # Process batch
            rels = tracker.infer_relationships(batch)
            yield from rels
            batch = []

# Stream to JSONL
jsonl_exporter = StructuredJSONLExporter()
orchestrator.register_exporter(ExportFormat.JSONL, jsonl_exporter)
orchestrator.export_streaming(
    chunk_iterator(),
    relationship_iterator(),
    "large_codebase.jsonl"
)
```

## Relationship Types

The system recognizes these relationship types:

| Type | Description | Example |
|------|-------------|---------|
| PARENT_CHILD | Hierarchical nesting | Method inside class |
| CALLS | Function/method invocation | `foo()` calls `bar()` |
| IMPORTS | Module/package import | `import os` |
| INHERITS | Class inheritance | `class Dog(Animal)` |
| IMPLEMENTS | Interface/trait implementation | `impl Trait for Struct` |
| USES | General usage | Variable reference |
| DEFINES | Definition relationship | Class defines method |
| REFERENCES | General reference | Type annotation |
| DEPENDS_ON | Dependency relationship | Module depends on another |

## Export Schemas

### JSON/JSONL Schema

```json
{
  "metadata": {
    "format": "json",
    "version": "1.0",
    "created_at": "2024-01-20T10:30:00Z",
    "source_files": ["file1.py", "file2.py"],
    "chunk_count": 42,
    "relationship_count": 73
  },
  "chunks": [
    {
      "chunk_id": "abc123",
      "language": "python",
      "file_path": "module.py",
      "node_type": "class_definition",
      "content": "class Example:...",
      "start_line": 10,
      "end_line": 25
    }
  ],
  "relationships": [
    {
      "source_chunk_id": "abc123",
      "target_chunk_id": "def456",
      "relationship_type": "inherits",
      "metadata": {"base_class": "BaseClass"}
    }
  ]
}
```

### Database Schema

#### Chunks Table
- `chunk_id` (PRIMARY KEY)
- `language`
- `file_path`
- `node_type`
- `start_line`, `end_line`
- `byte_start`, `byte_end`
- `parent_context`
- `content`
- `parent_chunk_id`
- `references` (JSON)
- `dependencies` (JSON)

#### Relationships Table
- `id` (PRIMARY KEY)
- `source_chunk_id` (FOREIGN KEY)
- `target_chunk_id` (FOREIGN KEY)
- `relationship_type`
- `metadata` (JSON)

## Visualization Tools

### Graphviz (DOT files)
```bash
# Generate SVG
dot -Tsvg dependencies.dot -o dependencies.svg

# Generate PNG
dot -Tpng dependencies.dot -o dependencies.png

# Other layouts
neato -Tsvg dependencies.dot -o dependencies_neato.svg
fdp -Tsvg dependencies.dot -o dependencies_fdp.svg
```

### yEd (GraphML files)
1. Open yEd Graph Editor
2. File → Open → Select .graphml file
3. Tools → Fit Node to Label
4. Layout → Hierarchical → OK

### Neo4j
```bash
# Import Cypher file
cat codebase.cypher | cypher-shell -u neo4j -p password

# Or in Neo4j Browser
# Copy contents of .cypher file and paste in query window
```

## Performance Considerations

1. **Memory Usage**: Use streaming exports for large codebases
2. **Batch Processing**: Configure batch sizes for database exports
3. **Relationship Inference**: Can be CPU intensive for large files
4. **Format Choice**: 
   - JSONL for streaming
   - Parquet for analytics
   - SQLite for local queries
   - Neo4j for graph analysis

## Integration with Other Phases

The structured export feature integrates with:

- **Phase 1 (Core Chunking)**: Uses chunks as input
- **Phase 2 (Language Plugins)**: Respects language-specific rules
- **Phase 3 (Parallel Processing)**: Can process files in parallel
- **Phase 4 (Streaming)**: Supports streaming for large datasets
- **Phase 5 (Caching)**: Can cache relationship analysis
- **Phase 6 (Config)**: Respects configuration settings

## Future Enhancements

1. **Additional Relationship Types**
   - Data flow analysis
   - Control flow relationships
   - Side effect tracking

2. **More Export Formats**
   - RDF/Turtle for semantic web
   - NetworkX for Python analysis
   - D3.js JSON for web visualization

3. **Advanced Analysis**
   - Cyclic dependency detection
   - Coupling metrics
   - Complexity analysis

4. **Performance Optimizations**
   - Parallel relationship inference
   - Incremental updates
   - Relationship caching
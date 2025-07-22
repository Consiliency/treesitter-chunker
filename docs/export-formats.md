# Export Formats Guide

Tree-sitter Chunker supports multiple export formats to integrate with different workflows and tools. This guide covers all available formats, their use cases, and advanced configuration options.

## Table of Contents

1. [Overview](#overview)
2. [JSON Export](#json-export)
3. [JSONL Export](#jsonl-export)
4. [Parquet Export](#parquet-export)
5. [Format Comparison](#format-comparison)
6. [Schema Types](#schema-types)
7. [Compression Options](#compression-options)
8. [Streaming Export](#streaming-export)
9. [Custom Export Formats](#custom-export-formats)
10. [Integration Examples](#integration-examples)

## Overview

Tree-sitter Chunker provides three main export formats:

- **JSON**: Human-readable, supports nested structures, ideal for small to medium datasets
- **JSONL**: Line-delimited JSON, perfect for streaming and log processing
- **Parquet**: Columnar format, excellent for analytics and big data workflows

Each format supports different schema types and compression options.

## JSON Export

JSON export provides a flexible, human-readable format with support for different schema types.

### Basic Usage

```python
from chunker import chunk_file
from chunker.export import JSONExporter, SchemaType

# Get chunks
chunks = chunk_file("example.py", "python")

# Export with default settings
exporter = JSONExporter()
exporter.export(chunks, "output.json")

# Export with pretty printing
exporter.export(chunks, "output.json", indent=2)

# Export with compression
exporter.export(chunks, "output.json.gz", compress=True)
```

### Schema Types

#### Flat Schema (Default)

Simple, denormalized structure with all chunk data in a flat array:

```python
exporter = JSONExporter(schema_type=SchemaType.FLAT)
exporter.export(chunks, "flat.json")
```

Output structure:
```json
{
  "chunks": [
    {
      "chunk_id": "abc123",
      "language": "python",
      "file_path": "/path/to/file.py",
      "node_type": "function_definition",
      "start_line": 10,
      "end_line": 20,
      "parent_context": "class:MyClass",
      "content": "def my_function():\n    pass"
    }
  ],
  "metadata": {
    "total_chunks": 42,
    "export_time": "2024-01-13T10:30:00Z",
    "chunker_version": "1.0.0"
  }
}
```

#### Nested Schema

Preserves hierarchical relationships between chunks:

```python
exporter = JSONExporter(schema_type=SchemaType.NESTED)
exporter.export(chunks, "nested.json")
```

Output structure:
```json
{
  "files": {
    "/path/to/file.py": {
      "language": "python",
      "chunks": [
        {
          "chunk_id": "abc123",
          "node_type": "class_definition",
          "start_line": 5,
          "end_line": 50,
          "children": [
            {
              "chunk_id": "def456",
              "node_type": "function_definition",
              "start_line": 10,
              "end_line": 20,
              "content": "def method(self):\n    pass"
            }
          ]
        }
      ]
    }
  }
}
```

#### Relational Schema

Normalized structure suitable for relational databases:

```python
exporter = JSONExporter(schema_type=SchemaType.RELATIONAL)
exporter.export(chunks, "relational.json")
```

Output structure:
```json
{
  "chunks": [
    {
      "chunk_id": "abc123",
      "file_id": "file_001",
      "parent_chunk_id": null,
      "node_type": "class_definition",
      "start_line": 5,
      "end_line": 50
    }
  ],
  "files": [
    {
      "file_id": "file_001",
      "file_path": "/path/to/file.py",
      "language": "python"
    }
  ],
  "relationships": [
    {
      "parent_id": "abc123",
      "child_id": "def456",
      "relationship_type": "contains"
    }
  ]
}
```

### Advanced JSON Export

```python
from chunker.export import JSONExporter, SchemaType
import json

class CustomJSONExporter(JSONExporter):
    """Extended JSON exporter with custom features."""
    
    def export_with_metadata(self, chunks, output_path, custom_metadata=None):
        """Export with additional metadata."""
        data = self._prepare_data(chunks)
        
        # Add custom metadata
        if custom_metadata:
            data['metadata'].update(custom_metadata)
        
        # Add statistics
        data['statistics'] = {
            'total_chunks': len(chunks),
            'chunks_by_type': self._count_by_type(chunks),
            'avg_chunk_size': self._avg_chunk_size(chunks),
            'languages': list(set(c.language for c in chunks))
        }
        
        # Export with custom encoder
        with open(output_path, 'w') as f:
            json.dump(data, f, cls=self.CustomEncoder, indent=2)
    
    def _count_by_type(self, chunks):
        counts = {}
        for chunk in chunks:
            counts[chunk.node_type] = counts.get(chunk.node_type, 0) + 1
        return counts
    
    def _avg_chunk_size(self, chunks):
        if not chunks:
            return 0
        total_lines = sum(c.end_line - c.start_line + 1 for c in chunks)
        return total_lines / len(chunks)
    
    class CustomEncoder(json.JSONEncoder):
        """Handle special types."""
        def default(self, obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            return super().default(obj)
```

## JSONL Export

JSON Lines format is ideal for streaming, logging, and processing large datasets.

### Basic Usage

```python
from chunker.export import JSONLExporter

# Export chunks to JSONL
exporter = JSONLExporter()
exporter.export(chunks, "output.jsonl")

# Export with compression
exporter.export(chunks, "output.jsonl.gz", compress=True)
```

### Streaming Export

Process and export large datasets without loading everything into memory:

```python
from chunker import chunk_file_streaming
from chunker.export import JSONLExporter

def export_large_codebase(directory, language):
    """Export large codebase using streaming."""
    exporter = JSONLExporter()
    
    # Create generator for all chunks
    def chunk_generator():
        from pathlib import Path
        for file_path in Path(directory).rglob(f"*.{language[:2]}"):
            for chunk in chunk_file_streaming(file_path, language):
                yield chunk
    
    # Stream export
    exporter.export_streaming(
        chunk_generator(),
        "large_export.jsonl",
        compress=True
    )

# Use it
export_large_codebase("src/", "python")
```

### JSONL with Filtering

```python
class FilteredJSONLExporter(JSONLExporter):
    """Export only chunks matching criteria."""
    
    def export_filtered(self, chunks, output_path, filter_func):
        """Export only chunks that pass filter."""
        filtered = (chunk for chunk in chunks if filter_func(chunk))
        self.export_streaming(filtered, output_path)

# Example: Export only large functions
exporter = FilteredJSONLExporter()
exporter.export_filtered(
    chunks,
    "large_functions.jsonl",
    lambda c: c.node_type == "function_definition" and 
              (c.end_line - c.start_line) > 50
)
```

### Processing JSONL Files

```python
import json

def process_jsonl_file(file_path):
    """Read and process JSONL file."""
    chunks = []
    
    with open(file_path, 'r') as f:
        for line in f:
            if line.strip():
                chunk_data = json.loads(line)
                chunks.append(chunk_data)
    
    return chunks

# Streaming processing
def stream_process_jsonl(file_path, processor_func):
    """Process JSONL file line by line."""
    with open(file_path, 'r') as f:
        for line in f:
            if line.strip():
                chunk_data = json.loads(line)
                processor_func(chunk_data)
```

## Parquet Export

Parquet is a columnar storage format that's highly efficient for analytics workloads.

### Basic Usage

```python
from chunker.exporters import ParquetExporter

# Basic export
exporter = ParquetExporter()
exporter.export(chunks, "output.parquet")

# Export with specific columns
exporter = ParquetExporter(
    columns=["language", "file_path", "node_type", "content", "start_line", "end_line"]
)
exporter.export(chunks, "output.parquet")
```

### Compression Options

Parquet supports multiple compression algorithms:

```python
# Snappy (default) - Fast compression
exporter = ParquetExporter(compression="snappy")

# Gzip - Higher compression ratio
exporter = ParquetExporter(compression="gzip")

# Brotli - Best compression ratio
exporter = ParquetExporter(compression="brotli")

# LZ4 - Fastest compression
exporter = ParquetExporter(compression="lz4")

# Zstd - Good balance
exporter = ParquetExporter(compression="zstd")

# No compression
exporter = ParquetExporter(compression=None)
```

### Partitioned Export

Partition data for efficient querying:

```python
# Partition by language and node type
exporter = ParquetExporter()
exporter.export_partitioned(
    chunks,
    "output_dir/",
    partition_cols=["language", "node_type"]
)

# Creates directory structure:
# output_dir/
#   language=python/
#     node_type=function_definition/
#       part-0.parquet
#     node_type=class_definition/
#       part-0.parquet
#   language=javascript/
#     node_type=function_declaration/
#       part-0.parquet
```

### Advanced Parquet Features

```python
import pyarrow as pa
import pyarrow.parquet as pq
from chunker.exporters import ParquetExporter

class AdvancedParquetExporter(ParquetExporter):
    """Extended Parquet exporter with advanced features."""
    
    def export_with_schema(self, chunks, output_path, custom_schema=None):
        """Export with custom schema."""
        # Convert chunks to records
        records = [self._chunk_to_record(chunk) for chunk in chunks]
        
        # Define schema if not provided
        if custom_schema is None:
            custom_schema = pa.schema([
                ('chunk_id', pa.string()),
                ('language', pa.string()),
                ('file_path', pa.string()),
                ('node_type', pa.string()),
                ('start_line', pa.int32()),
                ('end_line', pa.int32()),
                ('byte_start', pa.int64()),
                ('byte_end', pa.int64()),
                ('content', pa.string()),
                ('parent_context', pa.string()),
                ('metadata', pa.string()),  # JSON string
            ])
        
        # Create table with schema
        table = pa.Table.from_pylist(records, schema=custom_schema)
        
        # Write with options
        pq.write_table(
            table,
            output_path,
            compression=self.compression,
            use_dictionary=['language', 'node_type'],  # Dictionary encoding
            row_group_size=5000,
            data_page_size=1024*1024,  # 1MB pages
            version='2.6'  # Latest format
        )
    
    def export_with_statistics(self, chunks, output_path):
        """Export with column statistics for query optimization."""
        records = [self._chunk_to_record(chunk) for chunk in chunks]
        table = pa.Table.from_pylist(records)
        
        # Write with statistics
        pq.write_table(
            table,
            output_path,
            compression=self.compression,
            write_statistics=True,
            column_encoding={'content': 'PLAIN'},  # No dictionary for content
        )
```

### Reading Parquet Files

```python
import pyarrow.parquet as pq
import pandas as pd

# Read with PyArrow
def read_parquet_pyarrow(file_path):
    """Read Parquet file using PyArrow."""
    table = pq.read_table(file_path)
    
    # Filter example
    filtered = table.filter(
        (table['node_type'] == 'function_definition') & 
        (table['end_line'] - table['start_line'] > 50)
    )
    
    return filtered.to_pylist()

# Read with Pandas
def read_parquet_pandas(file_path):
    """Read Parquet file using Pandas."""
    df = pd.read_parquet(
        file_path,
        columns=['file_path', 'node_type', 'start_line', 'end_line']
    )
    
    # Analysis example
    print(df['node_type'].value_counts())
    return df

# Read partitioned dataset
def read_partitioned_dataset(directory):
    """Read partitioned Parquet dataset."""
    dataset = pq.ParquetDataset(directory)
    
    # Read with filters
    table = dataset.read(
        filters=[
            ('language', '=', 'python'),
            ('node_type', 'in', ['function_definition', 'class_definition'])
        ]
    )
    
    return table.to_pandas()
```

## Format Comparison

### Performance Comparison

| Format | Write Speed | Read Speed | Compression | File Size |
|--------|-------------|------------|-------------|-----------|
| JSON | Medium | Medium | Optional | Large |
| JSONL | Fast | Fast | Optional | Large |
| Parquet | Slow | Very Fast | Built-in | Small |

### Feature Comparison

| Feature | JSON | JSONL | Parquet |
|---------|------|-------|---------|
| Human Readable | ✅ | ✅ | ❌ |
| Streaming | ❌ | ✅ | ✅ |
| Schema Evolution | ✅ | ✅ | Limited |
| Query Performance | Poor | Medium | Excellent |
| Compression | External | External | Built-in |
| Partial Reads | ❌ | ✅ | ✅ |
| Column Selection | ❌ | ❌ | ✅ |

### Use Case Recommendations

**Use JSON when:**
- Human readability is important
- Working with small to medium datasets
- Integrating with web APIs
- Need flexible, nested structures

**Use JSONL when:**
- Processing streaming data
- Working with log files
- Need line-by-line processing
- Building data pipelines

**Use Parquet when:**
- Working with large datasets
- Performing analytics queries
- Need efficient storage
- Using data science tools

## Schema Types

### Flat Schema

Best for simple use cases and direct database imports:

```python
# Flat schema example
{
    "chunks": [
        {
            "chunk_id": "...",
            "all_fields": "..."
        }
    ]
}
```

### Nested Schema

Preserves relationships and hierarchy:

```python
# Nested schema example
{
    "files": {
        "path": {
            "chunks": [
                {
                    "chunk": "...",
                    "children": [...]
                }
            ]
        }
    }
}
```

### Relational Schema

Normalized for relational databases:

```python
# Relational schema example
{
    "chunks": [...],
    "files": [...],
    "relationships": [...]
}
```

## Compression Options

### Compression Comparison

| Algorithm | Compression Ratio | Speed | Use Case |
|-----------|------------------|-------|----------|
| None | 1:1 | Fastest | Local processing |
| Snappy | 2-4:1 | Very Fast | Default choice |
| LZ4 | 2-4:1 | Fastest | Speed critical |
| Gzip | 5-10:1 | Slow | Network transfer |
| Zstd | 5-15:1 | Medium | Balanced |
| Brotli | 10-20:1 | Very Slow | Storage critical |

### Compression Examples

```python
# JSON with gzip
from chunker.export import JSONExporter
exporter = JSONExporter()
exporter.export(chunks, "output.json.gz", compress=True)

# JSONL with custom compression
import gzip
import json

def export_jsonl_compressed(chunks, output_path):
    with gzip.open(output_path, 'wt', encoding='utf-8') as f:
        for chunk in chunks:
            json.dump(chunk.__dict__, f)
            f.write('\n')

# Parquet with zstd
from chunker.exporters import ParquetExporter
exporter = ParquetExporter(compression="zstd")
exporter.export(chunks, "output.parquet")
```

## Streaming Export

### Memory-Efficient Export

```python
from chunker import chunk_file_streaming
from chunker.export import JSONLExporter
from chunker.exporters import ParquetExporter

class StreamingExporter:
    """Memory-efficient export for large codebases."""
    
    def export_directory_streaming(self, directory, language, output_format="jsonl"):
        """Export entire directory with minimal memory usage."""
        from pathlib import Path
        
        def chunk_generator():
            for file_path in Path(directory).rglob(f"*.{language[:2]}"):
                print(f"Processing {file_path}")
                for chunk in chunk_file_streaming(file_path, language):
                    yield chunk
        
        if output_format == "jsonl":
            exporter = JSONLExporter()
            exporter.export_streaming(
                chunk_generator(),
                f"export.{output_format}",
                compress=True
            )
        elif output_format == "parquet":
            exporter = ParquetExporter()
            exporter.export_streaming(
                chunk_generator(),
                f"export.{output_format}",
                batch_size=10000  # Write in batches
            )
```

### Parallel Streaming Export

```python
from concurrent.futures import ThreadPoolExecutor
import queue
import threading

class ParallelStreamingExporter:
    """Export with parallel processing and streaming."""
    
    def __init__(self, num_workers=4):
        self.num_workers = num_workers
        self.chunk_queue = queue.Queue(maxsize=1000)
        self.done = threading.Event()
    
    def export_parallel(self, files, language, output_path):
        """Process files in parallel, export in streaming fashion."""
        # Start export thread
        export_thread = threading.Thread(
            target=self._export_worker,
            args=(output_path,)
        )
        export_thread.start()
        
        # Process files in parallel
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            futures = []
            for file_path in files:
                future = executor.submit(self._process_file, file_path, language)
                futures.append(future)
            
            # Wait for all processing to complete
            for future in futures:
                future.result()
        
        # Signal completion and wait for export to finish
        self.done.set()
        export_thread.join()
    
    def _process_file(self, file_path, language):
        """Process a single file and queue chunks."""
        for chunk in chunk_file_streaming(file_path, language):
            self.chunk_queue.put(chunk)
    
    def _export_worker(self, output_path):
        """Export chunks from queue."""
        from chunker.export import JSONLExporter
        exporter = JSONLExporter()
        
        with open(output_path, 'w') as f:
            while not self.done.is_set() or not self.chunk_queue.empty():
                try:
                    chunk = self.chunk_queue.get(timeout=0.1)
                    exporter._write_chunk(chunk, f)
                except queue.Empty:
                    continue
```

## Custom Export Formats

### CSV Export

```python
import csv
from typing import List
from chunker import CodeChunk

class CSVExporter:
    """Export chunks to CSV format."""
    
    def export(self, chunks: List[CodeChunk], output_path: str):
        """Export chunks to CSV."""
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'chunk_id', 'language', 'file_path', 'node_type',
                'start_line', 'end_line', 'parent_context'
            ]
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for chunk in chunks:
                writer.writerow({
                    'chunk_id': chunk.chunk_id,
                    'language': chunk.language,
                    'file_path': chunk.file_path,
                    'node_type': chunk.node_type,
                    'start_line': chunk.start_line,
                    'end_line': chunk.end_line,
                    'parent_context': chunk.parent_context or ''
                })
```

### XML Export

```python
import xml.etree.ElementTree as ET
from xml.dom import minidom

class XMLExporter:
    """Export chunks to XML format."""
    
    def export(self, chunks: List[CodeChunk], output_path: str):
        """Export chunks to XML."""
        root = ET.Element('chunks')
        
        for chunk in chunks:
            chunk_elem = ET.SubElement(root, 'chunk')
            chunk_elem.set('id', chunk.chunk_id)
            
            # Add child elements
            ET.SubElement(chunk_elem, 'language').text = chunk.language
            ET.SubElement(chunk_elem, 'file_path').text = chunk.file_path
            ET.SubElement(chunk_elem, 'node_type').text = chunk.node_type
            ET.SubElement(chunk_elem, 'start_line').text = str(chunk.start_line)
            ET.SubElement(chunk_elem, 'end_line').text = str(chunk.end_line)
            
            # Add content as CDATA
            content_elem = ET.SubElement(chunk_elem, 'content')
            content_elem.text = chunk.content
        
        # Pretty print
        xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_str)
```

### SQLite Export

```python
import sqlite3
from typing import List
from chunker import CodeChunk

class SQLiteExporter:
    """Export chunks to SQLite database."""
    
    def export(self, chunks: List[CodeChunk], db_path: str):
        """Export chunks to SQLite."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                language TEXT,
                file_path TEXT,
                node_type TEXT,
                start_line INTEGER,
                end_line INTEGER,
                byte_start INTEGER,
                byte_end INTEGER,
                parent_context TEXT,
                content TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_file_path ON chunks(file_path)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_node_type ON chunks(node_type)
        ''')
        
        # Insert chunks
        for chunk in chunks:
            cursor.execute('''
                INSERT OR REPLACE INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                chunk.chunk_id,
                chunk.language,
                chunk.file_path,
                chunk.node_type,
                chunk.start_line,
                chunk.end_line,
                chunk.byte_start,
                chunk.byte_end,
                chunk.parent_context,
                chunk.content
            ))
        
        conn.commit()
        conn.close()
```

## Integration Examples

### Elasticsearch Integration

```python
from elasticsearch import Elasticsearch, helpers
from chunker import chunk_directory_parallel

def index_to_elasticsearch(directory, language, es_host="localhost:9200"):
    """Index chunks to Elasticsearch."""
    es = Elasticsearch([es_host])
    
    # Create index with mapping
    es.indices.create(
        index="code_chunks",
        body={
            "mappings": {
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "language": {"type": "keyword"},
                    "file_path": {"type": "keyword"},
                    "node_type": {"type": "keyword"},
                    "content": {"type": "text"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"}
                }
            }
        },
        ignore=400  # Ignore if exists
    )
    
    # Process chunks
    results = chunk_directory_parallel(directory, language)
    
    # Prepare bulk actions
    actions = []
    for file_path, chunks in results.items():
        for chunk in chunks:
            actions.append({
                "_index": "code_chunks",
                "_id": chunk.chunk_id,
                "_source": {
                    "chunk_id": chunk.chunk_id,
                    "language": chunk.language,
                    "file_path": chunk.file_path,
                    "node_type": chunk.node_type,
                    "content": chunk.content,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line
                }
            })
    
    # Bulk index
    helpers.bulk(es, actions)
    print(f"Indexed {len(actions)} chunks")
```

### Vector Database Integration

```python
import chromadb
from chunker import chunk_file

def export_to_chroma(chunks, collection_name="code_chunks"):
    """Export chunks to ChromaDB for semantic search."""
    # Initialize ChromaDB
    client = chromadb.Client()
    collection = client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )
    
    # Prepare data
    documents = []
    metadatas = []
    ids = []
    
    for chunk in chunks:
        # Create searchable document
        doc = f"{chunk.node_type} in {chunk.file_path}\n{chunk.content}"
        documents.append(doc)
        
        # Metadata for filtering
        metadatas.append({
            "language": chunk.language,
            "file_path": chunk.file_path,
            "node_type": chunk.node_type,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line
        })
        
        ids.append(chunk.chunk_id)
    
    # Add to collection
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    
    return collection
```

### Data Pipeline Integration

```python
from chunker import chunk_file_streaming
from chunker.export import JSONLExporter
import apache_beam as beam

class ChunkToDict(beam.DoFn):
    """Convert chunk to dictionary for Beam."""
    def process(self, chunk):
        yield {
            'chunk_id': chunk.chunk_id,
            'language': chunk.language,
            'file_path': chunk.file_path,
            'node_type': chunk.node_type,
            'content': chunk.content,
            'metrics': {
                'lines': chunk.end_line - chunk.start_line + 1,
                'bytes': chunk.byte_end - chunk.byte_start
            }
        }

def create_beam_pipeline(input_files, language):
    """Create Apache Beam pipeline for chunk processing."""
    with beam.Pipeline() as p:
        chunks = (
            p
            | 'Read Files' >> beam.Create(input_files)
            | 'Extract Chunks' >> beam.FlatMap(
                lambda f: chunk_file_streaming(f, language)
            )
            | 'Convert to Dict' >> beam.ParDo(ChunkToDict())
            | 'Write to Parquet' >> beam.io.WriteToParquet(
                'output/chunks',
                schema=beam.io.parquetio.FastAvroSchema({
                    'chunk_id': 'string',
                    'language': 'string',
                    'file_path': 'string',
                    'node_type': 'string',
                    'content': 'string',
                    'metrics': {
                        'lines': 'int',
                        'bytes': 'long'
                    }
                })
            )
        )
```

## See Also

- [API Reference](api-reference.md) - Export API documentation
- [User Guide](user-guide.md) - Basic export examples
- [Performance Guide](performance-guide.md) - Export performance tips
- [Configuration](configuration.md) - Export configuration options
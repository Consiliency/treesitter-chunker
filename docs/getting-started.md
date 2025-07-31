# Getting Started with Tree-sitter Chunker

Welcome to Tree-sitter Chunker! This tutorial will guide you through installation, basic usage, and your first code chunking project. By the end, you'll be confidently chunking code and building useful tools.

## What is Tree-sitter Chunker?

Tree-sitter Chunker intelligently splits source code into semantic chunks like functions, classes, and methods. Unlike simple line-based splitting, it understands code structure, making it perfect for:

- Building code search systems
- Creating embeddings for AI/ML applications
- Generating documentation
- Analyzing code structure and complexity

## Prerequisites

- Python 3.8 or higher
- Basic command line familiarity
- A C compiler (for building grammars)
- Git (for fetching grammar repositories)

## Installation

### Step 1: Set Up Environment

We recommend using `uv` for package management:

```bash
# Install uv (if not already installed)
pip install uv

# Create a new project directory
mkdir my-chunker-project
cd my-chunker-project

# Create virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Step 2: Install Tree-sitter Chunker

```bash
# Clone the repository
git clone https://github.com/yourusername/treesitter-chunker.git
cd treesitter-chunker

# Install in development mode
uv pip install -e ".[dev]"

# Install py-tree-sitter with ABI 15 support
uv pip install git+https://github.com/tree-sitter/py-tree-sitter.git
```

### Step 3: Build Language Support

```bash
# Fetch grammar repositories
python scripts/fetch_grammars.py

# Compile grammars (this takes a minute)
python scripts/build_lib.py

# Verify installation
python -c "from chunker.parser import list_languages; print(list_languages())"
# Should output: ['c', 'cpp', 'javascript', 'python', 'rust']
```

## Your First Chunking Project

### Step 1: Create Sample Code

Let's create a Python file to analyze:

```python
# save as example.py
"""Example module for demonstrating code chunking."""

class DataProcessor:
    """Process data with various transformations."""
    
    def __init__(self, data):
        self.data = data
        self.results = []
    
    def clean_data(self):
        """Remove invalid entries from data."""
        self.data = [item for item in self.data if self.validate(item)]
        return self.data
    
    def validate(self, item):
        """Check if an item is valid."""
        return item is not None and len(str(item)) > 0
    
    def transform(self, func):
        """Apply a transformation function to all data."""
        self.results = [func(item) for item in self.data]
        return self.results

def process_numbers(numbers):
    """Process a list of numbers."""
    processor = DataProcessor(numbers)
    processor.clean_data()
    return processor.transform(lambda x: x * 2)

def main():
    """Main entry point."""
    test_data = [1, 2, None, 4, 5, ""]
    result = process_numbers(test_data)
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
```

### Step 2: Chunk with CLI

```bash
# Basic chunking - see the structure
python cli/main.py chunk example.py -l python

# Output:
# ┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
# ┃ Chunk# ┃ Node Type            ┃ Lines    ┃ Parent Context       ┃
# ┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
# │ 1      │ class_definition     │ 3-21     │                      │
# │ 2      │ function_definition  │ 6-8      │ class:DataProcessor  │
# │ 3      │ function_definition  │ 10-13    │ class:DataProcessor  │
# │ 4      │ function_definition  │ 15-17    │ class:DataProcessor  │
# │ 5      │ function_definition  │ 19-22    │ class:DataProcessor  │
# │ 6      │ function_definition  │ 24-28    │                      │
# │ 7      │ function_definition  │ 30-34    │                      │
# └────────┴──────────────────────┴──────────┴──────────────────────┘

# Get JSON output for programmatic use
python cli/main.py chunk example.py -l python --json > chunks.json
```

### Step 3: Use the Python API

Create a Python script to analyze the chunks:

```python
# save as analyze_chunks.py
from chunker.chunker import chunk_file
from chunker.parser import list_languages, get_language_info

# Check available languages
print("Available languages:", list_languages())

# Get language info
info = get_language_info("python")
print(f"\nPython language info:")
print(f"  ABI Version: {info.version}")
print(f"  Node types: {info.node_types_count}")
print(f"  Has scanner: {info.has_scanner}")

# Chunk the file
chunks = chunk_file("example.py", "python")

print(f"\nFound {len(chunks)} chunks:")
print("-" * 50)

for i, chunk in enumerate(chunks, 1):
    print(f"\nChunk {i}: {chunk.node_type}")
    print(f"  Location: lines {chunk.start_line}-{chunk.end_line}")
    print(f"  Parent: {chunk.parent_context or 'module level'}")
    
    # Show first line of content
    first_line = chunk.content.split('\n')[0]
    print(f"  Signature: {first_line}")
    
    # Extract docstring if present
    lines = chunk.content.split('\n')
    for line in lines[1:3]:
        if '"""' in line:
            print(f"  Docstring: {line.strip()}")
            break
```

Run it:
```bash
python analyze_chunks.py
```

## Building Useful Tools

### Tool 1: Function Extractor

Extract all functions with their metadata:

```python
# save as extract_functions.py
from chunker.chunker import chunk_file
from pathlib import Path
import json

def extract_functions(file_path, language):
    """Extract all functions from a source file."""
    chunks = chunk_file(file_path, language)
    
    functions = []
    for chunk in chunks:
        if "function" in chunk.node_type or "method" in chunk.node_type:
            # Extract function name from first line
            first_line = chunk.content.split('\n')[0]
            
            # Extract docstring
            docstring = None
            lines = chunk.content.split('\n')
            for i, line in enumerate(lines[1:], 1):
                if '"""' in line or "'''" in line:
                    # Simple single-line docstring
                    if line.count('"""') == 2 or line.count("'''") == 2:
                        docstring = line.strip().strip('"""').strip("'''")
                    break
            
            functions.append({
                "name": first_line.strip(),
                "type": chunk.node_type,
                "file": chunk.file_path,
                "lines": [chunk.start_line, chunk.end_line],
                "parent": chunk.parent_context,
                "docstring": docstring,
                "size": chunk.end_line - chunk.start_line + 1
            })
    
    return functions

# Extract from our example
functions = extract_functions("example.py", "python")

print("Functions found:")
print(json.dumps(functions, indent=2))

# Find complex functions
complex_functions = [f for f in functions if f["size"] > 10]
if complex_functions:
    print("\nComplex functions (>10 lines):")
    for f in complex_functions:
        print(f"  - {f['name']} ({f['size']} lines)")
```

### Tool 2: Code Structure Analyzer

Analyze the structure of your codebase:

```python
# save as analyze_structure.py
from chunker.chunker import chunk_file
from collections import defaultdict
import statistics

def analyze_file_structure(file_path, language):
    """Analyze code structure and complexity."""
    chunks = chunk_file(file_path, language)
    
    # Collect metrics
    metrics = {
        "total_chunks": len(chunks),
        "by_type": defaultdict(int),
        "sizes": [],
        "nesting_levels": defaultdict(list),
        "top_level": 0,
        "nested": 0
    }
    
    for chunk in chunks:
        # Count by type
        metrics["by_type"][chunk.node_type] += 1
        
        # Track sizes
        size = chunk.end_line - chunk.start_line + 1
        metrics["sizes"].append(size)
        
        # Track nesting
        if chunk.parent_context:
            metrics["nested"] += 1
            parent_type = chunk.parent_context.split(':')[0]
            metrics["nesting_levels"][parent_type].append(chunk.node_type)
        else:
            metrics["top_level"] += 1
    
    # Calculate statistics
    if metrics["sizes"]:
        metrics["avg_size"] = statistics.mean(metrics["sizes"])
        metrics["median_size"] = statistics.median(metrics["sizes"])
        metrics["max_size"] = max(metrics["sizes"])
        metrics["min_size"] = min(metrics["sizes"])
    
    return metrics

# Analyze our example
metrics = analyze_file_structure("example.py", "python")

print("Code Structure Analysis")
print("=" * 40)
print(f"Total chunks: {metrics['total_chunks']}")
print(f"Top-level: {metrics['top_level']}")
print(f"Nested: {metrics['nested']}")

print("\nChunk types:")
for chunk_type, count in metrics["by_type"].items():
    print(f"  {chunk_type}: {count}")

print("\nSize statistics:")
print(f"  Average: {metrics.get('avg_size', 0):.1f} lines")
print(f"  Median: {metrics.get('median_size', 0):.1f} lines")
print(f"  Range: {metrics.get('min_size', 0)}-{metrics.get('max_size', 0)} lines")

print("\nNesting:")
for parent, children in metrics["nesting_levels"].items():
    print(f"  {parent} contains: {len(children)} nested chunks")
```

### Tool 3: Multi-File Code Index

Build a searchable index across multiple files:

```python
# save as build_index.py
from chunker.chunker import chunk_file
from chunker.exceptions import LanguageNotFoundError
from pathlib import Path
import json

class CodeIndex:
    """Build and search a code index."""
    
    def __init__(self):
        self.index = []
        self.language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.rs': 'rust',
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp'
        }
    
    def add_file(self, file_path):
        """Add a file to the index."""
        path = Path(file_path)
        ext = path.suffix.lower()
        
        if ext not in self.language_map:
            return False
        
        language = self.language_map[ext]
        
        try:
            chunks = chunk_file(str(path), language)
            
            for chunk in chunks:
                # Extract identifier from first line
                first_line = chunk.content.split('\n')[0]
                
                entry = {
                    'file': str(path),
                    'language': language,
                    'type': chunk.node_type,
                    'identifier': self._extract_identifier(first_line, language),
                    'signature': first_line.strip(),
                    'lines': [chunk.start_line, chunk.end_line],
                    'parent': chunk.parent_context,
                    'size': chunk.end_line - chunk.start_line + 1
                }
                self.index.append(entry)
                
            return True
            
        except LanguageNotFoundError:
            print(f"Language not supported for {file_path}")
            return False
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return False
    
    def _extract_identifier(self, line, language):
        """Extract function/class name from first line."""
        import re
        
        patterns = {
            'python': r'(?:def|class)\s+(\w+)',
            'javascript': r'(?:function|class|const|let|var)\s+(\w+)',
            'rust': r'(?:fn|struct|impl|trait)\s+(\w+)',
            'c': r'(?:\w+\s+)?(\w+)\s*\(',
            'cpp': r'(?:class|struct|(?:\w+\s+)?(\w+)\s*\()'
        }
        
        pattern = patterns.get(language, r'(\w+)')
        match = re.search(pattern, line)
        return match.group(1) if match else line.split()[0]
    
    def add_directory(self, directory, recursive=True):
        """Add all supported files in a directory."""
        path = Path(directory)
        pattern = '**/*' if recursive else '*'
        
        files_added = 0
        for file_path in path.glob(pattern):
            if file_path.is_file() and self.add_file(file_path):
                files_added += 1
        
        return files_added
    
    def search(self, query, search_in='identifier'):
        """Search the index."""
        results = []
        query_lower = query.lower()
        
        for entry in self.index:
            if query_lower in entry[search_in].lower():
                results.append(entry)
        
        return results
    
    def save(self, filename):
        """Save index to JSON file."""
        with open(filename, 'w') as f:
            json.dump(self.index, f, indent=2)
    
    def load(self, filename):
        """Load index from JSON file."""
        with open(filename, 'r') as f:
            self.index = json.load(f)

# Build index
index = CodeIndex()

# Add current directory
files_added = index.add_directory(".", recursive=False)
print(f"Added {files_added} files to index")
print(f"Total chunks indexed: {len(index.index)}")

# Search examples
print("\nSearch results for 'process':")
results = index.search("process")
for r in results:
    print(f"  {r['file']}:{r['lines'][0]} - {r['identifier']} ({r['type']})")

print("\nSearch results for 'data':")
results = index.search("data")
for r in results:
    print(f"  {r['file']}:{r['lines'][0]} - {r['identifier']} ({r['type']})")

# Save index
index.save("code_index.json")
print("\nIndex saved to code_index.json")
```

## Using New Features

### Plugin System

Tree-sitter Chunker now includes a plugin system for language support:

```python
# save as use_plugins.py
from chunker.plugin_manager import get_plugin_manager
from chunker.core import chunk_file

# Load built-in plugins
manager = get_plugin_manager()
manager.load_built_in_plugins()

# List available plugins
print("Available plugins:", manager.list_plugins())
# Output: ['python', 'javascript', 'rust', 'c', 'cpp']

# Chunk with plugins loaded
chunks = chunk_file("example.py", "python")
print(f"Chunked {len(chunks)} items with plugin support")
```

### Parallel Processing

Process multiple files in parallel for better performance:

```python
# save as parallel_processing.py
from chunker.parallel import chunk_files_parallel, chunk_directory_parallel
from pathlib import Path

# Create some test files
test_files = ["example.py", "analyze_chunks.py", "extract_functions.py"]

# Process files in parallel
results = chunk_files_parallel(
    test_files,
    "python",
    max_workers=4,
    show_progress=True
)

print(f"\nProcessed {len(results)} files:")
for file_path, chunks in results.items():
    print(f"  {file_path}: {len(chunks)} chunks")

# Process entire directory
if Path("src").exists():
    dir_results = chunk_directory_parallel(
        "src/",
        "python",
        pattern="**/*.py",
        max_workers=4
    )
    print(f"\nDirectory processing: {len(dir_results)} files")
```

### Export Formats

Export chunks in different formats:

```python
# save as export_chunks.py
from chunker.core import chunk_file
from chunker.export.json_export import JSONExporter, JSONLExporter
from chunker.export.formatters import SchemaType
from chunker.exporters import ParquetExporter

# Get chunks
chunks = chunk_file("example.py", "python")

# Export to JSON with nested schema
json_exporter = JSONExporter(schema_type=SchemaType.NESTED)
json_exporter.export(chunks, "chunks_nested.json", indent=2)

# Export to JSONL for streaming
jsonl_exporter = JSONLExporter()
jsonl_exporter.export(chunks, "chunks.jsonl")

# Export to Parquet for analytics
parquet_exporter = ParquetExporter(compression="snappy")
parquet_exporter.export(chunks, "chunks.parquet")

print("Exported to:")
print("  - chunks_nested.json (nested hierarchy)")
print("  - chunks.jsonl (streaming format)")
print("  - chunks.parquet (columnar format)")
```

### Configuration Files

Use configuration files to customize behavior:

```bash
# Create a configuration file
cat > .chunkerrc << 'EOF'
# Tree-sitter Chunker Configuration

# Global settings
min_chunk_size = 3
max_chunk_size = 300

# Plugin directories
plugin_dirs = ["./plugins"]

# Language-specific settings
[languages.python]
chunk_types = ["function_definition", "class_definition", "async_function_definition"]
min_chunk_size = 5

[languages.javascript]
chunk_types = ["function_declaration", "arrow_function", "class_declaration"]
include_jsx = true
EOF

# Use with CLI
python cli/main.py chunk example.py -l python --config .chunkerrc
```

## Working with Different Languages

Let's create examples in multiple languages:

```bash
# Create a JavaScript example
cat > example.js << 'EOF'
class Calculator {
    constructor() {
        this.result = 0;
    }
    
    add(a, b) {
        return a + b;
    }
    
    multiply(a, b) {
        return a * b;
    }
}

const calculate = (operation, a, b) => {
    const calc = new Calculator();
    switch(operation) {
        case 'add': return calc.add(a, b);
        case 'multiply': return calc.multiply(a, b);
        default: throw new Error('Unknown operation');
    }
};
EOF

# Create a Rust example
cat > example.rs << 'EOF'
struct Calculator {
    result: f64,
}

impl Calculator {
    fn new() -> Self {
        Calculator { result: 0.0 }
    }
    
    fn add(&self, a: f64, b: f64) -> f64 {
        a + b
    }
    
    fn multiply(&self, a: f64, b: f64) -> f64 {
        a * b
    }
}

fn calculate(operation: &str, a: f64, b: f64) -> Result<f64, String> {
    let calc = Calculator::new();
    match operation {
        "add" => Ok(calc.add(a, b)),
        "multiply" => Ok(calc.multiply(a, b)),
        _ => Err("Unknown operation".to_string()),
    }
}
EOF
```

Now analyze all three languages:

```python
# save as compare_languages.py
from chunker.chunker import chunk_file

files = [
    ("example.py", "python"),
    ("example.js", "javascript"),
    ("example.rs", "rust")
]

for file_path, language in files:
    print(f"\n{'='*50}")
    print(f"Analyzing {file_path} ({language})")
    print('='*50)
    
    chunks = chunk_file(file_path, language)
    
    # Group by type
    by_type = {}
    for chunk in chunks:
        by_type.setdefault(chunk.node_type, []).append(chunk)
    
    # Display summary
    print(f"Total chunks: {len(chunks)}")
    for node_type, items in sorted(by_type.items()):
        print(f"\n{node_type} ({len(items)}):")
        for item in items:
            first_line = item.content.split('\n')[0].strip()
            if item.parent_context:
                print(f"  - {first_line} [in {item.parent_context}]")
            else:
                print(f"  - {first_line}")
```

## Best Practices

### 1. Handle Errors Gracefully

```python
from chunker.chunker import chunk_file
from chunker.exceptions import LanguageNotFoundError, ChunkerError

def safe_chunk_file(file_path, language):
    """Safely chunk a file with error handling."""
    try:
        return chunk_file(file_path, language)
    except LanguageNotFoundError as e:
        print(f"Language '{language}' not supported. Available: {e}")
        return []
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return []
    except ChunkerError as e:
        print(f"Chunking error: {e}")
        return []
```

### 2. Use Type Hints

```python
from typing import List, Dict, Optional
from chunker.chunker import CodeChunk

def analyze_chunks(chunks: List[CodeChunk]) -> Dict[str, int]:
    """Analyze chunks and return statistics."""
    stats: Dict[str, int] = {}
    for chunk in chunks:
        stats[chunk.node_type] = stats.get(chunk.node_type, 0) + 1
    return stats
```

### 3. Process Large Codebases Efficiently

```python
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

def process_codebase(root_dir: str, max_workers: int = 4):
    """Process a large codebase in parallel."""
    from chunker.chunker import chunk_file
    
    # Collect all Python files
    py_files = list(Path(root_dir).rglob("*.py"))
    
    def process_file(file_path):
        try:
            return chunk_file(str(file_path), "python")
        except Exception as e:
            print(f"Error in {file_path}: {e}")
            return []
    
    # Process in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_file, py_files))
    
    # Flatten results
    all_chunks = []
    for chunks in results:
        all_chunks.extend(chunks)
    
    return all_chunks
```

## Next Steps

You've now learned the basics of Tree-sitter Chunker! Here's what to explore next:

1. **[User Guide](user-guide.md)** - Comprehensive documentation including plugins and performance
2. **[API Reference](api-reference.md)** - Detailed documentation of all 27 exported APIs
3. **[Plugin Development](plugin-development.md)** - Create custom language plugins
4. **[Configuration](configuration.md)** - Advanced configuration options
5. **[Performance Guide](performance-guide.md)** - Optimization strategies
6. **[Export Formats](export-formats.md)** - Working with different output formats
7. **[Cookbook](cookbook.md)** - Advanced recipes and examples
8. **[Architecture](architecture.md)** - Understanding the internals

## Quick Reference Card

```python
# Import
from chunker.core import chunk_file
from chunker.parallel import chunk_files_parallel, chunk_directory_parallel
from chunker.streaming import chunk_file_streaming
from chunker.plugin_manager import get_plugin_manager
from chunker.cache import ASTCache
from chunker.chunker_config import ChunkerConfig
from chunker.types import CodeChunk
from chunker.parser import get_parser, list_languages
from chunker.export.json_export import JSONExporter, JSONLExporter
from chunker.export.formatters import SchemaType
from chunker.exporters.parquet import ParquetExporter

# Basic chunking
chunks = chunk_file("file.py", "python")

# Parallel processing
results = chunk_files_parallel(["file1.py", "file2.py"], "python")
dir_results = chunk_directory_parallel("src/", "python", pattern="**/*.py")

# Streaming for large files
for chunk in chunk_file_streaming("huge_file.py", "python"):
    process(chunk)

# Plugin management
manager = get_plugin_manager()
manager.load_built_in_plugins()

# Export formats
exporter = JSONExporter(schema_type=SchemaType.NESTED)
exporter.export(chunks, "output.json")

parquet = ParquetExporter(compression="snappy")
parquet.export(chunks, "output.parquet")

# Configuration
config = ChunkerConfig(".chunkerrc")

# Available languages
languages = list_languages()  # ['c', 'cpp', 'javascript', 'python', 'rust']

# Chunk properties
chunk.language       # Programming language
chunk.file_path      # Source file path  
chunk.node_type      # e.g., "function_definition"
chunk.start_line     # Starting line (1-indexed)
chunk.end_line       # Ending line
chunk.byte_start     # Starting byte offset
chunk.byte_end       # Ending byte offset
chunk.parent_context # e.g., "class:MyClass"
chunk.content        # Actual source code
chunk.chunk_id       # Unique identifier

# CLI usage
# python cli/main.py chunk <file> -l <language> [options]
# Options: --json, --jsonl, --config, --parallel, --progress

# Common patterns
functions = [c for c in chunks if "function" in c.node_type]
classes = [c for c in chunks if c.node_type == "class_definition"]
methods = [c for c in chunks if c.parent_context]
large_functions = [c for c in chunks if c.end_line - c.start_line > 50]
```

Happy chunking! 🚀
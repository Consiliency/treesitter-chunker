# Custom Chunking Rules

This implementation adds custom chunking rules that extend Tree-sitter's capabilities by extracting chunks that Tree-sitter might miss.

## Overview

The custom rules system provides:
- **Regex-based chunk boundaries** to complement Tree-sitter's AST-based chunking
- **Comment block chunking** with language-specific handling
- **File-level metadata chunks** 
- **Project-specific rule definitions** through extensible base classes
- **Rule composition and priority system** for conflict resolution

## Architecture

### Core Components

1. **Base Rule Classes** (`chunker/rules/custom.py`)
   - `BaseCustomRule`: Abstract base for all custom rules
   - `BaseRegexRule`: Base for regex-based pattern matching
   - `BaseCommentBlockRule`: Base for comment extraction
   - `MetadataRule`: Extracts file metadata

2. **Rule Engine** (`chunker/rules/engine.py`)
   - `DefaultRuleEngine`: Executes rules with priority handling
   - Manages rule registration and removal
   - Handles overlap detection and merging with Tree-sitter chunks
   - Supports both node-based and cross-boundary regex rules

3. **Built-in Rules** (`chunker/rules/builtin.py`)
   - `TodoCommentRule`: Extracts TODO/FIXME/HACK/NOTE comments
   - `CopyrightHeaderRule`: Finds copyright and license headers
   - `DocstringRule`: Extracts documentation strings
   - `ImportBlockRule`: Groups import statements
   - `CustomMarkerRule`: Finds custom CHUNK_START/CHUNK_END regions
   - `SectionHeaderRule`: Extracts section markers in comments
   - `ConfigurationBlockRule`: Finds embedded config in comments
   - `LanguageSpecificCommentRule`: Language-aware comment handling
   - `DebugStatementRule`: Finds debug print/log statements
   - `TestAnnotationRule`: Extracts test markers and annotations

## Usage

### Basic Usage

```python
from chunker import DefaultRuleEngine, get_builtin_rules, get_parser

# Create rule engine with built-in rules
engine = DefaultRuleEngine()
for rule in get_builtin_rules():
    engine.add_rule(rule)

# Parse a file
parser = get_parser("python")
with open("example.py", "rb") as f:
    source = f.read()
tree = parser.parse(source)

# Apply custom rules
custom_chunks = engine.apply_rules(tree, source, "example.py")

# Or get only regex-based chunks
regex_chunks = engine.apply_regex_rules(source, "example.py")
```

### Creating Custom Rules

```python
from chunker.rules.custom import BaseRegexRule

class SecurityAlertRule(BaseRegexRule):
    """Extract security-related comments."""
    
    def __init__(self, priority: int = 100):
        super().__init__(
            name="security_alerts",
            description="Extract SECURITY and VULNERABLE markers",
            pattern=r'(?:#|//)\s*(SECURITY|VULNERABLE|INSECURE):\s*(.+)',
            priority=priority,
            cross_boundaries=True
        )

# Add to engine
engine.add_rule(SecurityAlertRule())
```

### Merging with Tree-sitter Chunks

```python
# Get Tree-sitter chunks
from chunker import chunk_file
ts_chunks = chunk_file("example.py", "python")

# Merge with custom chunks
merged = engine.merge_with_tree_sitter_chunks(custom_chunks, ts_chunks)
```

## Rule Types

### Node-Based Rules
- Work within Tree-sitter node boundaries
- Can access node type, parent context
- Example: Comment blocks, metadata

### Cross-Boundary Regex Rules
- Can match patterns across multiple nodes
- Work on raw text
- Example: TODO comments, import blocks

### Priority System
- Higher priority rules take precedence in overlaps
- Default priorities:
  - Metadata: 100
  - Copyright: 90
  - Custom markers: 80
  - Import blocks: 70
  - Docstrings: 60
  - TODO comments: 50
  - Section headers: 40

## Testing

Run tests with:
```bash
python -m pytest tests/test_custom_rules.py -v
```

All 26 tests should pass, covering:
- Base rule implementations
- All built-in rules
- Rule engine functionality
- Priority ordering
- Overlap handling
- Tree-sitter integration

## Example Output

Given this Python code:
```python
# TODO: Add OAuth support
# FIXME: Security issue

class UserAuth:
    """Handle authentication."""
    pass
```

Custom rules will find:
- TODO comment at line 1
- FIXME comment at line 2
- Docstring at line 5
- File metadata chunk

While Tree-sitter finds:
- class_definition at lines 4-6

The system merges both for comprehensive code understanding.
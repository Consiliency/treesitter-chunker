# Custom Chunking Rules

The custom rules module extends Tree-sitter's AST-based chunking with pattern-based and semantic chunking capabilities. This allows you to define custom boundaries for code chunks based on comments, markers, patterns, and other heuristics.

## Overview

Custom rules complement Tree-sitter chunking by:
- Extracting semantically meaningful sections (e.g., TODO blocks, copyright headers)
- Finding pattern-based boundaries (e.g., #region/#endregion markers)
- Grouping related content (e.g., inline comment groups)
- Adding file-level metadata chunks

## Architecture

### Core Components

1. **Rule Engine** (`engine.py`)
   - Manages rule registration and execution
   - Handles priority-based rule application
   - Merges custom chunks with Tree-sitter chunks
   - Resolves conflicts between overlapping rules

2. **Base Rules** (`custom.py`)
   - `BaseCustomRule`: Abstract base for all custom rules
   - `BaseRegexRule`: Base for pattern-matching rules
   - `BaseCommentBlockRule`: Base for comment extraction rules
   - `MetadataRule`: Extracts file-level metadata

3. **Regex Rules** (`regex.py`)
   - `RegionMarkerRule`: Extract #region/#endregion blocks
   - `PatternBoundaryRule`: Custom regex boundaries
   - `AnnotationRule`: Extract @chunk annotated code
   - `FoldingMarkerRule`: Editor folding markers
   - `SeparatorLineRule`: Line-based separators

4. **Comment Rules** (`comment.py`)
   - `TodoBlockRule`: TODO/FIXME blocks with context
   - `DocumentationBlockRule`: Docstrings and JSDoc
   - `HeaderCommentRule`: File headers (copyright, license)
   - `InlineCommentGroupRule`: Group related comments
   - `StructuredCommentRule`: Comments with tables/lists

5. **Built-in Rules** (`builtin.py`)
   - Pre-configured rules for common patterns
   - Language-aware comment handling
   - Debug statement extraction
   - Test annotation detection

## Usage

### Basic Example

```python
from chunker.parser import get_parser
from chunker.rules import DefaultRuleEngine, TodoCommentRule, RegionMarkerRule

# Create rule engine
engine = DefaultRuleEngine()

# Add rules with priorities
engine.add_rule(TodoCommentRule(priority=60))
engine.add_rule(RegionMarkerRule(priority=80))

# Parse code
parser = get_parser("python")
tree = parser.parse(source_code)

# Apply rules
custom_chunks = engine.apply_rules(tree, source_code, "example.py")

# Merge with Tree-sitter chunks
all_chunks = engine.merge_with_tree_sitter_chunks(custom_chunks, ts_chunks)
```

### Creating Custom Rules

#### Simple Regex Rule

```python
from chunker.rules.regex import create_custom_regex_rule

# Extract sections marked with specific comments
section_rule = create_custom_regex_rule(
    name="sections",
    pattern=r"#\s*SECTION:\s*(.+)",
    description="Extract marked sections",
    priority=70
)

engine.add_rule(section_rule)
```

#### Custom Comment Rule

```python
from chunker.rules.comment import BaseCommentBlockRule

class ReviewCommentRule(BaseCommentBlockRule):
    """Extract code review comments."""
    
    def __init__(self):
        super().__init__(
            name="review_comments",
            description="Extract review comments",
            priority=65
        )
    
    def get_comment_markers(self):
        return {
            'single_line': ['#', '//'],
            'block_start': ['/*'],
            'block_end': ['*/']
        }
    
    def matches(self, node, source):
        if not super().matches(node, source):
            return False
        
        content = source[node.start_byte:node.end_byte].decode('utf-8')
        return '@review' in content.lower()
```

#### Complex Pattern Rule

```python
from chunker.rules import BaseRegexRule

class TestCaseRule(BaseRegexRule):
    """Extract test case definitions."""
    
    def __init__(self):
        super().__init__(
            name="test_cases",
            description="Extract test case blocks",
            pattern=r"(def\s+test_\w+.*?(?=\n(?:def|class|\Z)))",
            priority=75,
            cross_boundaries=True,
            multiline=True
        )
```

### Rule Priorities

Higher priority rules are executed first. Recommended ranges:
- 90-100: File metadata and headers
- 70-89: Structural markers (regions, sections)
- 50-69: Semantic comments (TODO, documentation)
- 30-49: General patterns
- 10-29: Low-priority fallbacks

### Rule Composition

Rules can be composed and chained:

```python
from chunker.rules.comment import (
    create_comment_rule_chain,
    TodoBlockRule,
    HeaderCommentRule,
    DocumentationBlockRule
)

# Create a chain of comment rules sorted by priority
comment_rules = create_comment_rule_chain(
    TodoBlockRule(priority=50),
    HeaderCommentRule(priority=90),
    DocumentationBlockRule(priority=70)
)

for rule in comment_rules:
    engine.add_rule(rule)
```

## Advanced Features

### Context-Aware Extraction

```python
# Extract TODO comments with surrounding context
todo_rule = TodoBlockRule(
    keywords=['TODO', 'FIXME', 'HACK'],
    include_context_lines=3  # Include 3 lines before/after
)
```

### Pattern Boundaries

```python
# Extract content between specific patterns
boundary_rule = PatternBoundaryRule(
    name="test_sections",
    pattern=r"^###\s*TEST\s*###$",
    extract_match_only=False,  # Extract between matches
    priority=60
)
```

### Language-Specific Rules

```python
class PythonDecoratorRule(BaseRegexRule):
    """Extract decorated functions/classes."""
    
    def __init__(self):
        super().__init__(
            name="python_decorators",
            pattern=r"(@\w+(?:\(.*?\))?\s*\n)+(?:def|class)\s+\w+",
            priority=65
        )
```

## Integration with Tree-sitter

Custom rules work alongside Tree-sitter chunking:

1. Tree-sitter provides structural chunks (functions, classes)
2. Custom rules add semantic chunks (TODOs, regions)
3. The engine merges both, handling overlaps intelligently
4. Tree-sitter chunks take precedence in conflicts

## Performance Considerations

- Rules are sorted by priority and executed in order
- Use `cross_boundaries=False` for better performance when possible
- Regex compilation happens once during rule creation
- The engine tracks processed ranges to avoid duplicates

## Testing

See `tests/test_custom_rules.py` for comprehensive examples:
- Basic rule functionality
- Priority ordering
- Overlap handling
- Rule composition
- Language-specific features

## Built-in Rules Reference

| Rule | Description | Default Priority |
|------|-------------|------------------|
| MetadataRule | File metadata | 100 |
| CopyrightHeaderRule | Copyright/license headers | 90 |
| HeaderCommentRule | File header comments | 85 |
| RegionMarkerRule | #region/#endregion blocks | 80 |
| SectionHeaderRule | Section dividers | 40 |
| ImportBlockRule | Import statements | 70 |
| DocstringRule | Documentation strings | 60 |
| TodoCommentRule | TODO/FIXME comments | 50 |
| DebugStatementRule | Debug prints/logs | 10 |
| TestAnnotationRule | Test markers | 35 |

## Examples

See `examples/custom_rules_demo.py` for a complete working example.
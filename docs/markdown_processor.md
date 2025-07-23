# Markdown Processor

The Markdown Processor is a specialized component of the tree-sitter-chunker that intelligently handles Markdown files while preserving document structure and formatting.

## Overview

The MarkdownProcessor provides intelligent chunking for Markdown documents by recognizing headers, code blocks, lists, tables, and other Markdown elements. It ensures that the chunked output maintains the document's logical structure and readability.

## Features

### Header-Aware Chunking
- Recognizes header hierarchy (# through ######)
- Groups content under headers
- Preserves document outline structure
- Supports both ATX and Setext style headers

### Code Block Preservation
- Keeps fenced code blocks intact
- Preserves language specifications
- Maintains indented code blocks
- Handles nested code in lists

### List Continuity
- Groups list items intelligently
- Preserves nested list structures
- Maintains numbering in ordered lists
- Handles mixed list types

### Table Integrity
- Keeps tables as single chunks
- Preserves alignment specifications
- Handles multi-line cells
- Maintains header rows

### Special Element Handling
- Front matter (YAML/TOML) preservation
- Blockquote grouping
- Link reference definitions
- Footnote continuity
- HTML block handling

## Usage

### Basic Usage
```python
from chunker.processors.markdown import MarkdownProcessor

processor = MarkdownProcessor()
chunks = processor.process_file("README.md")
```

### With Custom Configuration
```python
from chunker.processors.markdown import MarkdownProcessor, ProcessorConfig

config = ProcessorConfig(
    chunk_size=100,           # Target lines per chunk
    preserve_headers=True,    # Keep headers with content
    group_sections=True,      # Group by header sections
    preserve_code_blocks=True # Keep code blocks intact
)

processor = MarkdownProcessor(config)
chunks = processor.process_file("documentation.md")
```

### Integration with Main Chunker
The MarkdownProcessor is automatically used by the intelligent fallback system:

```python
from chunker import IntelligentFallbackChunker

chunker = IntelligentFallbackChunker()
chunks = chunker.chunk_text(markdown_content, "document.md")
```

## Chunking Strategy

### Section-Based Chunking
The processor uses headers as natural chunk boundaries:

```markdown
# Main Section
Content under main section...

## Subsection 1
Details for subsection 1...

## Subsection 2
Details for subsection 2...
```

Each section becomes a logical chunk, with subsections grouped under their parent headers when appropriate.

### Code Block Handling
Code blocks are never split:

```markdown
## Implementation

Here's how to use the API:

```python
def process_data(input_data):
    # This entire code block stays together
    result = transform(input_data)
    return result
```

Additional explanation...
```

### List Processing
Lists are kept together to maintain context:

```markdown
## Features

- Feature 1
  - Subfeature 1.1
  - Subfeature 1.2
- Feature 2
- Feature 3
```

### Table Preservation
Tables are treated as atomic units:

```markdown
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |
| Data 4   | Data 5   | Data 6   |
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `chunk_size` | int | 100 | Target lines per chunk |
| `preserve_headers` | bool | True | Keep headers with their content |
| `group_sections` | bool | True | Group content by header hierarchy |
| `preserve_code_blocks` | bool | True | Never split code blocks |
| `preserve_tables` | bool | True | Keep tables intact |
| `min_section_size` | int | 5 | Minimum lines for separate section |
| `max_header_depth` | int | 3 | Maximum header depth for grouping |

## Advanced Features

### Front Matter Support
YAML or TOML front matter is preserved as a separate chunk:

```markdown
---
title: "Document Title"
author: "Author Name"
date: 2024-01-23
---

# Main Content
...
```

### Link Reference Handling
Link references are grouped with their usage context:

```markdown
Check out [my website][website] for more information.

[website]: https://example.com "Example Website"
```

### Blockquote Grouping
Multi-line blockquotes are kept together:

```markdown
> This is a long quote that spans
> multiple lines and should be
> kept together as one chunk.
```

## Best Practices

1. **Header Hierarchy**: Use consistent header levels to enable better section grouping.

2. **Code Block Languages**: Always specify language in code blocks for better processing.

3. **List Formatting**: Use consistent indentation for nested lists to ensure proper grouping.

4. **Table Formatting**: Keep tables reasonably sized as they cannot be split.

5. **Section Size**: Balance section sizes to avoid extremely large or small chunks.

## Integration with Phase 11

The MarkdownProcessor is part of Phase 11's text processing capabilities and integrates with:
- Sliding Window Fallback system
- Intelligent Fallback Chunker
- Token limit handling
- Document processing pipeline

## See Also

- [Intelligent Fallback](intelligent_fallback.md) - Automatic processor selection
- [Config Processor](config_processor.md) - Configuration file processing
- [Log Processor](log_processor.md) - Log file processing
- [Token Limits](token_limits.md) - Token-aware chunking
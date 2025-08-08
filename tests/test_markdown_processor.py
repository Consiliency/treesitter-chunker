"""Tests for the Markdown processor.

This module tests the MarkdownProcessor's ability to:
- Parse Markdown structure
- Identify natural boundaries
- Preserve atomic elements (code blocks, tables)
- Handle various Markdown features
- Apply smart chunking with overlap
"""

import pytest

from chunker.processors import ProcessorConfig
from chunker.processors.markdown import MarkdownProcessor
from chunker.types import CodeChunk


class TestMarkdownProcessor:
    """Test suite for MarkdownProcessor."""

    @classmethod
    @pytest.fixture
    def processor(cls):
        """Create a default processor instance."""
        return MarkdownProcessor()

    @classmethod
    @pytest.fixture
    def custom_processor(cls):
        """Create a processor with custom configuration."""
        config = ProcessorConfig(
            max_chunk_size=500,
            min_chunk_size=50,
            overlap_size=50,
            preserve_structure=True,
        )
        return MarkdownProcessor(config)

    @staticmethod
    def test_can_process_markdown_files(processor):
        """Test file type detection."""
        assert processor.can_process("README.md", "# Hello")
        assert processor.can_process("doc.markdown", "# Hello")
        assert processor.can_process("notes.mdown", "# Hello")
        assert processor.can_process("guide.mkd", "# Hello")
        assert processor.can_process("README", "# Hello\n\n## World")
        assert processor.can_process("doc.txt", "```python\ncode\n```")
        assert processor.can_process("notes", "- List item\n- Another item")
        assert not processor.can_process("script.py", "def hello():\n    pass")
        assert not processor.can_process("data.json", '{"key": "value"}')

    @staticmethod
    def test_extract_structure_headers(processor):
        """Test header extraction."""
        content = """# Main Title

## Section 1
Content here.

### Subsection 1.1
More content.

## Section 2
Final content.

#### Deep Section
###### Very Deep Section
"""
        structure = processor.extract_structure(content)
        assert len(structure["headers"]) == 6
        assert structure["headers"][0].level == 1
        assert structure["headers"][0].metadata["title"] == "Main Title"
        assert structure["headers"][1].level == 2
        assert structure["headers"][2].level == 3
        assert structure["headers"][4].level == 4
        assert structure["headers"][5].level == 6
        assert len(structure["toc"]) == 6
        assert structure["toc"][0]["level"] == 1
        assert structure["toc"][0]["title"] == "Main Title"

    @staticmethod
    def test_extract_structure_code_blocks(processor):
        """Test code block extraction."""
        content = """# Code Examples

Here's some Python:

```python
def hello():
    print("Hello, World!")
```

And some JavaScript:

```javascript
console.log("Hello");
```

Inline code `example` should not be extracted.
"""
        structure = processor.extract_structure(content)
        assert len(structure["code_blocks"]) == 2
        assert structure["code_blocks"][0].type == "code_block"
        assert "def hello():" in structure["code_blocks"][0].metadata["code"]
        assert "console.log" in structure["code_blocks"][1].metadata["code"]

    @staticmethod
    def test_extract_structure_tables(processor):
        """Test table extraction."""
        content = """# Data

| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |
| Data 4   | Data 5   | Data 6   |

Another paragraph.

| Name | Age |
|------|-----|
| John | 30  |
"""
        structure = processor.extract_structure(content)
        assert len(structure["tables"]) == 2
        assert structure["tables"][0].type == "table"
        assert "Column 1" in structure["tables"][0].content
        assert "Name" in structure["tables"][1].content

    @staticmethod
    def test_extract_structure_lists(processor):
        """Test list extraction with nesting."""
        content = """# Lists

- Item 1
- Item 2
  - Nested 2.1
  - Nested 2.2
    - Deep nested
- Item 3

1. Ordered item
2. Another ordered
   1. Nested ordered
"""
        structure = processor.extract_structure(content)
        lists = structure["lists"]
        assert len(lists) > 0
        levels = [item.level for item in lists]
        assert 1 in levels
        assert 2 in levels
        assert 3 in levels

    @staticmethod
    def test_extract_structure_front_matter(processor):
        """Test front matter extraction."""
        content = """---
title: My Document
author: John Doe
date: 2024-01-01
---

# Main Content

This is the document.
"""
        structure = processor.extract_structure(content)
        assert structure["front_matter"] is not None
        assert structure["front_matter"].type == "front_matter"
        assert "title: My Document" in structure["front_matter"].metadata["raw"]

    @staticmethod
    def test_find_boundaries_respects_atomic(processor):
        """Test that boundaries respect atomic elements."""
        content = """# Section 1

Paragraph content.

```python
def long_function():
    # This is a very long function
    # that should not be split
    for i in range(100):
        print(i)
    return True
```

More content after code.
"""
        processor.extract_structure(content)
        boundaries = processor.find_boundaries(content)
        code_boundaries = [b for b in boundaries if b[2] == "code_block"]
        assert len(code_boundaries) == 1
        start, end, _ = code_boundaries[0]
        code_content = content[start:end]
        assert code_content.startswith("```python")
        assert code_content.strip().endswith("```")

    @staticmethod
    def test_find_boundaries_header_boundaries(processor):
        """Test that headers create natural boundaries."""
        content = """# Header 1

Content under header 1.

## Header 2

Content under header 2.

### Header 3

Content under header 3.
"""
        processor.extract_structure(content)
        boundaries = processor.find_boundaries(content)
        header_boundaries = [b for b in boundaries if "header" in b[2]]
        assert len(header_boundaries) >= 3

    @staticmethod
    def test_create_chunks_basic(processor):
        """Test basic chunk creation."""
        content = """# Document Title

This is the introduction paragraph with some content.

## Section 1

This section has multiple paragraphs.

Here is the second paragraph with more details.

## Section 2

Final section with content.
"""
        chunks = processor.process(content, "test.md")
        assert len(chunks) > 0
        assert all(isinstance(chunk, CodeChunk) for chunk in chunks)
        chunk_types = [chunk.node_type for chunk in chunks]
        assert any("section" in t for t in chunk_types)

    @classmethod
    def test_create_chunks_preserves_code_blocks(cls, processor):
        """Test that code blocks are never split."""
        content = """# Code Example

Here's a long code block:

```python
def very_long_function_with_many_lines():
    # Line 1
    # Line 2
    # Line 3
    # Line 4
    # Line 5
    # Line 6
    # Line 7
    # Line 8
    # Line 9
    # Line 10
    result = [i * 2 for i in range(100) if i % 2 == 0]        else:
            result.append(i * 3)
    return result
```

Content after code.
"""
        config = ProcessorConfig(max_chunk_size=100)
        processor = MarkdownProcessor(config)
        chunks = processor.process(content, "test.md")
        code_chunks = [c for c in chunks if c.node_type == "code_block"]
        assert len(code_chunks) >= 1
        for chunk in code_chunks:
            assert chunk.content.strip().startswith("```")
            assert chunk.content.strip().endswith("```")

    @classmethod
    def test_create_chunks_preserves_tables(cls, processor):
        """Test that tables are never split."""
        content = """# Data

Here's a table:

| Column A | Column B | Column C | Column D |
|----------|----------|----------|----------|
| Data 1   | Data 2   | Data 3   | Data 4   |
| Data 5   | Data 6   | Data 7   | Data 8   |
| Data 9   | Data 10  | Data 11  | Data 12  |
| Data 13  | Data 14  | Data 15  | Data 16  |

Content after table.
"""
        config = ProcessorConfig(max_chunk_size=50)
        processor = MarkdownProcessor(config)
        chunks = processor.process(content, "test.md")
        table_chunks = [c for c in chunks if c.node_type == "table"]
        assert len(table_chunks) >= 1
        for chunk in table_chunks:
            if "[...]" in chunk.content:
                continue
            lines = chunk.content.strip().split("\n")
            non_empty_lines = [
                line for line in lines if line.strip() and line.strip() != "[...]"
            ]
            assert len(non_empty_lines) >= 3
            assert "|" in non_empty_lines[0]
            assert "|" in non_empty_lines[1]
            assert all("|" in line for line in non_empty_lines[2:] if line.strip())

    @staticmethod
    def test_apply_overlap(custom_processor):
        """Test overlap application between chunks."""
        content = """# Section 1

This is the first section with some content that should be long enough to create multiple chunks when we use a small chunk size.

## Section 2

This is the second section that should be in a different chunk. The overlap from the previous chunk should appear here.

## Section 3

And this is the third section for testing overlap behavior.
"""
        chunks = custom_processor.process(content, "test.md")
        if len(chunks) > 1:
            for i in range(1, len(chunks)):
                chunk = chunks[i]
                if "has_overlap" in chunk.metadata:
                    assert chunk.metadata["has_overlap"]
                    assert "[...]" in chunk.content

    @classmethod
    def test_validate_chunk(cls):
        """Test chunk validation."""
        config = ProcessorConfig(min_chunk_size=10)
        processor = MarkdownProcessor(config)
        valid_chunk = CodeChunk(
            content="# Header\n\nContent here.",
            start_line=1,
            end_line=3,
            node_type="section_h1",
            language="markdown",
            file_path="test.md",
            byte_start=0,
            byte_end=25,
            parent_context="",
            metadata={"tokens": 4},
        )
        assert processor.validate_chunk(valid_chunk)
        short_chunk = CodeChunk(
            content="Hi",
            start_line=1,
            end_line=1,
            node_type="paragraph",
            language="markdown",
            file_path="test.md",
            byte_start=0,
            byte_end=2,
            parent_context="",
            metadata={"tokens": 1},
        )
        assert not processor.validate_chunk(short_chunk)
        bad_code = CodeChunk(
            content="```python\ncode here",
            start_line=1,
            end_line=2,
            node_type="code_block",
            language="markdown",
            file_path="test.md",
            byte_start=0,
            byte_end=20,
            parent_context="",
            metadata={"tokens": 3},
        )
        assert not processor.validate_chunk(bad_code)

    @staticmethod
    def test_complex_markdown_document(processor):
        """Test processing a complex Markdown document."""
        content = """---
title: Complex Document
author: Test Author
tags: [python, testing, documentation]
---

# Complex Markdown Document

This document tests various Markdown features.

## Table of Contents

- [Introduction](#introduction)
- [Code Examples](#code-examples)
- [Data Tables](#data-tables)
- [Nested Lists](#nested-lists)

## Introduction

This is a paragraph with **bold text**, *italic text*, and `inline code`.

> This is a blockquote that might span
> multiple lines and should be handled
> appropriately by the processor.

## Code Examples

Here's a Python example:

```python
class MarkdownProcessor:
    def __init__(self):
        self.config = {}

    def process(self, content):
        # Process the content
        return chunks
```

And a JavaScript example:

```javascript
function processMarkdown(content) {
    const lines = content.split('\\n');
    return lines.map(line => parse(line));
}
```

## Data Tables

| Feature | Supported | Notes |
|---------|-----------|-------|
| Headers | Yes | H1-H6 |
| Code Blocks | Yes | Fenced |
| Tables | Yes | GFM style |
| Lists | Yes | Nested |

## Nested Lists

1. First item
   - Nested bullet
   - Another nested bullet
     1. Deep nested ordered
     2. Another deep nested
2. Second item
   - With bullets
3. Third item

## Links and References

Here are some [inline links](https://example.com) and reference-style links [like this][ref].

[ref]: https://example.com/reference "Reference Title"

---

Footer content with horizontal rule above.
"""
        chunks = processor.process(content, "complex.md")
        assert len(chunks) > 1
        assert any("front_matter" in c.node_type for c in chunks)
        code_chunks = [c for c in chunks if c.node_type == "code_block"]
        assert len(code_chunks) >= 2
        table_chunks = [c for c in chunks if c.node_type == "table"]
        assert len(table_chunks) >= 1
        for chunk in chunks:
            assert "segment_types" in chunk.metadata
            assert "dominant_type" in chunk.metadata

    @classmethod
    def test_malformed_markdown_handling(cls):
        """Test handling of malformed Markdown."""
        config = ProcessorConfig(min_chunk_size=10)
        processor = MarkdownProcessor(config)
        content1 = """# Test

```python
def unclosed():
    pass

More content without closing fence.
"""
        chunks1 = processor.process(content1, "malformed1.md")
        assert len(chunks1) > 0
        content2 = "# Test\n\n| Col1 | Col2 |\n| Data without separator row |\n\nNormal content.\n"
        chunks2 = processor.process(content2, "malformed2.md")
        assert len(chunks2) > 0

    @staticmethod
    def test_empty_document(processor):
        """Test handling of empty or minimal documents."""
        chunks1 = processor.process("", "empty.md")
        assert len(chunks1) == 0
        chunks2 = processor.process("   \n\n   \n", "whitespace.md")
        assert len(chunks2) == 0
        chunks3 = processor.process("Just one line.", "single.md")
        assert len(chunks3) <= 1

    @staticmethod
    def test_special_markdown_features(processor):
        """Test handling of special Markdown features."""
        content = """# Special Features

## Task Lists

- [x] Completed task
- [ ] Incomplete task
- [x] Another completed task

## Footnotes

Here's a sentence with a footnote[^1].

[^1]: This is the footnote content.

## Definition Lists

Term 1
:   Definition for term 1

Term 2
:   Definition for term 2
:   Additional definition

## HTML Comments

<!-- This is an HTML comment -->

Regular content here.

<!--
Multi-line
HTML comment
-->

## Math Blocks

$$
E = mc^2
$$

Inline math: $x = y^2$
"""
        chunks = processor.process(content, "special.md")
        assert len(chunks) > 0
        full_content = "".join(c.content for c in chunks)
        assert "[x] Completed task" in full_content
        assert "[^1]" in full_content
        assert "E = mc^2" in full_content

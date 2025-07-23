# Mixed Content Example

This document demonstrates various Markdown features that the processor must handle correctly.

## Code Examples

### Python Implementation

```python
class ChunkProcessor:
    """Process chunks with advanced algorithms."""
    
    def __init__(self, config=None):
        self.config = config or self._default_config()
        self.cache = {}
        
    def process_chunk(self, content, boundaries):
        """
        Process a chunk of content with given boundaries.
        
        This is a long method that should not be split across chunks
        even if it exceeds the normal chunk size limit.
        """
        results = []
        
        for start, end in boundaries:
            # Extract segment
            segment = content[start:end]
            
            # Apply transformations
            transformed = self.transform(segment)
            
            # Validate result
            if self.validate(transformed):
                results.append(transformed)
                
        return results
        
    def transform(self, segment):
        """Apply transformations to segment."""
        # Complex transformation logic here
        return segment.upper()
```

### JavaScript Example

```javascript
// Async chunk processor
async function processChunksAsync(chunks) {
    const results = await Promise.all(
        chunks.map(async (chunk) => {
            // Process each chunk
            const processed = await processChunk(chunk);
            
            // Validate result
            if (!isValid(processed)) {
                throw new Error(`Invalid chunk: ${chunk.id}`);
            }
            
            return processed;
        })
    );
    
    return results;
}

// Helper functions
function isValid(chunk) {
    return chunk && chunk.content && chunk.content.length > 0;
}
```

## Data Structures

### Chunk Configuration Table

| Parameter | Type | Default | Description | Valid Range |
|-----------|------|---------|-------------|-------------|
| max_chunk_size | integer | 1500 | Maximum size of a chunk in tokens | 100-10000 |
| min_chunk_size | integer | 100 | Minimum size of a chunk in tokens | 10-1000 |
| overlap_size | integer | 100 | Number of overlapping tokens | 0-500 |
| preserve_structure | boolean | true | Whether to preserve document structure | true/false |
| boundary_markers | array | ['#', '##', '```'] | Markers that indicate chunk boundaries | Any valid markers |

### Performance Metrics

| Operation | Average Time | Memory Usage | Complexity |
|-----------|--------------|--------------|------------|
| Structure Extraction | 5ms | 1MB | O(n) |
| Boundary Detection | 10ms | 2MB | O(n log n) |
| Chunk Creation | 15ms | 5MB | O(n) |
| Overlap Application | 8ms | 3MB | O(n) |
| Total Processing | 38ms | 11MB | O(n log n) |

## Complex Nested Structures

### Nested Lists with Code

1. First major point
   - Sub-point with inline code: `processor.extract()`
   - Another sub-point with a code block:
   
     ```bash
     # Run the processor
     python -m chunker.process --input file.md
     ```
     
   - Final sub-point
   
2. Second major point
   - Nested list item 1
     1. Double nested ordered
     2. Another double nested
        - Triple nested bullet
        - Another triple nested
   - Back to single nested

### Blockquotes with Multiple Levels

> This is a top-level blockquote that contains important information
> about the processing algorithm.
>
> > This is a nested blockquote explaining implementation details.
> > It might span multiple lines and include code:
> >
> > ```python
> > # Nested code in nested blockquote
> > def nested_example():
> >     return "complex"
> > ```
>
> Back to the top-level blockquote with final thoughts.

## Links and References

Here's a paragraph with various link types:
- [Inline link](https://example.com)
- [Reference link][ref1]
- [Another reference][ref2]
- Raw URL: https://github.com/example/repo
- Email: user@example.com

[ref1]: https://example.com/ref1 "Reference 1 Title"
[ref2]: https://example.com/ref2 "Reference 2 Title"

## Special Markdown Features

### Task Lists

Project tasks:
- [x] Implement basic parser
- [x] Add structure extraction
- [ ] Add sliding window support
- [ ] Implement overlap algorithm
  - [x] Design algorithm
  - [ ] Implement algorithm
  - [ ] Test algorithm

### Footnotes

Here's some text with a footnote[^1] and another footnote[^2].

[^1]: This is the first footnote with some explanatory text.
[^2]: This is the second footnote with more details.

### HTML Elements

<details>
<summary>Click to expand</summary>

This is hidden content that should be processed correctly.
It might contain:
- Lists
- Code blocks
- Other Markdown elements

```python
# Code inside HTML
print("This works!")
```

</details>

## Mathematical Content

Inline math: $f(x) = x^2 + 2x + 1$

Block math:

$$
\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}
$$

Another equation:

$$
E = mc^2
$$

## Conclusion

This document has demonstrated various Markdown features that need special handling:

1. **Atomic Elements**: Code blocks and tables that must not be split
2. **Nested Structures**: Lists and blockquotes with multiple levels
3. **Special Features**: Task lists, footnotes, math, and HTML
4. **Mixed Content**: Combination of different element types

The processor must handle all these cases gracefully while maintaining document structure and readability.
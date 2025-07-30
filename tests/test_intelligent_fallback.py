"""Tests for intelligent fallback strategy."""

from chunker.fallback.intelligent_fallback import (
    ChunkingDecision,
    DecisionMetrics,
    IntelligentFallbackChunker,
)


class TestIntelligentFallback:
    """Test intelligent fallback functionality."""

    def test_basic_initialization(self):
        """Test basic initialization."""
        fallback = IntelligentFallbackChunker(token_limit=1000)

        assert fallback.token_limit == 1000
        assert fallback.model == "gpt-4"
        assert fallback._supported_languages is not None

    def test_language_detection(self):
        """Test language detection from file paths."""
        fallback = IntelligentFallbackChunker()

        # Test common extensions
        assert fallback._detect_language("test.py", "") == "python"
        assert fallback._detect_language("test.js", "") == "javascript"
        assert fallback._detect_language("test.rs", "") == "rust"
        assert fallback._detect_language("test.cpp", "") == "cpp"

        # Test shebang detection
        python_content = "#!/usr/bin/env python3\nprint('hello')"
        assert fallback._detect_language("script", python_content) == "python"

        node_content = "#!/usr/bin/env node\nconsole.log('hello');"
        assert fallback._detect_language("script", node_content) == "javascript"

    def test_tree_sitter_decision(self):
        """Test decision to use tree-sitter."""
        fallback = IntelligentFallbackChunker()

        python_code = """
def hello():
    print("Hello, World!")

def goodbye():
    print("Goodbye!")
"""

        chunks = fallback.chunk_text(python_code, "test.py")

        # Should use tree-sitter
        assert len(chunks) == 2
        assert all(
            c.metadata.get("chunking_decision") == ChunkingDecision.TREE_SITTER.value
            for c in chunks
        )

    def test_tree_sitter_with_split_decision(self):
        """Test decision to use tree-sitter with splitting."""
        # Use small token limit to force splitting
        fallback = IntelligentFallbackChunker(token_limit=50)

        # Create a large function
        large_function = '''
def process_data(data):
    """Process data with many steps and lots of code that will exceed token limit."""
    # Initialize variables
    results = []
    errors = []
    processed = 0

    # Process each item
    for item in data:
        try:
            # Validate
            if not isinstance(item, dict):
                errors.append(f"Invalid item: {item}")
                continue

            # Transform
            value = item.get('value', 0) * 2
            result = {'original': item, 'processed': value}
            results.append(result)
            processed += 1

        except (AttributeError, KeyError) as e:
            errors.append(f"Error: {e}")

    # Return summary
    return {
        'results': results,
        'errors': errors,
        'processed': processed,
        'total': len(data)
    }
'''

        chunks = fallback.chunk_text(large_function, "process.py")

        # Should use tree-sitter with splitting
        assert len(chunks) > 1  # Should be split
        assert any(
            c.metadata.get("chunking_decision")
            == ChunkingDecision.TREE_SITTER_WITH_SPLIT.value
            for c in chunks
        )

        # All chunks should respect token limit
        for chunk in chunks:
            assert chunk.metadata.get("token_count", 0) <= 50

    def test_sliding_window_decision_no_language_support(self):
        """Test decision to use sliding window when no language support."""
        fallback = IntelligentFallbackChunker()

        # Unknown language content
        content = """
        This is some content in an unsupported language.
        It will fall back to sliding window processing.
        Line 3
        Line 4
        """

        chunks = fallback.chunk_text(content, "unknown.xyz")

        # Should use sliding window
        assert len(chunks) >= 1
        assert all(
            c.metadata.get("chunking_decision") == ChunkingDecision.SLIDING_WINDOW.value
            for c in chunks
        )

    def test_specialized_processor_decision(self):
        """Test decision to use specialized processor."""
        fallback = IntelligentFallbackChunker()

        # Markdown content
        markdown_content = """
# Title

This is a markdown file.

## Section 1

Content here.

## Section 2

More content.
"""

        chunks = fallback.chunk_text(markdown_content, "test.md")

        # Should use specialized processor (markdown)
        assert len(chunks) >= 1
        # Check that it used sliding window or specialized processor
        decisions = {c.metadata.get("chunking_decision") for c in chunks}
        assert (
            ChunkingDecision.SLIDING_WINDOW.value in decisions
            or ChunkingDecision.SPECIALIZED_PROCESSOR.value in decisions
        )

    def test_get_decision_info(self):
        """Test getting detailed decision information."""
        fallback = IntelligentFallbackChunker(token_limit=1000)

        python_code = "def hello():\n    print('hi')"

        info = fallback.get_decision_info("test.py", python_code)

        assert "decision" in info
        assert "reason" in info
        assert "metrics" in info

        metrics = info["metrics"]
        assert metrics["has_tree_sitter_support"] is True
        assert metrics["parse_success"] is True
        assert metrics["is_code_file"] is True
        assert metrics["total_tokens"] > 0

    def test_token_limit_metadata(self):
        """Test that token metadata is added when token limit is set."""
        fallback = IntelligentFallbackChunker(token_limit=500, model="claude")

        code = "def test():\n    return 42"

        chunks = fallback.chunk_text(code, "test.py")

        assert len(chunks) >= 1
        for chunk in chunks:
            assert "token_count" in chunk.metadata
            assert "tokenizer_model" in chunk.metadata
            assert chunk.metadata["tokenizer_model"] == "claude"

    def test_parse_failure_fallback(self):
        """Test fallback when no tree-sitter chunks are produced."""
        fallback = IntelligentFallbackChunker()

        # Code that might not produce chunks (like a simple print statement)
        simple_code = """print("hello")"""

        # Should still produce chunks
        chunks = fallback.chunk_text(simple_code, "simple.py")

        # Even simple code should produce at least one chunk
        assert len(chunks) >= 1

        # Test with truly unsupported content
        unknown_content = "This is not valid code in any language"
        chunks2 = fallback.chunk_text(unknown_content, "unknown.xyz")

        # Should use sliding window fallback
        assert len(chunks2) >= 1
        assert (
            chunks2[0].metadata.get("chunking_decision")
            == ChunkingDecision.SLIDING_WINDOW.value
        )

    def test_metrics_analysis(self):
        """Test metrics analysis functionality."""
        fallback = IntelligentFallbackChunker()

        # Create metrics object
        metrics = DecisionMetrics()
        metrics.has_tree_sitter_support = True
        metrics.parse_success = True
        metrics.largest_chunk_tokens = 100
        metrics.token_limit_exceeded = False

        # Make decision
        decision, reason = fallback._make_decision(metrics)

        assert decision == ChunkingDecision.TREE_SITTER
        assert "successful" in reason.lower()

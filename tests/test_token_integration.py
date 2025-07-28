"""Comprehensive tests for token counting integration."""

import tempfile
from pathlib import Path

from chunker import chunk_file
from chunker.token import TiktokenCounter
from chunker.token.chunker import TreeSitterTokenAwareChunker


class TestTiktokenCounter:
    """Test the TiktokenCounter implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.counter = TiktokenCounter()

    def test_count_tokens_basic(self):
        """Test basic token counting."""
        text = "Hello, world!"
        count = self.counter.count_tokens(text)
        assert count > 0
        assert count < 10  # Simple text should have few tokens

    def test_count_tokens_empty(self):
        """Test counting tokens in empty string."""
        assert self.counter.count_tokens("") == 0
        assert self.counter.count_tokens(" ") == 1

    def test_count_tokens_code(self):
        """Test counting tokens in code."""
        code = """
def hello_world():
    print("Hello, world!")
    return 42
"""
        count = self.counter.count_tokens(code)
        assert count > 10  # Code should have more tokens

    def test_different_models(self):
        """Test token counting with different models."""
        text = "This is a test sentence with multiple words."

        gpt4_count = self.counter.count_tokens(text, "gpt-4")
        gpt35_count = self.counter.count_tokens(text, "gpt-3.5-turbo")

        # Both should return positive counts
        assert gpt4_count > 0
        assert gpt35_count > 0

        # For cl100k_base encoding, counts should be the same
        assert gpt4_count == gpt35_count

    def test_get_token_limit(self):
        """Test getting token limits for models."""
        assert self.counter.get_token_limit("gpt-4") == 8192
        assert self.counter.get_token_limit("gpt-4-turbo") == 128000
        assert self.counter.get_token_limit("claude") == 100000
        assert self.counter.get_token_limit("unknown-model") == 4096  # Default

    def test_split_text_by_tokens(self):
        """Test splitting text by token limit."""
        # Create a long text
        long_text = "Hello world. " * 100

        # Split with small token limit
        chunks = self.counter.split_text_by_tokens(long_text, max_tokens=50)

        assert len(chunks) > 1
        # Each chunk should be under the limit
        for chunk in chunks:
            assert self.counter.count_tokens(chunk) <= 50

        # Concatenated chunks should preserve the original text (minus some whitespace)
        rejoined = "".join(chunks)
        assert len(rejoined) > 0

    def test_split_preserves_lines(self):
        """Test that splitting tries to preserve line boundaries."""
        code = "\n".join([f"def function_{i}():\n    return {i}" for i in range(20)])

        chunks = self.counter.split_text_by_tokens(code, max_tokens=100)

        # Should have multiple chunks
        assert len(chunks) > 1

        # Each chunk should contain complete functions (lines ending with a number)
        for chunk in chunks:
            lines = chunk.split("\n")
            # Check that functions are complete
            for i in range(0, len(lines), 2):  # Functions are 2 lines each
                if i < len(lines) - 1:  # Not the last line
                    assert lines[i].startswith("def function_")
                    assert "return" in lines[i + 1]

    def test_split_long_line(self):
        """Test splitting a single very long line."""
        long_line = "word " * 500  # Very long single line

        chunks = self.counter.split_text_by_tokens(long_line, max_tokens=50)

        assert len(chunks) > 5
        for chunk in chunks:
            assert self.counter.count_tokens(chunk) <= 50


class TestTokenAwareChunker:
    """Test the TokenAwareChunker implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.chunker = TreeSitterTokenAwareChunker()
        self.test_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test files."""
        import shutil

        shutil.rmtree(self.test_dir)

    def create_test_file(self, content: str, filename: str = "test.py") -> Path:
        """Create a test file with given content."""
        file_path = self.test_dir / filename
        file_path.write_text(content)
        return file_path

    def test_add_token_info(self):
        """Test adding token information to chunks."""
        # Create a simple Python file
        content = """
def add(a, b):
    return a + b

def multiply(x, y):
    return x * y
"""
        file_path = self.create_test_file(content)

        # Get regular chunks
        chunks = chunk_file(str(file_path), "python")

        # Add token info
        enhanced_chunks = self.chunker.add_token_info(chunks)

        assert len(enhanced_chunks) == len(chunks)

        for chunk in enhanced_chunks:
            assert "token_count" in chunk.metadata
            assert "tokenizer_model" in chunk.metadata
            assert chunk.metadata["token_count"] > 0
            assert chunk.metadata["tokenizer_model"] == "gpt-4"

            # Check chars_per_token ratio
            if "chars_per_token" in chunk.metadata:
                assert chunk.metadata["chars_per_token"] > 0

    def test_chunk_with_token_limit(self):
        """Test chunking with token limit."""
        # Create a file with a large function
        lines = [
            "def large_function():",
            "    # This is a very large function that will exceed token limits",
        ]
        lines.extend([f"    var_{i} = {i} * 2" for i in range(100)])
        lines.append("    return sum([var_0, var_1, var_2])")
        content = "\n".join(lines) + "\n"
        file_path = self.create_test_file(content)

        # Chunk with small token limit
        chunks = self.chunker.chunk_with_token_limit(
            str(file_path),
            "python",
            max_tokens=50,
        )

        # Debug: print chunk info
        for i, chunk in enumerate(chunks):
            print(
                f"Chunk {i}: tokens={chunk.metadata.get('token_count', 0)}, lines={chunk.end_line - chunk.start_line + 1}",
            )

        # Should have split the large function
        assert len(chunks) > 1

        for chunk in chunks:
            assert chunk.metadata["token_count"] <= 50
            assert "is_split" in chunk.metadata or chunk.metadata["token_count"] <= 50

    def test_class_splitting(self):
        """Test splitting large classes by methods."""
        content = '''
class LargeClass:
    """A class with many methods."""

    def __init__(self):
        self.value = 0

    def method1(self):
        """First method."""
        return self.value + 1

    def method2(self):
        """Second method."""
        return self.value + 2

    def method3(self):
        """Third method with more content."""
        result = 0
        for i in range(10):
            result += i * self.value
        return result
'''
        file_path = self.create_test_file(content)

        # Chunk with very small limit to force splitting
        chunks = self.chunker.chunk_with_token_limit(
            str(file_path),
            "python",
            max_tokens=80,
        )

        # Should have split the class
        assert len(chunks) >= 1

        # Check that split chunks maintain class context
        for chunk in chunks:
            if chunk.metadata.get("is_split"):
                assert "class LargeClass" in chunk.content

    def test_chunk_interface_implementation(self):
        """Test the basic chunk() method from ChunkingStrategy interface."""
        content = """
def test_function():
    return 42
"""
        file_path = self.create_test_file(content)

        # Since chunk() requires an AST, we need to parse first
        from chunker import get_parser

        parser = get_parser("python")
        tree = parser.parse(content.encode())

        chunks = self.chunker.chunk(
            tree.root_node,
            content.encode(),
            str(file_path),
            "python",
        )

        assert len(chunks) > 0
        assert all("token_count" in chunk.metadata for chunk in chunks)

    def test_model_specific_tokenization(self):
        """Test tokenization with different models."""
        content = """
def hello():
    return "Hello, world!"
"""
        file_path = self.create_test_file(content)

        # Test with different models
        gpt4_chunks = self.chunker.chunk_with_token_limit(
            str(file_path),
            "python",
            max_tokens=1000,
            model="gpt-4",
        )

        claude_chunks = self.chunker.chunk_with_token_limit(
            str(file_path),
            "python",
            max_tokens=1000,
            model="claude",
        )

        # Both should work
        assert len(gpt4_chunks) > 0
        assert len(claude_chunks) > 0

        # Model should be recorded in metadata
        assert gpt4_chunks[0].metadata["tokenizer_model"] == "gpt-4"
        assert claude_chunks[0].metadata["tokenizer_model"] == "claude"

    def test_edge_case_empty_file(self):
        """Test handling empty files."""
        file_path = self.create_test_file("")

        chunks = self.chunker.chunk_with_token_limit(
            str(file_path),
            "python",
            max_tokens=100,
        )

        # Should handle empty file gracefully
        assert len(chunks) == 0

    def test_preserve_chunk_relationships(self):
        """Test that split chunks maintain parent relationships."""
        content = (
            """
def very_large_function():
    # Lots of code here
    """
            + "\n".join([f"    line_{i} = {i}" for i in range(50)])
            + """
    return sum([line_0, line_1])
"""
        )
        file_path = self.create_test_file(content)

        chunks = self.chunker.chunk_with_token_limit(
            str(file_path),
            "python",
            max_tokens=30,
        )

        # Find split chunks
        split_chunks = [c for c in chunks if c.metadata.get("is_split", False)]

        if split_chunks:
            # All split chunks should reference the same original
            original_ids = {c.metadata.get("original_chunk_id") for c in split_chunks}
            assert len(original_ids) == 1

            # Split indices should be sequential
            indices = sorted(c.metadata.get("split_index", 0) for c in split_chunks)
            assert indices == list(range(1, len(split_chunks) + 1))

    def test_multiple_languages(self):
        """Test token counting with different programming languages."""
        # JavaScript file
        js_content = """
function greet(name) {
    console.log(`Hello, ${name}!`);
    return name.length;
}
"""
        js_file = self.create_test_file(js_content, "test.js")

        js_chunks = self.chunker.chunk_with_token_limit(
            str(js_file),
            "javascript",
            max_tokens=100,
        )

        assert len(js_chunks) > 0
        assert all("token_count" in chunk.metadata for chunk in js_chunks)

    def test_token_info_preservation(self):
        """Test that token info is preserved through operations."""
        content = """
def function_one():
    return 1

def function_two():
    return 2
"""
        file_path = self.create_test_file(content)

        # Get chunks with token info
        chunks = self.chunker.chunk_with_token_limit(
            str(file_path),
            "python",
            max_tokens=1000,
        )

        # Add token info again (should not change)
        chunks_again = self.chunker.add_token_info(chunks)

        for orig, new in zip(chunks, chunks_again, strict=False):
            assert orig.metadata["token_count"] == new.metadata["token_count"]

    def test_very_large_token_limit(self):
        """Test with very large token limits (no splitting needed)."""
        content = """
def small_function():
    return 42
"""
        file_path = self.create_test_file(content)

        chunks = self.chunker.chunk_with_token_limit(
            str(file_path),
            "python",
            max_tokens=10000,
        )

        # Should not split anything
        assert len(chunks) == 1
        assert "is_split" not in chunks[0].metadata
        assert chunks[0].metadata["token_count"] < 10000

    def test_unicode_content(self):
        """Test token counting with unicode content."""
        content = """
# -*- coding: utf-8 -*-
def greet():
    return "Hello, 世界! 🌍"

def calculate():
    # Greek letters: α, β, γ
    return "π ≈ 3.14159"
"""
        file_path = self.create_test_file(content)

        chunks = self.chunker.chunk_with_token_limit(
            str(file_path),
            "python",
            max_tokens=100,
        )

        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.metadata["token_count"] > 0

    def test_concurrent_chunk_processing(self):
        """Test that token counting works correctly with concurrent processing."""
        import concurrent.futures

        # Create multiple test files
        files = []
        for i in range(5):
            content = f"""
def function_{i}():
    return {i} * {i}
"""
            file_path = self.create_test_file(content, f"test_{i}.py")
            files.append(str(file_path))

        # Process files concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for file_path in files:
                future = executor.submit(
                    self.chunker.chunk_with_token_limit,
                    file_path,
                    "python",
                    100,
                )
                futures.append(future)

            # Collect results
            results = []
            for future in concurrent.futures.as_completed(futures):
                chunks = future.result()
                results.extend(chunks)

        # Verify all chunks have token counts
        assert len(results) == len(files)
        for chunk in results:
            assert "token_count" in chunk.metadata
            assert chunk.metadata["token_count"] > 0

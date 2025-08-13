"""Tests for relationship extraction and tracking."""

import tempfile
from pathlib import Path

from chunker.core import chunk_file
from chunker.types import CodeChunk


def test_chunk_id_generation():
    """Test unique chunk ID generation."""
    chunk = CodeChunk(
        language="python",
        file_path="test.py",
        node_type="function_definition",
        start_line=1,
        end_line=5,
        byte_start=0,
        byte_end=100,
        parent_context="",
        content="def test():\n    pass",
    )

    chunk_id = chunk.generate_id()
    assert len(chunk_id) == 40  # full SHA-1 hex
    assert chunk_id.isalnum()

    # Same chunk should generate same ID
    chunk_id2 = chunk.generate_id()
    assert chunk_id == chunk_id2

    # Different content should generate different ID
    chunk.content = "def different():\n    pass"
    chunk_id3 = chunk.generate_id()
    assert chunk_id != chunk_id3


def test_parent_child_relationships():
    """Test parent-child relationship tracking."""
    with tempfile.NamedTemporaryFile(
        encoding="utf-8",
        mode="w",
        suffix=".py",
        delete=False,
    ) as f:
        f.write(
            """
class OuterClass:
    def method1(self):
        pass

    class InnerClass:
        def method2(self):
            pass
""",
        )
        temp_path = Path(f.name)

    try:
        chunks = chunk_file(temp_path, "python")

        # Should have 4 chunks: OuterClass, method1, InnerClass, method2
        assert len(chunks) == 4

        # Chunks should be in order: OuterClass, method1, InnerClass, method2
        outer_class = chunks[0]
        method1 = chunks[1]
        inner_class = chunks[2]
        method2 = chunks[3]

        assert outer_class.node_type == "class_definition"
        assert method1.node_type == "function_definition"
        assert inner_class.node_type == "class_definition"
        assert method2.node_type == "function_definition"

        # Check parent relationships
        assert method1.parent_chunk_id == outer_class.chunk_id
        assert inner_class.parent_chunk_id == outer_class.chunk_id
        assert method2.parent_chunk_id == inner_class.chunk_id

        # Check all chunks have IDs
        for chunk in chunks:
            assert chunk.chunk_id
            assert len(chunk.chunk_id) == 40

    finally:
        temp_path.unlink()


def test_nested_functions():
    """Test nested function relationships."""
    with tempfile.NamedTemporaryFile(
        encoding="utf-8",
        mode="w",
        suffix=".py",
        delete=False,
    ) as f:
        f.write(
            """
def outer_function():
    def inner_function():
        def deeply_nested():
            pass
        return deeply_nested
    return inner_function
""",
        )
        temp_path = Path(f.name)

    try:
        chunks = chunk_file(temp_path, "python")

        # Should have 3 chunks: outer, inner, deeply_nested
        assert len(chunks) == 3

        # Chunks should be in order: outer, inner, deeply_nested
        outer = chunks[0]
        inner = chunks[1]
        deeply = chunks[2]

        assert outer.node_type == "function_definition"
        assert inner.node_type == "function_definition"
        assert deeply.node_type == "function_definition"

        # Check parent relationships
        assert inner.parent_chunk_id == outer.chunk_id
        assert deeply.parent_chunk_id == inner.chunk_id

        # Check parent context
        assert not outer.parent_context
        assert inner.parent_context == "function_definition"
        assert deeply.parent_context == "function_definition"

    finally:
        temp_path.unlink()


def test_flat_structure_no_relationships():
    """Test that flat structure has no parent relationships."""
    with tempfile.NamedTemporaryFile(
        encoding="utf-8",
        mode="w",
        suffix=".py",
        delete=False,
    ) as f:
        f.write(
            """
def function1():
    pass

def function2():
    pass

class Class1:
    pass
""",
        )
        temp_path = Path(f.name)

    try:
        chunks = chunk_file(temp_path, "python")

        # Should have 3 chunks with no parent relationships
        assert len(chunks) == 3

        for chunk in chunks:
            assert chunk.parent_chunk_id is None
            assert not chunk.parent_context
    finally:
        temp_path.unlink()

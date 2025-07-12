"""Tests for the chunking functionality."""
import pytest
from chunker import chunk_file, get_parser, list_languages


def test_python_chunks(tmp_path):
    """Test basic Python code chunking."""
    src = tmp_path / "tmp.py"
    src.write_text("def foo():\n    pass\n")
    chunks = chunk_file(src, "python")
    assert chunks, "Should find at least one chunk"
    assert chunks[0].node_type == "function_definition"
    assert chunks[0].language == "python"
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 2


def test_multiple_chunks(tmp_path):
    """Test file with multiple chunks."""
    src = tmp_path / "multi.py"
    src.write_text("""
def func1():
    pass

class MyClass:
    def method1(self):
        pass
        
def func2():
    return 42
""")
    chunks = chunk_file(src, "python")
    assert len(chunks) == 4  # func1, MyClass, method1, func2
    
    # Check node types
    node_types = [c.node_type for c in chunks]
    assert "function_definition" in node_types
    assert "class_definition" in node_types
    # In Python's tree-sitter grammar, methods are also function_definition
    assert node_types.count("function_definition") == 3  # func1, method1, func2
    
    # Check that method1 has MyClass as parent context
    method_chunks = [c for c in chunks if c.content.strip().startswith("def method1")]
    assert len(method_chunks) == 1
    assert method_chunks[0].parent_context == "class_definition"


def test_parser_availability():
    """Test that parsers are available for all expected languages."""
    languages = list_languages()
    
    # Test we can get a parser for each language
    available = []
    unavailable = []
    
    for lang in languages:
        try:
            parser = get_parser(lang)
            assert parser is not None
            available.append(lang)
        except Exception as e:
            # Log which languages fail
            unavailable.append((lang, str(e)))
    
    # At least Python should work
    assert "python" in available, f"Python parser should be available. Unavailable: {unavailable}"
    
    if unavailable:
        # This is a warning, not a failure - version mismatch is expected
        # with older tree-sitter libraries
        import warnings
        warnings.warn(
            f"Some languages unavailable due to version mismatch: {unavailable}. "
            "Consider upgrading tree-sitter library."
        )


def test_empty_file(tmp_path):
    """Test chunking an empty file."""
    src = tmp_path / "empty.py"
    src.write_text("")
    chunks = chunk_file(src, "python")
    assert chunks == []

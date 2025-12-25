"""Tests for REQ-TSC-011: Stable content-insensitive definition_id.

The definition_id field provides a content-insensitive identifier for tracking
definitions across code changes. Unlike chunk_id/node_id which include content
hashes, definition_id is computed purely from structural/positional information.
"""

from chunker.types import CodeChunk, compute_definition_id


class TestComputeDefinitionId:
    """Tests for the compute_definition_id function."""

    def test_basic_computation(self):
        """Test that definition_id is computed as expected."""
        qr = ["class_definition:MyClass", "method_definition:foo"]
        def_id = compute_definition_id("/path/to/file.py", "python", qr)

        assert def_id is not None
        assert len(def_id) == 40  # SHA1 hex digest

    def test_same_route_same_id(self):
        """Same qualified_route produces same definition_id."""
        qr = ["function_definition:my_func"]

        id1 = compute_definition_id("/file.py", "python", qr)
        id2 = compute_definition_id("/file.py", "python", qr)

        assert id1 == id2

    def test_different_names_different_ids(self):
        """Different definition names produce different IDs."""
        id_foo = compute_definition_id("/file.py", "python", ["function_definition:foo"])
        id_bar = compute_definition_id("/file.py", "python", ["function_definition:bar"])

        assert id_foo != id_bar

    def test_different_paths_different_ids(self):
        """Same definition in different files produces different IDs."""
        qr = ["function_definition:foo"]

        id1 = compute_definition_id("/file1.py", "python", qr)
        id2 = compute_definition_id("/file2.py", "python", qr)

        assert id1 != id2

    def test_different_languages_different_ids(self):
        """Same definition in different languages produces different IDs."""
        qr = ["function_definition:foo"]

        id_py = compute_definition_id("/file", "python", qr)
        id_js = compute_definition_id("/file", "javascript", qr)

        assert id_py != id_js

    def test_nested_route(self):
        """Test qualified_route with nesting (class -> method)."""
        qr_method = ["class_definition:MyClass", "method_definition:do_stuff"]
        qr_other = ["class_definition:OtherClass", "method_definition:do_stuff"]

        # Same method name in different classes should have different IDs
        id1 = compute_definition_id("/file.py", "python", qr_method)
        id2 = compute_definition_id("/file.py", "python", qr_other)

        assert id1 != id2

    def test_empty_route(self):
        """Empty qualified_route still produces valid ID."""
        def_id = compute_definition_id("/file.py", "python", [])

        assert def_id is not None
        assert len(def_id) == 40


class TestCodeChunkDefinitionId:
    """Tests for definition_id on CodeChunk dataclass."""

    def test_definition_id_computed_from_qualified_route(self):
        """definition_id is computed when qualified_route is provided."""
        chunk = CodeChunk(
            language="python",
            file_path="/path/to/file.py",
            node_type="function_definition",
            start_line=10,
            end_line=20,
            byte_start=100,
            byte_end=500,
            parent_context="",
            content="def foo(): pass",
            parent_route=["function_definition"],
            qualified_route=["function_definition:foo"],
        )

        assert chunk.definition_id != ""
        assert len(chunk.definition_id) == 40

    def test_definition_id_stable_with_content_change(self):
        """definition_id stays same when only content changes."""
        chunk1 = CodeChunk(
            language="python",
            file_path="/file.py",
            node_type="function_definition",
            start_line=10,
            end_line=20,
            byte_start=100,
            byte_end=500,
            parent_context="",
            content="def foo(): pass",
            parent_route=["function_definition"],
            qualified_route=["function_definition:foo"],
        )

        chunk2 = CodeChunk(
            language="python",
            file_path="/file.py",
            node_type="function_definition",
            start_line=10,
            end_line=30,  # More lines
            byte_start=100,
            byte_end=800,  # More content
            parent_context="",
            content="def foo():\n    return 42\n    # and more",  # Different content
            parent_route=["function_definition"],
            qualified_route=["function_definition:foo"],  # Same qualified route
        )

        # Key assertion: definition_id is STABLE across content changes
        assert chunk1.definition_id == chunk2.definition_id

        # Contrast: node_id/chunk_id DO change with content
        assert chunk1.node_id != chunk2.node_id
        assert chunk1.chunk_id != chunk2.chunk_id

    def test_definition_id_empty_without_file_path(self):
        """definition_id is empty when file_path is not set."""
        chunk = CodeChunk(
            language="python",
            file_path="",  # Empty file path
            node_type="function_definition",
            start_line=10,
            end_line=20,
            byte_start=100,
            byte_end=500,
            parent_context="",
            content="def foo(): pass",
            parent_route=["function_definition"],
            qualified_route=["function_definition:foo"],
        )

        # Without file_path, definition_id should not be computed
        assert chunk.definition_id == ""

    def test_definition_id_empty_without_qualified_route(self):
        """definition_id is empty when qualified_route is empty (default)."""
        chunk = CodeChunk(
            language="python",
            file_path="/file.py",
            node_type="function_definition",
            start_line=10,
            end_line=20,
            byte_start=100,
            byte_end=500,
            parent_context="",
            content="def foo(): pass",
            parent_route=["function_definition"],
            # No qualified_route
        )

        assert chunk.definition_id == ""

    def test_anonymous_definition_uses_line_fallback(self):
        """Anonymous definitions use line-based fallback in qualified_route."""
        # This tests the format "node_type:anon@line"
        qr = ["function_definition:anon@42"]
        chunk = CodeChunk(
            language="python",
            file_path="/file.py",
            node_type="function_definition",
            start_line=42,
            end_line=50,
            byte_start=100,
            byte_end=500,
            parent_context="",
            content="lambda x: x + 1",
            parent_route=["function_definition"],
            qualified_route=qr,
        )

        assert chunk.definition_id != ""

        # Different line = different ID
        qr2 = ["function_definition:anon@43"]
        chunk2 = CodeChunk(
            language="python",
            file_path="/file.py",
            node_type="function_definition",
            start_line=43,
            end_line=51,
            byte_start=200,
            byte_end=600,
            parent_context="",
            content="lambda x: x * 2",
            parent_route=["function_definition"],
            qualified_route=qr2,
        )

        assert chunk.definition_id != chunk2.definition_id


class TestDefinitionIdIntegration:
    """Integration tests for definition_id in real-world scenarios."""

    def test_refactoring_preserves_definition_id(self):
        """Simulates refactoring: content changes but definition_id is stable."""
        # Before refactoring
        before = CodeChunk(
            language="python",
            file_path="/app/utils.py",
            node_type="function_definition",
            start_line=15,
            end_line=25,
            byte_start=200,
            byte_end=450,
            parent_context="",
            content="""def calculate_total(items):
    total = 0
    for item in items:
        total += item.price
    return total""",
            parent_route=["function_definition"],
            qualified_route=["function_definition:calculate_total"],
        )

        # After refactoring (using list comprehension)
        after = CodeChunk(
            language="python",
            file_path="/app/utils.py",
            node_type="function_definition",
            start_line=15,
            end_line=16,  # Now shorter
            byte_start=200,
            byte_end=280,
            parent_context="",
            content="""def calculate_total(items):
    return sum(item.price for item in items)""",
            parent_route=["function_definition"],
            qualified_route=["function_definition:calculate_total"],
        )

        # definition_id should be stable across refactoring
        assert before.definition_id == after.definition_id

    def test_moving_definition_changes_id(self):
        """Moving a definition to a new structural location changes definition_id."""
        # Function at module level
        at_module = CodeChunk(
            language="python",
            file_path="/file.py",
            node_type="function_definition",
            start_line=10,
            end_line=15,
            byte_start=100,
            byte_end=300,
            parent_context="",
            content="def helper(): pass",
            parent_route=["function_definition"],
            qualified_route=["function_definition:helper"],
        )

        # Same function moved into a class
        in_class = CodeChunk(
            language="python",
            file_path="/file.py",
            node_type="method_definition",  # Now it's a method
            start_line=20,
            end_line=25,
            byte_start=400,
            byte_end=600,
            parent_context="MyClass",
            content="def helper(self): pass",
            parent_route=["class_definition", "method_definition"],
            qualified_route=["class_definition:MyClass", "method_definition:helper"],
        )

        # definition_id should change when structural location changes
        assert at_module.definition_id != in_class.definition_id

    def test_renaming_changes_definition_id(self):
        """Renaming a definition changes its definition_id."""
        original = CodeChunk(
            language="python",
            file_path="/file.py",
            node_type="function_definition",
            start_line=10,
            end_line=15,
            byte_start=100,
            byte_end=300,
            parent_context="",
            content="def old_name(): pass",
            parent_route=["function_definition"],
            qualified_route=["function_definition:old_name"],
        )

        renamed = CodeChunk(
            language="python",
            file_path="/file.py",
            node_type="function_definition",
            start_line=10,
            end_line=15,
            byte_start=100,
            byte_end=300,
            parent_context="",
            content="def new_name(): pass",
            parent_route=["function_definition"],
            qualified_route=["function_definition:new_name"],
        )

        # definition_id should change when name changes
        assert original.definition_id != renamed.definition_id

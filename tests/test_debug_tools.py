"""
Tests for debug and visualization tools.
"""

import os
import tempfile

import pytest

from chunker.debug import (
    ASTVisualizer,
    ChunkDebugger,
    QueryDebugger,
    highlight_chunk_boundaries,
    print_ast_tree,
    render_ast_graph,
)


class TestASTVisualizer:
    """Test AST visualization functionality."""

    def test_ast_visualizer_creation(self):
        """Test creating AST visualizer."""
        visualizer = ASTVisualizer("python")
        assert visualizer.language == "python"
        assert visualizer.parser is not None

    def test_tree_visualization(self):
        """Test tree format visualization."""
        visualizer = ASTVisualizer("python")

        # Create test file
        code = "def hello():\n    print('Hello')"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            # Should not raise and return None for tree format
            result = visualizer.visualize_file(temp_file, output_format="tree")
            assert result is None
        finally:
            os.unlink(temp_file)

    def test_json_visualization(self):
        """Test JSON format visualization."""
        visualizer = ASTVisualizer("python")

        # Create test file
        code = "x = 42"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            result = visualizer.visualize_file(temp_file, output_format="json")
            assert result is not None
            assert isinstance(result, str)

            # Check JSON structure
            import json

            data = json.loads(result)
            assert "type" in data
            assert "children" in data
        finally:
            os.unlink(temp_file)

    def test_highlight_nodes(self):
        """Test node highlighting."""
        visualizer = ASTVisualizer("python")

        code = "def func():\n    x = 1\n    return x"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            # Should handle highlight_nodes parameter
            result = visualizer.visualize_file(
                temp_file,
                output_format="json",
                highlight_nodes={"function_definition", "return_statement"},
            )
            assert result is not None
        finally:
            os.unlink(temp_file)


class TestQueryDebugger:
    """Test query debugging functionality."""

    def test_query_debugger_creation(self):
        """Test creating query debugger."""
        debugger = QueryDebugger("python")
        assert debugger.language == "python"
        assert debugger.parser is not None

    def test_simple_query(self):
        """Test debugging a simple query."""
        debugger = QueryDebugger("python")

        code = "def test():\n    pass"
        query = "(function_definition) @func"

        matches = debugger.debug_query(query, code, show_ast=False)
        assert len(matches) == 1
        assert matches[0].captures.get("@func") is not None

    def test_query_with_captures(self):
        """Test query with multiple captures."""
        debugger = QueryDebugger("python")

        code = "def add(x, y):\n    return x + y"
        query = """
        (function_definition
          name: (identifier) @func_name
          parameters: (parameters) @params
        )
        """

        matches = debugger.debug_query(query, code, show_captures=True)
        assert len(matches) == 1
        assert "@func_name" in matches[0].captures
        assert "@params" in matches[0].captures

    def test_invalid_query(self):
        """Test handling invalid queries."""
        debugger = QueryDebugger("python")

        code = "x = 1"
        invalid_query = "(invalid_node_type)"

        # Should handle error gracefully
        matches = debugger.debug_query(invalid_query, code)
        assert len(matches) == 0

    def test_query_cache(self):
        """Test query caching."""
        debugger = QueryDebugger("python")

        code = "x = 1"
        query = "(identifier) @id"

        # First query
        matches1 = debugger.debug_query(query, code)

        # Second query (should use cache)
        matches2 = debugger.debug_query(query, code)

        assert len(matches1) == len(matches2)


class TestChunkDebugger:
    """Test chunk debugging functionality."""

    def test_chunk_debugger_creation(self):
        """Test creating chunk debugger."""
        debugger = ChunkDebugger("python")
        assert debugger.language == "python"
        assert debugger.parser is not None

    def test_chunk_analysis(self):
        """Test analyzing chunks."""
        debugger = ChunkDebugger("python")

        code = """
def func1():
    pass

def func2():
    x = 1
    y = 2
    return x + y

class TestClass:
    def method(self):
        pass
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            analysis = debugger.analyze_file(
                temp_file,
                show_decisions=True,
                show_overlap=True,
                show_gaps=True,
            )

            assert "total_chunks" in analysis
            assert "coverage_percent" in analysis
            assert "overlaps" in analysis
            assert "gaps" in analysis
            assert analysis["total_chunks"] >= 3  # At least 3 chunks
        finally:
            os.unlink(temp_file)

    def test_size_checking(self):
        """Test chunk size checking."""
        debugger = ChunkDebugger("python")

        code = """
def tiny():
    pass

def medium_function():
    # This is a medium function
    x = 1
    y = 2
    z = 3
    return x + y + z
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            analysis = debugger.analyze_file(
                temp_file,
                min_chunk_size=3,
                max_chunk_size=10,
            )

            assert "size_issues" in analysis
            # Should flag the tiny function
            assert len(analysis["size_issues"]) > 0
        finally:
            os.unlink(temp_file)


class TestVisualizationFunctions:
    """Test standalone visualization functions."""

    def test_print_ast_tree(self, capsys):
        """Test printing AST tree."""
        code = "x = 1"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            print_ast_tree(temp_file, "python", max_depth=2)
            captured = capsys.readouterr()
            # Should have printed something
            assert len(captured.out) > 0
        finally:
            os.unlink(temp_file)

    def test_highlight_chunk_boundaries(self, capsys):
        """Test highlighting chunk boundaries."""
        code = """
def func1():
    return 1

def func2():
    return 2
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            highlight_chunk_boundaries(temp_file, "python", show_stats=True)
            captured = capsys.readouterr()
            # Should have printed something
            assert len(captured.out) > 0
        finally:
            os.unlink(temp_file)

    @pytest.mark.skipif(
        not pytest.importorskip("graphviz", reason="graphviz not installed"),
        reason="graphviz required",
    )
    def test_render_ast_graph(self):
        """Test rendering AST graph."""
        code = "def hello():\n    print('world')"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            # Should return graph source
            source = render_ast_graph(temp_file, "python")
            assert source is not None
            assert "digraph" in source
            assert "function_definition" in source
        finally:
            os.unlink(temp_file)


class TestNodeExplorer:
    """Test node explorer functionality."""

    def test_node_explorer_creation(self):
        """Test creating node explorer."""
        from chunker.debug.interactive.node_explorer import NodeExplorer

        explorer = NodeExplorer("python")
        assert explorer.language == "python"
        assert explorer.parser is not None
        assert explorer.bookmarks == {}
        assert explorer.node_history == []

    def test_node_info(self):
        """Test getting node information."""
        from chunker.debug.interactive.node_explorer import NodeExplorer

        explorer = NodeExplorer("python")
        code = "x = 42"

        # Parse code
        tree = explorer.parser.parse(code.encode())
        node = tree.root_node

        # Get node info
        info = explorer._get_node_info(node)
        assert info.node == node
        assert info.content == code
        assert info.depth >= 0


class TestDebugREPL:
    """Test debug REPL functionality."""

    def test_repl_creation(self):
        """Test creating REPL instance."""
        from chunker.debug.interactive.repl import DebugREPL

        repl = DebugREPL()
        assert repl.current_language is None
        assert repl.current_file is None
        assert repl.current_code is None
        assert repl.history == []

    def test_set_language(self):
        """Test setting language in REPL."""
        from chunker.debug.interactive.repl import DebugREPL

        repl = DebugREPL()
        repl._set_language("python")

        assert repl.current_language == "python"
        assert repl.query_debugger is not None
        assert repl.chunk_debugger is not None
        assert repl.node_explorer is not None

    def test_set_code(self):
        """Test setting code in REPL."""
        from chunker.debug.interactive.repl import DebugREPL

        repl = DebugREPL()
        test_code = "def test():\n    pass"
        repl._set_code(test_code)

        assert repl.current_code == test_code
        assert repl.current_file is None

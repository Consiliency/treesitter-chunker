"""
Tests for debug and visualization tools.
"""
import json
import pathlib
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
from chunker.debug.interactive.node_explorer import NodeExplorer
from chunker.debug.interactive.repl import DebugREPL


class TestASTVisualizer:
    """Test AST visualization functionality."""

    @classmethod
    def test_ast_visualizer_creation(cls):
        """Test creating AST visualizer."""
        visualizer = ASTVisualizer("python")
        assert visualizer.language == "python"
        assert visualizer.parser is not None

    @classmethod
    def test_tree_visualization(cls):
        """Test tree format visualization."""
        visualizer = ASTVisualizer("python")
        code = "def hello():\n    print('Hello')"
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name
        try:
            result = visualizer.visualize_file(temp_file, output_format="tree")
            assert result is None
        finally:
            pathlib.Path(temp_file).unlink()

    @classmethod
    def test_json_visualization(cls):
        """Test JSON format visualization."""
        visualizer = ASTVisualizer("python")
        code = "x = 42"
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name
        try:
            result = visualizer.visualize_file(temp_file, output_format="json")
            assert result is not None
            assert isinstance(result, str)
            data = json.loads(result)
            assert "type" in data
            assert "children" in data
        finally:
            pathlib.Path(temp_file).unlink()

    @classmethod
    def test_highlight_nodes(cls):
        """Test node highlighting."""
        visualizer = ASTVisualizer("python")
        code = "def func():\n    x = 1\n    return x"
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name
        try:
            result = visualizer.visualize_file(temp_file, output_format="json", highlight_nodes={"function_definition",
                "return_statement"})
            assert result is not None
        finally:
            pathlib.Path(temp_file).unlink()


class TestQueryDebugger:
    """Test query debugging functionality."""

    @classmethod
    def test_query_debugger_creation(cls):
        """Test creating query debugger."""
        debugger = QueryDebugger("python")
        assert debugger.language == "python"
        assert debugger.parser is not None

    @classmethod
    def test_simple_query(cls):
        """Test debugging a simple query."""
        debugger = QueryDebugger("python")
        code = "def test():\n    pass"
        query = "(function_definition) @func"
        matches = debugger.debug_query(query, code, show_ast=False)
        assert len(matches) == 1
        assert matches[0].captures.get("@func") is not None

    @classmethod
    def test_query_with_captures(cls):
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

    @classmethod
    def test_invalid_query(cls):
        """Test handling invalid queries."""
        debugger = QueryDebugger("python")
        code = "x = 1"
        invalid_query = "(invalid_node_type)"
        matches = debugger.debug_query(invalid_query, code)
        assert len(matches) == 0

    @classmethod
    def test_query_cache(cls):
        """Test query caching."""
        debugger = QueryDebugger("python")
        code = "x = 1"
        query = "(identifier) @id"
        matches1 = debugger.debug_query(query, code)
        matches2 = debugger.debug_query(query, code)
        assert len(matches1) == len(matches2)


class TestChunkDebugger:
    """Test chunk debugging functionality."""

    @classmethod
    def test_chunk_debugger_creation(cls):
        """Test creating chunk debugger."""
        debugger = ChunkDebugger("python")
        assert debugger.language == "python"
        assert debugger.parser is not None

    @classmethod
    def test_chunk_analysis(cls):
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
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name
        try:
            analysis = debugger.analyze_file(temp_file, show_decisions=True,
                show_overlap=True, show_gaps=True)
            assert "total_chunks" in analysis
            assert "coverage_percent" in analysis
            assert "overlaps" in analysis
            assert "gaps" in analysis
            assert analysis["total_chunks"] >= 3
        finally:
            pathlib.Path(temp_file).unlink()

    @classmethod
    def test_size_checking(cls):
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
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name
        try:
            analysis = debugger.analyze_file(temp_file, min_chunk_size=3,
                max_chunk_size=10)
            assert "size_issues" in analysis
            assert len(analysis["size_issues"]) > 0
        finally:
            pathlib.Path(temp_file).unlink()


class TestVisualizationFunctions:
    """Test standalone visualization functions."""

    @staticmethod
    def test_print_ast_tree(capsys):
        """Test printing AST tree."""
        code = "x = 1"
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name
        try:
            print_ast_tree(temp_file, "python", max_depth=2)
            captured = capsys.readouterr()
            assert len(captured.out) > 0
        finally:
            pathlib.Path(temp_file).unlink()

    @staticmethod
    def test_highlight_chunk_boundaries(capsys):
        """Test highlighting chunk boundaries."""
        code = "\ndef func1():\n    return 1\n\ndef func2():\n    return 2\n"
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name
        try:
            highlight_chunk_boundaries(temp_file, "python", show_stats=True)
            captured = capsys.readouterr()
            assert len(captured.out) > 0
        finally:
            pathlib.Path(temp_file).unlink()

    @pytest.mark.skipif(not pytest.importorskip("graphviz", reason="graphviz not installed"), reason="graphviz required")
    @staticmethod
    def test_render_ast_graph():
        """Test rendering AST graph."""
        code = "def hello():\n    print('world')"
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name
        try:
            source = render_ast_graph(temp_file, "python")
            assert source is not None
            assert "digraph" in source
            assert "function_definition" in source
        finally:
            pathlib.Path(temp_file).unlink()


class TestNodeExplorer:
    """Test node explorer functionality."""

    @classmethod
    def test_node_explorer_creation(cls):
        """Test creating node explorer."""
        explorer = NodeExplorer("python")
        assert explorer.language == "python"
        assert explorer.parser is not None
        assert explorer.bookmarks == {}
        assert explorer.node_history == []

    @classmethod
    def test_node_info(cls):
        """Test getting node information."""
        explorer = NodeExplorer("python")
        code = "x = 42"
        explorer.current_content = code
        tree = explorer.parser.parse(code.encode())
        node = tree.root_node
        info = explorer._get_node_info(node)
        assert info.node == node
        assert info.content == code
        assert info.depth >= 0


class TestDebugREPL:
    """Test debug REPL functionality."""

    @classmethod
    def test_repl_creation(cls):
        """Test creating REPL instance."""
        repl = DebugREPL()
        assert repl.current_language is None
        assert repl.current_file is None
        assert repl.current_code is None
        assert repl.history == []

    @classmethod
    def test_set_language(cls):
        """Test setting language in REPL."""
        repl = DebugREPL()
        repl._set_language("python")
        assert repl.current_language == "python"
        assert repl.query_debugger is not None
        assert repl.chunk_debugger is not None
        assert repl.node_explorer is not None

    @classmethod
    def test_set_code(cls):
        """Test setting code in REPL."""
        repl = DebugREPL()
        test_code = "def test():\n    pass"
        repl._set_code(test_code)
        assert repl.current_code == test_code
        assert repl.current_file is None

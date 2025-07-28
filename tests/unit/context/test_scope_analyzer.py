"""Unit tests for scope analyzers."""

import pytest

from chunker.context import BaseScopeAnalyzer, ContextFactory
from chunker.parser import get_parser


class TestBaseScopeAnalyzer:
    """Test the base scope analyzer functionality."""

    def test_init(self):
        """Test initialization."""
        analyzer = BaseScopeAnalyzer("python")
        assert analyzer.language == "python"
        assert analyzer._scope_cache == {}
        assert analyzer._visible_symbols_cache == {}

    def test_get_scope_type_module(self):
        """Test getting scope type for module."""
        analyzer = BaseScopeAnalyzer("python")

        # Create a mock module node
        mock_node = type(
            "MockNode",
            (),
            {
                "type": "module",
                "parent": None,
            },
        )()

        result = analyzer.get_scope_type(mock_node)
        assert result == "module"

    def test_get_scope_type_unknown(self):
        """Test getting scope type for unknown node."""
        analyzer = BaseScopeAnalyzer("python")

        # Create a mock node with unknown type
        mock_node = type(
            "MockNode",
            (),
            {
                "type": "unknown_scope",
                "parent": None,
            },
        )()

        result = analyzer.get_scope_type(mock_node)
        assert result == "unknown"

    def test_get_scope_chain_empty(self):
        """Test getting scope chain for root node."""
        analyzer = BaseScopeAnalyzer("python")

        # Mock _is_scope_node to return False
        analyzer._is_scope_node = lambda node: False

        # Create a mock node
        mock_node = type(
            "MockNode",
            (),
            {
                "type": "identifier",
                "parent": None,
            },
        )()

        # Mock get_enclosing_scope to return None
        analyzer.get_enclosing_scope = lambda node: None

        result = analyzer.get_scope_chain(mock_node)
        assert result == []


class TestPythonScopeAnalyzer:
    """Test Python-specific scope analysis."""

    @pytest.fixture
    def python_code(self):
        """Sample Python code for testing."""
        return """
def outer_function():
    outer_var = 1

    def inner_function():
        inner_var = 2

        def deeply_nested():
            return outer_var + inner_var

        return deeply_nested()

    class InnerClass:
        def method(self):
            return outer_var

    return inner_function()

class TopLevel:
    class_var = 42

    def __init__(self):
        self.instance_var = 0
""".strip()

    def test_get_enclosing_scope(self, python_code):
        """Test finding enclosing scope."""
        parser = get_parser("python")
        tree = parser.parse(python_code.encode())

        analyzer = ContextFactory.create_scope_analyzer("python")

        # Find the deeply_nested function
        def find_function(node, name):
            if node.type == "function_definition":
                for child in node.children:
                    if child.type == "identifier" and child.text == name.encode():
                        return node
            for child in node.children:
                result = find_function(child, name)
                if result:
                    return result
            return None

        deeply_nested = find_function(tree.root_node, "deeply_nested")
        assert deeply_nested is not None

        # Get its enclosing scope
        enclosing = analyzer.get_enclosing_scope(deeply_nested)
        assert enclosing is not None
        assert analyzer.get_scope_type(enclosing) == "function"

    def test_get_scope_chain(self, python_code):
        """Test getting the chain of enclosing scopes."""
        parser = get_parser("python")
        tree = parser.parse(python_code.encode())

        analyzer = ContextFactory.create_scope_analyzer("python")

        # Find the deeply_nested function
        def find_function(node, name):
            if node.type == "function_definition":
                for child in node.children:
                    if child.type == "identifier" and child.text == name.encode():
                        return node
            for child in node.children:
                result = find_function(child, name)
                if result:
                    return result
            return None

        deeply_nested = find_function(tree.root_node, "deeply_nested")
        assert deeply_nested is not None

        # Get scope chain
        chain = analyzer.get_scope_chain(deeply_nested)
        assert len(chain) >= 2  # deeply_nested -> inner_function -> outer_function

        # Verify scope types
        scope_types = [analyzer.get_scope_type(scope) for scope in chain]
        assert "function" in scope_types

    def test_get_scope_type_map(self):
        """Test the scope type mapping for Python."""
        analyzer = ContextFactory.create_scope_analyzer("python")

        type_map = analyzer._get_scope_type_map()
        assert "module" in type_map
        assert "function_definition" in type_map
        assert "class_definition" in type_map
        assert "lambda" in type_map
        assert "list_comprehension" in type_map

    def test_is_scope_node(self):
        """Test checking if a node creates a scope."""
        analyzer = ContextFactory.create_scope_analyzer("python")

        # Create mock nodes
        func_node = type("MockNode", (), {"type": "function_definition"})()
        class_node = type("MockNode", (), {"type": "class_definition"})()
        other_node = type("MockNode", (), {"type": "identifier"})()

        assert analyzer._is_scope_node(func_node)
        assert analyzer._is_scope_node(class_node)
        assert not analyzer._is_scope_node(other_node)


class TestJavaScriptScopeAnalyzer:
    """Test JavaScript-specific scope analysis."""

    @pytest.fixture
    def javascript_code(self):
        """Sample JavaScript code for testing."""
        return """
function outerFunction() {
    const outerVar = 1;

    function innerFunction() {
        const innerVar = 2;

        const arrowFunc = () => {
            return outerVar + innerVar;
        };

        return arrowFunc();
    }

    class InnerClass {
        method() {
            return outerVar;
        }
    }

    return innerFunction();
}

class TopLevel {
    static classVar = 42;

    constructor() {
        this.instanceVar = 0;
    }

    get value() {
        return this.instanceVar;
    }
}

for (let i = 0; i < 10; i++) {
    // Block scope
    const blockVar = i * 2;
}
""".strip()

    def test_get_enclosing_scope(self, javascript_code):
        """Test finding enclosing scope in JavaScript."""
        parser = get_parser("javascript")
        tree = parser.parse(javascript_code.encode())

        analyzer = ContextFactory.create_scope_analyzer("javascript")

        # Find the arrow function
        def find_arrow_function(node):
            if node.type == "arrow_function":
                return node
            for child in node.children:
                result = find_arrow_function(child)
                if result:
                    return result
            return None

        arrow_func = find_arrow_function(tree.root_node)
        assert arrow_func is not None

        # Get its enclosing scope
        enclosing = analyzer.get_enclosing_scope(arrow_func)
        assert enclosing is not None
        assert analyzer.get_scope_type(enclosing) in ("function", "arrow")

    def test_block_scope(self, javascript_code):
        """Test that block statements create scopes in JavaScript."""
        parser = get_parser("javascript")
        tree = parser.parse(javascript_code.encode())

        analyzer = ContextFactory.create_scope_analyzer("javascript")

        # Find a for statement
        def find_for_statement(node):
            if node.type == "for_statement":
                return node
            for child in node.children:
                result = find_for_statement(child)
                if result:
                    return result
            return None

        for_stmt = find_for_statement(tree.root_node)
        assert for_stmt is not None

        # For statements create block scope
        assert analyzer._is_scope_node(for_stmt)
        assert analyzer.get_scope_type(for_stmt) == "block"

    def test_get_scope_type_map(self):
        """Test the scope type mapping for JavaScript."""
        analyzer = ContextFactory.create_scope_analyzer("javascript")

        type_map = analyzer._get_scope_type_map()
        assert "program" in type_map
        assert "function_declaration" in type_map
        assert "arrow_function" in type_map
        assert "class_declaration" in type_map
        assert "method_definition" in type_map
        assert "for_statement" in type_map
        assert "block_statement" in type_map
        assert "catch_clause" in type_map

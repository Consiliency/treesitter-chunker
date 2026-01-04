"""Integration tests for chunker with context extraction."""

import pytest

from chunker.context import ContextFactory
from chunker.core import chunk_text
from chunker.parser import get_parser


@pytest.mark.integration
class TestChunkerWithContext:
    """Test integrating context extraction with chunking."""

    @staticmethod
    @pytest.fixture
    def python_code_with_dependencies():
        """Python code with interdependencies."""
        return """
from typing import List, Dict
import math

class Point:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def distance_to(self, other: 'Point') -> float:
        ""\"Calculate distance to another point.""\"
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx * dx + dy * dy)

class Polygon:
    def __init__(self, points: List[Point]):
        if len(points) < 3:
            raise ValueError("Polygon must have at least 3 points")
        self.points = points

    def perimeter(self) -> float:
        ""\"Calculate the perimeter of the polygon.""\"
        total = 0.0
        for i in range(len(self.points)):
            p1 = self.points[i]
            p2 = self.points[(i + 1) % len(self.points)]
            total += p1.distance_to(p2)
        return total

    def add_point(self, point: Point) -> None:
        ""\"Add a point to the polygon.""\"
        self.points.append(point)

def create_square(size: float) -> Polygon:
    ""\"Create a square polygon.""\"
    points = [
        Point(0, 0),
        Point(size, 0),
        Point(size, size),
        Point(0, size)
    ]
    return Polygon(points)
""".strip()

    @staticmethod
    def test_chunk_with_context_preservation(python_code_with_dependencies):
        """Test that chunks include necessary context."""
        parser = get_parser("python")
        tree = parser.parse(python_code_with_dependencies.encode())
        source = python_code_with_dependencies.encode()
        chunks = chunk_text(python_code_with_dependencies, "python", "test.py")
        extractor = ContextFactory.create_context_extractor("python")
        filter_func = ContextFactory.create_context_filter("python")
        perimeter_chunk = None
        for chunk in chunks:
            if "perimeter" in chunk.content and "def perimeter" in chunk.content:
                perimeter_chunk = chunk
                break
        assert perimeter_chunk is not None

        def find_method_node(node, method_name):
            if node.type == "function_definition":
                for child in node.children:
                    if (
                        child.type == "identifier"
                        and child.text == method_name.encode()
                    ):
                        return node
            for child in node.children:
                result = find_method_node(child, method_name)
                if result:
                    return result
            return None

        perimeter_node = find_method_node(tree.root_node, "perimeter")
        assert perimeter_node is not None
        imports = extractor.extract_imports(tree.root_node, source)
        type_defs = extractor.extract_type_definitions(tree.root_node, source)
        parent_context = extractor.extract_parent_context(
            perimeter_node,
            tree.root_node,
            source,
        )
        dependencies = extractor.extract_dependencies(
            perimeter_node,
            tree.root_node,
            source,
        )
        all_context = imports + type_defs + parent_context + dependencies
        relevant_context = [
            item
            for item in all_context
            if filter_func.is_relevant(item, perimeter_node)
        ]
        context_prefix = extractor.build_context_prefix(relevant_context)
        assert "import math" in context_prefix
        assert "class Polygon" in context_prefix
        type_contents = [item.content for item in type_defs]
        assert any("class Point" in content for content in type_contents)
        enhanced_content = context_prefix + "\n\n" + perimeter_chunk.content
        assert "import" in enhanced_content
        assert "Point" in enhanced_content
        assert "distance_to" in enhanced_content or "class Point" in enhanced_content

    @staticmethod
    def test_context_for_function_using_classes(python_code_with_dependencies):
        """Test context for standalone function using classes."""
        parser = get_parser("python")
        tree = parser.parse(python_code_with_dependencies.encode())
        source = python_code_with_dependencies.encode()
        extractor, _resolver, _analyzer, filter_func = ContextFactory.create_all(
            "python",
        )

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

        create_square_node = find_function(tree.root_node, "create_square")
        assert create_square_node is not None
        dependencies = extractor.extract_dependencies(
            create_square_node,
            tree.root_node,
            source,
        )
        type_defs = extractor.extract_type_definitions(tree.root_node, source)
        all_context = dependencies + type_defs
        relevant_context = [
            item
            for item in all_context
            if filter_func.is_relevant(item, create_square_node)
        ]
        context_prefix = extractor.build_context_prefix(relevant_context)
        assert "class Point" in context_prefix
        assert "class Polygon" in context_prefix

    @staticmethod
    def test_javascript_react_component_context():
        """Test context extraction for React components."""
        javascript_code = """
import React, { useState } from 'react';
import { Button } from './components';
import { useAuth } from './hooks';

const LoginForm = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const { login, isLoading } = useAuth();

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            await login(email, password);
        } catch (error) {
            console.error('Login failed:', error);
        }
    };

    return (
        <form onSubmit={handleSubmit}>
            <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
            />
            <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
            />
            <Button type="submit" disabled={isLoading}>
                {isLoading ? 'Logging in...' : 'Login'}
            </Button>
        </form>
    );
};

export default LoginForm;
""".strip()
        parser = get_parser("javascript")
        tree = parser.parse(javascript_code.encode())
        source = javascript_code.encode()
        extractor = ContextFactory.create_context_extractor("javascript")

        def find_arrow_function(node, name):
            if node.type == "variable_declarator":
                has_name = False
                has_arrow = False
                for child in node.children:
                    if child.type == "identifier" and child.text == name.encode():
                        has_name = True
                    if child.type == "arrow_function":
                        has_arrow = True
                if has_name and has_arrow:
                    for child in node.children:
                        if child.type == "arrow_function":
                            return child
            for child in node.children:
                result = find_arrow_function(child, name)
                if result:
                    return result
            return None

        handle_submit = find_arrow_function(tree.root_node, "handleSubmit")
        assert handle_submit is not None
        imports = extractor.extract_imports(tree.root_node, source)
        parent_context = extractor.extract_parent_context(
            handle_submit,
            tree.root_node,
            source,
        )
        all_context = imports + parent_context
        context_prefix = extractor.build_context_prefix(all_context)
        assert "import React" in context_prefix
        assert "import { useAuth }" in context_prefix
        assert "const LoginForm" in context_prefix

    @staticmethod
    def test_context_size_limitation(python_code_with_dependencies):
        """Test that context can be limited in size."""
        parser = get_parser("python")
        tree = parser.parse(python_code_with_dependencies.encode())
        source = python_code_with_dependencies.encode()
        extractor = ContextFactory.create_context_extractor("python")
        imports = extractor.extract_imports(tree.root_node, source)
        type_defs = extractor.extract_type_definitions(tree.root_node, source)
        all_context = imports + type_defs
        unlimited = extractor.build_context_prefix(all_context)
        limited = extractor.build_context_prefix(all_context, max_size=50)
        assert len(limited) <= 100
        if len(unlimited) > 50:
            assert len(limited) < len(unlimited)
            assert "truncated" in limited

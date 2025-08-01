"""Tests for the hierarchical chunking strategy."""
import pytest

from chunker.parser import get_parser
from chunker.strategies.hierarchical import HierarchicalChunker


class TestHierarchicalChunker:
    """Test suite for HierarchicalChunker."""

    @classmethod
    @pytest.fixture
    def hierarchical_chunker(cls):
        """Create a hierarchical chunker instance."""
        return HierarchicalChunker()

    @staticmethod
    @pytest.fixture
    def nested_python_code():
        """Sample Python code with deep nesting."""
        return """
class OuterClass:
    ""\"Top-level class.""\"

    class MiddleClass:
        ""\"Nested class.""\"

        class InnerClass:
            ""\"Deeply nested class.""\"

            def inner_method(self):
                ""\"Method in deeply nested class.""\"
                return "inner"

        def middle_method(self):
            ""\"Method in nested class.""\"
            inner = self.InnerClass()
            return inner.inner_method()

    def outer_method(self):
        ""\"Method in top-level class.""\"
        middle = self.MiddleClass()
        return middle.middle_method()

    def complex_method(self):
        ""\"Method with nested control structures.""\"
        results = []

        for i in range(10):
            if i % 2 == 0:
                for j in range(5):
                    if j > 2:
                        try:
                            value = i * j
                            if value > 10:
                                results.append(value)
                        except (IndexError, KeyError, TypeError) as e:
                            print(f"Error: {e}")
            else:
                results.append(i)

        return results

def standalone_function():
    ""\"A standalone function outside classes.""\"
    data = [1, 2, 3, 4, 5]

    def process_item(item):
        ""\"Nested function.""\"
        return item * 2

    return [process_item(x) for x in data]
"""

    @staticmethod
    def test_can_handle(hierarchical_chunker):
        """Test language support."""
        assert hierarchical_chunker.can_handle("test.py", "python")
        assert hierarchical_chunker.can_handle("test.js", "javascript")
        assert hierarchical_chunker.can_handle("test.java", "java")
        assert not hierarchical_chunker.can_handle("test.xyz", "unknown")

    @staticmethod
    def test_hierarchical_structure(hierarchical_chunker, nested_python_code):
        """Test that hierarchical relationships are preserved."""
        parser = get_parser("python")
        tree = parser.parse(nested_python_code.encode())
        chunks = hierarchical_chunker.chunk(tree.root_node,
            nested_python_code.encode(), "test.py", "python")
        assert len(chunks) > 0
        parent_chunks = [c for c in chunks if c.parent_chunk_id is None]
        child_chunks = [c for c in chunks if c.parent_chunk_id is not None]
        assert len(parent_chunks) > 0
        assert len(child_chunks) > 0
        for chunk in chunks:
            assert hasattr(chunk, "metadata")
            assert "hierarchy_level" in chunk.metadata
            assert "hierarchy_depth" in chunk.metadata

    @staticmethod
    def test_granularity_settings(hierarchical_chunker, nested_python_code):
        """Test different granularity settings."""
        parser = get_parser("python")
        tree = parser.parse(nested_python_code.encode())
        hierarchical_chunker.configure({"granularity": "fine"})
        fine_chunks = hierarchical_chunker.chunk(tree.root_node,
            nested_python_code.encode(), "test.py", "python")
        hierarchical_chunker.configure({"granularity": "coarse"})
        coarse_chunks = hierarchical_chunker.chunk(tree.root_node,
            nested_python_code.encode(), "test.py", "python")
        assert len(fine_chunks) > len(coarse_chunks)
        coarse_levels = [c.metadata["hierarchy_level"] for c in coarse_chunks]
        assert max(coarse_levels) <= 2

    @staticmethod
    def test_max_depth_limit(hierarchical_chunker, nested_python_code):
        """Test that max depth is respected."""
        parser = get_parser("python")
        tree = parser.parse(nested_python_code.encode())
        hierarchical_chunker.configure({"max_depth": 2})
        chunks = hierarchical_chunker.chunk(tree.root_node,
            nested_python_code.encode(), "test.py", "python")
        for chunk in chunks:
            assert chunk.metadata["hierarchy_depth"] <= 2

    @staticmethod
    def test_leaf_node_preservation(hierarchical_chunker):
        """Test preservation of leaf nodes."""
        simple_code = """
def function1():
    return 1

def function2():
    return 2

x = 10
y = 20
z = x + y
"""
        parser = get_parser("python")
        tree = parser.parse(simple_code.encode())
        hierarchical_chunker.configure({"preserve_leaf_nodes": True})
        with_leaves = hierarchical_chunker.chunk(tree.root_node,
            simple_code.encode(), "test.py", "python")
        hierarchical_chunker.configure({"preserve_leaf_nodes": False,
            "min_chunk_size": 3})
        without_leaves = hierarchical_chunker.chunk(tree.root_node,
            simple_code.encode(), "test.py", "python")
        assert len(with_leaves) != len(without_leaves)

    @staticmethod
    def test_parent_context_tracking(hierarchical_chunker, nested_python_code):
        """Test that parent context is properly tracked."""
        parser = get_parser("python")
        tree = parser.parse(nested_python_code.encode())
        chunks = hierarchical_chunker.chunk(tree.root_node,
            nested_python_code.encode(), "test.py", "python")
        inner_chunks = [c for c in chunks if "inner" in c.content.lower() and
            c.parent_chunk_id]
        assert len(inner_chunks) > 0
        for inner in inner_chunks:
            assert inner.parent_context != "root"
            assert ":" in inner.parent_context
            parent = next((c for c in chunks if c.chunk_id == inner.
                parent_chunk_id), None)
            assert parent is not None

    @staticmethod
    def test_intermediate_nodes(hierarchical_chunker, nested_python_code):
        """Test inclusion of intermediate structural nodes."""
        parser = get_parser("python")
        tree = parser.parse(nested_python_code.encode())
        hierarchical_chunker.configure({"include_intermediate": True})
        with_intermediate = hierarchical_chunker.chunk(tree.root_node,
            nested_python_code.encode(), "test.py", "python")
        hierarchical_chunker.configure({"include_intermediate": False})
        without_intermediate = hierarchical_chunker.chunk(tree.root_node,
            nested_python_code.encode(), "test.py", "python")
        assert len(with_intermediate) >= len(without_intermediate)

    @staticmethod
    def test_hierarchical_optimization(hierarchical_chunker):
        """Test chunk optimization (splitting/merging)."""
        code_with_imbalance = """
class LargeClass:
    ""\"A class with imbalanced methods.""\"

    def tiny1(self):
        return 1

    def tiny2(self):
        return 2

    def tiny3(self):
        return 3

    def large_method(self):
        ""\"A very large method.""\"
        result = []

        # Many lines of code...
        for i in range(100):
            if i % 2 == 0:
                result.append(i)
            else:
                result.append(i * 2)

        # More processing...
        for i in range(50):
            if i % 3 == 0:
                result.append(i * 3)

        # Even more...
        for i in range(25):
            result.extend([i, i*2, i*3])

        return result
"""
        parser = get_parser("python")
        tree = parser.parse(code_with_imbalance.encode())
        chunks = hierarchical_chunker.chunk(tree.root_node,
            code_with_imbalance.encode(), "test.py", "python")
        for chunk in chunks:
            if hasattr(chunk, "metadata",
                ) and "merged_children" in chunk.metadata:
                assert chunk.metadata["merged_children"] > 0

    @staticmethod
    def test_javascript_hierarchy(hierarchical_chunker):
        """Test hierarchical chunking with JavaScript code."""
        js_code = """
class App {
    constructor() {
        this.state = {
            users: [],
            loading: false
        };
    }

    async loadUsers() {
        this.state.loading = true;

        try {
            const response = await fetch('/api/users');
            const data = await response.json();

            this.state.users = data.map(user => ({
                id: user.id,
                name: user.name,
                active: user.status === 'active'
            }));
        } catch (error) {
            console.error('Failed to load users:', error);
        } finally {
            this.state.loading = false;
        }
    }

    renderUser(user) {
        return {
            type: 'div',
            props: {
                className: user.active ? 'active' : 'inactive'
            },
            children: [user.name]
        };
    }
}

function createApp() {
    const app = new App();

    function handleClick() {
        app.loadUsers();
    }

    return { app, handleClick };
}
"""
        parser = get_parser("javascript")
        tree = parser.parse(js_code.encode())
        chunks = hierarchical_chunker.chunk(tree.root_node, js_code.encode(
            ), "test.js", "javascript")
        assert len(chunks) > 0
        node_types = {chunk.node_type for chunk in chunks}
        js_types = {"class_declaration", "method_definition",
            "function_declaration"}
        assert len(node_types & js_types) > 0

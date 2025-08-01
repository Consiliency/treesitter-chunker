"""Unit tests for context filters."""
from chunker.context import BaseContextFilter, ContextFactory
from chunker.interfaces.context import ContextItem, ContextType


class TestBaseContextFilter:
    """Test the base context filter_func functionality."""

    @classmethod
    def test_init(cls):
        """Test initialization."""
        filter_func = BaseContextFilter("python")
        assert filter_func.language == "python"
        assert filter_func._relevance_cache == {}

    @classmethod
    def test_is_relevant_imports_always_relevant(cls):
        """Test that imports are always considered relevant."""
        filter_func = BaseContextFilter("python")
        mock_node = type("MockNode", (), {"start_byte": 0, "end_byte": 10})()
        chunk_node = type("MockNode", (), {"start_byte": 100, "end_byte": 200},
            )()
        import_item = ContextItem(type=ContextType.IMPORT, content="import os", node=mock_node, line_number=1, importance=90)
        assert filter_func.is_relevant(import_item, chunk_node)

    @classmethod
    def test_is_relevant_parent_scope(cls):
        """Test that parent scope is relevant if it's an ancestor."""
        filter_func = BaseContextFilter("python")
        parent_node = type("MockNode", (), {"start_byte": 0, "end_byte":
            500, "parent": None})()
        chunk_node = type("MockNode", (), {"start_byte": 100, "end_byte":
            200, "parent": parent_node})()
        filter_func._is_ancestor = (lambda ancestor, node: ancestor ==
            parent_node)
        parent_item = ContextItem(type=ContextType.PARENT_SCOPE, content="class Parent:", node=parent_node, line_number=1, importance=70)
        assert filter_func.is_relevant(parent_item, chunk_node)

    @classmethod
    def test_score_relevance_by_type(cls):
        """Test relevance scoring based on context type."""
        filter_func = BaseContextFilter("python")
        mock_node = type("MockNode", (), {"start_byte": 0, "end_byte": 10})()
        chunk_node = type("MockNode", (), {"start_byte": 100, "end_byte": 200},
            )()
        filter_func._calculate_ast_distance = lambda n1, n2: 2
        filter_func._get_node_line = lambda node: 10
        filter_func._chunk_references_context = lambda chunk, ctx: False
        import_item = ContextItem(type=ContextType.IMPORT, content="import os", node=mock_node, line_number=1, importance=90)
        type_def_item = ContextItem(type=ContextType.TYPE_DEF, content="class MyClass:", node=mock_node, line_number=5, importance=80)
        constant_item = ContextItem(type=ContextType.CONSTANT, content="MAX_SIZE = 100", node=mock_node, line_number=8, importance=40)
        import_score = filter_func.score_relevance(import_item, chunk_node)
        type_def_score = filter_func.score_relevance(type_def_item, chunk_node)
        constant_score = filter_func.score_relevance(constant_item, chunk_node)
        assert import_score > type_def_score
        assert type_def_score > constant_score
        assert 0.0 <= import_score <= 1.0
        assert 0.0 <= type_def_score <= 1.0
        assert 0.0 <= constant_score <= 1.0

    @classmethod
    def test_score_relevance_by_distance(cls):
        """Test that closer items have higher relevance."""
        filter_func = BaseContextFilter("python")
        close_node = type("MockNode", (), {"start_byte": 80, "end_byte": 90})()
        far_node = type("MockNode", (), {"start_byte": 0, "end_byte": 10})()
        chunk_node = type("MockNode", (), {"start_byte": 100, "end_byte": 200},
            )()
        filter_func._get_node_line = lambda node: {id(close_node): 9, id(
            far_node): 1, id(chunk_node): 10}.get(id(node), 0)
        filter_func._calculate_ast_distance = lambda n1, n2: {(id(
            close_node), id(chunk_node)): 1, (id(far_node), id(chunk_node)): 10,
            }.get((id(n1), id(n2)), 5)
        filter_func._chunk_references_context = lambda chunk, ctx: False
        close_item = ContextItem(type=ContextType.DEPENDENCY, content="close_var = 1", node=close_node, line_number=9, importance=60)
        far_item = ContextItem(type=ContextType.DEPENDENCY, content="far_var = 1", node=far_node, line_number=1, importance=60)
        close_score = filter_func.score_relevance(close_item, chunk_node)
        far_score = filter_func.score_relevance(far_item, chunk_node)
        assert close_score > far_score

    @classmethod
    def test_score_relevance_with_references(cls):
        """Test that referenced context gets bonus relevance."""
        filter_func = BaseContextFilter("python")
        mock_node = type("MockNode", (), {"start_byte": 0, "end_byte": 10})()
        chunk_node = type("MockNode", (), {"start_byte": 100, "end_byte": 200},
            )()
        filter_func._calculate_ast_distance = lambda n1, n2: 5
        filter_func._get_node_line = (lambda node: 1 if node == mock_node else
            10)
        item = ContextItem(type=ContextType.DEPENDENCY, content="helper_func = lambda x: x * 2", node=mock_node, line_number=1,
            importance=60)
        filter_func._chunk_references_context = lambda chunk, ctx: False
        score_without_ref = filter_func.score_relevance(item, chunk_node)
        filter_func._relevance_cache.clear()
        filter_func._chunk_references_context = lambda chunk, ctx: True
        score_with_ref = filter_func.score_relevance(item, chunk_node)
        assert score_with_ref > score_without_ref
        assert abs(score_with_ref - (score_without_ref + 0.3)) < 0.001

    @classmethod
    def test_is_ancestor(cls):
        """Test the _is_ancestor helper method."""
        filter_func = BaseContextFilter("python")
        root = type("MockNode", (), {"parent": None})()
        parent = type("MockNode", (), {"parent": root})()
        child = type("MockNode", (), {"parent": parent})()
        unrelated = type("MockNode", (), {"parent": None})()
        assert filter_func._is_ancestor(root, child)
        assert filter_func._is_ancestor(parent, child)
        assert not filter_func._is_ancestor(child, child)
        assert not filter_func._is_ancestor(unrelated, child)
        assert not filter_func._is_ancestor(child, parent)

    @classmethod
    def test_calculate_ast_distance(cls):
        """Test calculating distance between nodes."""
        filter_func = BaseContextFilter("python")
        root = type("MockNode", (), {"parent": None})()
        left_parent = type("MockNode", (), {"parent": root})()
        right_parent = type("MockNode", (), {"parent": root})()
        left_child = type("MockNode", (), {"parent": left_parent})()
        right_child = type("MockNode", (), {"parent": right_parent})()
        distance = filter_func._calculate_ast_distance(left_parent,
            right_parent)
        assert distance == 2
        distance = filter_func._calculate_ast_distance(left_child, right_child)
        assert distance == 4
        distance = filter_func._calculate_ast_distance(left_child, left_child)
        assert distance == 0
        unrelated = type("MockNode", (), {"parent": None})()
        distance = filter_func._calculate_ast_distance(left_child, unrelated)
        assert distance == -1


class TestPythonContextFilter:
    """Test Python-specific context filtering."""

    @staticmethod
    def test_is_decorator_node():
        """Test identifying decorator nodes in Python."""
        filter_func = ContextFactory.create_context_filter("python")
        decorator_node = type("MockNode", (), {"type": "decorator"})()
        other_node = type("MockNode", (), {"type": "function_definition"})()
        assert filter_func._is_decorator_node(decorator_node)
        assert not filter_func._is_decorator_node(other_node)


class TestJavaScriptContextFilter:
    """Test JavaScript-specific context filtering."""

    @staticmethod
    def test_is_decorator_node():
        """Test identifying decorator nodes in JavaScript."""
        filter_func = ContextFactory.create_context_filter("javascript")
        decorator_node = type("MockNode", (), {"type": "decorator"})()
        other_node = type("MockNode", (), {"type": "function_declaration"})()
        assert filter_func._is_decorator_node(decorator_node)
        assert not filter_func._is_decorator_node(other_node)

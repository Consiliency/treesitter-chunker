"""Unit tests for context filters."""

import pytest

from chunker.context import BaseContextFilter, ContextFactory
from chunker.interfaces.context import ContextItem, ContextType
from chunker.parser import get_parser


class TestBaseContextFilter:
    """Test the base context filter functionality."""
    
    def test_init(self):
        """Test initialization."""
        filter = BaseContextFilter('python')
        assert filter.language == 'python'
        assert filter._relevance_cache == {}
    
    def test_is_relevant_imports_always_relevant(self):
        """Test that imports are always considered relevant."""
        filter = BaseContextFilter('python')
        
        # Create mock nodes
        mock_node = type('MockNode', (), {'start_byte': 0, 'end_byte': 10})()
        chunk_node = type('MockNode', (), {'start_byte': 100, 'end_byte': 200})()
        
        import_item = ContextItem(
            type=ContextType.IMPORT,
            content="import os",
            node=mock_node,
            line_number=1,
            importance=90
        )
        
        assert filter.is_relevant(import_item, chunk_node) == True
    
    def test_is_relevant_parent_scope(self):
        """Test that parent scope is relevant if it's an ancestor."""
        filter = BaseContextFilter('python')
        
        # Create mock nodes with parent relationship
        parent_node = type('MockNode', (), {
            'start_byte': 0, 
            'end_byte': 500,
            'parent': None
        })()
        
        chunk_node = type('MockNode', (), {
            'start_byte': 100, 
            'end_byte': 200,
            'parent': parent_node
        })()
        
        # Mock the _is_ancestor method
        filter._is_ancestor = lambda ancestor, node: ancestor == parent_node
        
        parent_item = ContextItem(
            type=ContextType.PARENT_SCOPE,
            content="class Parent:",
            node=parent_node,
            line_number=1,
            importance=70
        )
        
        assert filter.is_relevant(parent_item, chunk_node) == True
    
    def test_score_relevance_by_type(self):
        """Test relevance scoring based on context type."""
        filter = BaseContextFilter('python')
        
        # Create mock nodes
        mock_node = type('MockNode', (), {'start_byte': 0, 'end_byte': 10})()
        chunk_node = type('MockNode', (), {'start_byte': 100, 'end_byte': 200})()
        
        # Mock helper methods
        filter._calculate_ast_distance = lambda n1, n2: 2
        filter._get_node_line = lambda node: 10
        filter._chunk_references_context = lambda chunk, ctx: False
        
        # Test different context types
        import_item = ContextItem(
            type=ContextType.IMPORT,
            content="import os",
            node=mock_node,
            line_number=1,
            importance=90
        )
        
        type_def_item = ContextItem(
            type=ContextType.TYPE_DEF,
            content="class MyClass:",
            node=mock_node,
            line_number=5,
            importance=80
        )
        
        constant_item = ContextItem(
            type=ContextType.CONSTANT,
            content="MAX_SIZE = 100",
            node=mock_node,
            line_number=8,
            importance=40
        )
        
        import_score = filter.score_relevance(import_item, chunk_node)
        type_def_score = filter.score_relevance(type_def_item, chunk_node)
        constant_score = filter.score_relevance(constant_item, chunk_node)
        
        # Imports should have highest relevance
        assert import_score > type_def_score
        assert type_def_score > constant_score
        assert 0.0 <= import_score <= 1.0
        assert 0.0 <= type_def_score <= 1.0
        assert 0.0 <= constant_score <= 1.0
    
    def test_score_relevance_by_distance(self):
        """Test that closer items have higher relevance."""
        filter = BaseContextFilter('python')
        
        # Create mock nodes
        close_node = type('MockNode', (), {'start_byte': 80, 'end_byte': 90})()
        far_node = type('MockNode', (), {'start_byte': 0, 'end_byte': 10})()
        chunk_node = type('MockNode', (), {'start_byte': 100, 'end_byte': 200})()
        
        # Mock helper methods
        filter._get_node_line = lambda node: {
            id(close_node): 9,
            id(far_node): 1,
            id(chunk_node): 10
        }.get(id(node), 0)
        
        filter._calculate_ast_distance = lambda n1, n2: {
            (id(close_node), id(chunk_node)): 1,
            (id(far_node), id(chunk_node)): 10
        }.get((id(n1), id(n2)), 5)
        
        filter._chunk_references_context = lambda chunk, ctx: False
        
        close_item = ContextItem(
            type=ContextType.DEPENDENCY,
            content="close_var = 1",
            node=close_node,
            line_number=9,
            importance=60
        )
        
        far_item = ContextItem(
            type=ContextType.DEPENDENCY,
            content="far_var = 1",
            node=far_node,
            line_number=1,
            importance=60
        )
        
        close_score = filter.score_relevance(close_item, chunk_node)
        far_score = filter.score_relevance(far_item, chunk_node)
        
        # Closer items should have higher relevance
        assert close_score > far_score
    
    def test_score_relevance_with_references(self):
        """Test that referenced context gets bonus relevance."""
        filter = BaseContextFilter('python')
        
        # Create mock nodes
        mock_node = type('MockNode', (), {'start_byte': 0, 'end_byte': 10})()
        chunk_node = type('MockNode', (), {'start_byte': 100, 'end_byte': 200})()
        
        # Mock helper methods
        filter._calculate_ast_distance = lambda n1, n2: 5
        filter._get_node_line = lambda node: 1 if node == mock_node else 10
        
        item = ContextItem(
            type=ContextType.DEPENDENCY,
            content="helper_func = lambda x: x * 2",
            node=mock_node,
            line_number=1,
            importance=60
        )
        
        # Test without reference
        filter._chunk_references_context = lambda chunk, ctx: False
        score_without_ref = filter.score_relevance(item, chunk_node)
        
        # Clear cache before testing with reference
        filter._relevance_cache.clear()
        
        # Test with reference
        filter._chunk_references_context = lambda chunk, ctx: True
        score_with_ref = filter.score_relevance(item, chunk_node)
        
        # Referenced items should have higher score
        assert score_with_ref > score_without_ref
        assert abs(score_with_ref - (score_without_ref + 0.3)) < 0.001  # Handle floating point
    
    def test_is_ancestor(self):
        """Test the _is_ancestor helper method."""
        filter = BaseContextFilter('python')
        
        # Create node hierarchy
        root = type('MockNode', (), {'parent': None})()
        parent = type('MockNode', (), {'parent': root})()
        child = type('MockNode', (), {'parent': parent})()
        unrelated = type('MockNode', (), {'parent': None})()
        
        assert filter._is_ancestor(root, child) == True
        assert filter._is_ancestor(parent, child) == True
        assert filter._is_ancestor(child, child) == False  # Not its own ancestor
        assert filter._is_ancestor(unrelated, child) == False
        assert filter._is_ancestor(child, parent) == False  # Wrong direction
    
    def test_calculate_ast_distance(self):
        """Test calculating distance between nodes."""
        filter = BaseContextFilter('python')
        
        # Create node hierarchy
        root = type('MockNode', (), {'parent': None})()
        left_parent = type('MockNode', (), {'parent': root})()
        right_parent = type('MockNode', (), {'parent': root})()
        left_child = type('MockNode', (), {'parent': left_parent})()
        right_child = type('MockNode', (), {'parent': right_parent})()
        
        # Distance between siblings
        distance = filter._calculate_ast_distance(left_parent, right_parent)
        assert distance == 2  # Up to root and down
        
        # Distance between cousins
        distance = filter._calculate_ast_distance(left_child, right_child)
        assert distance == 4  # Up 2, down 2
        
        # Distance to self
        distance = filter._calculate_ast_distance(left_child, left_child)
        assert distance == 0
        
        # Unrelated nodes
        unrelated = type('MockNode', (), {'parent': None})()
        distance = filter._calculate_ast_distance(left_child, unrelated)
        assert distance == -1


class TestPythonContextFilter:
    """Test Python-specific context filtering."""
    
    def test_is_decorator_node(self):
        """Test identifying decorator nodes in Python."""
        filter = ContextFactory.create_context_filter('python')
        
        # Create mock nodes
        decorator_node = type('MockNode', (), {'type': 'decorator'})()
        other_node = type('MockNode', (), {'type': 'function_definition'})()
        
        assert filter._is_decorator_node(decorator_node) == True
        assert filter._is_decorator_node(other_node) == False


class TestJavaScriptContextFilter:
    """Test JavaScript-specific context filtering."""
    
    def test_is_decorator_node(self):
        """Test identifying decorator nodes in JavaScript."""
        filter = ContextFactory.create_context_filter('javascript')
        
        # Create mock nodes
        decorator_node = type('MockNode', (), {'type': 'decorator'})()
        other_node = type('MockNode', (), {'type': 'function_declaration'})()
        
        assert filter._is_decorator_node(decorator_node) == True
        assert filter._is_decorator_node(other_node) == False
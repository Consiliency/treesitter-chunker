"""Tests for smart context functionality."""
import time

import pytest

from chunker.interfaces.smart_context import ContextMetadata
from chunker.smart_context import (
    HybridContextStrategy,
    InMemoryContextCache,
    RelevanceContextStrategy,
    TreeSitterSmartContextProvider,
)
from chunker.types import CodeChunk


class TestTreeSitterSmartContextProvider:
    """Test the TreeSitterSmartContextProvider implementation."""

    @classmethod
    @pytest.fixture
    def provider(cls):
        """Create a smart context provider instance."""
        return TreeSitterSmartContextProvider()

    @classmethod
    @pytest.fixture
    def sample_chunks(cls):
        """Create sample code chunks for testing."""
        chunks = [CodeChunk(language="python", file_path="/test/module.py",
            node_type="function_definition", start_line=10, end_line=20,
            byte_start=100, byte_end=300, parent_context="", content="""def calculate_total(items):
    ""\"Calculate total price of items.""\"
    total = 0
    for item in items:
        total += item.price
    return total"""
            , chunk_id="chunk1"), CodeChunk(language="python", file_path="/test/module.py", node_type="function_definition", start_line=25, end_line=35, byte_start=400, byte_end=600, parent_context="", content="""def calculate_discount(total, discount_rate):
    ""\"Calculate discounted price.""\"
    if discount_rate < 0 or discount_rate > 1:
        raise ValueError("Invalid discount rate")
    return total * (1 - discount_rate)"""
            , chunk_id="chunk2"), CodeChunk(language="python", file_path="/test/module.py", node_type="class_definition", start_line=40,
            end_line=60, byte_start=700, byte_end=1000, parent_context="",
            content="""class ShoppingCart:
    def __init__(self):
        self.items = []

    def add_item(self, item):
        self.items.append(item)

    def get_total(self):
        return calculate_total(self.items)"""
            , chunk_id="chunk3"), CodeChunk(language="python", file_path="/test/utils.py", node_type="function_definition", start_line=5,
            end_line=10, byte_start=50, byte_end=150, parent_context="",
            content="""def format_price(price):
    ""\"Format price for display.""\"
    return f"${price:.2f}\""""
            , chunk_id="chunk4")]
        return chunks

    @staticmethod
    def test_semantic_context(provider, sample_chunks):
        """Test semantic context extraction."""
        context, metadata = provider.get_semantic_context(sample_chunks[0])
        assert isinstance(context, str)
        assert isinstance(metadata, ContextMetadata)
        assert metadata.relationship_type == "semantic"
        assert metadata.token_count >= 0

    @classmethod
    def test_semantic_similarity_calculation(cls, provider):
        """Test semantic similarity calculation between chunks."""
        chunk1 = CodeChunk(language="python", file_path="/test.py",
            node_type="function_definition", start_line=1, end_line=5,
            byte_start=0, byte_end=100, parent_context="", content="""def add(a, b):
    return a + b""", chunk_id="test1")
        chunk2 = CodeChunk(language="python", file_path="/test.py",
            node_type="function_definition", start_line=10, end_line=15,
            byte_start=200, byte_end=300, parent_context="", content="""def subtract(a, b):
    return a - b""", chunk_id="test2")
        features1 = provider._extract_semantic_features(chunk1)
        features2 = provider._extract_semantic_features(chunk2)
        similarity = provider._calculate_semantic_similarity(features1,
            features2)
        assert 0 < similarity < 1
        assert similarity > 0.3

    @staticmethod
    def test_dependency_context(provider, sample_chunks):
        """Test dependency context extraction."""
        dependencies = provider.get_dependency_context(sample_chunks[2],
            sample_chunks)
        assert isinstance(dependencies, list)
        assert len(dependencies) > 0
        dep_chunks = [dep[0] for dep in dependencies]
        dep_ids = [chunk.chunk_id for chunk in dep_chunks]
        assert "chunk1" in dep_ids
        for _chunk, metadata in dependencies:
            assert isinstance(metadata, ContextMetadata)
            assert metadata.relationship_type == "dependency"
            assert metadata.relevance_score > 0

    @staticmethod
    def test_usage_context(provider, sample_chunks):
        """Test usage context extraction."""
        usages = provider.get_usage_context(sample_chunks[0], sample_chunks)
        assert isinstance(usages, list)
        assert len(usages) > 0
        usage_chunks = [usage[0] for usage in usages]
        usage_ids = [chunk.chunk_id for chunk in usage_chunks]
        assert "chunk3" in usage_ids

    @staticmethod
    def test_structural_context(provider, sample_chunks):
        """Test structural context extraction."""
        structural = provider.get_structural_context(sample_chunks[0],
            sample_chunks)
        assert isinstance(structural, list)
        for chunk, metadata in structural:
            assert isinstance(metadata, ContextMetadata)
            assert metadata.relationship_type == "structural"
            assert chunk.file_path == sample_chunks[0].file_path

    @classmethod
    def test_extract_imports(cls, provider):
        """Test import extraction."""
        chunk = CodeChunk(language="python", file_path="/test.py",
            node_type="module", start_line=1, end_line=10, byte_start=0,
            byte_end=200, parent_context="", content="""import os
from pathlib import Path
from typing import List, Dict
import numpy as np"""
            , chunk_id="test_imports")
        imports = provider._extract_imports(chunk)
        assert "os" in imports
        assert "pathlib" in imports
        assert "Path" in imports
        assert "typing" in imports
        assert "List" in imports
        assert "Dict" in imports
        assert "numpy as np" in imports or "numpy" in imports

    @classmethod
    def test_extract_function_calls(cls, provider):
        """Test function call extraction."""
        chunk = CodeChunk(language="python", file_path="/test.py",
            node_type="function_definition", start_line=1, end_line=10,
            byte_start=0, byte_end=200, parent_context="", content="""def process_data(data):
    result = calculate_total(data)
    formatted = format_price(result)
    print(formatted)
    return formatted"""
            , chunk_id="test_calls")
        calls = provider._extract_function_calls(chunk)
        assert "calculate_total" in calls
        assert "format_price" in calls
        assert "print" in calls
        assert "def" not in calls

    @classmethod
    def test_extract_exports(cls, provider):
        """Test export extraction."""
        chunk = CodeChunk(language="python", file_path="/test.py",
            node_type="module", start_line=1, end_line=20, byte_start=0,
            byte_end=400, parent_context="", content="""CONSTANT = 42

def my_function():
    pass

class MyClass:
    pass

async def async_function():
    pass"""
            , chunk_id="test_exports")
        exports = provider._extract_exports(chunk)
        assert "my_function" in exports["functions"]
        assert "async_function" in exports["functions"]
        assert "MyClass" in exports["classes"]
        assert "CONSTANT" in exports["variables"]

    @classmethod
    def test_structural_relationships(cls, provider):
        """Test structural relationship detection."""
        parent_chunk = CodeChunk(language="python", file_path="/test.py",
            node_type="class_definition", start_line=1, end_line=20,
            byte_start=0, byte_end=400, parent_context="", content="""class Parent:
    pass""", chunk_id="parent")
        child_chunk = CodeChunk(language="python", file_path="/test.py",
            node_type="function_definition", start_line=5, end_line=10,
            byte_start=50, byte_end=150, parent_context="class Parent",
            content="""    def method(self):
        pass""", chunk_id="child")
        sibling_chunk = CodeChunk(language="python", file_path="/test.py",
            node_type="function_definition", start_line=12, end_line=15,
            byte_start=200, byte_end=250, parent_context="class Parent",
            content="""    def another_method(self):
        pass""",
            chunk_id="sibling")
        assert provider._is_parent_of(parent_chunk, child_chunk)
        assert provider._is_child_of(child_chunk, parent_chunk)
        assert provider._is_sibling_of(child_chunk, sibling_chunk)
        assert provider._is_in_same_class(child_chunk, sibling_chunk)


class TestContextStrategies:
    """Test context selection strategies."""

    @classmethod
    def test_relevance_strategy(cls):
        """Test relevance-based context selection."""
        strategy = RelevanceContextStrategy()
        main_chunk = CodeChunk(language="python", file_path="/test.py",
            node_type="function_definition", start_line=1, end_line=10,
            byte_start=0, byte_end=200, parent_context="", content="""def main():
    pass""", chunk_id="main")
        candidates = [(CodeChunk(language="python", file_path="/test.py",
            node_type="function_definition", start_line=15, end_line=20,
            byte_start=300, byte_end=400, parent_context="", content="""def helper1():
    pass""", chunk_id="helper1"),
            ContextMetadata(relevance_score=0.9, relationship_type="dependency", distance=5, token_count=50)), (CodeChunk(language="python", file_path="/test.py", node_type="function_definition", start_line=25, end_line=30, byte_start=500, byte_end=600, parent_context="", content="""def helper2():
    pass""", chunk_id="helper2"),
            ContextMetadata(relevance_score=0.7, relationship_type="semantic", distance=15, token_count=60)), (CodeChunk(language="python", file_path="/test.py", node_type="function_definition",
            start_line=35, end_line=40, byte_start=700, byte_end=800,
            parent_context="", content="""def helper3():
    pass""",
            chunk_id="helper3"), ContextMetadata(relevance_score=0.5,
            relationship_type="usage", distance=25, token_count=70))]
        selected = strategy.select_context(main_chunk, candidates,
            max_tokens=120)
        assert len(selected) == 2
        assert selected[0].chunk_id == "helper1"
        assert selected[1].chunk_id == "helper2"
        ranked = strategy.rank_candidates(main_chunk, candidates)
        assert len(ranked) == 3
        assert ranked[0][0].chunk_id == "helper1"
        assert ranked[0][1] > ranked[1][1]

    @classmethod
    def test_hybrid_strategy(cls):
        """Test hybrid context selection strategy."""
        strategy = HybridContextStrategy(weights={"dependency": 0.4,
            "semantic": 0.3, "usage": 0.2, "structural": 0.1})
        main_chunk = CodeChunk(language="python", file_path="/test.py",
            node_type="function_definition", start_line=1, end_line=10,
            byte_start=0, byte_end=200, parent_context="", content="""def main():
    pass""", chunk_id="main")
        candidates = [(CodeChunk(language="python", file_path="/test.py",
            node_type="function_definition", start_line=15, end_line=20,
            byte_start=300, byte_end=400, parent_context="", content="""def dep1():
    pass""", chunk_id="dep1"), ContextMetadata(
            relevance_score=0.9, relationship_type="dependency", distance=5,
            token_count=100)), (CodeChunk(language="python", file_path="/test.py", node_type="function_definition", start_line=25,
            end_line=30, byte_start=500, byte_end=600, parent_context="",
            content="""def dep2():
    pass""", chunk_id="dep2"),
            ContextMetadata(relevance_score=0.4, relationship_type="dependency", distance=15, token_count=100)), (CodeChunk(
            language="python", file_path="/test.py", node_type="function_definition", start_line=35, end_line=40, byte_start=700, byte_end=800, parent_context="", content="""def sem1():
    pass""", chunk_id="sem1"), ContextMetadata(
            relevance_score=0.8, relationship_type="semantic", distance=25,
            token_count=100))]
        selected = strategy.select_context(main_chunk, candidates,
            max_tokens=300)
        assert len(selected) > 0
        ranked = strategy.rank_candidates(main_chunk, candidates)
        assert len(ranked) == 3
        assert ranked[0][0].chunk_id == "dep1"


class TestContextCache:
    """Test context caching functionality."""

    @classmethod
    def test_cache_basic_operations(cls):
        """Test basic cache operations."""
        cache = InMemoryContextCache(ttl=60)
        chunk = CodeChunk(language="python", file_path="/test.py",
            node_type="function_definition", start_line=1, end_line=10,
            byte_start=0, byte_end=200, parent_context="", content="""def test():
    pass""", chunk_id="test1")
        context_data = [(chunk, ContextMetadata(relevance_score=0.8,
            relationship_type="dependency", distance=10, token_count=50))]
        cache.set("test1", "dependency", context_data)
        retrieved = cache.get("test1", "dependency")
        assert retrieved is not None
        assert len(retrieved) == 1
        assert retrieved[0][0].chunk_id == "test1"
        assert cache.get("test1", "usage") is None
        assert cache.get("test2", "dependency") is None

    @classmethod
    def test_cache_expiration(cls):
        """Test cache expiration."""
        cache = InMemoryContextCache(ttl=0.1)
        chunk = CodeChunk(language="python", file_path="/test.py",
            node_type="function_definition", start_line=1, end_line=10,
            byte_start=0, byte_end=200, parent_context="", content="""def test():
    pass""", chunk_id="test1")
        context_data = [(chunk, ContextMetadata(0.8, "dependency", 10, 50))]
        cache.set("test1", "dependency", context_data)
        assert cache.get("test1", "dependency") is not None
        time.sleep(0.2)
        assert cache.get("test1", "dependency") is None

    @classmethod
    def test_cache_invalidation(cls):
        """Test cache invalidation."""
        cache = InMemoryContextCache()
        for i in range(3):
            chunk = CodeChunk(language="python", file_path=f"/test{i}.py",
                node_type="function_definition", start_line=1, end_line=10,
                byte_start=0, byte_end=200, parent_context="", content=f"""def test{i}():
    pass""", chunk_id=f"test{i}")
            context_data = [(chunk, ContextMetadata(0.8, "dependency", 10, 50)),
                ]
            cache.set(f"test{i}", "dependency", context_data)
        assert cache.get("test0", "dependency") is not None
        assert cache.get("test1", "dependency") is not None
        assert cache.get("test2", "dependency") is not None
        cache.invalidate({"test0", "test1"})
        assert cache.get("test0", "dependency") is None
        assert cache.get("test1", "dependency") is None
        assert cache.get("test2", "dependency") is not None
        cache.invalidate()
        assert cache.get("test2", "dependency") is None


class TestIntegration:
    """Integration tests for smart context functionality."""

    @classmethod
    def test_full_context_workflow(cls):
        """Test complete context extraction workflow."""
        provider = TreeSitterSmartContextProvider()
        strategy = RelevanceContextStrategy()
        chunks = [CodeChunk(language="python", file_path="/app/models.py",
            node_type="class_definition", start_line=10, end_line=30,
            byte_start=100, byte_end=600, parent_context="", content="""class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email

    def validate_email(self):
        return '@' in self.email"""
            , chunk_id="user_class"), CodeChunk(language="python",
            file_path="/app/services.py", node_type="function_definition",
            start_line=5, end_line=15, byte_start=50, byte_end=300,
            parent_context="", content="""def create_user(name, email):
    from models import User
    user = User(name, email)
    if user.validate_email():
        return user
    raise ValueError("Invalid email")"""
            , chunk_id="create_user"), CodeChunk(language="python",
            file_path="/app/views.py", node_type="function_definition",
            start_line=20, end_line=30, byte_start=400, byte_end=600,
            parent_context="", content="""def register_view(request):
    from services import create_user
    user = create_user(request.name, request.email)
    return {"status": "success", "user_id": user.id}"""
            , chunk_id="register_view")]
        dependencies = provider.get_dependency_context(chunks[2], chunks)
        assert len(dependencies) > 0
        dep_ids = [d[0].chunk_id for d in dependencies]
        assert "create_user" in dep_ids
        usages = provider.get_usage_context(chunks[0], chunks)
        assert len(usages) > 0
        usage_ids = [u[0].chunk_id for u in usages]
        assert "create_user" in usage_ids
        all_context = dependencies + usages
        selected = strategy.select_context(chunks[2], all_context,
            max_tokens=500)
        assert len(selected) > 0
        assert all(isinstance(chunk, CodeChunk) for chunk in selected)

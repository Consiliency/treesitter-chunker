"""Integration tests for Phase 9 semantic merging with other features."""

import pytest
from pathlib import Path
from chunker import (
    chunk_file,
    TreeSitterSemanticMerger,
    TiktokenCounter,
    ChunkHierarchyBuilder,
    BaseMetadataExtractor as MetadataExtractor
)
from chunker.semantic_merging import MergeStrategy


class TestSemanticMergingIntegration:
    """Test semantic merging working with other Phase 9 features."""
    
    @pytest.fixture
    def test_file(self, tmp_path):
        """Create a test file with getter/setter pairs and small methods."""
        test_file = tmp_path / "user.py"
        test_file.write_text('''
class User:
    """User model with properties."""
    
    def __init__(self, name, age):
        self._name = name
        self._age = age
        self._email = None
    
    # Getter/setter pair for name
    def get_name(self):
        """Get user name."""
        return self._name
    
    def set_name(self, name):
        """Set user name."""
        self._name = name
    
    # Getter/setter pair for age
    def get_age(self):
        """Get user age."""
        return self._age
    
    def set_age(self, age):
        """Set user age."""
        if age < 0:
            raise ValueError("Age cannot be negative")
        self._age = age
    
    # Getter/setter pair for email
    def get_email(self):
        """Get user email."""
        return self._email
    
    def set_email(self, email):
        """Set user email."""
        if "@" not in email:
            raise ValueError("Invalid email")
        self._email = email
    
    # Utility methods
    def is_adult(self):
        """Check if user is adult."""
        return self._age >= 18
    
    def has_email(self):
        """Check if user has email."""
        return self._email is not None
    
    def format_name(self):
        """Format name for display."""
        return self._name.title()
''')
        return test_file
    
    def test_semantic_merging_with_token_counting(self, test_file):
        """Test that merged chunks respect token limits."""
        # Get original chunks
        chunks = chunk_file(test_file, "python")
        
        # Create merger with token limit
        counter = TiktokenCounter()
        merger = TreeSitterSemanticMerger(
            merge_strategy=MergeStrategy.BALANCED,
            max_chunk_size=200  # Small limit to test splitting
        )
        
        # Merge chunks
        merged_chunks = merger.merge_chunks(chunks)
        
        # Verify merged chunks
        assert len(merged_chunks) < len(chunks)  # Should have fewer chunks
        
        # Check token counts
        for chunk in merged_chunks:
            tokens = counter.count_tokens(chunk.content)
            assert tokens <= 200, f"Chunk exceeded token limit: {tokens} tokens"
        
        # Verify getter/setter pairs are merged
        merged_contents = [c.content for c in merged_chunks]
        getter_setter_merged = any(
            "get_name" in content and "set_name" in content
            for content in merged_contents
        )
        assert getter_setter_merged, "Getter/setter pairs should be merged"
    
    def test_semantic_merging_with_hierarchy(self, test_file):
        """Test that semantic merging preserves hierarchy relationships."""
        # Get original chunks
        chunks = chunk_file(test_file, "python")
        
        # Build hierarchy
        hierarchy_builder = ChunkHierarchyBuilder()
        hierarchy = hierarchy_builder.build_hierarchy(chunks)
        
        # Merge chunks
        merger = TreeSitterSemanticMerger()
        merged_chunks = merger.merge_chunks(chunks)
        
        # Rebuild hierarchy with merged chunks
        merged_hierarchy = hierarchy_builder.build_hierarchy(merged_chunks)
        
        # Verify class still has children
        class_chunk = next(c for c in merged_chunks if "class User" in c.content)
        assert merged_hierarchy.get_children(class_chunk.chunk_id), "Class should have children"
        
        # Verify merged methods are still children of class
        for chunk in merged_chunks:
            if chunk.chunk_id != class_chunk.chunk_id:
                parent = merged_hierarchy.get_parent(chunk.chunk_id)
                assert parent == class_chunk.chunk_id, "Methods should be children of class"
    
    def test_semantic_merging_with_metadata(self, test_file):
        """Test that semantic merging preserves and combines metadata."""
        # Get original chunks
        chunks = chunk_file(test_file, "python")
        
        # Extract metadata
        extractor = MetadataExtractor()
        for chunk in chunks:
            chunk.metadata = extractor.extract_metadata(chunk)
        
        # Merge chunks
        merger = TreeSitterSemanticMerger()
        merged_chunks = merger.merge_chunks(chunks)
        
        # Verify metadata is preserved
        for chunk in merged_chunks:
            assert chunk.metadata is not None
            
            # If chunk contains getters/setters, should have multiple signatures
            if "get_" in chunk.content and "set_" in chunk.content:
                signatures = chunk.metadata.get("signatures", [])
                assert len(signatures) >= 2, "Merged chunk should have multiple signatures"
    
    def test_semantic_merging_strategies(self, test_file):
        """Test different merge strategies produce different results."""
        chunks = chunk_file(test_file, "python")
        
        # Test aggressive merging
        aggressive_merger = TreeSitterSemanticMerger(
            merge_strategy=MergeStrategy.AGGRESSIVE,
            max_chunk_size=1000
        )
        aggressive_chunks = aggressive_merger.merge_chunks(chunks)
        
        # Test conservative merging
        conservative_merger = TreeSitterSemanticMerger(
            merge_strategy=MergeStrategy.CONSERVATIVE,
            max_chunk_size=1000
        )
        conservative_chunks = conservative_merger.merge_chunks(chunks)
        
        # Test preserve structure
        preserve_merger = TreeSitterSemanticMerger(
            merge_strategy=MergeStrategy.PRESERVE_STRUCTURE,
            max_chunk_size=1000
        )
        preserve_chunks = preserve_merger.merge_chunks(chunks)
        
        # Aggressive should produce fewest chunks
        assert len(aggressive_chunks) <= len(conservative_chunks)
        # Preserve structure should maintain original count
        assert len(preserve_chunks) == len(chunks)
        
    def test_semantic_merging_cross_file(self, tmp_path):
        """Test semantic merging across multiple files."""
        # Create related files
        base_file = tmp_path / "base.py"
        base_file.write_text('''
class BaseModel:
    def save(self):
        """Save model."""
        pass
    
    def delete(self):
        """Delete model."""
        pass
''')
        
        user_file = tmp_path / "user.py"
        user_file.write_text('''
from .base import BaseModel

class User(BaseModel):
    def save(self):
        """Save user."""
        super().save()
        print("User saved")
    
    def delete(self):
        """Delete user."""
        super().delete()
        print("User deleted")
''')
        
        # Process both files
        base_chunks = chunk_file(base_file, "python")
        user_chunks = chunk_file(user_file, "python")
        
        # Merge all chunks
        merger = TreeSitterSemanticMerger()
        all_chunks = base_chunks + user_chunks
        merged = merger.merge_chunks(all_chunks)
        
        # Should merge related methods across files
        assert len(merged) < len(all_chunks)
"""Integration tests to verify Phase 10 interfaces work together correctly."""

import pytest
from typing import List, Dict, Any
from pathlib import Path

# Import Phase 10 interfaces
from chunker.interfaces.smart_context import (
    SmartContextProvider, ContextStrategy, ContextMetadata
)
from chunker.interfaces.query_advanced import (
    ChunkQueryAdvanced, QueryIndexAdvanced, QueryType, QueryResult
)
from chunker.interfaces.optimization import (
    ChunkOptimizer, OptimizationStrategy, OptimizationMetrics
)
from chunker.interfaces.multi_language import (
    MultiLanguageProcessor, LanguageRegion, CrossLanguageReference
)
from chunker.interfaces.incremental import (
    IncrementalProcessor, ChunkCache, ChunkDiff, ChangeType
)

from chunker.types import CodeChunk
from chunker import chunk_file


class TestPhase10InterfaceCompatibility:
    """Test that Phase 10 interfaces work together correctly."""
    
    @pytest.fixture
    def sample_chunks(self, tmp_path) -> List[CodeChunk]:
        """Create sample chunks for testing."""
        test_file = tmp_path / "test.py"
        test_file.write_text('''
def calculate_sum(numbers: List[int]) -> int:
    """Calculate sum of numbers."""
    total = 0
    for num in numbers:
        total += num
    return total

def calculate_average(numbers: List[int]) -> float:
    """Calculate average of numbers."""
    if not numbers:
        return 0.0
    return calculate_sum(numbers) / len(numbers)

class Statistics:
    """Calculate statistics for number lists."""
    
    def __init__(self):
        self.data = []
    
    def add_data(self, numbers: List[int]):
        """Add data for analysis."""
        self.data.extend(numbers)
    
    def get_mean(self) -> float:
        """Get mean of all data."""
        return calculate_average(self.data)
''')
        chunks = chunk_file(test_file, "python")
        return chunks
    
    def test_smart_context_with_optimizer(self, sample_chunks):
        """Test that smart context works with chunk optimizer."""
        # This test verifies the interfaces can be used together
        # Actual implementation would be done in worktrees
        
        # Mock smart context provider
        class MockContextProvider(SmartContextProvider):
            def get_semantic_context(self, chunk, max_tokens=2000):
                return "# Related context", ContextMetadata(0.8, "semantic", 1, 50)
            
            def get_dependency_context(self, chunk, chunks):
                return [(chunks[0], ContextMetadata(0.9, "dependency", 0, 100))]
            
            def get_usage_context(self, chunk, chunks):
                return []
            
            def get_structural_context(self, chunk, chunks):
                return []
        
        # Mock optimizer
        class MockOptimizer(ChunkOptimizer):
            def optimize_for_llm(self, chunks, model, max_tokens, strategy=OptimizationStrategy.BALANCED):
                metrics = OptimizationMetrics(
                    len(chunks), len(chunks), 100, 120, 0.85, 0.9
                )
                return chunks, metrics
            
            def merge_small_chunks(self, chunks, min_tokens, preserve_boundaries=True):
                return chunks
            
            def split_large_chunks(self, chunks, max_tokens, split_points=None):
                return chunks
            
            def rebalance_chunks(self, chunks, target_tokens, variance=0.2):
                return chunks
            
            def optimize_for_embedding(self, chunks, model, max_tokens=512):
                return chunks
        
        # Test using them together
        context_provider = MockContextProvider()
        optimizer = MockOptimizer()
        
        # Get context for first chunk
        context_str, metadata = context_provider.get_semantic_context(sample_chunks[0])
        assert context_str == "# Related context"
        assert metadata.relevance_score == 0.8
        
        # Optimize chunks
        optimized, metrics = optimizer.optimize_for_llm(sample_chunks, "gpt-4", 8000)
        assert len(optimized) == len(sample_chunks)
        assert metrics.coherence_score == 0.85
    
    def test_query_with_multi_language(self, tmp_path):
        """Test querying across multiple languages."""
        # Create mixed language project structure
        project_dir = tmp_path / "mixed_project"
        project_dir.mkdir()
        
        # Python backend
        backend_dir = project_dir / "backend"
        backend_dir.mkdir()
        (backend_dir / "api.py").write_text('''
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/users')
def get_users():
    """Get all users from database."""
    return jsonify({"users": ["alice", "bob"]})
''')
        
        # JavaScript frontend
        frontend_dir = project_dir / "frontend"
        frontend_dir.mkdir()
        (frontend_dir / "api.js").write_text('''
async function fetchUsers() {
    const response = await fetch('/api/users');
    const data = await response.json();
    return data.users;
}
''')
        
        # Mock processors
        class MockMultiLanguageProcessor(MultiLanguageProcessor):
            def detect_project_languages(self, path):
                return {"python": 0.5, "javascript": 0.5}
            
            def identify_language_regions(self, file_path, content):
                return [LanguageRegion("python", 0, len(content), 1, 10)]
            
            def process_mixed_file(self, file_path, primary_language, content=None):
                return chunk_file(file_path, primary_language)
            
            def extract_embedded_code(self, content, host_lang, target_lang):
                return []
            
            def cross_language_references(self, chunks):
                # Find API references
                refs = []
                for i, chunk in enumerate(chunks):
                    if "/api/users" in chunk.content:
                        for j, other in enumerate(chunks):
                            if i != j and "get_users" in other.content:
                                refs.append(CrossLanguageReference(
                                    chunk, other, "api_call", 0.9
                                ))
                return refs
            
            def group_by_feature(self, chunks):
                return {"user_api": chunks}
        
        class MockQuery(ChunkQueryAdvanced):
            def search(self, query, chunks, query_type=QueryType.NATURAL_LANGUAGE, limit=None):
                results = []
                for chunk in chunks:
                    if query.lower() in chunk.content.lower():
                        results.append(QueryResult(chunk, 0.9, [], {}))
                return results
            
            def filter(self, chunks, **kwargs):
                return chunks
            
            def find_similar(self, chunk, chunks, threshold=0.7, limit=None):
                return []
        
        # Test cross-language functionality
        processor = MockMultiLanguageProcessor()
        query_engine = MockQuery()
        
        # Detect languages
        languages = processor.detect_project_languages(str(project_dir))
        assert "python" in languages
        assert "javascript" in languages
        
        # Process files
        py_chunks = chunk_file(backend_dir / "api.py", "python")
        js_chunks = chunk_file(frontend_dir / "api.js", "javascript")
        all_chunks = py_chunks + js_chunks
        
        # Find cross-language references
        refs = processor.cross_language_references(all_chunks)
        assert len(refs) > 0  # Should find API reference
        
        # Query across languages
        results = query_engine.search("users", all_chunks)
        assert len(results) >= 2  # Should find in both files
    
    def test_incremental_with_optimization(self, sample_chunks):
        """Test incremental processing with optimization."""
        # Mock incremental processor
        class MockIncrementalProcessor(IncrementalProcessor):
            def compute_diff(self, old_chunks, new_content, language):
                # Simulate one chunk modified
                changes = []
                if old_chunks:
                    changes.append(ChunkChange(
                        old_chunks[0].chunk_id,
                        ChangeType.MODIFIED,
                        old_chunks[0],
                        old_chunks[0],  # Would be new version
                        [(1, 5)],
                        0.95
                    ))
                return ChunkDiff(
                    changes, [], [], [(old_chunks[0], old_chunks[0])], 
                    old_chunks[1:], {"modified": 1}
                )
            
            def update_chunks(self, old_chunks, diff):
                return old_chunks  # Simplified
            
            def detect_moved_chunks(self, old_chunks, new_chunks):
                return []
            
            def merge_incremental_results(self, full, incremental, regions):
                return full
        
        class MockCache(ChunkCache):
            def __init__(self):
                self.cache = {}
            
            def store(self, file_path, chunks, file_hash, metadata=None):
                self.cache[file_path] = {
                    "chunks": chunks,
                    "hash": file_hash
                }
            
            def retrieve(self, file_path, file_hash=None):
                return self.cache.get(file_path)
            
            def invalidate(self, file_path=None, older_than=None):
                if file_path:
                    self.cache.pop(file_path, None)
                    return 1
                count = len(self.cache)
                self.cache.clear()
                return count
            
            def get_statistics(self):
                return {"entries": len(self.cache)}
            
            def export_cache(self, path):
                pass
            
            def import_cache(self, path):
                pass
        
        class MockOptimizer(ChunkOptimizer):
            def optimize_for_llm(self, chunks, model, max_tokens, strategy=OptimizationStrategy.BALANCED):
                return chunks, OptimizationMetrics(len(chunks), len(chunks), 100, 100, 0.9, 0.95)
            
            def merge_small_chunks(self, chunks, min_tokens, preserve_boundaries=True):
                # Simulate merging
                if len(chunks) > 1:
                    return chunks[:-1]  # Remove last chunk
                return chunks
            
            def split_large_chunks(self, chunks, max_tokens, split_points=None):
                return chunks
            
            def rebalance_chunks(self, chunks, target_tokens, variance=0.2):
                return chunks
            
            def optimize_for_embedding(self, chunks, model, max_tokens=512):
                return chunks
        
        # Test workflow
        processor = MockIncrementalProcessor()
        cache = MockCache()
        optimizer = MockOptimizer()
        
        # Initial processing
        cache.store("test.py", sample_chunks, "hash1")
        
        # Simulate file change
        new_content = "# Modified content"
        diff = processor.compute_diff(sample_chunks, new_content, "python")
        assert diff.summary["modified"] == 1
        
        # Update chunks
        updated = processor.update_chunks(sample_chunks, diff)
        
        # Optimize updated chunks
        optimized = optimizer.merge_small_chunks(updated, min_tokens=50)
        assert len(optimized) <= len(updated)
    
    def test_smart_context_with_query(self, sample_chunks):
        """Test smart context provider with query system."""
        # Mock implementations
        class MockContextProvider(SmartContextProvider):
            def get_semantic_context(self, chunk, max_tokens=2000):
                return "# Semantic context", ContextMetadata(0.8, "semantic", 1, 50)
            
            def get_dependency_context(self, chunk, chunks):
                deps = []
                # Find dependencies based on function calls
                for other in chunks:
                    if other.chunk_id != chunk.chunk_id:
                        if any(name in chunk.content for name in ["calculate_sum", "calculate_average"]):
                            if name in other.content:
                                deps.append((other, ContextMetadata(0.9, "dependency", 1, 80)))
                return deps
            
            def get_usage_context(self, chunk, chunks):
                return []
            
            def get_structural_context(self, chunk, chunks):
                return []
        
        class MockQueryIndex(QueryIndexAdvanced):
            def __init__(self):
                self.chunks = []
            
            def build_index(self, chunks):
                self.chunks = chunks
            
            def add_chunk(self, chunk):
                self.chunks.append(chunk)
            
            def remove_chunk(self, chunk_id):
                self.chunks = [c for c in self.chunks if c.chunk_id != chunk_id]
            
            def update_chunk(self, chunk):
                for i, c in enumerate(self.chunks):
                    if c.chunk_id == chunk.chunk_id:
                        self.chunks[i] = chunk
            
            def query(self, query, query_type=QueryType.NATURAL_LANGUAGE, limit=10):
                results = []
                for chunk in self.chunks:
                    if query.lower() in chunk.content.lower():
                        results.append(QueryResult(chunk, 0.8, [], {}))
                return results[:limit]
            
            def get_statistics(self):
                return {"indexed_chunks": len(self.chunks)}
        
        # Test integration
        context_provider = MockContextProvider()
        index = MockQueryIndex()
        
        # Build index
        index.build_index(sample_chunks)
        
        # Query for functions
        results = index.query("calculate", limit=5)
        assert len(results) > 0
        
        # Get context for query results
        if results:
            first_result = results[0].chunk
            deps = context_provider.get_dependency_context(first_result, sample_chunks)
            
            # Should find dependencies if it's the average function
            if "calculate_average" in first_result.content:
                assert len(deps) > 0  # Should depend on calculate_sum
    
    def test_all_interfaces_together(self, sample_chunks, tmp_path):
        """Test using all Phase 10 interfaces in a workflow."""
        # This test demonstrates that all interfaces can work together
        # in a realistic workflow, even with mock implementations
        
        # 1. Multi-language detection
        class MockMultiLang(MultiLanguageProcessor):
            def detect_project_languages(self, path):
                return {"python": 1.0}
            def identify_language_regions(self, file_path, content):
                return [LanguageRegion("python", 0, len(content), 1, 50)]
            def process_mixed_file(self, file_path, primary_language, content=None):
                return sample_chunks
            def extract_embedded_code(self, content, host, target):
                return []
            def cross_language_references(self, chunks):
                return []
            def group_by_feature(self, chunks):
                return {"main": chunks}
        
        # 2. Smart context
        class MockContext(SmartContextProvider):
            def get_semantic_context(self, chunk, max_tokens=2000):
                return "# Context", ContextMetadata(0.8, "semantic", 1, 50)
            def get_dependency_context(self, chunk, chunks):
                return []
            def get_usage_context(self, chunk, chunks):
                return []
            def get_structural_context(self, chunk, chunks):
                return []
        
        # 3. Query system
        class MockQuery(ChunkQueryAdvanced):
            def search(self, query, chunks, query_type=QueryType.NATURAL_LANGUAGE, limit=None):
                return [QueryResult(chunks[0], 0.9, [], {})] if chunks else []
            def filter(self, chunks, **kwargs):
                return chunks
            def find_similar(self, chunk, chunks, threshold=0.7, limit=None):
                return []
        
        # 4. Optimization
        class MockOptimizer(ChunkOptimizer):
            def optimize_for_llm(self, chunks, model, max_tokens, strategy=OptimizationStrategy.BALANCED):
                return chunks, OptimizationMetrics(len(chunks), len(chunks), 100, 100, 0.9, 0.95)
            def merge_small_chunks(self, chunks, min_tokens, preserve_boundaries=True):
                return chunks
            def split_large_chunks(self, chunks, max_tokens, split_points=None):
                return chunks
            def rebalance_chunks(self, chunks, target_tokens, variance=0.2):
                return chunks
            def optimize_for_embedding(self, chunks, model, max_tokens=512):
                return chunks
        
        # 5. Incremental processing
        class MockIncremental(IncrementalProcessor):
            def compute_diff(self, old_chunks, new_content, language):
                return ChunkDiff([], [], [], [], old_chunks, {})
            def update_chunks(self, old_chunks, diff):
                return old_chunks
            def detect_moved_chunks(self, old, new):
                return []
            def merge_incremental_results(self, full, inc, regions):
                return full
        
        # Execute workflow
        multi_lang = MockMultiLang()
        context = MockContext()
        query = MockQuery()
        optimizer = MockOptimizer()
        incremental = MockIncremental()
        
        # Detect language
        langs = multi_lang.detect_project_languages(str(tmp_path))
        assert "python" in langs
        
        # Process file
        chunks = multi_lang.process_mixed_file(tmp_path / "test.py", "python")
        
        # Add context
        ctx, metadata = context.get_semantic_context(chunks[0])
        
        # Query
        results = query.search("calculate", chunks)
        assert len(results) > 0
        
        # Optimize
        optimized, metrics = optimizer.optimize_for_llm(chunks, "gpt-4", 4000)
        assert metrics.coherence_score > 0.8
        
        # Check incremental
        diff = incremental.compute_diff(chunks, "new content", "python")
        updated = incremental.update_chunks(chunks, diff)
        
        # All interfaces used successfully in workflow
        assert len(updated) == len(chunks)
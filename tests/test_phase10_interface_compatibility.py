"""Integration tests to verify Phase 10 interfaces work together correctly."""

import pytest

from chunker import chunk_file
from chunker.interfaces.incremental import (
    ChangeType,
    ChunkCache,
    ChunkChange,
    ChunkDiff,
    IncrementalProcessor,
)
from chunker.interfaces.multi_language import (
    CrossLanguageReference,
    LanguageRegion,
    MultiLanguageProcessor,
)
from chunker.interfaces.optimization import (
    ChunkOptimizer,
    OptimizationMetrics,
    OptimizationStrategy,
)
from chunker.interfaces.query_advanced import (
    ChunkQueryAdvanced,
    QueryIndexAdvanced,
    QueryResult,
    QueryType,
)
from chunker.interfaces.smart_context import ContextMetadata, SmartContextProvider
from chunker.types import CodeChunk


class TestPhase10InterfaceCompatibility:
    """Test that Phase 10 interfaces work together correctly."""

    @staticmethod
    @pytest.fixture()
    def sample_chunks(tmp_path) -> list[CodeChunk]:
        """Create sample chunks for testing."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """
def calculate_sum(numbers: List[int]) -> int:
    ""\"Calculate sum of numbers.""\"
    total = 0
    for num in numbers:
        total += num
    return total

def calculate_average(numbers: List[int]) -> float:
    ""\"Calculate average of numbers.""\"
    if not numbers:
        return 0.0
    return calculate_sum(numbers) / len(numbers)

class Statistics:
    ""\"Calculate statistics for number lists.""\"

    def __init__(self):
        self.data = []

    def add_data(self, numbers: List[int]):
        ""\"Add data for analysis.""\"
        self.data.extend(numbers)

    def get_mean(self) -> float:
        ""\"Get mean of all data.""\"
        return calculate_average(self.data)
""",
        )
        chunks = chunk_file(test_file, "python")
        return chunks

    @classmethod
    def test_smart_context_with_optimizer(cls, sample_chunks):
        """Test that smart context works with chunk optimizer."""

        class MockContextProvider(SmartContextProvider):

            @classmethod
            def get_semantic_context(cls, _chunk, _max_tokens=2000):
                return "# Related context", ContextMetadata(0.8, "semantic", 1, 50)

            @classmethod
            def get_dependency_context(cls, _chunk, chunks):
                return [
                    (chunks[0], ContextMetadata(0.9, "dependency", 0, 100)),
                ]

            @staticmethod
            def get_usage_context(_chunk, _chunks):
                return []

            @staticmethod
            def get_structural_context(_chunk, _chunks):
                return []

        class MockOptimizer(ChunkOptimizer):

            @classmethod
            def optimize_for_llm(
                cls,
                chunks,
                _model,
                _max_tokens,
                _strategy=OptimizationStrategy.BALANCED,
            ):
                metrics = OptimizationMetrics(
                    len(chunks),
                    len(chunks),
                    100,
                    120,
                    0.85,
                    0.9,
                )
                return chunks, metrics

            @staticmethod
            def merge_small_chunks(
                chunks,
                _min_tokens,
                _preserve_boundaries=True,
            ):
                return chunks

            @staticmethod
            def split_large_chunks(chunks, _max_tokens, _split_points=None):
                return chunks

            @staticmethod
            def rebalance_chunks(chunks, _target_tokens, _variance=0.2):
                return chunks

            @staticmethod
            def optimize_for_embedding(chunks, _model, _max_tokens=512):
                return chunks

        context_provider = MockContextProvider()
        optimizer = MockOptimizer()
        context_str, metadata = context_provider.get_semantic_context(sample_chunks[0])
        assert context_str == "# Related context"
        assert metadata.relevance_score == 0.8
        optimized, metrics = optimizer.optimize_for_llm(sample_chunks, "gpt-4", 8000)
        assert len(optimized) == len(sample_chunks)
        assert metrics.coherence_score == 0.85

    @classmethod
    def test_query_with_multi_language(cls, tmp_path):
        """Test querying across multiple languages."""
        project_dir = tmp_path / "mixed_project"
        project_dir.mkdir()
        backend_dir = project_dir / "backend"
        backend_dir.mkdir()
        (backend_dir / "api.py").write_text(
            """
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/users')
def get_users():
    ""\"Get all users from database.""\"
    return jsonify({"users": ["alice", "bob"]})
""",
        )
        frontend_dir = project_dir / "frontend"
        frontend_dir.mkdir()
        (frontend_dir / "api.js").write_text(
            """
async function fetchUsers() {
    const response = await fetch('/api/users');
    const data = await response.json();
    return data.users;
}
""",
        )

        class MockMultiLanguageProcessor(MultiLanguageProcessor):

            @staticmethod
            def detect_project_languages(_path):
                return {"python": 0.5, "javascript": 0.5}

            @classmethod
            def identify_language_regions(cls, _file_path, content):
                return [LanguageRegion("python", 0, len(content), 1, 10)]

            @staticmethod
            def process_mixed_file(file_path, primary_language, _content=None):
                return chunk_file(file_path, primary_language)

            @staticmethod
            def extract_embedded_code(_content, _host_lang, _target_lang):
                return []

            @classmethod
            def cross_language_references(cls, chunks):
                refs = []
                for i, chunk in enumerate(chunks):
                    if "/api/users" in chunk.content:
                        for j, other in enumerate(chunks):
                            if i != j and "get_users" in other.content:
                                refs.append(
                                    CrossLanguageReference(
                                        chunk,
                                        other,
                                        "api_call",
                                        0.9,
                                    ),
                                )
                return refs

            @staticmethod
            def group_by_feature(chunks):
                return {"user_api": chunks}

        class MockQuery(ChunkQueryAdvanced):

            @classmethod
            def search(
                cls,
                query,
                chunks,
                _query_type=QueryType.NATURAL_LANGUAGE,
                _limit=None,
            ):
                results = [
                    QueryResult(chunk, 0.9, [], {})
                    for chunk in chunks
                    if query.lower() in chunk.content.lower()
                ]
                return results

            @staticmethod
            def filter(chunks, **_kwargs):
                return chunks

            @staticmethod
            def find_similar(_chunk, _chunks, _threshold=0.7, _limit=None):
                return []

        processor = MockMultiLanguageProcessor()
        query_engine = MockQuery()
        languages = processor.detect_project_languages(str(project_dir))
        assert "python" in languages
        assert "javascript" in languages
        py_chunks = chunk_file(backend_dir / "api.py", "python")
        js_chunks = chunk_file(frontend_dir / "api.js", "javascript")
        all_chunks = py_chunks + js_chunks
        refs = processor.cross_language_references(all_chunks)
        assert len(refs) > 0
        results = query_engine.search("users", all_chunks)
        assert len(results) >= 2

    @staticmethod
    def test_incremental_with_optimization(sample_chunks):
        """Test incremental processing with optimization."""

        class MockIncrementalProcessor(IncrementalProcessor):

            @classmethod
            def compute_diff(cls, old_chunks, _new_content, _language):
                changes = []
                if old_chunks:
                    changes.append(
                        ChunkChange(
                            old_chunks[0].chunk_id,
                            ChangeType.MODIFIED,
                            old_chunks[0],
                            old_chunks[0],
                            [(1, 5)],
                            0.95,
                        ),
                    )
                return ChunkDiff(
                    changes,
                    [],
                    [],
                    [(old_chunks[0], old_chunks[0])],
                    old_chunks[1:],
                    {"modified": 1},
                )

            @staticmethod
            def update_chunks(old_chunks, _diff):
                return old_chunks

            @staticmethod
            def detect_moved_chunks(_old_chunks, _new_chunks):
                return []

            @staticmethod
            def merge_incremental_results(full, _incremental, _regions):
                return full

        class MockCache(ChunkCache):

            def __init__(self):
                self.cache = {}

            def store(self, file_path, chunks, file_hash, _metadata=None):
                self.cache[file_path] = {"chunks": chunks, "hash": file_hash}

            def retrieve(self, file_path, _file_hash=None):
                return self.cache.get(file_path)

            def invalidate(self, file_path=None, _older_than=None):
                if file_path:
                    self.cache.pop(file_path, None)
                    return 1
                count = len(self.cache)
                self.cache.clear()
                return count

            def get_statistics(self):
                return {"entries": len(self.cache)}

            @staticmethod
            def export_cache(_path):
                pass

            @staticmethod
            def import_cache(_path):
                pass

        class MockOptimizer(ChunkOptimizer):

            @classmethod
            def optimize_for_llm(
                cls,
                chunks,
                _model,
                _max_tokens,
                _strategy=OptimizationStrategy.BALANCED,
            ):
                return chunks, OptimizationMetrics(
                    len(chunks),
                    len(chunks),
                    100,
                    100,
                    0.9,
                    0.95,
                )

            @staticmethod
            def merge_small_chunks(
                chunks,
                _min_tokens,
                _preserve_boundaries=True,
            ):
                if len(chunks) > 1:
                    return chunks[:-1]
                return chunks

            @staticmethod
            def split_large_chunks(chunks, _max_tokens, _split_points=None):
                return chunks

            @staticmethod
            def rebalance_chunks(chunks, _target_tokens, _variance=0.2):
                return chunks

            @staticmethod
            def optimize_for_embedding(chunks, _model, _max_tokens=512):
                return chunks

        processor = MockIncrementalProcessor()
        cache = MockCache()
        optimizer = MockOptimizer()
        cache.store("test.py", sample_chunks, "hash1")
        new_content = "# Modified content"
        diff = processor.compute_diff(sample_chunks, new_content, "python")
        assert diff.summary["modified"] == 1
        updated = processor.update_chunks(sample_chunks, diff)
        optimized = optimizer.merge_small_chunks(updated, min_tokens=50)
        assert len(optimized) <= len(updated)

    @staticmethod
    def test_smart_context_with_query(sample_chunks):
        """Test smart context provider with query system."""

        class MockContextProvider(SmartContextProvider):

            @classmethod
            def get_semantic_context(cls, _chunk, _max_tokens=2000):
                return "# Semantic context", ContextMetadata(0.8, "semantic", 1, 50)

            @classmethod
            def get_dependency_context(cls, chunk, chunks):
                deps = []
                for other in chunks:
                    if other.chunk_id != chunk.chunk_id:
                        deps.extend(
                            (other, ContextMetadata(0.9, "dependency", 1, 80))
                            for name in ["calculate_sum", "calculate_average"]
                            if name in chunk.content and name in other.content
                        )
                return deps

            @staticmethod
            def get_usage_context(_chunk, _chunks):
                return []

            @staticmethod
            def get_structural_context(_chunk, _chunks):
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

            def query(self, query, _query_type=QueryType.NATURAL_LANGUAGE, limit=10):
                results = [
                    QueryResult(chunk, 0.8, [], {})
                    for chunk in self.chunks
                    if query.lower() in chunk.content.lower()
                ]
                return results[:limit]

            def get_statistics(self):
                return {"indexed_chunks": len(self.chunks)}

        context_provider = MockContextProvider()
        index = MockQueryIndex()
        index.build_index(sample_chunks)
        results = index.query("calculate", limit=5)
        assert len(results) > 0
        if results:
            first_result = results[0].chunk
            deps = context_provider.get_dependency_context(first_result, sample_chunks)
            if "calculate_average" in first_result.content:
                assert len(deps) > 0

    @classmethod
    def test_all_interfaces_together(cls, sample_chunks, tmp_path):
        """Test using all Phase 10 interfaces in a workflow."""

        class MockMultiLang(MultiLanguageProcessor):

            @staticmethod
            def detect_project_languages(_path):
                return {"python": 1.0}

            @classmethod
            def identify_language_regions(cls, _file_path, content):
                return [LanguageRegion("python", 0, len(content), 1, 50)]

            @staticmethod
            def process_mixed_file(_file_path, _primary_language, _content=None):
                return sample_chunks

            @staticmethod
            def extract_embedded_code(_content, _host, _target):
                return []

            @staticmethod
            def cross_language_references(_chunks):
                return []

            @staticmethod
            def group_by_feature(chunks):
                return {"main": chunks}

        class MockContext(SmartContextProvider):

            @classmethod
            def get_semantic_context(cls, _chunk, _max_tokens=2000):
                return "# Context", ContextMetadata(0.8, "semantic", 1, 50)

            @staticmethod
            def get_dependency_context(_chunk, _chunks):
                return []

            @staticmethod
            def get_usage_context(_chunk, _chunks):
                return []

            @staticmethod
            def get_structural_context(_chunk, _chunks):
                return []

        class MockQuery(ChunkQueryAdvanced):

            @classmethod
            def search(
                cls,
                query,
                chunks,
                _query_type=QueryType.NATURAL_LANGUAGE,
                _limit=None,
            ):
                return [QueryResult(chunks[0], 0.9, [], {})] if chunks else []

            @staticmethod
            def filter(chunks, **_kwargs):
                return chunks

            @staticmethod
            def find_similar(_chunk, _chunks, _threshold=0.7, _limit=None):
                return []

        class MockOptimizer(ChunkOptimizer):

            @classmethod
            def optimize_for_llm(
                cls,
                chunks,
                _model,
                _max_tokens,
                _strategy=OptimizationStrategy.BALANCED,
            ):
                return chunks, OptimizationMetrics(
                    len(chunks),
                    len(chunks),
                    100,
                    100,
                    0.9,
                    0.95,
                )

            @staticmethod
            def merge_small_chunks(
                chunks,
                _min_tokens,
                _preserve_boundaries=True,
            ):
                return chunks

            @staticmethod
            def split_large_chunks(chunks, _max_tokens, _split_points=None):
                return chunks

            @staticmethod
            def rebalance_chunks(chunks, _target_tokens, _variance=0.2):
                return chunks

            @staticmethod
            def optimize_for_embedding(chunks, _model, _max_tokens=512):
                return chunks

        class MockIncremental(IncrementalProcessor):

            @classmethod
            def compute_diff(cls, old_chunks, _new_content, _language):
                return ChunkDiff([], [], [], [], old_chunks, {})

            @staticmethod
            def update_chunks(old_chunks, _diff):
                return old_chunks

            @staticmethod
            def detect_moved_chunks(_old, _new):
                return []

            @staticmethod
            def merge_incremental_results(full, _inc, _regions):
                return full

        multi_lang = MockMultiLang()
        context = MockContext()
        query = MockQuery()
        optimizer = MockOptimizer()
        incremental = MockIncremental()
        langs = multi_lang.detect_project_languages(str(tmp_path))
        assert "python" in langs
        chunks = multi_lang.process_mixed_file(tmp_path / "test.py", "python")
        _ctx, _metadata = context.get_semantic_context(chunks[0])
        results = query.search("calculate", chunks)
        assert len(results) > 0
        _optimized, metrics = optimizer.optimize_for_llm(chunks, "gpt-4", 4000)
        assert metrics.coherence_score > 0.8
        diff = incremental.compute_diff(chunks, "new content", "python")
        updated = incremental.update_chunks(chunks, diff)
        assert len(updated) == len(chunks)

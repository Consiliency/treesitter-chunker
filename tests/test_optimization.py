"""Tests for chunk optimization functionality."""
from unittest.mock import MagicMock, patch

import pytest

from chunker import (
    ChunkBoundaryAnalyzer,
    ChunkOptimizer,
    CodeChunk,
    OptimizationConfig,
    OptimizationMetrics,
    OptimizationStrategy,
)


class TestChunkOptimizer:
    """Test suite for ChunkOptimizer."""

    @classmethod
    @pytest.fixture
    def sample_chunks(cls):
        """Create sample chunks for testing."""
        return [CodeChunk(language="python", file_path="test.py", node_type="function", start_line=1, end_line=5, byte_start=0, byte_end=100, parent_context="module", content="""def hello():
    print('Hello')
    return True
""",
            chunk_id="chunk1"), CodeChunk(language="python", file_path="test.py", node_type="function", start_line=6, end_line=10,
            byte_start=101, byte_end=200, parent_context="module", content="""def world():
    print('World')
    return False
""",
            chunk_id="chunk2"), CodeChunk(language="python", file_path="test.py", node_type="class", start_line=12, end_line=30,
            byte_start=201, byte_end=800, parent_context="module", content="""class LargeClass:
""" + "    " * 50 + "def method1(self):\n" +
            "        " * 100 + "pass\n" * 20, chunk_id="chunk3")]

    @classmethod
    @pytest.fixture
    def optimizer(cls):
        """Create a ChunkOptimizer instance."""
        return ChunkOptimizer()

    @classmethod
    @pytest.fixture
    def mock_token_counter(cls):
        """Mock the token counter."""
        with patch("chunker.optimization.TiktokenCounter") as mock:
            counter = MagicMock()

            def count_tokens_side_effect(text, model="gpt-4"):
                return len(text) // 4
            counter.count_tokens.side_effect = count_tokens_side_effect
            counter.split_text_by_tokens.return_value = ["chunk1", "chunk2"]
            mock.return_value = counter
            yield counter

    @staticmethod
    def test_optimize_for_llm_balanced(optimizer, sample_chunks,
        mock_token_counter):
        """Test balanced optimization strategy."""
        mock_token_counter.count_tokens.side_effect = (lambda text, model="gpt-4": len(text) // 4)
        _result_chunks, metrics = optimizer.optimize_for_llm(sample_chunks,
            model="gpt-4", max_tokens=100, strategy=OptimizationStrategy.
            BALANCED)
        assert isinstance(metrics, OptimizationMetrics)
        assert metrics.original_count == 3
        assert metrics.optimized_count >= 2
        assert 0 <= metrics.coherence_score <= 1
        assert 0 <= metrics.token_efficiency <= 1

    @staticmethod
    def test_optimize_for_llm_aggressive(optimizer, sample_chunks,
        mock_token_counter):
        """Test aggressive optimization strategy."""
        mock_token_counter.count_tokens.side_effect = (lambda text, model="gpt-4": len(text) // 4)
        _result_chunks, metrics = optimizer.optimize_for_llm(sample_chunks,
            model="gpt-4", max_tokens=200, strategy=OptimizationStrategy.
            AGGRESSIVE)
        assert isinstance(metrics, OptimizationMetrics)
        assert metrics.optimized_count <= metrics.original_count

    @staticmethod
    def test_optimize_for_llm_conservative(optimizer, sample_chunks,
        mock_token_counter):
        """Test conservative optimization strategy."""
        mock_token_counter.count_tokens.side_effect = (lambda text, model="gpt-4": len(text) // 4)
        _result_chunks, metrics = optimizer.optimize_for_llm(sample_chunks,
            model="gpt-4", max_tokens=50, strategy=OptimizationStrategy.
            CONSERVATIVE)
        assert isinstance(metrics, OptimizationMetrics)
        assert metrics.optimized_count >= metrics.original_count

    @staticmethod
    def test_optimize_for_llm_preserve_structure(optimizer, sample_chunks,
        mock_token_counter):
        """Test preserve structure optimization strategy."""
        mock_token_counter.count_tokens.side_effect = (lambda text, model="gpt-4": len(text) // 4)
        _result_chunks, metrics = optimizer.optimize_for_llm(sample_chunks,
            model="gpt-4", max_tokens=50, strategy=OptimizationStrategy.
            BALANCED)
        assert isinstance(metrics, OptimizationMetrics)
        assert metrics.optimized_count >= metrics.original_count

    @classmethod
    def test_merge_small_chunks(cls, optimizer, mock_token_counter):
        """Test merging of small chunks."""
        small_chunks = [CodeChunk(language="python", file_path="test.py",
            node_type="function", start_line=1, end_line=2, byte_start=0,
            byte_end=20, parent_context="module", content="""def a():
    pass""", chunk_id="small1"), CodeChunk(language="python", file_path="test.py", node_type="function",
            start_line=3, end_line=4, byte_start=21, byte_end=40,
            parent_context="module", content="""def b():
    pass""",
            chunk_id="small2")]
        mock_token_counter.count_tokens.side_effect = (lambda text, model="gpt-4": 5)
        merged = optimizer.merge_small_chunks(small_chunks, min_tokens=20)
        assert len(merged) == 1
        assert "def a():" in merged[0].content
        assert "def b():" in merged[0].content

    @classmethod
    def test_merge_small_chunks_preserve_boundaries(cls, optimizer,
        mock_token_counter):
        """Test merging with boundary preservation."""
        chunks = [CodeChunk(language="python", file_path="test1.py",
            node_type="function", start_line=1, end_line=2, byte_start=0,
            byte_end=20, parent_context="module", content="""def a():
    pass""", chunk_id="file1"), CodeChunk(language="python", file_path="test2.py", node_type="function",
            start_line=1, end_line=2, byte_start=0, byte_end=20,
            parent_context="module", content="""def b():
    pass""",
            chunk_id="file2")]
        mock_token_counter.count_tokens.side_effect = (lambda text, model="gpt-4": 5)
        merged = optimizer.merge_small_chunks(chunks, min_tokens=20,
            preserve_boundaries=True)
        assert len(merged) == 2

    @classmethod
    def test_split_large_chunks(cls, optimizer, mock_token_counter):
        """Test splitting of large chunks."""
        large_chunk = CodeChunk(language="python", file_path="test.py",
            node_type="class", start_line=1, end_line=100, byte_start=0,
            byte_end=2000, parent_context="module", content="class Large:\n" + """    def method1(self):
        pass
""" *
            30, chunk_id="large")

        def mock_count_tokens(text, model="gpt-4"):
            return len(text) // 4
        mock_token_counter.count_tokens.side_effect = mock_count_tokens
        with patch.object(optimizer.boundary_analyzer,
            "find_natural_boundaries") as mock_boundaries:
            mock_boundaries.return_value = [50, 100, 150]
            split = optimizer.split_large_chunks([large_chunk], max_tokens=100)
            assert len(split) > 1
            for chunk in split:
                if chunk.chunk_id != "large":
                    assert chunk.parent_chunk_id == "large" or chunk.parent_chunk_id is not None

    @staticmethod
    def test_rebalance_chunks(optimizer, sample_chunks, mock_token_counter):
        """Test chunk rebalancing."""
        token_counts = [20, 30, 200]
        count_call = 0

        def count_tokens_mock(text, model="gpt-4"):
            nonlocal count_call
            if count_call < len(token_counts):
                result = token_counts[count_call]
                count_call += 1
                return result
            return 50
        mock_token_counter.count_tokens.side_effect = count_tokens_mock
        rebalanced = optimizer.rebalance_chunks(sample_chunks,
            target_tokens=50, variance=0.2)
        assert len(rebalanced) >= 2

    @staticmethod
    def test_optimize_for_embedding(optimizer, sample_chunks,
        mock_token_counter):
        """Test optimization for embeddings."""
        mock_token_counter.count_tokens.side_effect = (lambda text, model="gpt-4": len(text) // 4)
        embedded = optimizer.optimize_for_embedding(sample_chunks,
            embedding_model="text-embedding-ada-002", max_tokens=50)
        assert len(embedded) >= len(sample_chunks)
        for chunk in embedded:
            if "embedding_optimized" in chunk.metadata:
                assert chunk.metadata["embedding_optimized"] is True

    @staticmethod
    def test_empty_chunks(optimizer):
        """Test handling of empty chunk lists."""
        result, metrics = optimizer.optimize_for_llm([], "gpt-4", 100)
        assert result == []
        assert metrics.original_count == 0
        assert metrics.optimized_count == 0

    @classmethod
    def test_coherence_score_calculation(cls, optimizer, mock_token_counter):
        """Test coherence score calculation."""
        chunks = [CodeChunk(language="python", file_path="test.py",
            node_type="function", start_line=1, end_line=5, byte_start=0,
            byte_end=100, parent_context="module", content="""def complete_function():
    x = 1
    return x
""",
            chunk_id="complete"), CodeChunk(language="python", file_path="test.py", node_type="function", start_line=6, end_line=8,
            byte_start=101, byte_end=150, parent_context="module", content="""def incomplete():
    x = 1
    if True:""", chunk_id="incomplete")]
        mock_token_counter.count_tokens.return_value = 50
        _, metrics = optimizer.optimize_for_llm(chunks, "gpt-4", 100,
            OptimizationStrategy.CONSERVATIVE)
        assert 0 < metrics.coherence_score < 1

    @classmethod
    def test_custom_config(cls):
        """Test optimizer with custom configuration."""
        config = OptimizationConfig()
        config.min_chunk_tokens = 100
        config.max_chunk_tokens = 1000
        config.merge_threshold = 0.8
        optimizer = ChunkOptimizer(config)
        assert optimizer.config.min_chunk_tokens == 100
        assert optimizer.config.max_chunk_tokens == 1000
        assert optimizer.config.merge_threshold == 0.8


class TestChunkBoundaryAnalyzer:
    """Test suite for ChunkBoundaryAnalyzer."""

    @classmethod
    @pytest.fixture
    def analyzer(cls):
        """Create a ChunkBoundaryAnalyzer instance."""
        return ChunkBoundaryAnalyzer()

    @staticmethod
    def test_find_natural_boundaries_python(analyzer):
        """Test finding natural boundaries in Python code."""
        python_code = """
def function1():
    pass

def function2():
    pass

class MyClass:
    def method(self):
        pass
"""
        boundaries = analyzer.find_natural_boundaries(python_code, "python")
        assert len(boundaries) > 0
        assert any(python_code[b:b + 4] == "\ndef" for b in boundaries)
        assert any(python_code[b:b + 6] == "\nclass" for b in boundaries)

    @staticmethod
    def test_find_natural_boundaries_javascript(analyzer):
        """Test finding natural boundaries in JavaScript code."""
        js_code = """
function func1() {
    return 1;
}

const func2 = () => {
    return 2;
};

class MyClass {
    method() {
        return 3;
    }
}
"""
        boundaries = analyzer.find_natural_boundaries(js_code, "javascript")
        assert len(boundaries) > 0
        assert any(js_code[b:b + 9] == "\nfunction" for b in boundaries)
        assert any(js_code[b:b + 6] == "\nconst" for b in boundaries)

    @staticmethod
    def test_score_boundary(analyzer):
        """Test boundary scoring."""
        code = "def func1():\n    return 1\n\ndef func2():\n    return 2"
        good_boundary = code.find("\ndef func2")
        good_score = analyzer.score_boundary(code, good_boundary, "python")
        bad_boundary = code.find("return 1") - 2
        bad_score = analyzer.score_boundary(code, bad_boundary, "python")
        assert good_score > bad_score
        assert 0 <= good_score <= 1
        assert 0 <= bad_score <= 1

    @classmethod
    def test_suggest_merge_points(cls, analyzer):
        """Test merge point suggestions."""
        chunks = [CodeChunk(language="python", file_path="test.py",
            node_type="function", start_line=1, end_line=3, byte_start=0,
            byte_end=50, parent_context="module", content="""def a():
    pass""", chunk_id="chunk1"), CodeChunk(language="python", file_path="test.py", node_type="function",
            start_line=4, end_line=6, byte_start=51, byte_end=100,
            parent_context="module", content="""def b():
    pass""",
            chunk_id="chunk2"), CodeChunk(language="python", file_path="other.py", node_type="function", start_line=1, end_line=3,
            byte_start=0, byte_end=50, parent_context="module", content="""def c():
    pass""", chunk_id="chunk3")]
        suggestions = analyzer.suggest_merge_points(chunks)
        assert len(suggestions) > 0
        assert any(s[0] == 0 and s[1] == 1 for s in suggestions)
        assert not any(s[1] == 2 for s in suggestions)

    @staticmethod
    def test_boundary_with_strings(analyzer):
        """Test boundary detection doesn't break strings."""
        code = """def func():
    text = "This is a
    multiline string"
    return text

def func2():
    pass"""
        boundaries = analyzer.find_natural_boundaries(code, "python")
        func2_boundary = code.find("\ndef func2")
        assert func2_boundary in boundaries
        string_middle = code.find("multiline")
        score = analyzer.score_boundary(code, string_middle, "python")
        assert score < 0.6

    @staticmethod
    def test_language_specific_patterns(analyzer):
        """Test language-specific pattern recognition."""
        java_code = """
public class MyClass {
    private void method1() {
        return;
    }

    public void method2() {
        return;
    }
}
"""
        boundaries = analyzer.find_natural_boundaries(java_code, "java")
        assert len(boundaries) > 0
        unknown_boundaries = analyzer.find_natural_boundaries(java_code,
            "unknown")
        assert len(unknown_boundaries) > 0


class TestOptimizationIntegration:
    """Integration tests for optimization features."""

    @classmethod
    @pytest.fixture
    def real_optimizer(cls):
        """Create optimizer with real token counter."""
        return ChunkOptimizer()

    @classmethod
    def test_real_token_counting(cls, real_optimizer):
        """Test with real token counting if tiktoken is available."""
        try:
            chunk = CodeChunk(language="python", file_path="test.py",
                node_type="function", start_line=1, end_line=10, byte_start=0, byte_end=200, parent_context="module", content="""def example_function(param1, param2):
    '''A docstring'''
    result = param1 + param2
    return result
"""
                , chunk_id="test")
            optimized, metrics = real_optimizer.optimize_for_llm([chunk],
                "gpt-4", 100)
            assert len(optimized) >= 1
            assert metrics.avg_tokens_after > 0
        except ImportError:
            pytest.skip("tiktoken not available")

    @classmethod
    def test_optimization_preserves_chunk_integrity(cls, real_optimizer):
        """Test that optimization preserves important chunk properties."""
        chunks = [CodeChunk(language="python", file_path="module.py",
            node_type="class", start_line=1, end_line=20, byte_start=0,
            byte_end=400, parent_context="module", content="""class ImportantClass:
    def __init__(self):
        self.value = 0
"""
            , chunk_id="class1", references=["ref1", "ref2"], dependencies=["dep1"], metadata={"important": True})]
        optimized, _ = real_optimizer.optimize_for_llm(chunks, "gpt-4",
            1000, OptimizationStrategy.CONSERVATIVE)
        assert len(optimized) >= 1
        assert optimized[0].language == "python"
        assert optimized[0].file_path == "module.py"
        assert "ImportantClass" in optimized[0].content
        if len(optimized) == 1:
            assert "ref1" in optimized[0].references
            assert "dep1" in optimized[0].dependencies

    @classmethod
    def test_cross_file_optimization(cls, real_optimizer):
        """Test optimization across multiple files."""
        chunks = [CodeChunk(language="python", file_path="module1.py",
            node_type="function", start_line=1, end_line=5, byte_start=0,
            byte_end=100, parent_context="module", content="""def func1():
    pass""", chunk_id="m1f1"), CodeChunk(
            language="python", file_path="module2.py", node_type="function",
            start_line=1, end_line=5, byte_start=0, byte_end=100,
            parent_context="module", content="""def func2():
    pass""",
            chunk_id="m2f1"), CodeChunk(language="python", file_path="module1.py", node_type="function", start_line=6, end_line=10,
            byte_start=101, byte_end=200, parent_context="module", content="""def func3():
    pass""", chunk_id="m1f2")]
        optimized, _metrics = real_optimizer.optimize_for_llm(chunks,
            "gpt-4", 200, OptimizationStrategy.BALANCED)
        for chunk in optimized:
            assert chunk.file_path in {"module1.py", "module2.py"}

    @classmethod
    def test_extreme_token_limits(cls, real_optimizer):
        """Test optimization with extreme token limits."""
        chunk = CodeChunk(language="python", file_path="test.py", node_type="function", start_line=1, end_line=50, byte_start=0, byte_end=1000, parent_context="module", content="""def large_function():
""" + "    x = 1\n" * 100, chunk_id="large")
        optimized_small, _ = real_optimizer.optimize_for_llm([chunk],
            "gpt-4", 10, OptimizationStrategy.AGGRESSIVE)
        assert len(optimized_small) > 1
        optimized_large, _ = real_optimizer.optimize_for_llm([chunk],
            "gpt-4", 10000, OptimizationStrategy.AGGRESSIVE)
        assert len(optimized_large) == 1

    @classmethod
    def test_mixed_language_chunks(cls, real_optimizer):
        """Test optimization with chunks from different languages."""
        chunks = [CodeChunk(language="python", file_path="script.py",
            node_type="function", start_line=1, end_line=5, byte_start=0,
            byte_end=100, parent_context="module", content="""def python_func():
    return True""", chunk_id="py1"),
            CodeChunk(language="javascript", file_path="script.js",
            node_type="function", start_line=1, end_line=5, byte_start=0,
            byte_end=100, parent_context="module", content="""function jsFunc() {
    return true;
}""", chunk_id="js1")]
        optimized, _ = real_optimizer.optimize_for_llm(chunks, "gpt-4", 200,
            OptimizationStrategy.BALANCED)
        for chunk in optimized:
            assert chunk.language in {"python", "javascript"}


class TestOptimizationEdgeCases:
    """Test edge cases and error handling."""

    @classmethod
    @pytest.fixture
    def optimizer(cls):
        return ChunkOptimizer()

    @classmethod
    def test_single_character_chunk(cls, optimizer):
        """Test optimization of very small chunks."""
        chunk = CodeChunk(language="python", file_path="test.py", node_type="text", start_line=1, end_line=1, byte_start=0, byte_end=1,
            parent_context="module", content="x", chunk_id="tiny")
        optimized, _metrics = optimizer.optimize_for_llm([chunk], "gpt-4", 100)
        assert len(optimized) == 1
        assert optimized[0].content == "x"

    @classmethod
    def test_unicode_content(cls, optimizer):
        """Test optimization with unicode content."""
        chunk = CodeChunk(language="python", file_path="test.py", node_type="comment", start_line=1, end_line=3, byte_start=0, byte_end=100, parent_context="module", content="""# 你好世界
# こんにちは
# مرحبا بالعالم""", chunk_id="unicode")
        optimized, _metrics = optimizer.optimize_for_llm([chunk], "gpt-4", 50)
        assert len(optimized) >= 1
        assert "你好世界" in optimized[0].content

    @classmethod
    def test_malformed_chunk_data(cls, optimizer):
        """Test handling of malformed chunk data."""
        chunk = CodeChunk(language="python", file_path="test.py", node_type="function", start_line=10, end_line=5, byte_start=100,
            byte_end=50, parent_context="module", content="""def invalid():
    pass""", chunk_id="invalid")
        optimized, _metrics = optimizer.optimize_for_llm([chunk], "gpt-4", 100)
        assert len(optimized) >= 1

    @classmethod
    def test_circular_references(cls, optimizer):
        """Test handling of chunks with circular references."""
        chunk1 = CodeChunk(language="python", file_path="test.py",
            node_type="function", start_line=1, end_line=5, byte_start=0,
            byte_end=100, parent_context="module", content="""def func1():
    func2()""", chunk_id="chunk1", references=[
            "chunk2"])
        chunk2 = CodeChunk(language="python", file_path="test.py",
            node_type="function", start_line=6, end_line=10, byte_start=101,
            byte_end=200, parent_context="module", content="""def func2():
    func1()""", chunk_id="chunk2", references=[
            "chunk1"])
        optimized, metrics = optimizer.optimize_for_llm([chunk1, chunk2],
            "gpt-4", 150, OptimizationStrategy.BALANCED)
        assert len(optimized) >= 1
        assert metrics.coherence_score > 0

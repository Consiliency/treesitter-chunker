"""Tests for advanced query functionality."""

import numpy as np
import pytest

from chunker.interfaces.query_advanced import QueryType
from chunker.query_advanced import (
    AdvancedQueryIndex,
    NaturalLanguageQueryEngine,
    SmartQueryOptimizer,
)
from chunker.types import CodeChunk


class TestNaturalLanguageQueryEngine:
    """Test natural language query engine."""

    @pytest.fixture
    def query_engine(self):
        """Create query engine instance."""
        return NaturalLanguageQueryEngine()

    @pytest.fixture
    def sample_chunks(self):
        """Create sample code chunks for testing."""
        return [
            CodeChunk(
                language="python",
                file_path="/src/auth.py",
                node_type="function_definition",
                start_line=10,
                end_line=20,
                byte_start=100,
                byte_end=300,
                parent_context="class:AuthManager",
                content="""def authenticate_user(username, password):
    try:
        user = User.objects.get(username=username)
        if user.check_password(password):
            return create_token(user)
    except User.DoesNotExist:
        raise AuthenticationError("Invalid credentials")""",
                chunk_id="auth_1",
            ),
            CodeChunk(
                language="python",
                file_path="/src/auth.py",
                node_type="function_definition",
                start_line=25,
                end_line=30,
                byte_start=350,
                byte_end=450,
                parent_context="class:AuthManager",
                content="""def logout_user(token):
    session = Session.objects.get(token=token)
    session.delete()
    return {"status": "logged out"}""",
                chunk_id="auth_2",
            ),
            CodeChunk(
                language="python",
                file_path="/src/errors.py",
                node_type="class_definition",
                start_line=5,
                end_line=15,
                byte_start=50,
                byte_end=250,
                parent_context="",
                content="""class ErrorHandler:
    def handle_exception(self, e):
        logger.error(f"Exception occurred: {e}")
        if isinstance(e, ValidationError):
            return {"error": "Invalid input", "details": str(e)}
        return {"error": "Internal server error"}""",
                chunk_id="error_1",
            ),
            CodeChunk(
                language="javascript",
                file_path="/src/api.js",
                node_type="function_definition",
                start_line=20,
                end_line=35,
                byte_start=400,
                byte_end=700,
                parent_context="",
                content="""async function fetchUserData(userId) {
    try {
        const response = await fetch(`/api/users/${userId}`);
        if (!response.ok) {
            throw new Error('Failed to fetch user');
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching user:', error);
        throw error;
    }
}""",
                chunk_id="api_1",
            ),
            CodeChunk(
                language="python",
                file_path="/tests/test_auth.py",
                node_type="function_definition",
                start_line=10,
                end_line=20,
                byte_start=200,
                byte_end=400,
                parent_context="class:TestAuthentication",
                content="""def test_login_success(self):
    user = User.objects.create_user('testuser', 'password')
    response = self.client.post('/login', {
        'username': 'testuser',
        'password': 'password'
    })
    assert response.status_code == 200
    assert 'token' in response.json()""",
                chunk_id="test_1",
            ),
        ]

    def test_natural_language_search(self, query_engine, sample_chunks):
        """Test natural language search functionality."""
        # Search for authentication code
        results = query_engine.search(
            "find authentication functions",
            sample_chunks,
            QueryType.NATURAL_LANGUAGE,
        )

        assert len(results) >= 2
        assert results[0].chunk.chunk_id in ["auth_1", "auth_2"]
        assert results[0].score > 0.3  # More reasonable threshold
        # Check that at least one of the results has authentication intent
        auth_intents_found = any(
            "authentication" in r.metadata.get("matched_intents", [])
            for r in results[:2]
        )
        assert auth_intents_found or any(
            "auth" in r.chunk.content.lower() for r in results[:2]
        )

    def test_error_handling_search(self, query_engine, sample_chunks):
        """Test searching for error handling code."""
        results = query_engine.search(
            "show me error handling code",
            sample_chunks,
            QueryType.NATURAL_LANGUAGE,
        )

        assert len(results) >= 2
        # Should find both error handler class and try-catch blocks
        chunk_ids = [r.chunk.chunk_id for r in results]
        assert "error_1" in chunk_ids
        assert "api_1" in chunk_ids or "auth_1" in chunk_ids

    def test_structured_search(self, query_engine, sample_chunks):
        """Test structured query search."""
        # Search for Python functions
        results = query_engine.search(
            "type:function_definition language:python",
            sample_chunks,
            QueryType.STRUCTURED,
        )

        assert len(results) == 3  # auth_1, auth_2, test_1
        for result in results:
            assert result.chunk.language == "python"
            assert result.chunk.node_type == "function_definition"

    def test_regex_search(self, query_engine, sample_chunks):
        """Test regex pattern search."""
        # Search for async functions
        results = query_engine.search(
            r"async\s+function",
            sample_chunks,
            QueryType.REGEX,
        )

        assert len(results) == 1
        assert results[0].chunk.chunk_id == "api_1"
        assert len(results[0].highlights) > 0

    def test_ast_pattern_search(self, query_engine, sample_chunks):
        """Test AST pattern matching."""
        results = query_engine.search(
            "function_definition parent=class:AuthManager",
            sample_chunks,
            QueryType.AST_PATTERN,
        )

        assert len(results) == 2
        assert all(r.chunk.parent_context == "class:AuthManager" for r in results)

    def test_filter_functionality(self, query_engine, sample_chunks):
        """Test chunk filtering."""
        # Filter by language
        filtered = query_engine.filter(
            sample_chunks,
            languages=["python"],
        )
        assert len(filtered) == 4

        # Filter by node type
        filtered = query_engine.filter(
            sample_chunks,
            node_types=["class_definition"],
        )
        assert len(filtered) == 1
        assert filtered[0].chunk_id == "error_1"

        # Filter by line count
        filtered = query_engine.filter(
            sample_chunks,
            min_lines=10,
            max_lines=15,
        )
        assert all(10 <= (c.end_line - c.start_line + 1) <= 15 for c in filtered)

    def test_find_similar_chunks(self, query_engine, sample_chunks):
        """Test finding similar chunks."""
        # Find chunks similar to auth_1
        auth_chunk = sample_chunks[0]
        results = query_engine.find_similar(
            auth_chunk,
            sample_chunks,
            threshold=0.3,
        )

        assert len(results) >= 1
        # Should find auth_2 as most similar (same file, same parent)
        assert results[0].chunk.chunk_id == "auth_2"
        assert results[0].score > 0.5

    def test_empty_query(self, query_engine, sample_chunks):
        """Test handling of empty queries."""
        results = query_engine.search("", sample_chunks)
        assert len(results) == 0

    def test_no_matches(self, query_engine, sample_chunks):
        """Test query with no matches."""
        results = query_engine.search(
            "find quantum computing algorithms",
            sample_chunks,
        )
        # All results should have very low scores
        assert all(r.score < 0.1 for r in results)

    def test_case_insensitive_search(self, query_engine, sample_chunks):
        """Test case insensitive searching."""
        results1 = query_engine.search("ERROR handling", sample_chunks)
        results2 = query_engine.search("error HANDLING", sample_chunks)

        assert len(results1) == len(results2)
        assert [r.chunk.chunk_id for r in results1] == [
            r.chunk.chunk_id for r in results2
        ]

    def test_highlight_generation(self, query_engine, sample_chunks):
        """Test highlight position generation."""
        results = query_engine.search(
            "user password",
            sample_chunks,
            QueryType.NATURAL_LANGUAGE,
        )

        assert len(results) > 0
        # Check highlights are valid positions
        for result in results:
            content = result.chunk.content
            for start, end in result.highlights:
                assert 0 <= start < len(content)
                assert start < end <= len(content)


class TestAdvancedQueryIndex:
    """Test advanced query index functionality."""

    @pytest.fixture
    def index(self):
        """Create index instance."""
        return AdvancedQueryIndex()

    @pytest.fixture
    def sample_chunks(self):
        """Create sample chunks."""
        return [
            CodeChunk(
                language="python",
                file_path="/src/utils.py",
                node_type="function_definition",
                start_line=1,
                end_line=5,
                byte_start=0,
                byte_end=100,
                parent_context="",
                content="def calculate_sum(a, b):\n    return a + b",
                chunk_id="chunk_1",
            ),
            CodeChunk(
                language="python",
                file_path="/src/utils.py",
                node_type="function_definition",
                start_line=7,
                end_line=12,
                byte_start=120,
                byte_end=250,
                parent_context="",
                content="def calculate_product(a, b):\n    return a * b",
                chunk_id="chunk_2",
            ),
            CodeChunk(
                language="javascript",
                file_path="/src/math.js",
                node_type="function_definition",
                start_line=1,
                end_line=3,
                byte_start=0,
                byte_end=50,
                parent_context="",
                content="function add(x, y) { return x + y; }",
                chunk_id="chunk_3",
            ),
        ]

    def test_index_building(self, index, sample_chunks):
        """Test building index from chunks."""
        index.build_index(sample_chunks)

        stats = index.get_statistics()
        assert stats["total_chunks"] == 3
        assert stats["unique_languages"] == 2
        assert stats["unique_files"] == 2

    def test_add_remove_chunk(self, index, sample_chunks):
        """Test adding and removing individual chunks."""
        # Add chunks
        for chunk in sample_chunks:
            index.add_chunk(chunk)

        assert len(index.chunks) == 3

        # Remove a chunk
        index.remove_chunk("chunk_1")
        assert len(index.chunks) == 2
        assert "chunk_1" not in index.chunks

    def test_update_chunk(self, index, sample_chunks):
        """Test updating a chunk."""
        index.build_index(sample_chunks)

        # Update chunk content
        updated_chunk = CodeChunk(
            language="python",
            file_path="/src/utils.py",
            node_type="function_definition",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="",
            content="def calculate_sum(a, b):\n    # Add two numbers\n    return a + b",
            chunk_id="chunk_1",
        )

        index.update_chunk(updated_chunk)

        # Verify update
        assert index.chunks["chunk_1"].content == updated_chunk.content

    def test_index_query(self, index, sample_chunks):
        """Test querying the index."""
        index.build_index(sample_chunks)

        # Query for "calculate"
        results = index.query("calculate", limit=5)

        assert len(results) >= 2
        chunk_ids = [r.chunk.chunk_id for r in results]
        assert "chunk_1" in chunk_ids
        assert "chunk_2" in chunk_ids

    def test_tokenization(self, index):
        """Test text tokenization."""
        text = "calculateSum getUserName test_function"
        tokens = index._tokenize(text)

        assert "calculatesum" in tokens
        assert "sum" in tokens  # Extracted from camelCase
        assert "calculate" in tokens  # Extracted from camelCase
        assert "getusername" in tokens
        assert "get" in tokens  # Extracted from camelCase
        assert "user" in tokens  # Extracted from camelCase
        assert "name" in tokens  # Extracted from camelCase
        assert "test_function" in tokens
        assert "test" in tokens
        assert "function" in tokens

    def test_embedding_generation(self, index, sample_chunks):
        """Test embedding generation."""
        chunk = sample_chunks[0]
        embedding = index._generate_embedding(chunk)

        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (128,)
        assert np.isclose(np.linalg.norm(embedding), 1.0)  # Normalized

    def test_statistics(self, index, sample_chunks):
        """Test index statistics."""
        index.build_index(sample_chunks)
        stats = index.get_statistics()

        assert "total_chunks" in stats
        assert "unique_terms" in stats
        assert "avg_terms_per_chunk" in stats
        assert "index_memory_bytes" in stats

        assert stats["total_chunks"] == 3
        assert stats["unique_terms"] > 0
        assert stats["avg_terms_per_chunk"] > 0

    def test_empty_index(self, index):
        """Test operations on empty index."""
        stats = index.get_statistics()
        assert stats["total_chunks"] == 0

        results = index.query("test")
        assert len(results) == 0

        # Remove non-existent chunk
        index.remove_chunk("nonexistent")  # Should not raise

    def test_candidate_selection(self, index, sample_chunks):
        """Test candidate chunk selection."""
        index.build_index(sample_chunks)

        # Should find chunks with "calculate"
        candidates = index._get_candidate_chunks("calculate")
        assert len(candidates) >= 2

        # Should expand search for partial matches
        candidates = index._get_candidate_chunks("calc")
        assert len(candidates) >= 2


class TestSmartQueryOptimizer:
    """Test query optimization functionality."""

    @pytest.fixture
    def optimizer(self):
        """Create optimizer instance."""
        return SmartQueryOptimizer()

    def test_typo_correction(self, optimizer):
        """Test typo correction in queries."""
        # Natural language
        optimized = optimizer.optimize_query(
            "find fucntion with retrun statement",
            QueryType.NATURAL_LANGUAGE,
        )
        assert "function" in optimized
        assert "return" in optimized
        assert "fucntion" not in optimized

        # Structured
        optimized = optimizer.optimize_query(
            "typ:calss",
            QueryType.STRUCTURED,
        )
        assert optimized == "type:class"

    def test_synonym_expansion(self, optimizer):
        """Test synonym expansion."""
        optimized = optimizer.optimize_query(
            "find authentication methods",
            QueryType.NATURAL_LANGUAGE,
        )

        # Should expand authentication
        assert "auth" in optimized or "login" in optimized

    def test_stop_word_removal(self, optimizer):
        """Test removal of stop words."""
        optimized = optimizer.optimize_query(
            "find the function with a return statement",
            QueryType.NATURAL_LANGUAGE,
        )

        assert "the" not in optimized.split()
        assert "a" not in optimized.split()
        assert "with" not in optimized.split()
        assert "function" in optimized
        assert "return" in optimized

    def test_regex_optimization(self, optimizer):
        """Test regex pattern optimization."""
        # Add word boundaries for simple words
        optimized = optimizer.optimize_query("test", QueryType.REGEX)
        assert optimized == r"\btest\b"

        # Should not modify patterns with dots (common in filenames)
        optimized = optimizer.optimize_query("test.py", QueryType.REGEX)
        assert optimized == "test.py"  # Dots in filenames are usually literal

        # Leave complex patterns alone
        complex_pattern = r"test\d+\.py"
        optimized = optimizer.optimize_query(complex_pattern, QueryType.REGEX)
        assert optimized == complex_pattern

    def test_query_suggestions(self, optimizer):
        """Test query suggestions."""
        chunks = [
            CodeChunk(
                language="python",
                file_path="/test.py",
                node_type="function_definition",
                start_line=1,
                end_line=5,
                byte_start=0,
                byte_end=100,
                parent_context="",
                content="def test_authentication():\n    pass",
                chunk_id="1",
            ),
            CodeChunk(
                language="python",
                file_path="/test.py",
                node_type="class_definition",
                start_line=10,
                end_line=20,
                byte_start=200,
                byte_end=400,
                parent_context="",
                content="class TestUser:\n    pass",
                chunk_id="2",
            ),
        ]

        # Test natural language suggestions
        suggestions = optimizer.suggest_queries("test", chunks)
        assert len(suggestions) > 0
        assert any("test" in s for s in suggestions)

        # Test structured query suggestions
        suggestions = optimizer.suggest_queries("type:func", chunks)
        assert any("function_definition" in s for s in suggestions)

    def test_empty_query_optimization(self, optimizer):
        """Test optimization of empty queries."""
        optimized = optimizer.optimize_query("", QueryType.NATURAL_LANGUAGE)
        assert optimized == ""

    def test_preserve_query_structure(self, optimizer):
        """Test that optimization preserves important structure."""
        # Should not remove important keywords
        query = "class ErrorHandler"
        optimized = optimizer.optimize_query(query, QueryType.NATURAL_LANGUAGE)
        assert "class" in optimized
        assert "errorhandler" in optimized.lower()

    def test_structured_key_normalization(self, optimizer):
        """Test normalization of structured query keys."""
        optimized = optimizer.optimize_query(
            "lang:python typ:function",
            QueryType.STRUCTURED,
        )
        assert "language:python" in optimized
        assert "type:function" in optimized


class TestIntegration:
    """Integration tests for the complete query system."""

    @pytest.fixture
    def query_system(self):
        """Create complete query system."""
        engine = NaturalLanguageQueryEngine()
        index = AdvancedQueryIndex()
        optimizer = SmartQueryOptimizer()
        return engine, index, optimizer

    def test_end_to_end_query(self, query_system):
        """Test complete query workflow."""
        engine, index, optimizer = query_system

        # Create test chunks
        chunks = [
            CodeChunk(
                language="python",
                file_path="/src/auth.py",
                node_type="function_definition",
                start_line=1,
                end_line=10,
                byte_start=0,
                byte_end=200,
                parent_context="",
                content="""def login_user(username, password):
    if not username or not password:
        raise ValueError("Missing credentials")
    user = authenticate(username, password)
    return create_session(user)""",
                chunk_id="auth_func",
            ),
            CodeChunk(
                language="python",
                file_path="/tests/test_auth.py",
                node_type="function_definition",
                start_line=1,
                end_line=8,
                byte_start=0,
                byte_end=150,
                parent_context="",
                content="""def test_login():
    result = login_user("test", "pass")
    assert result is not None""",
                chunk_id="test_func",
            ),
        ]

        # Build index
        index.build_index(chunks)

        # Optimize query
        query = "find fucntion for user authentication"
        optimized = optimizer.optimize_query(query, QueryType.NATURAL_LANGUAGE)

        # Search
        results = index.query(optimized)

        assert len(results) > 0
        assert results[0].chunk.chunk_id == "auth_func"
        assert results[0].score > 0.5

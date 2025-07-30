"""
Comprehensive Phase 10 Integration Test - All features working together.
"""

import os
import shutil
import tempfile
from pathlib import Path

from chunker import (  # Incremental; Multi-language; Query Advanced; Smart Context
    AdvancedQueryIndex,
    ChunkOptimizer,
    DefaultChangeDetector,
    DefaultChunkCache,
    DefaultIncrementalProcessor,
    InMemoryContextCache,
    LanguageDetectorImpl,
    MultiLanguageProcessorImpl,
    NaturalLanguageQueryEngine,
    OptimizationStrategy,
    ProjectAnalyzerImpl,
    SmartQueryOptimizer,
    TreeSitterSmartContextProvider,
    chunk_file,
)
from chunker.types import CodeChunk


class TestPhase10FullIntegration:
    """Test all Phase 10 features working together in a realistic scenario."""

    def setup_method(self):
        """Set up a multi-file_path project for testing."""
        self.test_dir = tempfile.mkdtemp()

        # Create a Python backend file_path
        self.backend_file = Path(self.test_dir) / "api" / "server.py"
        Path(Path(self.backend_file).mkdir(parents=True).parent, exist_ok=True)
        with open(self.backend_file, "w") as f:
            f.write(
                '''
"""API server for data processing."""
from flask import Flask, jsonify, request
from typing import List, Dict, Any
import json

app = Flask(__name__)

class DataProcessor:
    """Process incoming data with validation."""

    def __init__(self):
        self.cache = {}

    def validate(self, data: Dict[str, Any]) -> bool:
        """Validate input data."""
        required_fields = ['id', 'value', 'type']
        return all(field in data for field in required_fields)

    def transform(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data according to business rules."""
        if not self.validate(data):
            raise ValueError("Invalid data format")

        return {
            'id': data['id'],
            'processed_value': data['value'] * 2,
            'type': data['type'].upper(),
            'timestamp': '2024-01-01T00:00:00Z'
        }

    def process_batch(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process multiple items."""
        results = []
        for item in items:
            try:
                result = self.transform(item)
                results.append(result)
                self.cache[item['id']] = result
            except ValueError as e:
                results.append({'error': str(e), 'item': item})
        return results

processor = DataProcessor()

@app.route('/api/process', methods=['POST'])
def process_data():
    """API endpoint for data processing."""
    data = request.json
    if isinstance(data, list):
        results = processor.process_batch(data)
    else:
        results = processor.transform(data)
    return jsonify(results)

@app.route('/api/status', methods=['GET'])
def status():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'cache_size': len(processor.cache)
    })
''',
            )

        # Create a JavaScript frontend file_path
        self.frontend_file = Path(self.test_dir) / "frontend" / "client.js"
        Path(Path(self.frontend_file).mkdir(parents=True).parent, exist_ok=True)
        with open(self.frontend_file, "w") as f:
            f.write(
                """
// JavaScript API Client
class APIClient {
    constructor(baseUrl = '/api') {
        this.baseUrl = baseUrl;
        this.cache = new Map();
    }

    async processData(items) {
        const response = await fetch(`${this.baseUrl}/process`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(items),
        });

        const results = await response.json();

        // Cache results
        results.forEach((item) => {
            if (item.id) {
                this.cache.set(item.id, item);
            }
        });

        return results;
    }

    async checkStatus() {
        const response = await fetch(`${this.baseUrl}/status`);
        return response.json();
    }

    getCached(id) {
        return this.cache.get(id);
    }
}

// Example usage
const client = new APIClient();
const testData = [
    { id: '1', value: 10, type: 'numeric' },
    { id: '2', value: 20, type: 'numeric' },
];

// Process data
client.processData(testData).then(results => {
    console.log('Processed:', results);
});
""",
            )

        # Create a SQL file_path
        self.sql_file = Path(self.test_dir) / "schema.sql"
        with open(self.sql_file, "w") as f:
            f.write(
                """
-- Database schema for processed data
CREATE TABLE IF NOT EXISTS processed_items (
    id VARCHAR(255) PRIMARY KEY,
    original_value DECIMAL(10, 2),
    processed_value DECIMAL(10, 2),
    item_type VARCHAR(50),
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_type (item_type),
    INDEX idx_timestamp (processed_at)
);

-- Audit log
CREATE TABLE IF NOT EXISTS processing_log (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    item_id VARCHAR(255),
    action VARCHAR(50),
    details JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES processed_items(id)
);
""",
            )

    def teardown_method(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir)

    def test_complete_phase10_workflow(self):
        """Test the complete Phase 10 workflow with all features."""
        # 1. Multi-language Detection and Processing
        ml_processor = MultiLanguageProcessorImpl()
        lang_detector = LanguageDetectorImpl()
        project_analyzer = ProjectAnalyzerImpl()

        # Detect languages in project
        project_languages = ml_processor.detect_project_languages(self.test_dir)
        assert "python" in project_languages
        assert "javascript" in project_languages

        # Analyze project structure
        project_analyzer.analyze_structure(self.test_dir)
        file_language_map = {}
        for root, _dirs, files in os.walk(self.test_dir):
            for file_path in files:
                file_path = Path(root) / file_path
                lang, _ = lang_detector.detect_from_file(file_path)
                if lang:
                    file_language_map[file_path] = lang

        # 2. Chunk all files
        all_chunks = []
        chunk_map = {}

        for file_path, language in file_language_map.items():
            if language in ["python", "typescript", "javascript"]:
                chunks = chunk_file(file_path, language=language)
                all_chunks.extend(chunks)
                chunk_map[file_path] = chunks

        assert len(all_chunks) > 0

        # 3. Smart Context Analysis
        context_provider = TreeSitterSmartContextProvider(
            cache=InMemoryContextCache(ttl=3600),
        )

        # Find the DataProcessor class chunk
        processor_chunk = next(
            (c for c in all_chunks if "class DataProcessor" in c.content),
            None,
        )
        assert processor_chunk is not None

        # Get semantic context
        context, metadata = context_provider.get_semantic_context(processor_chunk)
        assert metadata.relationship_type in [
            "semantic",
            "dependency",
            "usage",
            "structural",
        ]
        assert "process" in context.lower()

        # Get dependency context
        deps = context_provider.get_dependency_context(processor_chunk, all_chunks)
        assert len(deps) > 0

        # 4. Advanced Query System
        query_index = AdvancedQueryIndex()
        for chunk in all_chunks:
            query_index.add_chunk(chunk)

        query_engine = NaturalLanguageQueryEngine(query_index)
        SmartQueryOptimizer()

        # Natural language query
        results = query_engine.search("functions that process data")
        assert len(results) > 0
        assert any("process" in r.chunk.content.lower() for r in results)

        # Query for API endpoints
        api_results = query_engine.search("API endpoints")
        assert any("@app.route" in r.chunk.content for r in api_results)

        # Cross-language query
        cache_results = query_engine.search("cache implementation")
        assert len(cache_results) > 0
        # Should find both Python and TypeScript cache implementations
        languages = {r.chunk.language for r in cache_results}
        assert len(languages) >= 2

        # 5. Chunk Optimization
        chunk_optimizer = ChunkOptimizer()

        # Optimize Python chunks for LLM
        py_chunks = chunk_map.get(self.backend_file, [])
        optimized, metrics = chunk_optimizer.optimize_for_llm(
            py_chunks,
            model="gpt-4",
            max_tokens=2000,
            strategy=OptimizationStrategy.BALANCED,
        )

        assert metrics.optimized_count <= metrics.original_count
        assert metrics.coherence_score > 0.5

        # 6. Incremental Processing
        incremental_processor = DefaultIncrementalProcessor()
        DefaultChangeDetector()
        DefaultChunkCache()

        # Initial processing
        for file_path, chunks in chunk_map.items():
            incremental_processor.update_chunks(file_path, chunks)

        # Simulate file_path modification
        with open(self.backend_file, "a") as f:
            f.write(
                '''

@app.route('/api/clear-cache', methods=['POST'])
def clear_cache():
    """Clear the processing cache."""
    processor.cache.clear()
    return jsonify({'status': 'cache cleared'})
''',
            )

        # Re-chunk and detect changes
        new_chunks = chunk_file(self.backend_file, language="python")
        diff = incremental_processor.compute_diff(self.backend_file, new_chunks)

        assert diff is not None
        assert len(diff.added) > 0  # New endpoint added
        assert any("clear-cache" in chunk.content for chunk in diff.added)

        # 7. Cross-Feature Integration
        # Find related chunks across languages using smart context
        api_chunk = next(
            (
                c
                for c in all_chunks
                if "@app.route" in c.content and "process" in c.content
            ),
            None,
        )

        if api_chunk:
            # Get usage context to find frontend code calling this API
            usage_context = context_provider.get_usage_context(api_chunk, all_chunks)

            # Should find JavaScript code that calls the API
            js_usage = [
                (chunk, meta)
                for chunk, meta in usage_context
                if chunk.language == "javascript"
            ]
            assert len(js_usage) > 0

        # 8. Query optimization with context
        # Use smart context to improve query results
        enhanced_results = []
        for result in results[:3]:  # Top 3 results
            context, _ = context_provider.get_semantic_context(result.chunk)
            enhanced_results.append(
                {
                    "chunk": result.chunk,
                    "score": result.score,
                    "context": context,
                },
            )

        # 9. Language-aware optimization
        # Group chunks by feature across languages
        feature_groups = project_analyzer.suggest_chunk_grouping(all_chunks)

        # Optimize each feature group
        for feature_chunks in feature_groups.values():
            if len(feature_chunks) > 1:
                optimized, _ = chunk_optimizer.optimize_for_llm(
                    feature_chunks,
                    model="gpt-4",
                    max_tokens=4000,
                    strategy=OptimizationStrategy.CONSERVATIVE,
                )

        # 10. Final verification
        # All chunks should be processable
        assert all(hasattr(chunk, "content") for chunk in all_chunks)
        assert all(hasattr(chunk, "language") for chunk in all_chunks)

        # Query index should have all chunks
        stats = query_index.get_statistics()
        assert stats["total_chunks"] == len(all_chunks)

        # Context cache should have entries
        assert context_provider._cache.size() > 0

        print(
            f"✓ Processed {len(all_chunks)} chunks across {len(project_languages)} languages",
        )
        print(f"✓ Query index contains {stats['total_chunks']} chunks")
        print(f"✓ Found {len(diff.added)} new chunks after modification")
        print("✓ All Phase 10 features working together successfully!")

    def test_error_handling_and_edge_cases(self):
        """Test error handling across all Phase 10 features."""
        # Empty file_path handling
        empty_file = Path(self.test_dir) / "empty.py"
        with Path(empty_file).open("w") as f:
            f.write("")

        # Multi-language processor should handle empty files
        ml_processor = MultiLanguageProcessorImpl()
        result = ml_processor.process_file(empty_file)
        assert result is not None

        # Query engine with no chunks
        empty_index = AdvancedQueryIndex()
        query_engine = NaturalLanguageQueryEngine(empty_index)
        results = query_engine.search("anything")
        assert results == []

        # Optimization with no chunks
        optimizer = ChunkOptimizer()
        optimized, metrics = optimizer.optimize_for_llm(
            [],
            model="gpt-4",
            max_tokens=2000,
        )
        assert optimized == []
        assert metrics.original_count == 0

        # Incremental processing with no changes
        processor = DefaultIncrementalProcessor()
        chunk = CodeChunk(
            id="test",
            content="def test(): pass",
            start_line=1,
            end_line=1,
            language="python",
        )
        processor.update_chunks("test.py", [chunk])
        diff = processor.compute_diff("test.py", [chunk])
        assert len(diff.added) == 0
        assert len(diff.removed) == 0
        assert len(diff.modified) == 0

    def test_performance_with_large_codebase(self):
        """Test Phase 10 features perform well with many files."""
        # Create 50 Python files
        large_chunks = []
        for i in range(50):
            content = f'''
def function_{i}(x, y):
    """Function {i} documentation."""
    result = x + y + {i}
    return result * 2

class Class_{i}:
    def method(self):
        return function_{i}(1, 2)
'''
            chunk = CodeChunk(
                id=f"chunk_{i}",
                content=content,
                start_line=i * 10,
                end_line=i * 10 + 9,
                language="python",
            )
            large_chunks.append(chunk)

        # Test query performance
        import time

        index = AdvancedQueryIndex()
        start = time.time()
        for chunk in large_chunks:
            index.add_chunk(chunk)
        index_time = time.time() - start
        assert index_time < 1.0  # Should index in under 1 second

        # Test query performance
        engine = NaturalLanguageQueryEngine(index)
        start = time.time()
        results = engine.search("function documentation")
        query_time = time.time() - start
        assert query_time < 0.5  # Should query in under 0.5 seconds
        assert len(results) > 0

        # Test optimization performance
        optimizer = ChunkOptimizer()
        start = time.time()
        optimized, _ = optimizer.optimize_for_llm(
            large_chunks[:20],  # Optimize 20 chunks
            model="gpt-4",
            max_tokens=2000,
        )
        opt_time = time.time() - start
        assert opt_time < 2.0  # Should optimize in under 2 seconds

        print(f"✓ Indexed {len(large_chunks)} chunks in {index_time:.2f}s")
        print(f"✓ Queried in {query_time:.2f}s")
        print(f"✓ Optimized 20 chunks in {opt_time:.2f}s")

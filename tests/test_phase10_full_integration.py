"""
Comprehensive Phase 10 Integration Test - All features working together.
"""

import os
import shutil
import tempfile
import time
from pathlib import Path

from chunker import (
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
        self.backend_file = Path(self.test_dir) / "api" / "server.py"
        Path(Path(self.backend_file).mkdir(parents=True).parent, exist_ok=True)
        with Path(self.backend_file).open("w", encoding="utf-8") as f:
            f.write(
                """
""\"API server for data processing.""\"
from flask import Flask, jsonify, request
from typing import List, Dict, Any
import json

app = Flask(__name__)

class DataProcessor:
    ""\"Process incoming data with validation.""\"

    def __init__(self):
        self.cache = {}

    def validate(self, data: Dict[str, Any]) -> bool:
        ""\"Validate input data.""\"
        required_fields = ['id', 'value', 'type']
        return all(field in data for field in required_fields)

    def transform(self, data: Dict[str, Any]) -> Dict[str, Any]:
        ""\"Transform data according to business rules.""\"
        if not self.validate(data):
            raise ValueError("Invalid data format")

        return {
            'id': data['id'],
            'processed_value': data['value'] * 2,
            'type': data['type'].upper(),
            'timestamp': '2024-01-01T00:00:00Z'
        }

    def process_batch(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ""\"Process multiple items.""\"
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
    ""\"API endpoint for data processing.""\"
    data = request.json
    if isinstance(data, list):
        results = processor.process_batch(data)
    else:
        results = processor.transform(data)
    return jsonify(results)

@app.route('/api/status', methods=['GET'])
def status():
    ""\"Health check endpoint.""\"
    return jsonify({
        'status': 'healthy',
        'cache_size': len(processor.cache)
    })
""",
            )
        self.frontend_file = Path(self.test_dir) / "frontend" / "client.js"
        Path(
            Path(self.frontend_file).mkdir(parents=True).parent,
            exist_ok=True,
        )
        with Path(self.frontend_file).open("w", encoding="utf-8") as f:
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
        self.sql_file = Path(self.test_dir) / "schema.sql"
        with Path(self.sql_file).open("w", encoding="utf-8") as f:
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
        ml_processor = MultiLanguageProcessorImpl()
        lang_detector = LanguageDetectorImpl()
        project_analyzer = ProjectAnalyzerImpl()
        project_languages = ml_processor.detect_project_languages(
            self.test_dir,
        )
        assert "python" in project_languages
        assert "javascript" in project_languages
        project_analyzer.analyze_structure(self.test_dir)
        file_language_map = {}
        for root, _dirs, files in os.walk(self.test_dir):
            for file_path in files:
                file_path = Path(root) / file_path
                lang, _ = lang_detector.detect_from_file(file_path)
                if lang:
                    file_language_map[file_path] = lang
        all_chunks = []
        chunk_map = {}
        for file_path, language in file_language_map.items():
            if language in {"python", "typescript", "javascript"}:
                chunks = chunk_file(file_path, language=language)
                all_chunks.extend(chunks)
                chunk_map[file_path] = chunks
        assert len(all_chunks) > 0
        context_provider = TreeSitterSmartContextProvider(
            cache=InMemoryContextCache(ttl=3600),
        )
        processor_chunk = next(
            (c for c in all_chunks if "class DataProcessor" in c.content),
            None,
        )
        assert processor_chunk is not None
        context, metadata = context_provider.get_semantic_context(processor_chunk)
        assert metadata.relationship_type in {
            "semantic",
            "dependency",
            "usage",
            "structural",
        }
        assert "process" in context.lower()
        deps = context_provider.get_dependency_context(processor_chunk, all_chunks)
        assert len(deps) > 0
        query_index = AdvancedQueryIndex()
        for chunk in all_chunks:
            query_index.add_chunk(chunk)
        query_engine = NaturalLanguageQueryEngine(query_index)
        SmartQueryOptimizer()
        results = query_engine.search("functions that process data")
        assert len(results) > 0
        assert any("process" in r.chunk.content.lower() for r in results)
        api_results = query_engine.search("API endpoints")
        assert any("@app.route" in r.chunk.content for r in api_results)
        cache_results = query_engine.search("cache implementation")
        assert len(cache_results) > 0
        languages = {r.chunk.language for r in cache_results}
        assert len(languages) >= 2
        chunk_optimizer = ChunkOptimizer()
        py_chunks = chunk_map.get(self.backend_file, [])
        optimized, metrics = chunk_optimizer.optimize_for_llm(
            py_chunks,
            model="gpt-4",
            max_tokens=2000,
            strategy=OptimizationStrategy.BALANCED,
        )
        assert metrics.optimized_count <= metrics.original_count
        assert metrics.coherence_score > 0.5
        incremental_processor = DefaultIncrementalProcessor()
        DefaultChangeDetector()
        DefaultChunkCache()
        for file_path, chunks in chunk_map.items():
            incremental_processor.update_chunks(file_path, chunks)
        with Path(self.backend_file).open("a", encoding="utf-8") as f:
            f.write(
                """

@app.route('/api/clear-cache', methods=['POST'])
def clear_cache():
    ""\"Clear the processing cache.""\"
    processor.cache.clear()
    return jsonify({'status': 'cache cleared'})
""",
            )
        new_chunks = chunk_file(self.backend_file, language="python")
        diff = incremental_processor.compute_diff(
            self.backend_file,
            new_chunks,
        )
        assert diff is not None
        assert len(diff.added) > 0
        assert any("clear-cache" in chunk.content for chunk in diff.added)
        api_chunk = next(
            (
                c
                for c in all_chunks
                if "@app.route" in c.content and "process" in c.content
            ),
            None,
        )
        if api_chunk:
            usage_context = context_provider.get_usage_context(api_chunk, all_chunks)
            js_usage = [
                (chunk, meta)
                for chunk, meta in usage_context
                if chunk.language == "javascript"
            ]
            assert len(js_usage) > 0
        enhanced_results = []
        for result in results[:3]:
            context, _ = context_provider.get_semantic_context(result.chunk)
            enhanced_results.append(
                {"chunk": result.chunk, "score": result.score, "context": context},
            )
        feature_groups = project_analyzer.suggest_chunk_grouping(all_chunks)
        for feature_chunks in feature_groups.values():
            if len(feature_chunks) > 1:
                _optimized, _ = chunk_optimizer.optimize_for_llm(
                    feature_chunks,
                    model="gpt-4",
                    max_tokens=4000,
                    strategy=OptimizationStrategy.CONSERVATIVE,
                )
        assert all(hasattr(chunk, "content") for chunk in all_chunks)
        assert all(hasattr(chunk, "language") for chunk in all_chunks)
        stats = query_index.get_statistics()
        assert stats["total_chunks"] == len(all_chunks)
        assert context_provider._cache.size() > 0
        print(
            f"✓ Processed {len(all_chunks)} chunks across {len(project_languages)} languages",
        )
        print(f"✓ Query index contains {stats['total_chunks']} chunks")
        print(f"✓ Found {len(diff.added)} new chunks after modification")
        print("✓ All Phase 10 features working together successfully!")

    def test_error_handling_and_edge_cases(self):
        """Test error handling across all Phase 10 features."""
        empty_file = Path(self.test_dir) / "empty.py"
        with Path(empty_file).open("w", encoding="utf-8") as f:
            f.write("")
        ml_processor = MultiLanguageProcessorImpl()
        result = ml_processor.process_file(empty_file)
        assert result is not None
        empty_index = AdvancedQueryIndex()
        query_engine = NaturalLanguageQueryEngine(empty_index)
        results = query_engine.search("anything")
        assert results == []
        optimizer = ChunkOptimizer()
        optimized, metrics = optimizer.optimize_for_llm(
            [],
            model="gpt-4",
            max_tokens=2000,
        )
        assert optimized == []
        assert metrics.original_count == 0
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

    @classmethod
    def test_performance_with_large_codebase(cls):
        """Test Phase 10 features perform well with many files."""
        large_chunks = []
        for i in range(50):
            content = f"""
def function_{i}(x, y):
    ""\"Function {i} documentation.""\"
    result = x + y + {i}
    return result * 2

class Class_{i}:
    def method(self):
        return function_{i}(1, 2)
"""
            chunk = CodeChunk(
                id=f"chunk_{i}",
                content=content,
                start_line=i * 10,
                end_line=i * 10 + 9,
                language="python",
            )
            large_chunks.append(chunk)
        index = AdvancedQueryIndex()
        start = time.time()
        for chunk in large_chunks:
            index.add_chunk(chunk)
        index_time = time.time() - start
        assert index_time < 1.0
        engine = NaturalLanguageQueryEngine(index)
        start = time.time()
        results = engine.search("function documentation")
        query_time = time.time() - start
        assert query_time < 0.5
        assert len(results) > 0
        optimizer = ChunkOptimizer()
        start = time.time()
        _optimized, _ = optimizer.optimize_for_llm(
            large_chunks[:20],
            model="gpt-4",
            max_tokens=2000,
        )
        opt_time = time.time() - start
        assert opt_time < 2.0
        print(f"✓ Indexed {len(large_chunks)} chunks in {index_time:.2f}s")
        print(f"✓ Queried in {query_time:.2f}s")
        print(f"✓ Optimized 20 chunks in {opt_time:.2f}s")

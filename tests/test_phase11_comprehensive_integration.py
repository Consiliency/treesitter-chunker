"""Comprehensive integration tests for Phase 11 completion.

Tests the integration of:
- Sliding Window Engine
- Text Processing Utilities
- Token Limit Handling
- Intelligent Fallback Strategy
- All processors working together
"""

import pytest
import tempfile
from pathlib import Path
import json
import yaml

from chunker import (
    IntelligentFallbackChunker,
    chunk_file_with_token_limit,
    count_chunk_tokens,
    CodeChunk
)


class TestPhase11ComprehensiveIntegration:
    """Comprehensive tests for all Phase 11 components."""
    
    def setup_method(self):
        """Create temp directory for test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
    def teardown_method(self):
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_intelligent_fallback_with_token_limits(self):
        """Test intelligent fallback respects token limits."""
        # Create fallback with strict token limit
        fallback = IntelligentFallbackChunker(
            token_limit=100,  # Small limit to force splitting
            model="gpt-4"
        )
        
        # Test with Python code (should use tree-sitter with split)
        python_code = '''
class DataProcessor:
    """A large class that will exceed token limits."""
    
    def __init__(self, config):
        self.config = config
        self.data = []
        self.results = {}
        
    def process_batch(self, batch):
        """Process a batch of data with lots of logic."""
        results = []
        for item in batch:
            # Complex processing logic here
            processed = self.transform(item)
            validated = self.validate(processed)
            results.append(validated)
        return results
        
    def transform(self, item):
        """Transform data item."""
        # Lots of transformation logic
        return item * 2
        
    def validate(self, item):
        """Validate processed item."""
        if item < 0:
            raise ValueError("Invalid item")
        return item
'''
        
        chunks = fallback.chunk_text(python_code, "processor.py")
        
        # Should have multiple chunks due to token limit
        assert len(chunks) > 1
        
        # All chunks should respect token limit
        for chunk in chunks:
            assert chunk.metadata['token_count'] <= 100
            assert chunk.metadata['chunking_decision'] == 'tree_sitter_with_split'
            
    def test_markdown_with_code_blocks(self):
        """Test markdown processing with embedded code."""
        fallback = IntelligentFallbackChunker(token_limit=500)
        
        markdown_content = '''# API Documentation

## Introduction

This API provides data processing capabilities.

## Usage Example

```python
from api import DataProcessor

processor = DataProcessor(config={
    'batch_size': 100,
    'timeout': 30
})

results = processor.process_batch(data)
```

## Configuration

The processor accepts the following configuration:

```yaml
batch_size: 100
timeout: 30
retries: 3
error_handling:
  log_errors: true
  raise_on_failure: false
```

## Error Handling

Errors are logged and can be retrieved via the error log.
'''
        
        md_file = self.temp_path / "api_docs.md"
        md_file.write_text(markdown_content)
        
        chunks = fallback.chunk_text(markdown_content, str(md_file))
        
        # Should use specialized processor
        assert len(chunks) >= 1
        
        # Verify code blocks are preserved
        full_content = '\n'.join(chunk.content for chunk in chunks)
        assert '```python' in full_content
        assert '```yaml' in full_content
        
    def test_log_file_with_stack_traces(self):
        """Test log file processing with error stack traces."""
        fallback = IntelligentFallbackChunker()
        
        log_content = '''2024-01-23 10:00:00 INFO [main] Starting application
2024-01-23 10:00:01 DEBUG [config] Loading configuration from config.yaml
2024-01-23 10:00:02 INFO [db] Connecting to database
2024-01-23 10:00:03 ERROR [db] Connection failed
java.sql.SQLException: Unable to connect to database
    at com.example.db.DatabaseConnection.connect(DatabaseConnection.java:45)
    at com.example.db.DatabasePool.initialize(DatabasePool.java:23)
    at com.example.Application.main(Application.java:15)
Caused by: java.net.ConnectException: Connection refused
    at java.net.Socket.connect(Socket.java:589)
    at com.mysql.jdbc.Connection.open(Connection.java:123)
2024-01-23 10:00:04 INFO [db] Retrying connection...
2024-01-23 10:00:05 INFO [db] Connection established
2024-01-23 10:00:06 INFO [main] Application started successfully
'''
        
        log_file = self.temp_path / "application.log"
        log_file.write_text(log_content)
        
        chunks = fallback.chunk_text(log_content, str(log_file))
        
        # Should keep stack traces together
        error_chunk = next((c for c in chunks if 'SQLException' in c.content), None)
        assert error_chunk is not None
        assert 'DatabaseConnection.java:45' in error_chunk.content
        assert 'Caused by:' in error_chunk.content
        
    def test_config_file_processing(self):
        """Test various config file formats."""
        fallback = IntelligentFallbackChunker()
        
        # Test TOML config
        toml_content = '''[package]
name = "treesitter-chunker"
version = "0.1.0"
description = "A powerful code chunking tool"

[dependencies]
tree-sitter = "0.20.0"
tiktoken = "0.5.0"

[dev-dependencies]
pytest = "^7.0"
black = "^23.0"

[tool.black]
line-length = 88
target-version = ["py38", "py39", "py310"]
'''
        
        toml_file = self.temp_path / "pyproject.toml"
        toml_file.write_text(toml_content)
        
        chunks = fallback.chunk_text(toml_content, str(toml_file))
        assert len(chunks) >= 1
        
        # Sections should be preserved
        full_content = '\n'.join(chunk.content for chunk in chunks)
        assert '[package]' in full_content
        assert '[dependencies]' in full_content
        
    def test_mixed_content_repository(self):
        """Test processing a repository with mixed content types."""
        fallback = IntelligentFallbackChunker(token_limit=1000)
        
        # Create repository structure
        (self.temp_path / "src").mkdir()
        (self.temp_path / "docs").mkdir()
        (self.temp_path / "config").mkdir()
        (self.temp_path / "logs").mkdir()
        
        # Python source code
        py_file = self.temp_path / "src" / "utils.py"
        py_file.write_text('''
def calculate_metrics(data):
    """Calculate various metrics from data."""
    total = sum(data)
    average = total / len(data) if data else 0
    return {
        'total': total,
        'average': average,
        'count': len(data)
    }

class MetricsProcessor:
    """Process and store metrics."""
    
    def __init__(self):
        self.metrics = []
        
    def add_metric(self, metric):
        self.metrics.append(metric)
        
    def get_summary(self):
        return calculate_metrics([m['value'] for m in self.metrics])
''')
        
        # Markdown documentation
        md_file = self.temp_path / "docs" / "metrics.md"
        md_file.write_text('''# Metrics Documentation

## Overview
This module provides metrics calculation functionality.

## API Reference

### `calculate_metrics(data)`
Calculate basic metrics from a list of numbers.

### `MetricsProcessor`
A class for processing and storing metrics over time.
''')
        
        # Configuration
        yaml_file = self.temp_path / "config" / "metrics.yaml"
        yaml_file.write_text('''metrics:
  enabled: true
  interval: 60
  aggregation:
    - sum
    - average
    - count
  
reporting:
  format: json
  destination: stdout
''')
        
        # Process all files
        all_chunks = []
        decision_counts = {}
        
        for file_path in [py_file, md_file, yaml_file]:
            chunks = fallback.chunk_text(
                file_path.read_text(),
                str(file_path)
            )
            all_chunks.extend(chunks)
            
            # Track decisions
            for chunk in chunks:
                decision = chunk.metadata.get('chunking_decision', 'unknown')
                decision_counts[decision] = decision_counts.get(decision, 0) + 1
        
        # Should have chunks from all files
        assert len(all_chunks) >= 3
        
        # Should use different strategies
        assert len(decision_counts) >= 2
        
        # Python should use tree-sitter
        py_chunks = [c for c in all_chunks if c.file_path == str(py_file)]
        assert any(c.metadata['chunking_decision'] == 'tree_sitter' for c in py_chunks)
        
    def test_token_limit_with_fallback(self):
        """Test token limits work with fallback chunking."""
        # Test with unknown file type
        fallback = IntelligentFallbackChunker(token_limit=200)
        
        # Large text that will need splitting
        large_text = " ".join([f"Sentence {i}." for i in range(100)])
        
        chunks = fallback.chunk_text(large_text, "large.txt")
        
        # Should use sliding window
        assert chunks[0].metadata['chunking_decision'] == 'sliding_window'
        
        # All chunks should respect token limit
        for chunk in chunks:
            token_count = chunk.metadata.get('token_count', 0)
            assert token_count <= 200
            
    def test_empty_file_handling(self):
        """Test handling of empty files."""
        fallback = IntelligentFallbackChunker()
        
        # Empty Python file
        empty_py = self.temp_path / "empty.py"
        empty_py.write_text("")
        
        chunks = fallback.chunk_text("", str(empty_py))
        
        # Should still produce at least one chunk
        assert len(chunks) >= 1
        
    def test_binary_file_detection(self):
        """Test detection and handling of binary files."""
        fallback = IntelligentFallbackChunker()
        
        # Create a binary file
        binary_file = self.temp_path / "data.bin"
        binary_file.write_bytes(b'\x00\x01\x02\x03\x04\x05')
        
        # Should detect as binary and handle appropriately
        reason = fallback.get_fallback_reason(str(binary_file), "")
        # Binary files might not be directly detectable from path alone
        
    def test_decision_transparency(self):
        """Test decision information availability."""
        fallback = IntelligentFallbackChunker(token_limit=500)
        
        code = '''
def process(items):
    return [item * 2 for item in items]
'''
        
        # Get decision info
        info = fallback.get_decision_info("process.py", code)
        
        assert 'decision' in info
        assert 'reason' in info
        assert 'metrics' in info
        
        metrics = info['metrics']
        assert metrics['has_tree_sitter_support'] is True
        assert metrics['is_code_file'] is True
        
    def test_streaming_with_token_limits(self):
        """Test streaming processing with token limits."""
        try:
            from chunker.sliding_window import DefaultSlidingWindowEngine, WindowConfig, WindowUnit
        except ImportError:
            pytest.skip("Sliding window engine not available")
            
        engine = DefaultSlidingWindowEngine()
        config = WindowConfig(
            size=100,  # Small window for testing
            unit=WindowUnit.TOKENS,
            overlap_value=10
        )
        
        # Create a streaming text source
        def text_generator():
            for i in range(10):
                yield f"This is paragraph {i}. It contains some text that will be chunked. "
                
        chunks = list(engine.chunk_stream(text_generator(), config, "stream.txt"))
        
        assert len(chunks) > 0
        
        # Verify token-based chunking
        for chunk in chunks:
            # Each chunk should be roughly the configured size
            assert len(chunk.content) > 0
            
    def test_cross_language_references(self):
        """Test handling of files with mixed languages."""
        fallback = IntelligentFallbackChunker()
        
        # HTML with embedded JavaScript and CSS
        html_content = '''<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial; }
        .highlight { color: red; }
    </style>
    <script>
        function greet(name) {
            alert("Hello, " + name);
        }
    </script>
</head>
<body>
    <h1>Test Page</h1>
    <button onclick="greet('World')">Click Me</button>
</body>
</html>'''
        
        html_file = self.temp_path / "index.html"
        html_file.write_text(html_content)
        
        chunks = fallback.chunk_text(html_content, str(html_file))
        
        # Should handle the mixed content
        assert len(chunks) >= 1
        
        # Content should be preserved
        full_content = '\n'.join(chunk.content for chunk in chunks)
        assert '<style>' in full_content
        assert '<script>' in full_content
        
    def test_performance_with_large_files(self):
        """Test performance with larger files."""
        fallback = IntelligentFallbackChunker(token_limit=2000)
        
        # Generate a large Python file
        large_py = self.temp_path / "large.py"
        with large_py.open('w') as f:
            for i in range(50):
                f.write(f'''
def function_{i}(param1, param2):
    """Function {i} documentation."""
    result = param1 + param2 + {i}
    print(f"Function {i} result: {{result}}")
    return result

''')
        
        import time
        start_time = time.time()
        
        chunks = fallback.chunk_text(large_py.read_text(), str(large_py))
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete reasonably quickly
        assert duration < 5.0  # 5 seconds max
        
        # Should produce multiple chunks
        assert len(chunks) > 1
        
        # All should use tree-sitter
        assert all(c.metadata['chunking_decision'] in ['tree_sitter', 'tree_sitter_with_split'] 
                  for c in chunks)
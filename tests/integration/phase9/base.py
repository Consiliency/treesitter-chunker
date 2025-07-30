"""Base class and utilities for Phase 9 integration tests."""

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from chunker.hierarchy import ChunkHierarchyBuilder, HierarchyNavigator
from chunker.metadata import BaseMetadataExtractor
from chunker.rules import DefaultRuleEngine
from chunker.token import TiktokenCounter, TokenAwareChunker
from chunker.types import CodeChunk


class Phase9IntegrationTestBase:
    """Base class for Phase 9 integration tests."""

    @pytest.fixture
    def test_repo_path(self, tmp_path):
        """Create a test repository with various file types."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()

        # Create Python files
        python_dir = repo_path / "src" / "python"
        python_dir.mkdir(parents=True)

        (python_dir / "main.py").write_text(
            '''
"""Main module for the application."""

import os
import sys
from typing import List, Optional

class Calculator:
    """A simple calculator class."""

    def __init__(self):
        self.history: List[float] = []

    def add(self, a: float, b: float) -> float:
        """Add two numbers."""
        result = a + b
        self.history.append(result)
        return result

    def subtract(self, a: float, b: float) -> float:
        """Subtract b from a."""
        result = a - b
        self.history.append(result)
        return result

    def multiply(self, a: float, b: float) -> float:
        """Multiply two numbers."""
        result = a * b
        self.history.append(result)
        return result

    def divide(self, a: float, b: float) -> float:
        """Divide a by b."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        result = a / b
        self.history.append(result)
        return result

    def get_history(self) -> List[float]:
        """Get calculation history."""
        return self.history.copy()

    def clear_history(self) -> None:
        """Clear calculation history."""
        self.history.clear()

def main():
    """Main entry point."""
    calc = Calculator()
    print(calc.add(10, 5))
    print(calc.multiply(3, 4))

if __name__ == "__main__":
    main()
''',
        )

        (python_dir / "utils.py").write_text(
            r'''
"""Utility functions."""

import re
from functools import lru_cache

# TODO: Add more utility functions
# TODO: Implement caching strategy

@lru_cache(maxsize=128)
def validate_email(email: str) -> bool:
    """Validate email address format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def format_name(first: str, last: str) -> str:
    """Format a person's name."""
    return f"{first.title()} {last.title()}"

class StringUtils:
    """String manipulation utilities."""

    @staticmethod
    def truncate(text: str, max_length: int = 50) -> str:
        """Truncate text to maximum length."""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."

    @staticmethod
    def word_count(text: str) -> int:
        """Count words in text."""
        return len(text.split())
''',
        )

        # Create JavaScript files
        js_dir = repo_path / "src" / "javascript"
        js_dir.mkdir(parents=True)

        (js_dir / "app.js").write_text(
            """
/**
 * Main application module
 * @module app
 */

import { EventEmitter } from 'events';

/**
 * Application class
 * @class
 */
class Application extends EventEmitter {
    constructor() {
        super();
        this.config = {};
        this.isRunning = false;
    }

    /**
     * Initialize the application
     * @param {Object} config - Configuration object
     */
    async initialize(config) {
        this.config = config;
        this.emit('initializing');

        // Perform initialization
        await this.loadModules();
        await this.connectDatabase();

        this.emit('initialized');
    }

    /**
     * Load application modules
     * @private
     */
    async loadModules() {
        // Module loading logic
        console.log('Loading modules...');
    }

    /**
     * Connect to database
     * @private
     */
    async connectDatabase() {
        // Database connection logic
        console.log('Connecting to database...');
    }

    /**
     * Start the application
     */
    start() {
        if (this.isRunning) {
            throw new Error('Application is already running');
        }

        this.isRunning = true;
        this.emit('started');
        console.log('Application started');
    }

    /**
     * Stop the application
     */
    stop() {
        if (!this.isRunning) {
            throw new Error('Application is not running');
        }

        this.isRunning = false;
        this.emit('stopped');
        console.log('Application stopped');
    }
}

// Helper functions
function createApp(config) {
    return new Application();
}

function getDefaultConfig() {
    return {
        port: 3000,
        host: 'localhost',
        debug: false
    };
}

export { Application, createApp, getDefaultConfig };
""",
        )

        # Create a markdown file (for fallback chunking)
        docs_dir = repo_path / "docs"
        docs_dir.mkdir()

        (docs_dir / "README.md").write_text(
            """
# Test Repository

This is a test repository for Phase 9 integration testing.

## Features

- Calculator implementation in Python
- Application framework in JavaScript
- Comprehensive documentation

## Installation

```bash
pip install -r requirements.txt
npm install
```

## Usage

### Python Calculator

```python
from src.python.main import Calculator

calc = Calculator()
result = calc.add(10, 5)
print(result)  # 15
```

### JavaScript Application

```javascript
import { createApp } from './src/javascript/app.js';

const app = createApp();
await app.initialize({ port: 3000 });
app.start();
```

## API Documentation

### Calculator Class

The calculator provides basic arithmetic operations:

- `add(a, b)`: Add two numbers
- `subtract(a, b)`: Subtract b from a
- `multiply(a, b)`: Multiply two numbers
- `divide(a, b)`: Divide a by b (raises error for division by zero)

### Application Class

The application framework provides:

- Event-based architecture
- Async initialization
- Module loading system
- Database connectivity

## Contributing

Please read CONTRIBUTING.md for details on our code of conduct.

## License

This project is licensed under the MIT License.
""",
        )

        # Create a log file (for fallback chunking)
        logs_dir = repo_path / "logs"
        logs_dir.mkdir()

        (logs_dir / "app.log").write_text(
            """
2024-01-15 10:00:00 INFO Starting application
2024-01-15 10:00:01 INFO Loading configuration from config.yaml
2024-01-15 10:00:02 INFO Configuration loaded successfully
2024-01-15 10:00:03 INFO Initializing database connection
2024-01-15 10:00:04 INFO Connected to database: postgresql://localhost:5432/app_db
2024-01-15 10:00:05 INFO Loading application modules
2024-01-15 10:00:06 DEBUG Module 'auth' loaded
2024-01-15 10:00:07 DEBUG Module 'api' loaded
2024-01-15 10:00:08 DEBUG Module 'admin' loaded
2024-01-15 10:00:09 INFO All modules loaded successfully
2024-01-15 10:00:10 INFO Starting HTTP server on port 3000
2024-01-15 10:00:11 INFO Server started successfully
2024-01-15 10:00:12 INFO Application ready to accept requests
2024-01-15 10:15:23 INFO Received GET request: /api/users
2024-01-15 10:15:24 INFO Request processed successfully
2024-01-15 10:30:45 WARNING High memory usage detected: 85%
2024-01-15 10:30:46 INFO Running garbage collection
2024-01-15 10:30:47 INFO Memory usage reduced to 65%
2024-01-15 11:00:00 ERROR Database connection lost
2024-01-15 11:00:01 INFO Attempting to reconnect to database
2024-01-15 11:00:05 INFO Database connection restored
2024-01-15 12:00:00 INFO Shutting down application
2024-01-15 12:00:01 INFO Closing database connections
2024-01-15 12:00:02 INFO Application stopped
""",
        )

        # Create .gitignore
        (repo_path / ".gitignore").write_text(
            """
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/
pip-log.txt
pip-delete-this-directory.txt
.tox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.log
.git
.pytest_cache
.mypy_cache
.hypothesis

# JavaScript
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.npm
.eslintcache

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db
""",
        )

        # Initialize git repo
        subprocess.run(["git", "init"], check=False, cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "add", "."],
            check=False,
            cwd=repo_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            check=False,
            cwd=repo_path,
            capture_output=True,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.com",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.com",
            },
        )

        return repo_path

    @pytest.fixture
    def sample_python_file(self, tmp_path):
        """Create a sample Python file for testing."""
        file_path = tmp_path / "sample.py"
        file_path.write_text(
            '''
class DataProcessor:
    """Process data with various operations."""

    def __init__(self, name: str):
        self.name = name
        self._data = []

    def add_data(self, item: Any) -> None:
        """Add data item."""
        self._data.append(item)

    def get_data(self) -> List[Any]:
        """Get all data."""
        return self._data.copy()

    def process(self) -> Dict[str, Any]:
        """Process all data."""
        return {
            "name": self.name,
            "count": len(self._data),
            "data": self._data
        }

    def clear(self) -> None:
        """Clear all data."""
        self._data.clear()

# Helper functions
def create_processor(name: str) -> DataProcessor:
    """Create a new data processor."""
    return DataProcessor(name)

def merge_processors(p1: DataProcessor, p2: DataProcessor) -> DataProcessor:
    """Merge two processors."""
    merged = DataProcessor(f"{p1.name}_{p2.name}")
    for item in p1.get_data() + p2.get_data():
        merged.add_data(item)
    return merged
''',
        )
        return file_path

    def create_phase9_chunker(
        self,
        enable_tokens: bool = True,
        enable_hierarchy: bool = True,
        enable_metadata: bool = True,
        enable_semantic: bool = True,
        enable_rules: bool = True,
        token_limit: int | None = None,
    ) -> dict[str, Any]:
        """Create a chunker with Phase 9 features enabled."""
        components = {}

        if enable_tokens:

            components["token_counter"] = TiktokenCounter()
            if token_limit:
                components["token_chunker"] = TokenAwareChunker(
                    max_tokens=token_limit,
                )

        if enable_hierarchy:

            components["hierarchy_builder"] = ChunkHierarchyBuilder()
            components["hierarchy_navigator"] = HierarchyNavigator()

        if enable_metadata:

            components["metadata_extractor"] = BaseMetadataExtractor()

        if enable_semantic:
            from chunker.semantic import (
                MergeConfig,
                TreeSitterRelationshipAnalyzer,
                TreeSitterSemanticMerger,
            )

            components["relationship_analyzer"] = TreeSitterRelationshipAnalyzer()
            components["semantic_merger"] = TreeSitterSemanticMerger(
                config=MergeConfig(),
            )

        if enable_rules:

            components["rule_engine"] = DefaultRuleEngine()

        return components

    def assert_chunks_have_tokens(self, chunks: list[CodeChunk]) -> None:
        """Assert that all chunks have token counts."""
        for chunk in chunks:
            assert hasattr(chunk, "metadata"), f"Chunk missing metadata: {chunk}"
            assert "tokens" in chunk.metadata, f"Chunk missing token count: {chunk}"
            assert isinstance(chunk.metadata["tokens"], int)
            assert chunk.metadata["tokens"] > 0

    def assert_chunks_have_hierarchy(self, chunks: list[CodeChunk]) -> None:
        """Assert that chunks have hierarchical relationships."""
        # At least some chunks should have parent/child relationships
        has_parent = any(
            chunk.metadata.get("parent_id") is not None
            for chunk in chunks
            if hasattr(chunk, "metadata")
        )
        has_children = any(
            chunk.metadata.get("child_ids", [])
            for chunk in chunks
            if hasattr(chunk, "metadata")
        )
        assert has_parent or has_children, "No hierarchical relationships found"

    def assert_chunks_have_metadata(self, chunks: list[CodeChunk]) -> None:
        """Assert that chunks have extracted metadata."""
        for chunk in chunks:
            assert hasattr(chunk, "metadata"), f"Chunk missing metadata: {chunk}"
            # Check for common metadata fields
            metadata = chunk.metadata
            if chunk.chunk_type in ["function_definition", "method_definition"]:
                assert any(
                    key in metadata
                    for key in [
                        "signature",
                        "parameters",
                        "return_type",
                        "complexity",
                    ]
                )

    def create_test_config_file(self, path: Path, config: dict[str, Any]) -> Path:
        """Create a test configuration file."""
        config_path = path / ".chunkerrc"
        with Path(config_path).open(
            "w",
        ) as f:
            import toml

            toml.dump(config, f)
        return config_path

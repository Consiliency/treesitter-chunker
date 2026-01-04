"""Integration tests for metadata extraction with custom rules."""

from typing import Any

import pytest

from chunker.core import chunk_file
from chunker.rules.builtin import ImportBlockRule
from chunker.rules.custom import MetadataRule
from chunker.rules.engine import DefaultRuleEngine


class TestMetadataRulesIntegration:
    """Test metadata extraction integrated with custom rules."""

    @staticmethod
    @pytest.fixture
    def sample_python_file_with_todos(tmp_path):
        """Create a Python file with TODO comments and various metadata."""
        file_path = tmp_path / "tasks.py"
        file_path.write_text(
            """
""\"
Task management module.

Copyright (c) 2024 Test Corp. All rights reserved.
""\"

import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

# TODO: Add support for priority levels
# TODO: Implement task persistence

@dataclass
class Task:
    ""\"Represents a single task.""\"
    id: int
    title: str
    completed: bool = False
    metadata: Dict[str, Any] = None

    def complete(self) -> None:
        ""\"Mark task as completed.""\"
        self.completed = True
        # TODO: Add completion timestamp

class TaskManager:
    ""\"Manages a collection of tasks.""\"

    def __init__(self, name: str = "default"):
        ""\"Initialize task manager.

        Args:
            name: Name of this task manager instance
        ""\"
        self.name = name
        self.tasks: List[Task] = []
        self._next_id = 1

    def add_task(self, title: str, **metadata) -> Task:
        ""\"Add a new task.

        Args:
            title: Task title
            **metadata: Additional task metadata

        Returns:
            The created task
        ""\"
        task = Task(
            id=self._next_id,
            title=title,
            metadata=metadata or {}
        )
        self.tasks.append(task)
        self._next_id += 1
        return task

    async def process_tasks(self) -> int:
        ""\"Process all pending tasks asynchronously.

        Returns:
            Number of tasks processed
        ""\"
        # TODO: Implement actual async processing
        pending = [t for t in self.tasks if not t.completed]

        # Simulate async processing
        for task in pending:
            await asyncio.sleep(0.1)
            task.complete()

        return len(pending)

    def get_stats(self) -> Dict[str, int]:
        ""\"Get task statistics.

        Returns:
            Dictionary with task counts
        ""\"
        completed = sum(1 for t in self.tasks if t.completed)
        pending = len(self.tasks) - completed

        return {
            'total': len(self.tasks),
            'completed': completed,
            'pending': pending,
            'completion_rate': completed / len(self.tasks) if self.tasks else 0
        }

# Helper functions
def create_default_manager() -> TaskManager:
    ""\"Create a task manager with default settings.""\"
    return TaskManager("default")

# TODO: Add CLI interface
# TODO: Add export functionality
""",
        )
        return file_path

    @staticmethod
    def test_metadata_extraction_with_todo_rules(
        sample_python_file_with_todos,
    ):
        """Test extracting metadata while also finding TODO comments."""
        chunks = chunk_file(
            sample_python_file_with_todos,
            "python",
            extract_metadata=True,
        )
        content = sample_python_file_with_todos.read_text()
        assert "TODO:" in content, "File should contain TODO comments"
        assert "Copyright (c)" in content, "File should contain copyright"
        for chunk in chunks:
            assert hasattr(chunk, "metadata"), "Chunk should have metadata"
            metadata = chunk.metadata
            if chunk.node_type in {"function_definition", "method"}:
                assert (
                    "signature" in metadata
                ), f"Function chunk should have signature: {chunk.node_type}"
                sig = metadata["signature"]
                assert "name" in sig
                assert "parameters" in sig
        chunk_types = {chunk.node_type for chunk in chunks}
        assert "class_definition" in chunk_types
        assert "function_definition" in chunk_types or "method" in chunk_types
        async_chunks = [
            c
            for c in chunks
            if c.node_type in {"function_definition", "method"} and "async" in c.content
        ]
        assert len(async_chunks) > 0, "Should have async functions"

    @classmethod
    def test_custom_rule_with_metadata_filtering(cls, sample_python_file_with_todos):
        """Test using custom rules to filter chunks based on metadata."""

        class AsyncFunctionRule(MetadataRule):
            """Find async functions."""

            @property
            def rule_name(self) -> str:
                return "async_functions"

            @staticmethod
            def matches_metadata(metadata: dict[str, Any]) -> bool:
                """Check if chunk is an async function."""
                if "signature" in metadata:
                    sig = metadata["signature"]
                    return sig.get("modifiers", []) and "async" in sig["modifiers"]
                return False

        chunks = chunk_file(
            sample_python_file_with_todos,
            "python",
            extract_metadata=True,
        )
        async_rule = AsyncFunctionRule()
        async_chunks = [
            chunk
            for chunk in chunks
            if hasattr(chunk, "metadata")
            and async_rule.matches_metadata(chunk.metadata)
        ]
        assert len(async_chunks) > 0, "Should find async functions"
        assert any("process_tasks" in chunk.content for chunk in async_chunks)

    @classmethod
    def test_complexity_metadata_with_rules(
        cls,
        sample_python_file_with_todos,
    ):
        """Test complexity analysis with custom complexity rules."""

        class ComplexFunctionRule(MetadataRule):
            """Find functions with high complexity."""

            @property
            def rule_name(self) -> str:
                return "complex_functions"

            @staticmethod
            def matches_metadata(metadata: dict[str, Any]) -> bool:
                """Check if function has high complexity."""
                if "complexity" in metadata:
                    complexity = metadata["complexity"]
                    return (
                        complexity.get(
                            "cyclomatic",
                            0,
                        )
                        > 3
                        or complexity.get("cognitive", 0) > 5
                    )
                return False

        chunks = chunk_file(
            sample_python_file_with_todos,
            "python",
            extract_metadata=True,
        )
        complex_rule = ComplexFunctionRule()

        [
            chunk
            for chunk in chunks
            if hasattr(chunk, "metadata")
            and complex_rule.matches_metadata(
                chunk.metadata,
            )
        ]
        # Check that we can identify complexity
        for chunk in chunks:
            if chunk.node_type in {"function_definition", "method"}:
                assert "complexity" in chunk.metadata
                complexity = chunk.metadata["complexity"]
                assert "cyclomatic" in complexity
                assert "cognitive" in complexity
                assert "lines_of_code" in complexity

    @staticmethod
    @pytest.mark.xfail(
        reason="Docstring extraction not finding class docstrings - tracked in issue"
    )
    def test_docstring_extraction_with_rules(sample_python_file_with_todos):
        """Test docstring extraction combined with docstring rules."""
        chunks = chunk_file(
            sample_python_file_with_todos,
            "python",
            extract_metadata=True,
        )
        chunks_with_docstrings = [
            c for c in chunks if hasattr(c, "metadata") and "docstring" in c.metadata
        ]
        assert (
            len(
                chunks_with_docstrings,
            )
            > 0
        ), "Should have chunks with docstrings"
        for chunk in chunks_with_docstrings:
            docstring = chunk.metadata["docstring"]
            assert docstring, f"Chunk {chunk.node_type} should have non-empty docstring"
            assert isinstance(docstring, str)
        class_chunks = [c for c in chunks if c.node_type == "class_definition"]
        assert any(
            "Represents a single task" in c.metadata.get("docstring", "")
            for c in class_chunks
        ), "Should find Task class docstring"

    @classmethod
    def test_import_analysis_with_rules(cls, sample_python_file_with_todos):
        """Test import dependency analysis with import block rules."""
        chunks = chunk_file(
            sample_python_file_with_todos,
            "python",
            extract_metadata=True,
        )
        rule_engine = DefaultRuleEngine()
        rule_engine.add_rule(ImportBlockRule())
        content = sample_python_file_with_todos.read_text()
        assert "import asyncio" in content
        assert "from typing import" in content
        for chunk in chunks:
            if hasattr(chunk, "metadata") and "dependencies" in chunk.metadata:
                deps = chunk.metadata["dependencies"]
                assert isinstance(deps, list), "Dependencies should be a list"
                if chunk.node_type == "module":
                    assert any("asyncio" in str(dep) for dep in deps)

    @classmethod
    def test_combined_metadata_and_rule_application(cls, tmp_path):
        """Test applying multiple rules and extracting metadata simultaneously."""
        complex_file = tmp_path / "complex.py"
        complex_file.write_text(
            """
#!/usr/bin/env python3
""\"
Complex module with various patterns.

This module demonstrates multiple code patterns that can be
detected by both metadata extraction and custom rules.
""\"

# Standard library imports
import os
import sys
from functools import lru_cache
from typing import Optional, List, Dict

# TODO: Refactor this module
# FIXME: Handle edge cases in parsing

__version__ = "1.0.0"
__author__ = "Test Author"

# Configuration section
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
MAX_RETRIES = 3

@lru_cache(maxsize=128)
def fibonacci(n: int) -> int:
    ""\"Calculate fibonacci number recursively with memoization.

    Args:
        n: The position in fibonacci sequence

    Returns:
        The fibonacci number at position n
    ""\"
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

class DataProcessor:
    ""\"Process data with various algorithms.""\"

    # TODO: Add more algorithms

    def __init__(self, algorithm: str = "default"):
        self.algorithm = algorithm
        self._cache: Dict[str, Any] = {}

    def process(self, data: List[Any]) -> List[Any]:
        ""\"Process data using selected algorithm.

        This method demonstrates high complexity with multiple
        branches and nested conditions.
        ""\"
        if not data:
            return []

        results = []
        for i, item in enumerate(data):
            # Complex nested logic
            if isinstance(item, dict):
                if "value" in item:
                    if item["value"] > 0:
                        results.append(item["value"] * 2)
                    else:
                        results.append(0)
                else:
                    # FIXME: Better error handling needed
                    results.append(None)
            elif isinstance(item, (int, float)):
                results.append(item)
            else:
                # TODO: Support more data types
                try:
                    results.append(float(item))
                except (ValueError, TypeError):
                    results.append(None)

        return results

# Test section
if __name__ == "__main__":
    # Run some tests
    proc = DataProcessor()
    test_data = [1, {"value": 5}, "3.14", None]
    print(proc.process(test_data))
""",
        )
        from chunker.rules.builtin import (
            ConfigurationBlockRule,
            DebugStatementRule,
            DocstringRule,
            ImportBlockRule,
            TodoCommentRule,
        )

        chunks = chunk_file(complex_file, "python", extract_metadata=True)
        rule_engine = DefaultRuleEngine()
        rule_engine.add_rule(TodoCommentRule())
        rule_engine.add_rule(DocstringRule())
        rule_engine.add_rule(ImportBlockRule())
        rule_engine.add_rule(ConfigurationBlockRule())
        rule_engine.add_rule(DebugStatementRule())
        content = complex_file.read_text()
        assert "TODO:" in content
        assert "FIXME:" in content
        assert "import os" in content
        assert '"""' in content
        function_chunks = [c for c in chunks if c.node_type == "function_definition"]
        assert len(function_chunks) > 0
        fib_chunk = next((c for c in function_chunks if "fibonacci" in c.content), None)
        assert fib_chunk is not None
        assert "signature" in fib_chunk.metadata
        assert "decorators" in fib_chunk.metadata["signature"]
        assert len(fib_chunk.metadata["signature"]["decorators"]) > 0
        process_chunk = next((c for c in chunks if "def process" in c.content), None)
        assert process_chunk is not None
        assert "complexity" in process_chunk.metadata
        assert process_chunk.metadata["complexity"]["cyclomatic"] > 5

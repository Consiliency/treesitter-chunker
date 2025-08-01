"""Comprehensive benchmark suite for Tree-sitter Chunker.

This module provides extensive benchmarking across different scenarios.
"""
import gc
import json
import multiprocessing
import os
import shutil
import statistics
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chunker import (
    ASTCache,
    chunk_directory_parallel,
    chunk_file,
    chunk_file_with_token_limit,
    chunk_files_parallel,
    get_parser,
    list_languages,
)
from chunker.fallback.intelligent_fallback import IntelligentFallbackChunker
from chunker.strategies import (
    AdaptiveChunker,
    CompositeChunker,
    HierarchicalChunker,
    SemanticChunker,
)


@dataclass
class BenchmarkScenario:
    """Defines a benchmark scenario."""
    name: str
    description: str
    setup: callable
    benchmark: callable
    teardown: callable | None = None
    iterations: int = 5
    warmup: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


class ComprehensiveBenchmarkSuite:
    """Comprehensive benchmark suite for different use cases."""

    def __init__(self, output_dir: (Path | None) = None):
        self.output_dir = output_dir or Path("benchmark_results")
        self.output_dir.mkdir(exist_ok=True)
        self.scenarios: list[BenchmarkScenario] = []
        self._setup_scenarios()

    def _setup_scenarios(self):
        """Setup all benchmark scenarios."""
        self.scenarios.append(BenchmarkScenario(name="language_comparison",
            description="Compare chunking performance across languages",
            setup=self._setup_multi_language_files, benchmark=self.
            _benchmark_languages, metadata={"category": "language",
            "languages": list_languages()}))
        self.scenarios.append(BenchmarkScenario(name="file_size_scaling",
            description="Test performance with different file sizes", setup=self._setup_size_scaling_files, benchmark=self.
            _benchmark_size_scaling, metadata={"category": "scaling",
            "sizes": ["small", "medium", "large", "xlarge"]}))
        self.scenarios.append(BenchmarkScenario(name="strategy_comparison",
            description="Compare different chunking strategies", setup=self
            ._setup_strategy_test_files, benchmark=self.
            _benchmark_strategies, metadata={"category": "strategy",
            "strategies": ["semantic", "hierarchical", "adaptive",
            "composite"]}))
        self.scenarios.append(BenchmarkScenario(name="concurrency_scaling",
            description="Test parallel processing with different worker counts", setup=self._setup_parallel_test_files, benchmark=self.
            _benchmark_concurrency, metadata={"category": "concurrency",
            "workers": [1, 2, 4, 8, 16]}))
        self.scenarios.append(BenchmarkScenario(name="cache_effectiveness",
            description="Measure cache hit rates and performance impact",
            setup=self._setup_cache_test_files, benchmark=self.
            _benchmark_cache, metadata={"category": "cache", "scenarios": [
            "cold", "warm", "partial"]}))
        self.scenarios.append(BenchmarkScenario(name="token_limit_chunking",
            description="Test token-aware chunking performance", setup=self
            ._setup_token_test_files, benchmark=self.
            _benchmark_token_limits, metadata={"category": "tokens",
            "limits": [1000, 2000, 4000, 8000]}))
        self.scenarios.append(BenchmarkScenario(name="fallback_scenarios",
            description="Test intelligent fallback performance", setup=self
            ._setup_fallback_test_files, benchmark=self._benchmark_fallback,
            metadata={"category": "fallback", "file_types": ["code", "text",
            "mixed"]}))
        self.scenarios.append(BenchmarkScenario(name="memory_profiling",
            description="Profile memory usage patterns", setup=self.
            _setup_memory_test_files, benchmark=self._benchmark_memory,
            metadata={"category": "memory", "metrics": ["rss", "vms",
            "objects"]}))
        self.scenarios.append(BenchmarkScenario(name="real_world_repo",
            description="Benchmark on real repository structure", setup=self._setup_repo_structure, benchmark=self.
            _benchmark_repository, metadata={"category": "real_world",
            "structure": "mixed_project"}))
        self.scenarios.append(BenchmarkScenario(name="export_formats",
            description="Compare export format performance", setup=self.
            _setup_export_test_files, benchmark=self._benchmark_exports,
            metadata={"category": "export", "formats": ["json", "jsonl",
            "parquet", "csv"]}))

    @classmethod
    def _create_test_file(cls, language: str, size: str = "medium") -> Path:
        """Create a test file for a specific language and size."""
        templates = {"python": {"small":
            """
def hello():
    return "world"

class Test:
    def method(self):
        pass
"""
            , "medium": "\n".join([
            f"""
def function_{i}(x, y):
    '''Function {i} docstring.'''
    result = x + y + {i}
    for j in range(10):
        result += j
    return result

class Class_{i}:
    def __init__(self):
        self.value = {i}

    def process(self, data):
        return [x * self.value for x in data]
"""
             for i in range(20)]), "large": "\n".join([
            f"""
def complex_function_{i}(data, options=None):
    '''Complex function with multiple operations.'''
    if options is None:
        options = {{}}

    result = []
    for item in data:
        if isinstance(item, dict):
            processed = {{k: v * {i} for k, v in item.items()}}
        elif isinstance(item, list):
            processed = [x + {i} for x in item]
        else:
            processed = item
        result.append(processed)

    # Nested class
    class Processor_{i}:
        def __init__(self, factor={i}):
            self.factor = factor

        def apply(self, value):
            return value * self.factor

    return Processor_{i}().apply(sum(result))
"""
             for i in range(100)])}, "javascript": {"small":
            """
function hello() {
    return "world";
}

class Test {
    method() {
        return 42;
    }
}
"""
            , "medium": "\n".join([
            f"""
function function_{i}(x, y) {{
    // Function {i}
    let result = x + y + {i};
    for (let j = 0; j < 10; j++) {{
        result += j;
    }}
    return result;
}}

class Class_{i} {{
    constructor() {{
        this.value = {i};
    }}

    process(data) {{
        return data.map(x => x * this.value);
    }}
}}
"""
             for i in range(20)])}}
        if language not in templates:
            language = "python"
        content = templates[language].get(size, templates[language]["medium"])
        suffix = {"python": ".py", "javascript": ".js", "rust": ".rs", "c":
            ".c", "cpp": ".cpp"}.get(language, ".txt")
        temp_file = tempfile.NamedTemporaryFile(encoding="utf-8", mode="w",
            suffix=suffix, delete=False)
        temp_file.write(content)
        temp_file.close()
        return Path(temp_file.name)

    def _setup_multi_language_files(self) -> dict[str, list[Path]]:
        """Setup files for multiple languages."""
        files = {}
        for lang in ["python", "javascript", "rust", "c", "cpp"]:
            try:
                get_parser(lang)
                files[lang] = [self._create_test_file(lang, size) for size in
                    ["small", "medium", "large"]]
            except (ImportError, RuntimeError):
                pass
        return {"files": files}

    @staticmethod
    def _benchmark_languages(context: dict[str, Any]) -> dict[str, Any]:
        """Benchmark different languages."""
        results = {}
        for lang, file_list in context["files"].items():
            times = []
            chunks_count = []
            for file_path in file_list:
                start = time.perf_counter()
                chunks = chunk_file(file_path, lang)
                elapsed = time.perf_counter() - start
                times.append(elapsed)
                chunks_count.append(len(chunks))
            results[lang] = {"mean_time": statistics.mean(times),
                "total_chunks": sum(chunks_count), "files_processed": len(
                file_list)}
        return results

    @classmethod
    def _setup_size_scaling_files(cls) -> dict[str, Any]:
        """Setup files of different sizes."""
        sizes = {"small": 10, "medium": 50, "large": 200, "xlarge": 1000}
        files = {}
        for size_name, count in sizes.items():
            content = "\n".join([
                f"""
def function_{i}(x, y, z=None):
    '''Function {i} with size {size_name}.'''
    if z is None:
        z = {i}
    result = x + y + z
    # Some padding to make functions more realistic
    temp = result * 2
    temp2 = temp / 3
    return temp2 + {i}
"""
                 for i in range(count)])
            temp_file = tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py", delete=False)
            temp_file.write(content)
            temp_file.close()
            files[size_name] = Path(temp_file.name)
        return {"files": files}

    @staticmethod
    def _benchmark_size_scaling(context: dict[str, Any]) -> dict[str, Any]:
        """Benchmark size scaling."""
        results = {}
        for size_name, file_path in context["files"].items():
            times = []
            for _ in range(5):
                start = time.perf_counter()
                chunks = chunk_file(file_path, "python")
                elapsed = time.perf_counter() - start
                times.append(elapsed)
            file_size = file_path.stat().st_size
            results[size_name] = {"mean_time": statistics.mean(times),
                "file_size_kb": file_size / 1024, "chunks": len(chunks),
                "time_per_kb": statistics.mean(times) / (file_size / 1024)}
        return results

    @classmethod
    def _setup_strategy_test_files(cls) -> dict[str, Any]:
        """Setup files for strategy testing."""
        complex_code = """
# Top-level imports
import os
import sys
from typing import List, Dict, Optional

# Constants
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30

class DatabaseConnection:
    '''Main database connection class.'''

    def __init__(self, config: Dict):
        self.config = config
        self.connection = None
        self._pool = []

    def connect(self):
        '''Establish database connection.'''
        # Connection logic here
        pass

    def disconnect(self):
        '''Close database connection.'''
        # Disconnection logic
        pass

    def execute(self, query: str, params: Optional[List] = None):
        '''Execute a database query.'''
        if not self.connection:
            self.connect()

        # Query execution logic
        return []

class QueryBuilder:
    '''Build SQL queries programmatically.'''

    def __init__(self):
        self.query_parts = []

    def select(self, *columns):
        self.query_parts.append(f"SELECT {', '.join(columns)}")
        return self

    def from_table(self, table: str):
        self.query_parts.append(f"FROM {table}")
        return self

    def where(self, condition: str):
        self.query_parts.append(f"WHERE {condition}")
        return self

    def build(self) -> str:
        return ' '.join(self.query_parts)

def process_data(data: List[Dict]) -> List[Dict]:
    '''Process a list of data items.'''
    results = []

    for item in data:
        # Validate item
        if not validate_item(item):
            continue

        # Transform item
        transformed = transform_item(item)

        # Apply business rules
        if apply_rules(transformed):
            results.append(transformed)

    return results

def validate_item(item: Dict) -> bool:
    '''Validate a single item.'''
    required_fields = ['id', 'name', 'value']
    return all(field in item for field in required_fields)

def transform_item(item: Dict) -> Dict:
    '''Transform an item.'''
    return {
        'id': item['id'],
        'name': item['name'].upper(),
        'value': item['value'] * 2,
        'processed': True
    }

def apply_rules(item: Dict) -> bool:
    '''Apply business rules to an item.'''
    return item['value'] > 10

# Async functions
async def fetch_data(url: str):
    '''Fetch data from URL.'''
    # Async fetch logic
    pass

async def process_async(items: List):
    '''Process items asynchronously.'''
    # Async processing
    pass
"""
        temp_file = tempfile.NamedTemporaryFile(encoding="utf-8", mode="w",
            suffix=".py", delete=False)
        temp_file.write(complex_code)
        temp_file.close()
        return {"test_file": Path(temp_file.name)}

    @classmethod
    def _benchmark_strategies(cls, context: dict[str, Any]) -> dict[str, Any]:
        """Benchmark different strategies."""
        test_file = context["test_file"]
        results = {}
        parser = get_parser("python")
        with Path(test_file).open("rb") as f:
            source = f.read()
        tree = parser.parse(source)
        strategies = {"semantic": SemanticChunker(), "hierarchical":
            HierarchicalChunker(), "adaptive": AdaptiveChunker(),
            "composite": CompositeChunker()}
        for name, strategy in strategies.items():
            times = []
            for _ in range(5):
                start = time.perf_counter()
                chunks = strategy.chunk(tree.root_node, source, str(
                    test_file), "python")
                elapsed = time.perf_counter() - start
                times.append(elapsed)
            results[name] = {"mean_time": statistics.mean(times), "chunks":
                len(chunks), "avg_chunk_size": statistics.mean([(c.end_line -
                c.start_line) for c in chunks]) if chunks else 0}
        return results

    @classmethod
    def _setup_parallel_test_files(cls) -> dict[str, Any]:
        """Setup files for parallel processing tests."""
        temp_dir = tempfile.mkdtemp()
        files = []
        for i in range(100):
            content = f"""
def process_{i}(data):
    return data * {i}

class Handler_{i}:
    def handle(self, request):
        return {{'id': {i}, 'data': request}}
"""
            file_path = Path(temp_dir) / f"file_{i}.py"
            file_path.write_text(content)
            files.append(file_path)
        return {"directory": Path(temp_dir), "files": files}

    @staticmethod
    def _benchmark_concurrency(context: dict[str, Any]) -> dict[str, Any]:
        """Benchmark parallel processing."""
        files = context["files"]
        results = {}
        for workers in [1, 2, 4, 8, multiprocessing.cpu_count()]:
            times = []
            for _ in range(3):
                start = time.perf_counter()
                chunk_results = chunk_files_parallel(files[:50], "python",
                    num_workers=workers)
                elapsed = time.perf_counter() - start
                times.append(elapsed)
            results[f"{workers}_workers"] = {"mean_time": statistics.mean(
                times), "files_processed": len(chunk_results), "speedup":
                results.get("1_workers", {}).get("mean_time", times[0]) /
                statistics.mean(times) if workers > 1 else 1.0}
        return results

    def _setup_cache_test_files(self) -> dict[str, Any]:
        """Setup for cache testing."""
        return self._setup_strategy_test_files()

    @classmethod
    def _benchmark_cache(cls, context: dict[str, Any]) -> dict[str, Any]:
        """Benchmark cache effectiveness."""
        test_file = context["test_file"]
        cache = ASTCache()
        results = {}
        cache.invalidate_cache()
        cold_times = []
        for _ in range(5):
            cache.invalidate_cache(test_file)
            start = time.perf_counter()
            chunk_file(test_file, "python", use_cache=True)
            cold_times.append(time.perf_counter() - start)
        warm_times = []
        for _ in range(5):
            start = time.perf_counter()
            chunk_file(test_file, "python", use_cache=True)
            warm_times.append(time.perf_counter() - start)
        content = test_file.read_text()
        test_file.write_text(content + "\n# Modified")
        partial_times = []
        for _ in range(5):
            start = time.perf_counter()
            chunk_file(test_file, "python", use_cache=True)
            partial_times.append(time.perf_counter() - start)
        results["cold_cache"] = {"mean_time": statistics.mean(cold_times)}
        results["warm_cache"] = {"mean_time": statistics.mean(warm_times),
            "speedup": statistics.mean(cold_times) / statistics.mean(
            warm_times)}
        results["partial_invalidation"] = {"mean_time": statistics.mean(
            partial_times)}
        return results

    @classmethod
    def _setup_token_test_files(cls) -> dict[str, Any]:
        """Setup for token limit testing."""
        large_content = "\n".join([
            f"""
def detailed_function_{i}(parameter_one, parameter_two, parameter_three=None):
    '''
    This is a detailed docstring for function {i}.
    It contains multiple lines of documentation to increase token count.

    Args:
        parameter_one: First parameter description
        parameter_two: Second parameter description
        parameter_three: Optional third parameter

    Returns:
        A complex result based on the input parameters
    '''
    # Initialize variables
    result = {{}}
    intermediate_value = parameter_one * 2

    # Process parameter_two
    if isinstance(parameter_two, list):
        for index, item in enumerate(parameter_two):
            result[f'item_{{index}}'] = item * intermediate_value

    # Handle optional parameter
    if parameter_three is not None:
        result['optional'] = parameter_three

    return result
"""
             for i in range(50)])
        temp_file = tempfile.NamedTemporaryFile(encoding="utf-8", mode="w",
            suffix=".py", delete=False)
        temp_file.write(large_content)
        temp_file.close()
        return {"test_file": Path(temp_file.name)}

    @staticmethod
    def _benchmark_token_limits(context: dict[str, Any]) -> dict[str, Any]:
        """Benchmark token-aware chunking."""
        test_file = context["test_file"]
        results = {}
        for limit in [1000, 2000, 4000, 8000]:
            times = []
            for _ in range(5):
                start = time.perf_counter()
                chunks = chunk_file_with_token_limit(test_file, "python", limit,
                    )
                elapsed = time.perf_counter() - start
                times.append(elapsed)
            results[f"limit_{limit}"] = {"mean_time": statistics.mean(times,
                ), "chunks": len(chunks), "avg_tokens": limit}
        return results

    @classmethod
    def _setup_fallback_test_files(cls) -> dict[str, Any]:
        """Setup for fallback testing."""
        files = {}
        code_content = """
def main():
    print("Hello, World!")

class Application:
    def run(self):
        pass
"""
        code_file = tempfile.NamedTemporaryFile(encoding="utf-8", mode="w",
            suffix=".py", delete=False)
        code_file.write(code_content)
        code_file.close()
        files["code"] = Path(code_file.name)
        text_content = """
This is a plain text document.

It contains multiple paragraphs of text that should be chunked differently than code.

Each paragraph represents a logical unit of content.
"""
        text_file = tempfile.NamedTemporaryFile(encoding="utf-8", mode="w",
            suffix=".txt", delete=False)
        text_file.write(text_content)
        text_file.close()
        files["text"] = Path(text_file.name)
        mixed_content = """
# Configuration and Documentation

This file contains both code and documentation.

```python
def example():
    return 42
```

## More Documentation

Additional text content here.
"""
        mixed_file = tempfile.NamedTemporaryFile(encoding="utf-8", mode="w",
            suffix=".md", delete=False)
        mixed_file.write(mixed_content)
        mixed_file.close()
        files["mixed"] = Path(mixed_file.name)
        return {"files": files}

    @classmethod
    def _benchmark_fallback(cls, context: dict[str, Any]) -> dict[str, Any]:
        """Benchmark fallback chunking."""
        results = {}
        chunker = IntelligentFallbackChunker()
        for file_type, file_path in context["files"].items():
            times = []
            for _ in range(5):
                start = time.perf_counter()
                chunks, decision = chunker.chunk_with_fallback(file_path)
                elapsed = time.perf_counter() - start
                times.append(elapsed)
            results[file_type] = {"mean_time": statistics.mean(times),
                "chunks": len(chunks), "method_used": decision.method_used}
        return results

    def _setup_memory_test_files(self) -> dict[str, Any]:
        """Setup for memory profiling."""
        return self._setup_size_scaling_files()

    @staticmethod
    def _benchmark_memory(context: dict[str, Any]) -> dict[str, Any]:
        """Benchmark memory usage."""
        try:
            import tracemalloc

            import psutil
        except ImportError:
            return {"error": "psutil or tracemalloc not available"}
        results = {}
        process = psutil.Process(os.getpid())
        for size_name, file_path in context["files"].items():
            gc_collect()
            baseline_memory = process.memory_info().rss
            tracemalloc.start()
            chunks = chunk_file(file_path, "python")
            _current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            final_memory = process.memory_info().rss
            results[size_name] = {"baseline_mb": baseline_memory / 1024 /
                1024, "final_mb": final_memory / 1024 / 1024, "peak_mb":
                peak / 1024 / 1024, "chunks": len(chunks),
                "memory_per_chunk": (final_memory - baseline_memory) / len(
                chunks) if chunks else 0}
        return results

    @classmethod
    def _setup_repo_structure(cls) -> dict[str, Any]:
        """Setup a realistic repository structure."""
        temp_dir = Path(tempfile.mkdtemp())
        (temp_dir / "src").mkdir()
        (temp_dir / "tests").mkdir()
        (temp_dir / "docs").mkdir()
        files = []
        for i in range(10):
            content = f"""
from .base import BaseClass

class Module{i}(BaseClass):
    def process(self, data):
        return self.transform(data)

    def transform(self, data):
        return [x * {i} for x in data]
"""
            file_path = temp_dir / "src" / f"module_{i}.py"
            file_path.write_text(content)
            files.append(file_path)
        for i in range(5):
            content = f"""
import pytest
from src.module_{i} import Module{i}

def test_module_{i}():
    module = Module{i}()
    result = module.process([1, 2, 3])
    assert result == [{i}, {i * 2}, {i * 3}]
"""
            file_path = temp_dir / "tests" / f"test_module_{i}.py"
            file_path.write_text(content)
            files.append(file_path)
        readme = temp_dir / "README.md"
        readme.write_text(
            """
# Test Repository

This is a test repository for benchmarking.

## Features
- Multiple modules
- Comprehensive tests
- Documentation
""",
            )
        return {"directory": temp_dir, "files": files}

    @staticmethod
    def _benchmark_repository(context: dict[str, Any]) -> dict[str, Any]:
        """Benchmark repository processing."""
        directory = context["directory"]
        results = {}
        start = time.perf_counter()
        sequential_chunks = {}
        for file_path in directory.rglob("*.py"):
            sequential_chunks[str(file_path)] = chunk_file(file_path, "python")
        sequential_time = time.perf_counter() - start
        start = time.perf_counter()
        parallel_chunks = chunk_directory_parallel(directory, "python")
        parallel_time = time.perf_counter() - start
        results["sequential"] = {"time": sequential_time, "files": len(
            sequential_chunks), "total_chunks": sum(len(chunks) for chunks in
            sequential_chunks.values())}
        results["parallel"] = {"time": parallel_time, "files": len(
            parallel_chunks), "total_chunks": sum(len(chunks) for chunks in
            parallel_chunks.values()), "speedup": sequential_time /
            parallel_time if parallel_time > 0 else 0}
        return results

    def _setup_export_test_files(self) -> dict[str, Any]:
        """Setup for export format testing."""
        return self._setup_strategy_test_files()

    def _benchmark_exports(self, context: dict[str, Any]) -> dict[str, Any]:
        """Benchmark export formats."""
        test_file = context["test_file"]
        chunks = chunk_file(test_file, "python")
        results = {}
        try:
            from chunker.export import (
                CSVExporter,
                JSONExporter,
                JSONLExporter,
                ParquetExporter,
            )
            exporters = {"json": JSONExporter(), "jsonl": JSONLExporter(),
                "parquet": ParquetExporter(), "csv": CSVExporter()}
            for format_name, exporter in exporters.items():
                output_file = self.output_dir / f"export_test.{format_name}"
                times = []
                for _ in range(5):
                    start = time.perf_counter()
                    exporter.export(chunks, output_file)
                    elapsed = time.perf_counter() - start
                    times.append(elapsed)
                file_size = output_file.stat().st_size if output_file.exists(
                    ) else 0
                results[format_name] = {"mean_time": statistics.mean(times),
                    "file_size_kb": file_size / 1024, "chunks_exported":
                    len(chunks)}
                if output_file.exists():
                    output_file.unlink()
        except ImportError:
            results["error"] = "Export modules not available"
        return results

    def run_all(self) -> dict[str, Any]:
        """Run all benchmark scenarios."""
        results = {}
        for scenario in self.scenarios:
            print(f"\nRunning benchmark: {scenario.name}")
            print(f"Description: {scenario.description}")
            context = scenario.setup()
            if scenario.warmup > 0:
                print(f"  Warming up ({scenario.warmup} iterations)...")
                for _ in range(scenario.warmup):
                    scenario.benchmark(context)
            print(f"  Benchmarking ({scenario.iterations} iterations)...")
            result = scenario.benchmark(context)
            if scenario.teardown:
                scenario.teardown(context)
            else:
                for value in context.values():
                    if isinstance(value, Path) and value.exists():
                        if value.is_file():
                            value.unlink()
                        elif value.is_dir():
                            shutil.rmtree(value)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, Path) and item.exists():
                                item.unlink()
                    elif isinstance(value, dict):
                        for v in value.values():
                            if isinstance(v, Path) and v.exists():
                                v.unlink()
            results[scenario.name] = {"description": scenario.description,
                "metadata": scenario.metadata, "results": result}
            print(f"  Completed: {scenario.name}")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"benchmark_results_{timestamp}.json"
        with Path(output_file).open("w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nResults saved to: {output_file}")
        return results

    @staticmethod
    def generate_report(results: dict[str, Any]) -> str:
        """Generate a human-readable report from results."""
        lines = ["Comprehensive Benchmark Report", "=" * 50,
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
        for scenario_name, scenario_data in results.items():
            lines.append(f"\n{scenario_name}")
            lines.append("-" * len(scenario_name))
            lines.append(scenario_data["description"])
            lines.append("")
            if scenario_name == "language_comparison":
                for lang, stats in scenario_data["results"].items():
                    lines.append(
                        f"  {lang}: {stats['mean_time'] * 1000:.2f}ms ({stats['total_chunks']} chunks)",
                        )
            elif scenario_name == "file_size_scaling":
                for size, stats in scenario_data["results"].items():
                    lines.append(
                        f"  {size}: {stats['mean_time'] * 1000:.2f}ms ({stats['file_size_kb']:.1f}KB, {stats['time_per_kb'] * 1000:.2f}ms/KB)",
                        )
            elif scenario_name == "strategy_comparison":
                for strategy, stats in scenario_data["results"].items():
                    lines.append(
                        f"  {strategy}: {stats['mean_time'] * 1000:.2f}ms ({stats['chunks']} chunks, avg size: {stats['avg_chunk_size']:.1f} lines)",
                        )
            elif scenario_name == "concurrency_scaling":
                for workers, stats in scenario_data["results"].items():
                    lines.append(
                        f"  {workers}: {stats['mean_time'] * 1000:.2f}ms (speedup: {stats.get('speedup', 1.0):.2f}x)",
                        )
            else:
                for key, value in scenario_data["results"].items():
                    if isinstance(value, dict):
                        lines.append(f"  {key}:")
                        for k, v in value.items():
                            if isinstance(v, float):
                                lines.append(f"    {k}: {v:.3f}")
                            else:
                                lines.append(f"    {k}: {v}")
                    else:
                        lines.append(f"  {key}: {value}")
        return "\n".join(lines)


def gc_collect():
    """Force garbage collection."""
    gc.collect()


if __name__ == "__main__":
    suite = ComprehensiveBenchmarkSuite()
    results = suite.run_all()
    report = suite.generate_report(results)
    print("\n" + "=" * 50)
    print(report)
    report_file = (suite.output_dir /
        f"benchmark_report_{time.strftime('%Y%m%d_%H%M%S')}.txt")
    report_file.write_text(report)
    print(f"\nReport saved to: {report_file}")

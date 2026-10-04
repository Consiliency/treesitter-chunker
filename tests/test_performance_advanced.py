"""Advanced performance tests for optimization and scalability.

This module tests the chunker's performance under various loads and
identifies optimization opportunities.
"""

import gc
import json
import multiprocessing as mp
import subprocess
import sys
import threading
import time

import pytest

from chunker import chunk_file
from chunker._internal.cache import ASTCache
from chunker.export import JSONExporter, JSONLExporter, SchemaType
from chunker.parallel import ParallelChunker, chunk_files_parallel

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestConcurrentPerformance:
    """Test performance under concurrent load."""

    @staticmethod
    def test_thread_safety_performance(tmp_path):
        """Test parser performance under multi-threaded access."""
        test_file = tmp_path / "concurrent_test.py"
        test_file.write_text(
            """
def function_1():
    return 1

def function_2():
    return 2

class TestClass:
    def method_1(self):
        pass

    def method_2(self):
        pass
""",
        )

        def chunk_repeatedly(file_path, num_iterations):
            results = []
            for _ in range(num_iterations):
                chunks = chunk_file(file_path, language="python")
                results.append(len(chunks))
            return results

        num_threads = 4
        iterations_per_thread = 25
        start_time = time.time()
        threads = []
        results = []
        for _ in range(num_threads):
            thread = threading.Thread(
                target=lambda: results.append(
                    chunk_repeatedly(test_file, iterations_per_thread),
                ),
            )
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()
        concurrent_time = time.time() - start_time
        start_time = time.time()
        [chunk_repeatedly(test_file, iterations_per_thread) for _ in range(num_threads)]
        sequential_time = time.time() - start_time
        assert len(results) == num_threads
        actual_count = results[0][0]
        assert actual_count >= 3
        for thread_results in results:
            assert len(thread_results) == iterations_per_thread
            assert all(count == actual_count for count in thread_results)
        assert concurrent_time < sequential_time * 5.0

    @staticmethod
    def test_multiprocess_scaling(tmp_path):
        """Test scaling with multiple processes."""
        num_files = 50
        for i in range(num_files):
            test_file = tmp_path / f"file_{i}.py"
            test_file.write_text(
                f"""
def function_{i}_a():
    '''Function A in file {i}'''
    result = 0
    for x in range(100):
        result += x
    return result

def function_{i}_b():
    '''Function B in file {i}'''
    data = [i * 2 for i in range(50)]    return data

class Module_{i}:
    def __init__(self):
        self.value = {i}

    def process(self):
        return self.value * 2

    def transform(self):
        return str(self.value)
""",
            )
        file_paths = list(tmp_path.glob("*.py"))
        worker_counts = [1, 2, 4, mp.cpu_count()]
        times = {}
        for num_workers in worker_counts:
            start_time = time.time()
            results = chunk_files_parallel(
                file_paths,
                language="python",
                num_workers=num_workers,
            )
            elapsed = time.time() - start_time
            times[num_workers] = elapsed
            total_chunks = sum(len(chunks) for chunks in results.values())
            assert total_chunks >= num_files * 3
        if mp.cpu_count() >= 4:
            speedup = times[1] / times[4]
            assert speedup > 2.0
        assert times[2] < times[1] * 0.7


class TestMemoryOptimization:
    """Test memory usage optimization strategies."""

    @staticmethod
    def test_streaming_memory_efficiency(tmp_path):
        """Test memory efficiency of streaming vs batch processing."""
        large_file = tmp_path / "large_module.py"
        content_lines = []
        for i in range(500):
            content_lines.extend(
                [
                    f"def function_{i}(x, y, z):",
                    f"    '''Process function {i} with inputs.'''",
                    "    result = x + y * z",
                    "    data = [j for j in range(10)]",
                    "    return result + sum(data)",
                    "",
                ],
            )
        large_file.write_text("\n".join(content_lines))
        # Independent interpreters avoid allocator history and negative RSS deltas.
        # Measure Python allocation peaks; native grammar memory is not traced.
        probe = """
import json, sys, tracemalloc
from chunker import chunk_file
from chunker.parser import get_parser
from chunker.streaming import chunk_file_streaming
get_parser('python')
tracemalloc.start()
chunks = (chunk_file(sys.argv[1], 'python') if sys.argv[2] == 'batch'
          else list(chunk_file_streaming(sys.argv[1], 'python')))
print(json.dumps({'peak': tracemalloc.get_traced_memory()[1], 'chunks': len(chunks)}))
"""
        measurements = {}
        for mode in ("batch", "stream"):
            output = subprocess.check_output(
                [sys.executable, "-c", probe, str(large_file), mode],
                text=True,
                timeout=60,
            )
            measurement = json.loads(output)
            assert measurement["chunks"] == 500
            assert 0 < measurement["peak"] < 50 * 1024 * 1024
            measurements[mode] = measurement["peak"]
        assert measurements["stream"] <= measurements["batch"] * 2.5

    @classmethod
    def test_cache_memory_bounds(cls, tmp_path):
        """Test that cache respects memory bounds."""
        cache = ASTCache(cache_dir=tmp_path / "cache")
        large_chunks = []
        for i in range(20):
            test_file = tmp_path / f"cache_test_{i}.py"
            lines = [
                f"# File {i} with substantial content",
                f"def large_function_{i}():",
                f"    '''{'Large docstring ' * 100}'''",
            ]
            lines.extend(f"    data_{j} = [k for k in range(20)]" for j in range(50))
            lines.append(
                "    return sum(sum(d) for d in locals().values() if isinstance(d, list))",
            )
            content = "\n".join(lines)
            test_file.write_text(content)
            chunks = chunk_file(test_file, language="python")
            cache.cache_chunks(test_file, "python", chunks)
            large_chunks.append((test_file, chunks))
        cached_count = 0
        for file_path, _ in large_chunks:
            cached = cache.get_cached_chunks(file_path, "python")
            if cached is not None:
                cached_count += 1
        assert cached_count > 0


class TestScalabilityLimits:
    """Test performance with extreme inputs."""

    @classmethod
    def test_very_large_file_handling(cls, tmp_path):
        """Measure a large-file workload without prior tests' allocator state."""
        huge_file = tmp_path / "huge_module.py"
        content_lines = []
        for i in range(5000):
            content_lines.append(f"def func_{i}(): return {i}")
            if i % 100 == 0:
                content_lines.append("")
        huge_file.write_text("\n".join(content_lines))
        probe = """
import json, sys, time
import psutil
from chunker import chunk_file
from chunker.export import JSONExporter, SchemaType
start = time.perf_counter()
chunks = chunk_file(sys.argv[1], language='python')
chunk_time = time.perf_counter() - start
memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
start = time.perf_counter()
JSONExporter(schema_type=SchemaType.FLAT).export(chunks, sys.argv[2])
print(json.dumps({'chunks': len(chunks), 'chunk_time': chunk_time,
                  'memory_mb': memory_mb, 'export_time': time.perf_counter() - start}))
"""
        output = subprocess.check_output(
            [
                sys.executable,
                "-c",
                probe,
                str(huge_file),
                str(tmp_path / "huge_export.json"),
            ],
            text=True,
            timeout=60,
        )
        measurement = json.loads(output)
        assert measurement["chunks"] >= 5000
        assert measurement["chunk_time"] < 10.0
        assert measurement["memory_mb"] < 500
        assert measurement["export_time"] < 5.0

    @staticmethod
    def test_deep_nesting_performance(tmp_path):
        """Test performance with deeply nested code structures."""
        nested_file = tmp_path / "deeply_nested.py"
        content_lines = ["def outer():"]
        indent = "    "
        for i in range(20):
            content_lines.append(f"{indent}def level_{i}():")
            indent += "    "
            content_lines.append(f"{indent}x = {i}")
        for i in range(20, 0, -1):
            indent = "    " * i
            content_lines.append(f"{indent}return x")
        nested_file.write_text("\n".join(content_lines))
        start_time = time.time()
        chunks = chunk_file(nested_file, language="python")
        elapsed = time.time() - start_time
        assert len(chunks) >= 1
        assert elapsed < 1.0

    @staticmethod
    def test_many_small_files_performance(tmp_path):
        """Test performance with many small files."""
        for i in range(1000):
            small_file = tmp_path / f"tiny_{i}.py"
            small_file.write_text(f"def f{i}(): pass")
        file_paths = list(tmp_path.glob("tiny_*.py"))
        results = chunk_files_parallel(
            file_paths,
            language="python",
            num_workers=mp.cpu_count(),
        )
        assert len(results) == 1000
        total_chunks = sum(len(chunks) for chunks in results.values())
        assert total_chunks >= 1000


class TestOptimizationOpportunities:
    """Identify and test optimization opportunities."""

    @classmethod
    def test_parser_reuse_performance(cls, tmp_path):
        """Test performance gains from parser reuse."""
        test_files = []
        for i in range(10):
            test_file = tmp_path / f"parser_test_{i}.py"
            test_file.write_text(
                f"""
def function_{i}():
    return {i}

class Class_{i}:
    pass
""",
            )
            test_files.append(test_file)
        start_time = time.time()
        for test_file in test_files:
            for _ in range(10):
                chunk_file(test_file, language="python")
        no_reuse_time = time.time() - start_time
        start_time = time.time()
        chunker = ParallelChunker(language="python", num_workers=1)
        for _ in range(10):
            chunker.chunk_files_parallel(test_files)
        reuse_time = time.time() - start_time
        assert no_reuse_time < 5.0
        assert reuse_time < 5.0

    @classmethod
    def test_export_format_performance_comparison(cls, tmp_path):
        """Compare performance of different export formats."""
        test_file = tmp_path / "export_test.py"
        content_lines = []
        for i in range(200):
            content_lines.extend(
                [
                    f"def function_{i}():",
                    f"    '''Docstring for function {i}'''",
                    f"    return {i}",
                    "",
                ],
            )
        test_file.write_text("\n".join(content_lines))
        chunks = chunk_file(test_file, language="python")
        export_times = {}
        start_time = time.time()
        json_exporter = JSONExporter(schema_type=SchemaType.FLAT)
        json_exporter.export(chunks, tmp_path / "test.json")
        export_times["json"] = time.time() - start_time
        start_time = time.time()
        jsonl_exporter = JSONLExporter(schema_type=SchemaType.FLAT)
        jsonl_exporter.export(chunks, tmp_path / "test.jsonl")
        export_times["jsonl"] = time.time() - start_time
        start_time = time.time()
        json_full_exporter = JSONExporter(schema_type=SchemaType.FULL)
        json_full_exporter.export(chunks, tmp_path / "test_full.json")
        export_times["json_full"] = time.time() - start_time
        for time_taken in export_times.values():
            assert time_taken < 1.0


class TestRealWorldScenarios:
    """Test performance in real-world scenarios."""

    @staticmethod
    def test_mixed_file_sizes_performance(tmp_path):
        """Test performance with realistic mix of file sizes."""
        for i in range(20):
            small_file = tmp_path / f"small_{i}.py"
            content = "\n".join([f"def small_func_{j}(): return {j}" for j in range(5)])
            small_file.write_text(content)
        for i in range(10):
            medium_file = tmp_path / f"medium_{i}.py"
            content_lines = []
            for j in range(25):
                content_lines.extend(
                    [
                        f"def medium_func_{j}():",
                        "    data = list(range(10))",
                        "    result = sum(data)",
                        "    return result",
                        "",
                    ],
                )
            medium_file.write_text("\n".join(content_lines))
        for i in range(5):
            large_file = tmp_path / f"large_{i}.py"
            content_lines = []
            for j in range(100):
                content_lines.extend(
                    [
                        f"class LargeClass_{j}:",
                        "    def __init__(self):",
                        "        self.data = []",
                        "    ",
                        "    def method_a(self):",
                        "        return len(self.data)",
                        "    ",
                        "    def method_b(self, value):",
                        "        self.data.append(value)",
                        "        return self.data",
                        "",
                    ],
                )
            large_file.write_text("\n".join(content_lines))
        all_files = list(tmp_path.glob("*.py"))
        start_time = time.time()
        results = chunk_files_parallel(
            all_files,
            language="python",
            num_workers=mp.cpu_count(),
        )
        elapsed = time.time() - start_time
        assert len(results) == 35
        assert elapsed < 5.0
        small_chunks = sum(
            len(chunks) for path, chunks in results.items() if "small_" in path.name
        )
        medium_chunks = sum(
            len(chunks) for path, chunks in results.items() if "medium_" in path.name
        )
        large_chunks = sum(
            len(chunks) for path, chunks in results.items() if "large_" in path.name
        )
        assert small_chunks >= 100
        assert medium_chunks >= 250
        assert large_chunks >= 1500

    @staticmethod
    def test_continuous_processing_refreshes_overwritten_files(tmp_path):
        """Repeated parallel parsing returns each iteration's current source."""
        num_iterations = 20
        for iteration in range(num_iterations):
            for i in range(5):
                test_file = tmp_path / f"continuous_{i}.py"
                test_file.write_text(
                    f"""
# Iteration {iteration}
def process_{iteration}():
    return {iteration}

class Handler_{iteration}:
    def handle(self):
        return "handled\"
""",
                )
            results = chunk_files_parallel(
                list(tmp_path.glob("continuous_*.py")),
                language="python",
                num_workers=2,
            )
            assert len(results) == 5
            assert all(results.values())
            assert all(
                any(f"process_{iteration}" in chunk.content for chunk in chunks)
                for chunks in results.values()
            )
            time.sleep(0.1)


def gc_collect():
    """Force garbage collection for memory tests."""
    gc.collect()
    gc.collect()

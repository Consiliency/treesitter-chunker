"""Integration tests for Parquet export with CLI options."""

import pytest
import subprocess
import sys
import time
import psutil
import os
import json
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, patch, MagicMock
import pyarrow.parquet as pq
import pyarrow as pa
from concurrent.futures import ThreadPoolExecutor, as_completed

from tests.integration.fixtures import (
    temp_workspace, test_file_generator, sample_code_files,
    performance_monitor, thread_safe_counter
)

# Try to import CLI runner
try:
    from click.testing import CliRunner
    from cli.main import cli
except ImportError:
    CliRunner = MagicMock()
    cli = MagicMock()


class MockCLIRunner:
    """Mock CLI runner for testing command-line interface."""
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.process = None
        
    def invoke(self, args: List[str], capture_output: bool = True) -> 'CLIResult':
        """Run CLI command and return result."""
        # Construct full command
        # Use the worktree root as the working directory
        worktree_root = Path(__file__).parent.parent
        cmd = [sys.executable, "-m", "cli.main"] + args
        
        # Run command from worktree root so cli module can be found
        result = subprocess.run(
            cmd,
            cwd=str(worktree_root),
            capture_output=capture_output,
            text=True
        )
        
        return CLIResult(
            exit_code=result.returncode,
            output=result.stdout,
            error=result.stderr,
            exception=None
        )
    
    def invoke_async(self, args: List[str]) -> subprocess.Popen:
        """Run CLI command asynchronously."""
        worktree_root = Path(__file__).parent.parent
        cmd = [sys.executable, "-m", "cli.main"] + args
        
        self.process = subprocess.Popen(
            cmd,
            cwd=str(worktree_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        return self.process


class CLIResult:
    """Result from CLI invocation."""
    
    def __init__(self, exit_code: int, output: str, error: str, exception: Optional[Exception]):
        self.exit_code = exit_code
        self.output = output
        self.error = error
        self.exception = exception
        
    @property
    def stdout(self):
        return self.output


@pytest.mark.skip(reason="Parquet export CLI functionality not yet implemented")
class TestParquetCLIIntegration:
    """Test Parquet export with various CLI options."""
    
    def test_parquet_with_include_exclude_filters(self, temp_workspace, 
                                                 test_file_generator,
                                                 sample_code_files):
        """Test Parquet export with include/exclude filters."""
        # Create test file structure
        src_dir = temp_workspace / "src"
        src_dir.mkdir(exist_ok=True)
        test_dir = temp_workspace / "tests"
        test_dir.mkdir(exist_ok=True)
        
        # Create various files
        test_files = {
            "src/main.py": sample_code_files["example.py"],
            "src/utils.py": "def helper(): return 42",
            "src/test_main.py": "def test_main(): assert True",
            "tests/test_utils.py": "def test_helper(): assert True",
            "src/data.json": '{"key": "value"}',
            "src/script.js": sample_code_files["example.js"],
        }
        
        for path, content in test_files.items():
            file_path = temp_workspace / path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
        
        # Output file
        output_file = temp_workspace / "output" / "filtered.parquet"
        output_file.parent.mkdir(exist_ok=True)
        
        # Run CLI with filters
        runner = MockCLIRunner(temp_workspace)
        
        # Test 1: Include only Python files, exclude test files
        result = runner.invoke([
            "chunk",
            str(src_dir),
            "--output", str(output_file),
            "--format", "parquet",
            "--include", "*.py",
            "--exclude", "*test*"
        ])
        
        # Check command succeeded
        assert result.exit_code == 0, f"Command failed: {result.error}"
        
        # Verify Parquet file created
        assert output_file.exists()
        
        # Read and verify Parquet content
        table = pq.read_table(output_file)
        df = table.to_pandas()
        
        # Check only non-test Python files included
        file_paths = df['file_path'].unique()
        assert len(file_paths) == 2  # main.py and utils.py
        assert any("main.py" in path for path in file_paths)
        assert any("utils.py" in path for path in file_paths)
        assert not any("test" in path for path in file_paths)
        
        # Verify schema includes file metadata
        schema = table.schema
        expected_columns = ['file_path', 'language', 'chunk_type', 'name', 
                          'start_line', 'end_line', 'content']
        for col in expected_columns:
            assert col in schema.names, f"Missing column: {col}"
        
        # Test 2: Multiple patterns
        output_file2 = temp_workspace / "output" / "multi_pattern.parquet"
        
        result = runner.invoke([
            "chunk",
            str(temp_workspace),
            "--output", str(output_file2),
            "--format", "parquet",
            "--include", "*.py",
            "--include", "*.js",
            "--exclude", "tests/*"
        ])
        
        assert result.exit_code == 0
        
        # Verify both Python and JS files included
        table2 = pq.read_table(output_file2)
        df2 = table2.to_pandas()
        
        languages = df2['language'].unique()
        assert 'python' in languages
        assert 'javascript' in languages
        
        # Test 3: Complex patterns
        output_file3 = temp_workspace / "output" / "complex_pattern.parquet"
        
        result = runner.invoke([
            "chunk",
            str(temp_workspace),
            "--output", str(output_file3),
            "--format", "parquet",
            "--include", "src/**/*.py",  # Recursive pattern
            "--exclude", "**/*test*"
        ])
        
        assert result.exit_code == 0
        
        # Verify recursive pattern worked
        table3 = pq.read_table(output_file3)
        df3 = table3.to_pandas()
        
        # Should include src files but not test files
        for path in df3['file_path'].unique():
            assert "src" in path
            assert "test" not in path.lower()
    
    def test_parquet_with_chunk_type_filtering(self, temp_workspace,
                                              test_file_generator):
        """Test filtering specific chunk types."""
        # Create test file with various chunk types
        test_content = """
# Module comment

def simple_function():
    '''A simple function'''
    return 42

class MyClass:
    '''A test class'''
    
    def method(self):
        '''Instance method'''
        return self
    
    @classmethod
    def class_method(cls):
        '''Class method'''
        return cls
    
    @staticmethod
    def static_method():
        '''Static method'''
        return True

async def async_function():
    '''Async function'''
    await something()
    
def nested_function():
    '''Function with nested function'''
    def inner():
        return 1
    return inner()

# Global variable
CONSTANT = 100
"""
        
        test_file = test_file_generator.create_file("chunk_types.py", test_content)
        output_file = temp_workspace / "output" / "filtered_chunks.parquet"
        
        # Test 1: Filter only functions and classes
        runner = MockCLIRunner(temp_workspace)
        result = runner.invoke([
            "chunk",
            str(test_file),
            "--output", str(output_file),
            "--format", "parquet",
            "--chunk-types", "function,class"
        ])
        
        assert result.exit_code == 0, f"Command failed: {result.error}"
        
        # Read and verify chunks
        table = pq.read_table(output_file)
        df = table.to_pandas()
        
        # Check chunk types
        chunk_types = df['chunk_type'].unique()
        assert 'function' in chunk_types or 'function_definition' in chunk_types
        assert 'class' in chunk_types or 'class_definition' in chunk_types
        
        # Verify specific functions found
        function_names = df[df['chunk_type'].str.contains('function', case=False)]['name'].tolist()
        assert 'simple_function' in function_names
        assert 'async_function' in function_names
        assert 'nested_function' in function_names
        
        # Test 2: Filter only classes
        output_file2 = temp_workspace / "output" / "classes_only.parquet"
        result = runner.invoke([
            "chunk",
            str(test_file),
            "--output", str(output_file2),
            "--format", "parquet",
            "--chunk-types", "class"
        ])
        
        assert result.exit_code == 0
        
        table2 = pq.read_table(output_file2)
        df2 = table2.to_pandas()
        
        # Should only have class chunks
        assert len(df2) > 0
        assert all('class' in ct.lower() for ct in df2['chunk_type'].unique())
        
        # Test 3: Multiple languages with chunk filtering
        js_content = """
function regularFunction() {
    return 42;
}

const arrowFunction = () => {
    return 'arrow';
};

class JavaScriptClass {
    constructor() {
        this.value = 1;
    }
    
    method() {
        return this.value;
    }
}

const objectLiteral = {
    method: function() {
        return 'object method';
    }
};
"""
        
        js_file = test_file_generator.create_file("chunk_types.js", js_content)
        
        output_file3 = temp_workspace / "output" / "multi_lang_chunks.parquet"
        result = runner.invoke([
            "chunk",
            str(temp_workspace),
            "--output", str(output_file3),
            "--format", "parquet",
            "--chunk-types", "function,class",
            "--include", "*.py",
            "--include", "*.js"
        ])
        
        assert result.exit_code == 0
        
        table3 = pq.read_table(output_file3)
        df3 = table3.to_pandas()
        
        # Verify both languages present
        languages = df3['language'].unique()
        assert 'python' in languages
        assert 'javascript' in languages
        
        # Verify schema consistency across languages
        for lang in languages:
            lang_df = df3[df3['language'] == lang]
            assert len(lang_df) > 0
            # All rows should have the same columns filled
            assert not lang_df.isnull().all().any()
    
    def test_parquet_with_parallel_processing(self, temp_workspace, 
                                            test_file_generator,
                                            performance_monitor):
        """Test Parquet export with parallel processing."""
        # Create multiple test files
        test_files = []
        for i in range(20):
            content = f"""
def function_{i}_1():
    '''Function {i}-1'''
    return {i * 10}

def function_{i}_2():
    '''Function {i}-2'''
    return {i * 20}

class Class_{i}:
    '''Class {i}'''
    def method(self):
        return {i}
"""
            file = test_file_generator.create_file(f"parallel_test_{i}.py", content)
            test_files.append(file)
        
        output_file = temp_workspace / "output" / "parallel.parquet"
        
        # Test with parallel processing
        runner = MockCLIRunner(temp_workspace)
        
        with performance_monitor.measure("parallel_export"):
            result = runner.invoke([
                "chunk",
                str(temp_workspace),
                "--output", str(output_file),
                "--format", "parquet",
                "-j", "4",  # 4 parallel workers
                "--include", "*.py"
            ])
        
        assert result.exit_code == 0, f"Command failed: {result.error}"
        
        # Verify Parquet file integrity
        table = pq.read_table(output_file)
        df = table.to_pandas()
        
        # Check all files processed
        assert len(df) > 0
        file_count = df['file_path'].nunique()
        assert file_count == 20  # All files should be processed
        
        # Verify no data corruption
        # Check each file's chunks are complete
        for i in range(20):
            file_chunks = df[df['file_path'].str.contains(f'parallel_test_{i}.py')]
            
            # Should have functions and class from each file
            chunk_names = file_chunks['name'].tolist()
            assert f'function_{i}_1' in chunk_names
            assert f'function_{i}_2' in chunk_names
            assert f'Class_{i}' in chunk_names
        
        # Test thread safety by checking for duplicate entries
        # Group by all identifying columns
        duplicates = df.duplicated(subset=['file_path', 'chunk_type', 'name', 'start_line'])
        assert not duplicates.any(), "Found duplicate chunks - thread safety issue"
        
        # Verify ordering is maintained within files
        for file_path in df['file_path'].unique():
            file_df = df[df['file_path'] == file_path].sort_values('start_line')
            
            # Check start lines are in ascending order
            start_lines = file_df['start_line'].tolist()
            assert start_lines == sorted(start_lines), f"Chunks out of order in {file_path}"
        
        # Test with different worker counts
        stats = {}
        for workers in [1, 2, 4, 8]:
            output = temp_workspace / "output" / f"parallel_{workers}.parquet"
            
            with performance_monitor.measure(f"export_j{workers}"):
                result = runner.invoke([
                    "chunk",
                    str(temp_workspace),
                    "--output", str(output),
                    "--format", "parquet",
                    "-j", str(workers),
                    "--include", "*.py"
                ])
            
            assert result.exit_code == 0
            
            # Verify same content regardless of worker count
            table_w = pq.read_table(output)
            df_w = table_w.to_pandas()
            assert len(df_w) == len(df), f"Different chunk count with {workers} workers"
        
        # Check performance scaling
        perf_stats = {
            w: performance_monitor.get_stats(f"export_j{w}")["average"]
            for w in [1, 2, 4, 8]
        }
        
        # Parallel should be faster than serial (with some overhead tolerance)
        assert perf_stats[4] < perf_stats[1] * 0.8, "Parallel processing not improving performance"
    
    def test_large_file_streaming_to_parquet(self, test_file_generator,
                                            temp_workspace,
                                            performance_monitor):
        """Test streaming large file to Parquet."""
        # Create a large file (100MB+)
        large_content = []
        
        # Generate ~100MB of Python code
        functions_per_mb = 250  # Approximate
        total_functions = functions_per_mb * 100
        
        for i in range(total_functions):
            large_content.append(f"""
def function_{i}(param1, param2, param3):
    '''
    This is function {i} with a longer docstring to increase file size.
    It performs various calculations and returns results.
    Additional lines to increase size...
    '''
    result = param1 + param2 * param3
    intermediate = result ** 2
    final = intermediate / (param1 + 1)
    
    # Some additional logic
    if final > 1000:
        return final * 0.9
    else:
        return final * 1.1
""")
            
            if i % 1000 == 0:
                # Add a class every 1000 functions
                large_content.append(f"""
class LargeClass_{i}:
    '''A class in the large file'''
    
    def __init__(self):
        self.data = list(range(1000))
    
    def process(self):
        return sum(self.data)
""")
        
        # Write large file
        large_file = test_file_generator.create_file(
            "large_file.py",
            "\n".join(large_content)
        )
        
        # Check file size
        file_size_mb = large_file.stat().st_size / (1024 * 1024)
        assert file_size_mb > 100, f"File too small: {file_size_mb:.1f}MB"
        
        output_file = temp_workspace / "output" / "large_streaming.parquet"
        
        # Monitor memory during export
        memory_samples = []
        monitoring = threading.Event()
        
        def monitor_memory():
            process = psutil.Process()
            while not monitoring.is_set():
                memory_mb = process.memory_info().rss / (1024 * 1024)
                memory_samples.append(memory_mb)
                time.sleep(0.1)
        
        # Start memory monitoring
        monitor_thread = threading.Thread(target=monitor_memory)
        monitor_thread.start()
        
        # Run export with streaming
        runner = MockCLIRunner(temp_workspace)
        
        with performance_monitor.measure("large_file_export"):
            result = runner.invoke([
                "chunk",
                str(large_file),
                "--output", str(output_file),
                "--format", "parquet",
                "--streaming",  # Enable streaming mode
                "--batch-size", "1000"  # Process in batches
            ])
        
        # Stop monitoring
        monitoring.set()
        monitor_thread.join()
        
        assert result.exit_code == 0, f"Command failed: {result.error}"
        
        # Verify complete export
        table = pq.read_table(output_file)
        df = table.to_pandas()
        
        # Check we got all functions
        function_chunks = df[df['chunk_type'].str.contains('function', case=False)]
        assert len(function_chunks) >= total_functions * 0.95  # Allow small margin
        
        # Verify memory usage stayed reasonable
        if memory_samples:
            peak_memory = max(memory_samples)
            avg_memory = sum(memory_samples) / len(memory_samples)
            
            # Peak memory should be much less than file size (streaming benefit)
            assert peak_memory < file_size_mb * 2, \
                f"Memory usage too high: {peak_memory:.1f}MB for {file_size_mb:.1f}MB file"
            
            # Average memory should be even lower
            assert avg_memory < file_size_mb, \
                f"Average memory too high: {avg_memory:.1f}MB"
        
        # Test streaming with different batch sizes
        batch_sizes = [100, 500, 2000]
        for batch_size in batch_sizes:
            output = temp_workspace / "output" / f"batch_{batch_size}.parquet"
            
            result = runner.invoke([
                "chunk",
                str(large_file),
                "--output", str(output),
                "--format", "parquet",
                "--streaming",
                "--batch-size", str(batch_size)
            ])
            
            assert result.exit_code == 0
            
            # Verify same content
            table_batch = pq.read_table(output)
            df_batch = table_batch.to_pandas()
            assert len(df_batch) == len(df), f"Different results with batch size {batch_size}"
    
    def test_schema_evolution_across_languages(self, temp_workspace,
                                             test_file_generator,
                                             sample_code_files):
        """Test Parquet schema handles multiple languages."""
        # Create files in different languages
        test_files = {
            "example.py": sample_code_files["example.py"],
            "example.js": sample_code_files["example.js"],
            "example.rs": sample_code_files["example.rs"],
            "example.c": """
#include <stdio.h>

int add(int a, int b) {
    return a + b;
}

struct Point {
    int x;
    int y;
};

void print_point(struct Point p) {
    printf("(%d, %d)", p.x, p.y);
}
"""
        }
        
        for filename, content in test_files.items():
            test_file_generator.create_file(filename, content)
        
        output_file = temp_workspace / "output" / "multi_language.parquet"
        
        # Export all languages to single Parquet file
        runner = MockCLIRunner(temp_workspace)
        result = runner.invoke([
            "chunk",
            str(temp_workspace),
            "--output", str(output_file),
            "--format", "parquet"
        ])
        
        assert result.exit_code == 0, f"Command failed: {result.error}"
        
        # Read and analyze schema
        table = pq.read_table(output_file)
        schema = table.schema
        df = table.to_pandas()
        
        # Verify schema can handle all languages
        languages = df['language'].unique()
        assert len(languages) >= 3  # At least Python, JS, Rust
        
        # Check for language-specific fields
        expected_fields = [
            'file_path', 'language', 'chunk_type', 'name',
            'start_line', 'end_line', 'content'
        ]
        
        for field in expected_fields:
            assert field in schema.names, f"Missing required field: {field}"
        
        # Verify nullable columns for language-specific data
        # Some languages might have additional metadata
        for lang in languages:
            lang_df = df[df['language'] == lang]
            
            # Each language should have valid data
            assert not lang_df['chunk_type'].isnull().all()
            assert not lang_df['name'].isnull().all()
            assert not lang_df['content'].isnull().all()
        
        # Test schema backward compatibility
        # Add a new file with different structure
        cpp_content = """
template<typename T>
class Container {
    T* data;
public:
    Container() : data(nullptr) {}
    T& operator[](size_t idx) { return data[idx]; }
};

namespace Utils {
    void helper() {}
}
"""
        
        test_file_generator.create_file("example.cpp", cpp_content)
        
        # Re-export with additional language
        output_file2 = temp_workspace / "output" / "evolved_schema.parquet"
        result = runner.invoke([
            "chunk",
            str(temp_workspace),
            "--output", str(output_file2),
            "--format", "parquet"
        ])
        
        assert result.exit_code == 0
        
        # Verify schema evolution
        table2 = pq.read_table(output_file2)
        schema2 = table2.schema
        
        # Schema should be compatible
        for field in schema.names:
            assert field in schema2.names, f"Schema lost field: {field}"
        
        # Test reading with schema validation
        # Both files should be readable with same schema
        combined_table = pq.concat_tables([table, table2])
        combined_df = combined_table.to_pandas()
        
        # Should have all languages
        all_languages = combined_df['language'].unique()
        assert len(all_languages) >= 4  # Original 3 + C++
    
    def test_compression_options(self, temp_workspace, test_file_generator,
                               performance_monitor, sample_code_files):
        """Test different Parquet compression options."""
        # Create test data
        test_files = []
        for i in range(10):
            content = sample_code_files["example.py"] * 10  # Replicate for size
            file = test_file_generator.create_file(f"compress_test_{i}.py", content)
            test_files.append(file)
        
        compression_types = ['snappy', 'gzip', 'brotli', 'lz4', 'zstd', None]
        results = {}
        
        runner = MockCLIRunner(temp_workspace)
        
        for compression in compression_types:
            output_file = temp_workspace / "output" / f"compressed_{compression or 'none'}.parquet"
            
            args = [
                "chunk",
                str(temp_workspace),
                "--output", str(output_file),
                "--format", "parquet",
                "--include", "*.py"
            ]
            
            if compression:
                args.extend(["--compression", compression])
            
            # Measure compression time
            with performance_monitor.measure(f"compress_{compression or 'none'}"):
                result = runner.invoke(args)
            
            if compression in ['lz4', 'zstd'] and result.exit_code != 0:
                # These might not be available in all environments
                continue
                
            assert result.exit_code == 0, f"Failed with {compression}: {result.error}"
            
            # Measure file size
            file_size = output_file.stat().st_size
            
            # Verify file is readable
            table = pq.read_table(output_file)
            df = table.to_pandas()
            
            # Verify content integrity
            assert len(df) > 0
            assert df['file_path'].nunique() == 10
            
            # Get actual compression used
            parquet_file = pq.ParquetFile(output_file)
            actual_compression = parquet_file.metadata.row_group(0).column(0).compression
            
            results[compression or 'none'] = {
                'size': file_size,
                'time': performance_monitor.get_stats(f"compress_{compression or 'none'}")["average"],
                'actual': actual_compression,
                'row_count': len(df)
            }
        
        # Compare results
        if 'none' in results:
            uncompressed_size = results['none']['size']
            
            # All compression types should reduce size
            for comp_type, data in results.items():
                if comp_type != 'none':
                    compression_ratio = data['size'] / uncompressed_size
                    assert compression_ratio < 1.0, \
                        f"{comp_type} didn't compress: {compression_ratio:.2f}"
                    
                    # Typically expect at least 20% compression on code
                    assert compression_ratio < 0.9, \
                        f"{comp_type} compression too weak: {compression_ratio:.2f}"
        
        # Brotli should give best compression (if available)
        if 'brotli' in results and 'gzip' in results:
            assert results['brotli']['size'] <= results['gzip']['size'], \
                "Brotli should compress better than gzip"
        
        # Snappy should be fastest (if available)
        if 'snappy' in results and 'gzip' in results:
            assert results['snappy']['time'] < results['gzip']['time'] * 1.5, \
                "Snappy should be faster than gzip"
        
        # Test decompression
        for compression in results:
            output_file = temp_workspace / "output" / f"compressed_{compression}.parquet"
            
            with performance_monitor.measure(f"decompress_{compression}"):
                table = pq.read_table(output_file)
                _ = table.to_pandas()  # Force full decompression
            
            # Decompression should be reasonably fast
            decomp_time = performance_monitor.get_stats(f"decompress_{compression}")["average"]
            assert decomp_time < 5.0, f"Decompression too slow for {compression}"
    
    def test_memory_usage_profiling(self, temp_workspace, test_file_generator,
                                   performance_monitor):
        """Test memory usage during large Parquet export."""
        # Create a dataset that will test memory limits
        num_files = 50
        chunks_per_file = 100
        
        for i in range(num_files):
            content = []
            for j in range(chunks_per_file):
                content.append(f"""
def function_{i}_{j}(data):
    '''Process data for file {i} function {j}'''
    # Simulate some code content
    result = []
    for item in data:
        result.append(item * {j})
    return result
""")
            
            test_file_generator.create_file(
                f"memory_test_{i}.py",
                "\n".join(content)
            )
        
        output_file = temp_workspace / "output" / "memory_profiled.parquet"
        
        # Track memory usage
        memory_samples = []
        peak_memory = 0
        monitoring = threading.Event()
        
        def monitor_memory():
            nonlocal peak_memory
            process = psutil.Process()
            baseline = process.memory_info().rss / (1024 * 1024)
            
            while not monitoring.is_set():
                current = process.memory_info().rss / (1024 * 1024)
                memory_mb = current - baseline  # Relative to baseline
                memory_samples.append(memory_mb)
                peak_memory = max(peak_memory, memory_mb)
                time.sleep(0.05)
        
        # Start monitoring
        monitor_thread = threading.Thread(target=monitor_memory)
        monitor_thread.start()
        
        # Run export
        runner = MockCLIRunner(temp_workspace)
        
        with performance_monitor.measure("memory_export"):
            # Use streaming to limit memory
            result = runner.invoke([
                "chunk",
                str(temp_workspace),
                "--output", str(output_file),
                "--format", "parquet",
                "--streaming",
                "--batch-size", "500",
                "--include", "memory_test_*.py"
            ])
        
        # Stop monitoring
        monitoring.set()
        monitor_thread.join()
        
        assert result.exit_code == 0, f"Export failed: {result.error}"
        
        # Verify export completed
        table = pq.read_table(output_file)
        df = table.to_pandas()
        
        expected_chunks = num_files * chunks_per_file
        assert len(df) >= expected_chunks * 0.95  # Allow small margin
        
        # Analyze memory usage
        if memory_samples:
            avg_memory = sum(memory_samples) / len(memory_samples)
            
            # Memory should stay bounded with streaming
            assert peak_memory < 500, f"Peak memory too high: {peak_memory:.1f}MB"
            assert avg_memory < 200, f"Average memory too high: {avg_memory:.1f}MB"
            
            # Check for memory leaks
            # Memory at end should be similar to beginning
            start_samples = memory_samples[:10]
            end_samples = memory_samples[-10:]
            
            if len(start_samples) > 0 and len(end_samples) > 0:
                start_avg = sum(start_samples) / len(start_samples)
                end_avg = sum(end_samples) / len(end_samples)
                
                # Allow some growth but not unbounded
                assert end_avg < start_avg + 50, \
                    f"Possible memory leak: {start_avg:.1f}MB -> {end_avg:.1f}MB"
        
        # Test different batch sizes impact on memory
        batch_sizes = [100, 1000, 5000]
        memory_by_batch = {}
        
        for batch_size in batch_sizes:
            output = temp_workspace / "output" / f"batch_memory_{batch_size}.parquet"
            samples = []
            monitoring = threading.Event()
            
            def monitor_batch():
                process = psutil.Process()
                baseline = process.memory_info().rss / (1024 * 1024)
                
                while not monitoring.is_set():
                    current = process.memory_info().rss / (1024 * 1024)
                    samples.append(current - baseline)
                    time.sleep(0.05)
            
            monitor_thread = threading.Thread(target=monitor_batch)
            monitor_thread.start()
            
            result = runner.invoke([
                "chunk",
                str(temp_workspace),
                "--output", str(output),
                "--format", "parquet",
                "--streaming",
                "--batch-size", str(batch_size),
                "--include", "memory_test_*.py"
            ])
            
            monitoring.set()
            monitor_thread.join()
            
            if samples:
                memory_by_batch[batch_size] = max(samples)
        
        # Larger batches should use more memory
        if 100 in memory_by_batch and 5000 in memory_by_batch:
            assert memory_by_batch[5000] > memory_by_batch[100]
    
    def test_progress_tracking_accuracy(self, temp_workspace, test_file_generator,
                                      thread_safe_counter):
        """Test progress tracking during Parquet export."""
        # Create test files
        num_files = 20
        for i in range(num_files):
            content = f"""
def function_{i}():
    return {i}

class Class_{i}:
    pass
"""
            test_file_generator.create_file(f"progress_test_{i}.py", content)
        
        output_file = temp_workspace / "output" / "progress_tracked.parquet"
        
        # Capture progress output
        progress_updates = []
        progress_pattern = r'(\d+)%|\[.*\]|(\d+)/(\d+)'
        
        runner = MockCLIRunner(temp_workspace)
        
        # Run with progress flag
        start_time = time.time()
        
        # Use subprocess to capture real-time output
        process = runner.invoke_async([
            "chunk",
            str(temp_workspace),
            "--output", str(output_file),
            "--format", "parquet",
            "--progress",
            "--include", "progress_test_*.py"
        ])
        
        # Capture output in real-time
        output_lines = []
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                output_lines.append(line.strip())
                
                # Look for progress indicators
                if '%' in line or '[' in line or '/' in line:
                    progress_updates.append({
                        'time': time.time() - start_time,
                        'line': line.strip()
                    })
        
        # Wait for completion
        process.wait()
        assert process.returncode == 0, f"Export failed: {process.stderr.read()}"
        
        # Analyze progress updates
        percentages = []
        for update in progress_updates:
            line = update['line']
            
            # Extract percentage if present
            import re
            match = re.search(r'(\d+)%', line)
            if match:
                percentages.append(int(match.group(1)))
        
        if percentages:
            # Progress should be monotonic
            for i in range(1, len(percentages)):
                assert percentages[i] >= percentages[i-1], \
                    f"Progress went backward: {percentages[i-1]}% -> {percentages[i]}%"
            
            # Should start near 0 and end near 100
            assert percentages[0] < 20, f"Progress started too high: {percentages[0]}%"
            assert percentages[-1] > 80, f"Progress didn't reach completion: {percentages[-1]}%"
            
            # Updates should be reasonably smooth
            large_jumps = 0
            for i in range(1, len(percentages)):
                jump = percentages[i] - percentages[i-1]
                if jump > 25:  # More than 25% jump
                    large_jumps += 1
            
            assert large_jumps < len(percentages) * 0.2, "Too many large jumps in progress"
        
        # Test ETA calculation
        eta_updates = []
        for update in progress_updates:
            if 'ETA' in update['line'] or 'remaining' in update['line']:
                eta_updates.append(update)
        
        if eta_updates:
            # ETA should generally decrease
            # Extract time values and verify they decrease
            pass  # Mock CLI might not provide real ETAs
        
        # Verify actual completion
        table = pq.read_table(output_file)
        df = table.to_pandas()
        assert len(df) > 0
        assert df['file_path'].nunique() == num_files
        
        # Test progress with different file sizes
        # Create files of varying sizes
        varied_files = []
        sizes = [10, 50, 200, 500]  # Different line counts
        
        for i, size in enumerate(sizes):
            content = []
            for j in range(size):
                content.append(f"def func_{i}_{j}(): pass")
            
            file = test_file_generator.create_file(
                f"varied_size_{i}.py",
                "\n".join(content)
            )
            varied_files.append(file)
        
        output_file2 = temp_workspace / "output" / "varied_progress.parquet"
        
        # Progress should account for file sizes
        result = runner.invoke([
            "chunk",
            str(temp_workspace),
            "--output", str(output_file2),
            "--format", "parquet",
            "--progress",
            "--include", "varied_size_*.py"
        ])
        
        assert result.exit_code == 0
        
        # Verify all files processed
        table2 = pq.read_table(output_file2)
        df2 = table2.to_pandas()
        assert df2['file_path'].nunique() == len(sizes)

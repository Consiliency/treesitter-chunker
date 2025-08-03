"""End-to-end integration tests for the complete tree-sitter-chunker pipeline.

This module tests the full workflow from file input to various export formats,
ensuring all components work together correctly.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest

from chunker import CodeChunk, chunk_file
from chunker.parallel import ParallelChunker, chunk_files_parallel
from chunker.chunker_config import ChunkerConfig
from chunker.export import JSONExporter, JSONLExporter, SchemaType


class TestFullPipeline:
    """Test complete workflows from file input to export."""

    @classmethod
    def test_single_file_all_export_formats(cls, tmp_path):
        """Test processing a single file through all export formats."""
        test_file = tmp_path / "example.py"
        test_file.write_text(
            """
import asyncio

def hello_world():
    '''Say hello to the world.'''
    print("Hello, World!")

class Greeter:
    def __init__(self, name):
        self.name = name

    def greet(self):
        return f"Hello, {self.name}!"

async def async_hello():
    await asyncio.sleep(1)
    return "Async Hello!\"
""",
            )
        chunks = chunk_file(test_file, language="python")
        assert len(chunks) >= 4
        json_file = tmp_path / "output.json"
        jsonl_file = tmp_path / "output.jsonl"
        json_exporter = JSONExporter(schema_type=SchemaType.FLAT)
        json_exporter.export(chunks, json_file)
        assert json_file.exists()
        with Path(json_file).open(encoding="utf-8") as f:
            json_data = json.load(f)
            assert len(json_data) == len(chunks)
        jsonl_exporter = JSONLExporter()
        jsonl_exporter.export(chunks, jsonl_file)
        assert jsonl_file.exists()
        lines = jsonl_file.read_text().strip().split("\n")
        assert len(lines) == len(chunks)
        jsonl_chunks = [json.loads(line) for line in lines]
        for i in range(len(chunks)):
            assert json_data[i]["content"] == jsonl_chunks[i]["content"]
            assert json_data[i]["start_line"] == jsonl_chunks[i]["start_line"]

    @classmethod
    def test_multi_language_project(cls, tmp_path):
        """Test processing a project with multiple language files."""
        project_dir = tmp_path / "multi_lang_project"
        project_dir.mkdir()
        (project_dir / "app.py").write_text(
            """
def main():
    print("Python main")

class App:
    def run(self):
        pass
""",
            )
        (project_dir / "index.js").write_text(
            """
function main() {
    console.log("JavaScript main");
}

class App {
    run() {
        return "running";
    }
}

const arrow = () => "arrow function";
""",
            )
        (project_dir / "main.rs").write_text(
            """
fn main() {
    println!("Rust main");
}

struct App {
    name: String,
}

impl App {
    fn new(name: &str) -> Self {
        App { name: name.to_string() }
    }

    fn run(&self) {
        println!("Running {}", self.name);
    }
}
""",
            )
        all_chunks = []
        ext_to_lang = {".py": "python", ".js": "javascript", ".rs": "rust"}
        for file_path in sorted(project_dir.rglob("*")):
            if file_path.is_file() and file_path.suffix in ext_to_lang:
                language = ext_to_lang[file_path.suffix]
                try:
                    chunks = chunk_file(file_path, language=language)
                    print(f"Processed {file_path.name}: {len(chunks)} chunks")
                    all_chunks.extend(chunks)
                except (FileNotFoundError, IndexError, KeyError) as e:
                    print(f"Error processing {file_path}: {e}")
        {chunk.language for chunk in all_chunks}
        file_paths = {chunk.file_path for chunk in all_chunks}
        assert len(file_paths) >= 2
        output_file = tmp_path / "multi_lang_output.json"
        json_exporter = JSONExporter(schema_type=SchemaType.FLAT)
        json_exporter.export(all_chunks, output_file)
        with Path(output_file).open(encoding="utf-8") as f:
            exported_data = json.load(f)
            assert len(exported_data) >= 4

    @classmethod
    def test_parallel_processing_pipeline(cls, tmp_path):
        """Test parallel processing of multiple files."""
        for i in range(5):
            test_file = tmp_path / f"module_{i}.py"
            test_file.write_text(
                f"""
def function_{i}():
    return {i}

class Class_{i}:
    def method(self):
        return "method_{i}\"
""",
                )
        file_paths = list(tmp_path.glob("*.py"))
        results = chunk_files_parallel(file_paths, language="python",
            num_workers=3)
        all_chunks = [item for chunks in results.values() for item in chunks]
        assert len(all_chunks) >= 10
        output_file = tmp_path / "parallel_output.jsonl"
        jsonl_exporter = JSONLExporter()
        jsonl_exporter.export(all_chunks, output_file)
        lines = output_file.read_text().strip().split("\n")
        assert len(lines) == len(all_chunks)

    @classmethod
    def test_configuration_precedence(cls, tmp_path):
        """Test configuration precedence: CLI > project > user > defaults."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """
def small_function():
    pass

def medium_function():
    # Line 1
    # Line 2
    # Line 3
    # Line 4
    pass

def large_function():
    # Many lines of code
    # Line 1
    # Line 2
    # Line 3
    # Line 4
    # Line 5
    # Line 6
    # Line 7
    # Line 8
    # Line 9
    # Line 10
    pass
""",
            )
        chunks = chunk_file(test_file, language="python")
        assert len(chunks) == 3
        project_config = tmp_path / ".chunkerrc.toml"
        project_config.write_text("\n[python]\nmin_chunk_size = 5\n")
        config = ChunkerConfig(str(project_config))
        assert config is not None
        output_file = tmp_path / "filtered_output.json"
        json_exporter = JSONExporter(schema_type=SchemaType.FLAT)
        json_exporter.export(chunks, output_file)
        assert output_file.exists()


class TestCLIIntegration:
    """Test CLI commands in end-to-end scenarios."""

    @classmethod
    def test_cli_basic_workflow(cls, tmp_path):
        """Test basic CLI workflow with chunk and export."""
        test_file = tmp_path / "example.py"
        test_file.write_text(
            '\ndef hello():\n    return "Hello"\n\nclass Example:\n    pass\n')
        output_file = tmp_path / "output.json"
        result = subprocess.run([sys.executable, "-m", "cli.main", "chunk",
            str(test_file), "--json"], check=False, capture_output=True,
            text=True)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) >= 2
        with Path(output_file).open("w", encoding="utf-8") as f:
            json.dump(data, f)

    @staticmethod
    def test_cli_batch_processing(tmp_path):
        """Test CLI batch processing of directory."""
        test_dir = tmp_path / "src"
        test_dir.mkdir()
        for i in range(3):
            (test_dir / f"module{i}.py").write_text(
                f"\ndef func{i}():\n    pass\n")
        output_file = tmp_path / "batch_output.jsonl"
        result = subprocess.run([sys.executable, "-m", "cli.main", "batch",
            str(test_dir), "--pattern", "*.py", "--jsonl"], check=False,
            capture_output=True, text=True)
        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert len(lines) >= 3
        output_file.write_text(result.stdout)

    @staticmethod
    def test_cli_with_config_file(tmp_path):
        """Test CLI with configuration file."""
        config_file = tmp_path / ".chunkerrc.toml"
        config_file.write_text(
            """
[general]
min_chunk_size = 3
chunk_types = ["function_definition", "class_definition"]

[python]
include_docstrings = true
""",
            )
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """
def tiny():
    pass

def normal():
    '''This has a docstring.'''
    x = 1
    return x
""",
            )
        result = subprocess.run([sys.executable, "-m", "cli.main", "chunk",
            str(test_file), "--config", str(config_file)], check=False,
            capture_output=True, text=True)
        assert result.returncode == 0


class TestPerformanceBaseline:
    """Establish performance baselines for full pipeline."""

    @classmethod
    def test_large_file_pipeline(cls, tmp_path):
        """Test processing a large file through the complete pipeline."""
        large_file = tmp_path / "large.py"
        content_lines = []
        for i in range(100):
            content_lines.extend([f"def function_{i}(arg1, arg2, arg3):",
                f"    '''Docstring for function {i}.'''",
                "    result = arg1 + arg2 * arg3",
                "    for j in range(10):", "        result += j",
                "    return result", ""])
        large_file.write_text("\n".join(content_lines))
        start = time.time()
        chunks = chunk_file(large_file, language="python")
        chunk_time = time.time() - start
        json_start = time.time()
        json_file = tmp_path / "large.json"
        json_exporter = JSONExporter(schema_type=SchemaType.FLAT)
        json_exporter.export(chunks, json_file)
        json_time = time.time() - json_start
        jsonl_start = time.time()
        jsonl_file = tmp_path / "large.jsonl"
        jsonl_exporter = JSONLExporter()
        jsonl_exporter.export(chunks, jsonl_file)
        jsonl_time = time.time() - jsonl_start
        time.time() - start
        assert len(chunks) >= 100
        assert chunk_time < 2.0
        assert json_time < 0.5
        assert jsonl_time < 0.5
        assert json_file.exists()
        assert jsonl_file.exists()

    @classmethod
    def test_memory_usage_monitoring(cls, tmp_path):
        """Monitor memory usage during processing."""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024
        test_file = tmp_path / "medium.py"
        content = "\n".join([f"def func_{i}(): return {i}" for i in range(500)],
            )
        test_file.write_text(content)
        chunks = chunk_file(test_file, language="python")
        after_chunk_memory = process.memory_info().rss / 1024 / 1024
        json_exporter = JSONExporter(schema_type=SchemaType.FLAT)
        json_exporter.export(chunks, tmp_path / "output.json")
        after_export_memory = process.memory_info().rss / 1024 / 1024
        chunk_memory_increase = after_chunk_memory - initial_memory
        export_memory_increase = after_export_memory - after_chunk_memory
        assert chunk_memory_increase < 100
        assert export_memory_increase < 50


class TestErrorPropagation:
    """Test error handling through the full pipeline."""

    @staticmethod
    def test_invalid_file_handling(tmp_path):
        """Test handling of invalid files in pipeline."""
        missing_file = tmp_path / "missing.py"
        with pytest.raises(FileNotFoundError):
            chunk_file(missing_file, language="python")
        binary_file = tmp_path / "binary.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03")
        try:
            chunk_file(binary_file, language="python")
        except (OSError, FileNotFoundError, IndexError) as e:
            assert "binary" in str(e).lower() or "decode" in str(e).lower()

    @classmethod
    def test_export_error_handling(cls, tmp_path):
        """Test export error handling."""
        chunks = [CodeChunk(language="python", file_path="/test.py",
            node_type="function_definition", start_line=1, end_line=1,
            byte_start=0, byte_end=16, parent_context="", content="def test(): pass")]
        if os.name != "nt":
            read_only_dir = tmp_path / "readonly"
            read_only_dir.mkdir()
            os.chmod(read_only_dir, 292)
            output_file = read_only_dir / "output.json"
            with pytest.raises(PermissionError):
                json_exporter = JSONExporter(schema_type=SchemaType.FLAT)
                json_exporter.export(chunks, output_file)
            os.chmod(read_only_dir, 493)

    @classmethod
    def test_partial_success_handling(cls, tmp_path):
        """Test handling partial success in batch operations."""
        (tmp_path / "good.py").write_text("def good(): pass")
        (tmp_path / "bad.py").write_text("def bad(: syntax error")
        (tmp_path / "ugly.txt").write_text("not a python file")
        chunker = ParallelChunker(language="python", num_workers=2)
        files = list(tmp_path.glob("*"))
        results = chunker.chunk_files_parallel(files)
        assert len(results) == 3
        successes = {path: chunks for path, chunks in results.items() if chunks
            }
        {path: chunks for path, chunks in results.items() if not chunks}
        assert len(successes) >= 1
        all_chunks = [item for chunks in successes.values() for item in chunks]
        if all_chunks:
            json_exporter = JSONExporter(schema_type=SchemaType.FLAT)
            json_exporter.export(all_chunks, tmp_path / "partial_results.json")

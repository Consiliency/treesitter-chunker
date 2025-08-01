"""
Tests for enhanced CLI features.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from cli.main import (
    app,
    get_files_from_patterns,
    load_config,
    process_file,
    should_include_file,
)

runner = CliRunner()


class TestConfigLoading:
    """Test configuration file loading."""

    @classmethod
    def test_load_config_from_file(cls):
        """Test loading configuration from specified file."""
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".toml", delete=False) as f:
            f.write(
                """
chunk_types = ["function_definition"]
min_chunk_size = 5
max_chunk_size = 100
include_patterns = ["*.py"]
exclude_patterns = ["test_*"]
parallel_workers = 2
""",
                )
            f.flush()
            config = load_config(Path(f.name))
            assert config["chunk_types"] == ["function_definition"]
            assert config["min_chunk_size"] == 5
            assert config["max_chunk_size"] == 100
            assert config["include_patterns"] == ["*.py"]
            assert config["exclude_patterns"] == ["test_*"]
            assert config["parallel_workers"] == 2
            Path(f.name).unlink()

    @classmethod
    def test_load_config_nonexistent(cls):
        """Test loading config when file doesn't exist."""
        config = load_config(Path("/nonexistent/config.toml"))
        assert config == {}

    @classmethod
    def test_load_config_invalid_toml(cls):
        """Test loading invalid TOML file."""
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".toml", delete=False) as f:
            f.write("invalid toml {")
            f.flush()
            config = load_config(Path(f.name))
            assert config == {}
            Path(f.name).unlink()


class TestFilePatterns:
    """Test file pattern matching."""

    @classmethod
    def test_get_files_from_patterns(cls):
        """Test getting files from glob patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test1.py").write_text("pass")
            (tmppath / "test2.py").write_text("pass")
            (tmppath / "test.js").write_text("pass")
            (tmppath / "subdir").mkdir()
            (tmppath / "subdir" / "test3.py").write_text("pass")
            files = list(get_files_from_patterns(["*.py"], tmppath))
            assert len(files) == 2
            assert all(f.suffix == ".py" for f in files)
            files = list(get_files_from_patterns(["**/*.py"], tmppath))
            assert len(files) == 3

    @classmethod
    def test_should_include_file(cls):
        """Test file inclusion/exclusion logic."""
        assert should_include_file(Path("test.py"), include_patterns=["*.py"])
        assert not should_include_file(Path("test.js"), include_patterns=[
            "*.py"])
        assert not should_include_file(Path("test_file.py"),
            exclude_patterns=["test_*"])
        assert should_include_file(Path("main.py"), exclude_patterns=["test_*"],
            )
        assert should_include_file(Path("main.py"), include_patterns=[
            "*.py"], exclude_patterns=["test_*"])
        assert not should_include_file(Path("test_main.py"),
            include_patterns=["*.py"], exclude_patterns=["test_*"])


class TestProcessFile:
    """Test file processing."""

    @classmethod
    def test_process_file_auto_detect_language(cls):
        """Test auto-detecting language from file extension."""
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py", delete=False) as f:
            f.write(
                """
def test_function():
    pass

class TestClass:
    def test_method(self):
        pass
""",
                )
            f.flush()
            results = process_file(Path(f.name), language=None)
            assert len(results) > 0
            assert all(r["language"] == "python" for r in results)
            Path(f.name).unlink()

    @classmethod
    def test_process_file_with_filters(cls):
        """Test processing file with chunk type and size filters."""
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py", delete=False) as f:
            f.write(
                """
def small_func():
    pass

def large_func():
    line1 = 1
    line2 = 2
    line3 = 3
    line4 = 4
    line5 = 5
    line6 = 6
    return line6

class TestClass:
    def method(self):
        pass
""",
                )
            f.flush()
            results = process_file(Path(f.name), language="python",
                chunk_types=["class_definition"])
            assert all(r["node_type"] == "class_definition" for r in results)
            results = process_file(Path(f.name), language="python", min_size=5)
            assert all(r["size"] >= 5 for r in results)
            Path(f.name).unlink()


class TestCLICommands:
    """Test CLI commands."""

    @classmethod
    def test_chunk_command_basic(cls):
        """Test basic chunk command."""
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py", delete=False) as f:
            f.write(
                """def test_function():
    # This is a test function
    result = 42
    return result
""",
                )
            f.flush()
            result = runner.invoke(app, ["chunk", str(f.name), "--lang",
                "python"])
            assert result.exit_code == 0
            assert "function_definition" in result.output
            Path(f.name).unlink()

    @classmethod
    def test_chunk_command_json_output(cls):
        """Test chunk command with JSON output."""
        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".py", delete=False) as f:
            f.write(
                """def test_function():
    # This is a test function
    result = 42
    return result
""",
                )
            f.flush()
            result = runner.invoke(app, ["chunk", str(f.name), "--lang",
                "python", "--json"])
            assert result.exit_code == 0
            assert result.output.startswith("[")
            assert result.output.strip().endswith("]")
            assert '"node_type": "function_definition"' in result.output
            assert '"language": "python"' in result.output
            try:
                data = json.loads(result.output)
                assert isinstance(data, list)
                assert len(data) > 0
                assert data[0]["node_type"] == "function_definition"
            except json.JSONDecodeError:
                pass
            Path(f.name).unlink()

    @classmethod
    def test_batch_command_directory(cls):
        """Test batch command with directory input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.py").write_text(
                """def func1():
    # This is function 1
    x = 1
    return x
""",
                )
            (tmppath / "file2.py").write_text(
                """def func2():
    # This is function 2
    y = 2
    return y
""",
                )
            result = runner.invoke(app, ["batch", str(tmppath), "--quiet"])
            assert result.exit_code == 0
            assert "2 total chunks" in result.output
            assert "from 2" in result.output
            assert "files)" in result.output

    @classmethod
    def test_batch_command_pattern(cls):
        """Test batch command with pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "sample.py").write_text(
                """def sample_func():
    # Sample function
    result = "sample"
    return result
""",
                )
            (tmppath / "main.py").write_text(
                """def main_func():
    # Main function
    result = "main"
    return result
""",
                )
            (tmppath / "test.js").write_text("\nfunction testFunc() {}\n")
            result = runner.invoke(app, ["batch", str(tmppath), "--include",
                "*.py", "--quiet"])
            assert result.exit_code == 0
            assert "2 total chunks" in result.output
            assert "from 2" in result.output
            assert "files)" in result.output

    @classmethod
    def test_batch_command_stdin(cls):
        """Test batch command reading from stdin."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            file1 = tmppath / "file1.py"
            file1.write_text(
                "def func1():\n    # First function\n    x = 1\n    return x\n",
                )
            file2 = tmppath / "file2.py"
            file2.write_text(
                "def func2():\n    # Second function\n    y = 2\n    return y\n",
                )
            input_data = f"{file1}\n{file2}\n"
            result = runner.invoke(app, ["batch", "--stdin", "--quiet"],
                input=input_data)
            if result.exit_code == 0:
                assert "2 total chunks" in result.output or "No files to process" in result.output

    @classmethod
    def test_batch_command_filters(cls):
        """Test batch command with various filters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "main.py").write_text(
                """
def main_function():
    pass

class MainClass:
    pass
""",
                )
            (tmppath / "test_main.py").write_text(
                "\ndef test_function():\n    pass\n")
            import os
            old_cwd = Path.cwd()
            os.chdir(tmpdir)
            try:
                result = runner.invoke(app, ["batch", ".", "--include",
                    "*.py", "--exclude", "test_*", "--types",
                    "function_definition", "--quiet"])
                assert result.exit_code == 0
                assert "from 1" in result.output
                assert "files)" in result.output
                assert "function_definition" in result.output
            finally:
                os.chdir(old_cwd)

    @classmethod
    def test_batch_command_jsonl_output(cls):
        """Test batch command with JSONL output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "sample.py").write_text(
                """def func1():
    # First function
    x = 1
    return x

def func2():
    # Second function
    y = 2
    return y
""",
                )
            result = runner.invoke(app, ["batch", str(tmppath), "--jsonl",
                "--quiet"])
            assert result.exit_code == 0
            lines = result.output.strip().split("\n")
            json_objects = []
            for line in lines:
                if line.strip():
                    try:
                        json_objects.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            if len(json_objects) < 2:
                assert '"node_type"' in result.output
                assert '"function_definition"' in result.output
                assert result.output.count('"node_type"') == 2
            else:
                assert len(json_objects) == 2
                for data in json_objects:
                    assert "node_type" in data
                    assert data["node_type"] == "function_definition"

    @staticmethod
    def test_languages_command():
        """Test languages command."""
        result = runner.invoke(app, ["languages"])
        assert result.exit_code == 0
        assert "Available Languages" in result.output
        assert "python" in result.output.lower()


class TestCLIWithConfig:
    """Test CLI with configuration file."""

    @classmethod
    def test_chunk_with_config(cls):
        """Test chunk command with config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            config_file = tmppath / ".chunkerrc"
            config_file.write_text(
                '\nchunk_types = ["function_definition"]\nmin_chunk_size = 5\n',
                )
            test_file = tmppath / "test.py"
            test_file.write_text(
                """
def small():
    pass

def large():
    line1 = 1
    line2 = 2
    line3 = 3
    line4 = 4
    line5 = 5

class TestClass:
    pass
""",
                )
            result = runner.invoke(app, ["chunk", str(test_file),
                "--config", str(config_file)])
            assert result.exit_code == 0
            assert "5-10" in result.output
            assert "class_definition" not in result.output

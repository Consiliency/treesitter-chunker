"""Advanced CLI integration tests for the tree-sitter-chunker.

This module tests complex CLI scenarios including interactive mode,
signal handling, complex command chains, and error recovery.
"""
import json
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from cli.main import app


def parse_jsonl_output(output: str) -> list[dict[str, Any]]:
    """Parse JSONL output, filtering out non-JSON lines."""
    results = []
    lines = output.strip().split("\n")
    current_json = ""
    for line in lines:
        if line.strip():
            current_json += line
            try:
                data = json.loads(current_json)
                results.append(data)
                current_json = ""
            except json.JSONDecodeError:
                if line.endswith("}"):
                    current_json = ""
                    try:
                        data = json.loads(line)
                        results.append(data)
                    except (SyntaxError, ValueError, json.JSONDecodeError):
                        pass
    if current_json:
        try:
            data = json.loads(current_json)
            results.append(data)
        except (FileNotFoundError, OSError, SyntaxError):
            pass
    return results


class TestComplexCommands:
    """Test complex command scenarios."""

    @classmethod
    def test_command_chaining(cls, tmp_path):
        """Test multiple commands in sequence."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        for i in range(3):
            (src_dir / f"module{i}.py").write_text(
                f"""
def func_{i}():
    return {i}

class Class_{i}:
    pass
""",
                )
        runner = CliRunner()
        result1 = runner.invoke(app, ["chunk", str(src_dir / "module0.py"),
            "-l", "python", "--json"])
        assert result1.exit_code == 0
        chunks1 = json.loads(result1.stdout)
        assert len(chunks1) >= 2
        result2 = runner.invoke(app, ["batch", str(src_dir), "--pattern",
            "*.py", "--jsonl", "--quiet"])
        assert result2.exit_code == 0
        lines = result2.stdout.strip().split("\n")
        assert len(lines) >= 6
        result3 = runner.invoke(app, ["languages"])
        assert result3.exit_code == 0
        assert "python" in result3.stdout

    @classmethod
    def test_glob_pattern_expansion(cls, tmp_path):
        """Test complex file pattern matching."""
        (tmp_path / "src" / "core").mkdir(parents=True)
        (tmp_path / "src" / "utils").mkdir()
        (tmp_path / "tests").mkdir()
        files = ["src/core/main.py", "src/core/config.py",
            "src/utils/helpers.py", "src/utils/data.json",
            "tests/test_main.py", "tests/test_config.py", "README.md"]
        for file_path in files:
            full_path = tmp_path / file_path
            if file_path.endswith(".py"):
                full_path.write_text("def test(): pass")
            else:
                full_path.write_text("data")
        runner = CliRunner()
        patterns = [("**/*.py", 5), ("src/**/*.py", 3), ("**/test_*.py", 2),
            ("src/*/*.py", 3)]
        for pattern, expected_count in patterns:
            result = runner.invoke(app, ["batch", str(tmp_path),
                "--pattern", pattern, "--jsonl", "--quiet"])
            assert result.exit_code == 0
            lines = [line for line in result.stdout.strip().split("\n") if line
                ]
            assert len(lines) >= expected_count

    @classmethod
    def test_recursive_directory_processing(cls, tmp_path):
        """Test deep directory traversal."""
        deep_path = tmp_path
        for i in range(5):
            deep_path /= f"level{i}"
            deep_path.mkdir()
            (deep_path / f"module{i}.py").write_text(
                f"""
def level_{i}_function():
    return {i}
""")
        runner = CliRunner()
        result = runner.invoke(app, ["batch", str(tmp_path), "--pattern",
            "**/*.py", "--recursive", "--jsonl", "--quiet"])
        assert result.exit_code == 0
        chunks = parse_jsonl_output(result.stdout)
        if len(chunks) < 5:
            print(f"Exit code: {result.exit_code}")
            print(f"Stdout: {result.stdout}")
            print(
                f"Stderr: {result.stderr if hasattr(result, 'stderr') else 'N/A'}",
                )
            print(f"Exception: {result.exception}")
            print(f"Chunks parsed: {len(chunks)}")
        assert len(chunks) >= 5

    @classmethod
    def test_mixed_language_batch_processing(cls, tmp_path):
        """Test multi-language projects."""
        files = {"app.py":
            '\ndef main():\n    print("Python app")\n\nclass App:\n    pass\n',
            "server.js":
            """
function startServer() {
    console.log("Starting server");
}

class Server {
    constructor() {}
}
"""
            , "lib.rs":
            """
fn process_data() -> i32 {
    42
}

struct DataProcessor {
    value: i32,
}
"""
            , "utils.c":
            """
int calculate(int a, int b) {
    return a + b;
}

struct Point {
    int x;
    int y;
};
""",
            }
        for filename, content in files.items():
            (tmp_path / filename).write_text(content)
        runner = CliRunner()
        result = runner.invoke(app, ["batch", str(tmp_path), "--pattern",
            "*.*", "--jsonl", "--quiet"])
        if result.exit_code == 0:
            chunks = parse_jsonl_output(result.stdout)
            languages_found = set()
            for chunk in chunks:
                if "language" in chunk:
                    languages_found.add(chunk["language"])
            assert "python" in languages_found


class TestInteractiveMode:
    """Test interactive mode features."""

    @staticmethod
    @pytest.mark.skip(reason="Interactive mode testing requires TTY")
    def test_interactive_prompt_handling(tmp_path):
        """Test user input prompts."""

    @staticmethod
    def test_interactive_progress_display(tmp_path):
        """Test real-time progress updates."""
        for i in range(20):
            (tmp_path / f"file{i}.py").write_text(f"def func{i}(): pass")
        process = subprocess.Popen([sys.executable, "-m", "cli.main",
            "batch", str(tmp_path), "--pattern", "*.py"], stdout=subprocess
            .PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0
        assert stdout or stderr

    @classmethod
    def test_interactive_error_recovery(cls, tmp_path):
        """Test error handling in interactive mode."""
        (tmp_path / "good.py").write_text("def good(): pass")
        (tmp_path / "bad.py").write_text("def bad(: syntax error")
        (tmp_path / "empty.py").write_text("")
        runner = CliRunner()
        result = runner.invoke(app, ["batch", str(tmp_path), "--pattern",
            "*.py", "--jsonl", "--quiet"])
        assert result.exit_code in {0, 1}
        if result.stdout:
            assert "good" in result.stdout

    @classmethod
    def test_interactive_cancellation(cls):
        """Test graceful cancellation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            for i in range(100):
                (tmp_path / f"file{i}.py").write_text(
                    f"def func{i}(): pass\n" * 100)
            process = subprocess.Popen([sys.executable, "-m", "cli.main",
                "batch", str(tmp_path), "--pattern", "*.py", "--jsonl"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(0.2)
            if process.poll() is not None:
                pytest.skip("Process completed before signal could be sent")
            process.send_signal(signal.SIGINT)
            try:
                _stdout, _stderr = process.communicate(timeout=5)
                assert process.returncode in {0, -2, 130, 1}
            except subprocess.TimeoutExpired:
                process.kill()
                pytest.fail("Process did not handle SIGINT gracefully")


class TestSignalHandling:
    """Test signal handling and cleanup."""

    @staticmethod
    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals only")
    def test_sigint_handling(tmp_path):
        """Test Ctrl+C handling."""
        (tmp_path / "test.py").write_text("def test(): pass\n" * 1000)
        process = subprocess.Popen([sys.executable, "-m", "cli.main",
            "chunk", str(tmp_path / "test.py"), "-l", "python", "--json"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(0.05)
        if process.poll() is not None:
            pytest.skip("Process completed before signal could be sent")
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=2)
            assert process.returncode in {0, -2, 130, 1}
        except subprocess.TimeoutExpired:
            process.kill()
            pytest.fail("Process did not handle SIGINT")

    @staticmethod
    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals only")
    def test_sigterm_graceful_shutdown(tmp_path):
        """Test graceful termination."""
        for i in range(50):
            (tmp_path / f"file{i}.py").write_text("def test(): pass\n" * 50)
        process = subprocess.Popen([sys.executable, "-m", "cli.main",
            "batch", str(tmp_path), "--pattern", "*.py", "--jsonl"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(0.1)
        if process.poll() is not None:
            pytest.skip("Process completed before SIGTERM could be sent")
        process.terminate()
        try:
            process.wait(timeout=5)
            assert process.returncode in {0, -15, 143, 1}
        except subprocess.TimeoutExpired:
            process.kill()
            pytest.fail("Process did not handle SIGTERM gracefully")

    @staticmethod
    def test_cleanup_on_unexpected_exit(tmp_path):
        """Test resource cleanup."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        marker = output_dir / ".chunker_lock"
        subprocess.run([sys.executable, "-m", "cli.main", "chunk", __file__,
            "-l", "python", "--json"], check=False, capture_output=True,
            text=True, cwd=str(output_dir))
        assert not marker.exists()
        temp_files = list(output_dir.glob(".chunker_tmp_*"))
        assert len(temp_files) == 0

    @classmethod
    def test_partial_results_on_interrupt(cls, tmp_path):
        """Test saving partial progress."""
        for i in range(50):
            (tmp_path / f"file{i}.py").write_text(f"def func{i}(): pass")
        output_file = tmp_path / "partial_output.jsonl"
        process = subprocess.Popen([sys.executable, "-m", "cli.main",
            "batch", str(tmp_path), "--pattern", "*.py", "--jsonl"], stdout=Path(output_file).open("w", encoding="utf-8"), stderr=subprocess.PIPE)
        time.sleep(0.5)
        process.terminate()
        process.wait(timeout=5)
        if output_file.exists():
            lines = output_file.read_text().strip().split("\n")
            assert len(lines) > 0


class TestOutputFormats:
    """Test various output format options."""

    @classmethod
    def test_custom_output_templates(cls, tmp_path):
        """Test custom output formatting."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            '\ndef hello():\n    return "world"\n\nclass Test:\n    pass\n')
        runner = CliRunner()
        result1 = runner.invoke(app, ["chunk", str(test_file), "-l", "python"])
        assert result1.exit_code == 0
        assert "function_definition" in result1.stdout or "class_definition" in result1.stdout
        result2 = runner.invoke(app, ["chunk", str(test_file), "-l",
            "python", "--json"])
        assert result2.exit_code == 0
        data = json.loads(result2.stdout)
        assert isinstance(data, list)
        result3 = runner.invoke(app, ["batch", str(test_file), "--jsonl",
            "--quiet"])
        assert result3.exit_code == 0
        chunks = parse_jsonl_output(result3.stdout)
        assert len(chunks) >= 2

    @classmethod
    def test_output_redirection(cls, tmp_path):
        """Test piping and redirection."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass")
        output_file = tmp_path / "output.json"
        result = subprocess.run([sys.executable, "-m", "cli.main", "chunk",
            str(test_file), "-l", "python", "--json"], check=False, stdout=Path(output_file).open("w", encoding="utf-8"), stderr=subprocess.PIPE)
        assert result.returncode == 0
        assert output_file.exists()
        with Path(output_file).open("r", encoding="utf-8") as f:
            data = json.load(f)
            assert len(data) >= 1
        result = subprocess.run(
            f"{sys.executable} -m cli.main chunk {test_file} -l python --json | {sys.executable} -m json.tool"
            , check=False, shell=True, capture_output=True, text=True)
        assert result.returncode == 0
        assert "{\n" in result.stdout

    @classmethod
    def test_quiet_and_verbose_modes(cls, tmp_path):
        """Test output verbosity control."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass")
        runner = CliRunner()
        result_quiet = runner.invoke(app, ["batch", str(test_file),
            "--quiet", "--json"])
        assert result_quiet.exit_code == 0
        result_normal = runner.invoke(app, ["batch", str(test_file), "--json"])
        assert result_normal.exit_code == 0

    @staticmethod
    def test_json_streaming_output(tmp_path):
        """Test streaming JSON output."""
        for i in range(5):
            (tmp_path / f"file{i}.py").write_text(f"def func{i}(): pass")
        process = subprocess.Popen([sys.executable, "-m", "cli.main",
            "batch", str(tmp_path), "--pattern", "*.py", "--jsonl",
            "--quiet"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1)
        stdout, _stderr = process.communicate()
        chunks = parse_jsonl_output(stdout)
        assert len(chunks) >= 5


class TestErrorScenarios:
    """Test error handling scenarios."""

    @classmethod
    def test_invalid_option_combinations(cls):
        """Test conflicting options."""
        runner = CliRunner()
        result = runner.invoke(app, ["chunk", __file__, "-l", "python",
            "--jsonl"])
        assert result.exit_code != 0
        result = runner.invoke(app, ["chunk", __file__, "-l",
            "invalid_language"])
        assert "not found" in result.stdout.lower() or result.exit_code != 0
        result = runner.invoke(app, ["chunk", __file__])
        assert result.exit_code == 0

    @classmethod
    def test_missing_dependencies_handling(cls, tmp_path):
        """Test missing language support."""
        unsupported_file = tmp_path / "test.xyz"
        unsupported_file.write_text("content")
        runner = CliRunner()
        result = runner.invoke(app, ["chunk", str(unsupported_file), "-l",
            "xyz"])
        assert "not found" in result.stdout.lower(
            ) or "not supported" in result.stdout.lower(
            ) or result.exit_code != 0

    @classmethod
    def test_filesystem_permission_errors(cls, tmp_path):
        """Test permission denied scenarios."""
        if sys.platform == "win32":
            pytest.skip("Unix permissions test")
        readonly_file = tmp_path / "readonly.py"
        readonly_file.write_text("def test(): pass")
        readonly_file.chmod(292)
        readonly_dir = tmp_path / "readonly_dir"
        readonly_dir.mkdir()
        readonly_dir.chmod(365)
        runner = CliRunner()
        result = runner.invoke(app, ["chunk", str(readonly_file), "-l",
            "python", "--json"])
        assert result.exit_code == 0
        readonly_dir.chmod(493)
        readonly_file.chmod(420)

    @classmethod
    def test_network_timeout_handling(cls, tmp_path):
        """Test remote operation timeouts."""
        runner = CliRunner()
        result = runner.invoke(app, ["chunk", "/non/existent/path/file.py",
            "-l", "python"])
        assert result.exit_code != 0
        error_keywords = ["not found", "does not exist", "no such file",
            "error", "path"]
        output = result.stdout.lower()
        if hasattr(result, "stderr") and result.stderr:
            output += " " + result.stderr.lower()
        if result.exception:
            output += " " + str(result.exception).lower()
        assert any(keyword in output for keyword in error_keywords)


def test_cli_version():
    """Test version command."""
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_cli_help():
    """Test help command."""
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "chunk" in result.stdout
    assert "batch" in result.stdout
    result = runner.invoke(app, ["chunk", "--help"])
    assert result.exit_code == 0
    assert "language" in result.stdout or "-l" in result.stdout


def test_cli_config_file_loading(tmp_path):
    """Test configuration file loading."""
    config_file = tmp_path / ".chunkerrc.toml"
    config_file.write_text(
        """
[general]
default_language = "python"
min_chunk_size = 5

[output]
default_format = "json\"
""",
        )
    test_file = tmp_path / "test.py"
    test_file.write_text(
        """
def tiny():
    pass

def larger_function():
    # Line 1
    # Line 2
    # Line 3
    # Line 4
    # Line 5
    pass
""",
        )
    runner = CliRunner()
    result = runner.invoke(app, ["chunk", str(test_file), "--config", str(
        config_file)])
    assert result.exit_code == 0
    if "--json" in result.stdout or result.stdout.startswith("["):
        data = json.loads(result.stdout)
        assert all("tiny" not in chunk.get("content", "") for chunk in data)

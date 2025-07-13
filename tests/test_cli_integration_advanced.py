"""Advanced CLI integration tests for the tree-sitter-chunker.

This module tests complex CLI scenarios including interactive mode,
signal handling, complex command chains, and error recovery.
"""

import os
import sys
import signal
import subprocess
import threading
import time
import json
from pathlib import Path
from typing import List, Dict, Any
import pytest
import tempfile

from typer.testing import CliRunner
from cli.main import app


class TestComplexCommands:
    """Test complex command scenarios."""
    
    def test_command_chaining(self, tmp_path):
        """Test multiple commands in sequence."""
        # Create test files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        
        for i in range(3):
            (src_dir / f"module{i}.py").write_text(f"""
def func_{i}():
    return {i}

class Class_{i}:
    pass
""")
        
        # Chain multiple commands
        runner = CliRunner()
        
        # First command: chunk files
        result1 = runner.invoke(app, [
            "chunk", str(src_dir / "module0.py"),
            "-l", "python",
            "--json"
        ])
        assert result1.exit_code == 0
        chunks1 = json.loads(result1.stdout)
        assert len(chunks1) >= 2
        
        # Second command: batch process
        result2 = runner.invoke(app, [
            "batch", str(src_dir),
            "--pattern", "*.py",
            "--jsonl",
            "--quiet"
        ])
        assert result2.exit_code == 0
        lines = result2.stdout.strip().split('\n')
        assert len(lines) >= 6  # At least 2 chunks per file
        
        # Third command: list languages
        result3 = runner.invoke(app, ["languages"])
        assert result3.exit_code == 0
        assert "python" in result3.stdout
    
    def test_glob_pattern_expansion(self, tmp_path):
        """Test complex file pattern matching."""
        # Create nested directory structure
        (tmp_path / "src" / "core").mkdir(parents=True)
        (tmp_path / "src" / "utils").mkdir()
        (tmp_path / "tests").mkdir()
        
        # Create files with different extensions
        files = [
            "src/core/main.py",
            "src/core/config.py",
            "src/utils/helpers.py",
            "src/utils/data.json",
            "tests/test_main.py",
            "tests/test_config.py",
            "README.md"
        ]
        
        for file_path in files:
            full_path = tmp_path / file_path
            if file_path.endswith('.py'):
                full_path.write_text("def test(): pass")
            else:
                full_path.write_text("data")
        
        runner = CliRunner()
        
        # Test various glob patterns
        patterns = [
            ("**/*.py", 5),  # All Python files
            ("src/**/*.py", 3),  # Python files in src
            ("**/test_*.py", 2),  # Test files
            ("src/*/*.py", 3),  # Python files one level deep in src
        ]
        
        for pattern, expected_count in patterns:
            result = runner.invoke(app, [
                "batch", str(tmp_path),
                "--pattern", pattern,
                "--jsonl",
                "--quiet"
            ])
            assert result.exit_code == 0
            
            # Count processed files
            lines = [l for l in result.stdout.strip().split('\n') if l]
            assert len(lines) >= expected_count
    
    def test_recursive_directory_processing(self, tmp_path):
        """Test deep directory traversal."""
        # Create deep directory structure
        deep_path = tmp_path
        for i in range(5):
            deep_path = deep_path / f"level{i}"
            deep_path.mkdir()
            (deep_path / f"module{i}.py").write_text(f"""
def level_{i}_function():
    return {i}
""")
        
        runner = CliRunner()
        
        # Process recursively
        result = runner.invoke(app, [
            "batch", str(tmp_path),
            "--pattern", "**/*.py",
            "--recursive",
            "--jsonl",
            "--quiet"
        ])
        assert result.exit_code == 0
        
        # Should find all 5 files
        lines = result.stdout.strip().split('\n')
        chunks_found = 0
        for line in lines:
            if line:
                try:
                    chunk = json.loads(line)
                    if 'content' in chunk:
                        chunks_found += 1
                except json.JSONDecodeError as e:
                    # Print debug info if JSON parsing fails
                    print(f"Failed to parse line: {repr(line)}")
                    print(f"Error: {e}")
                    if result.stderr:
                        print(f"stderr: {result.stderr}")
        
        assert chunks_found >= 5
    
    def test_mixed_language_batch_processing(self, tmp_path):
        """Test multi-language projects."""
        # Create files in different languages
        files = {
            "app.py": """
def main():
    print("Python app")

class App:
    pass
""",
            "server.js": """
function startServer() {
    console.log("Starting server");
}

class Server {
    constructor() {}
}
""",
            "lib.rs": """
fn process_data() -> i32 {
    42
}

struct DataProcessor {
    value: i32,
}
""",
            "utils.c": """
int calculate(int a, int b) {
    return a + b;
}

struct Point {
    int x;
    int y;
};
"""
        }
        
        for filename, content in files.items():
            (tmp_path / filename).write_text(content)
        
        runner = CliRunner()
        
        # Process all files with auto-detection
        result = runner.invoke(app, [
            "batch", str(tmp_path),
            "--pattern", "*.*",
            "--jsonl",
            "--quiet"
        ])
        
        # Should process files in supported languages
        if result.exit_code == 0:
            lines = result.stdout.strip().split('\n')
            languages_found = set()
            
            for line in lines:
                if line:
                    try:
                        chunk = json.loads(line)
                        if 'language' in chunk:
                            languages_found.add(chunk['language'])
                    except json.JSONDecodeError:
                        pass
            
            # Should detect at least Python
            assert 'python' in languages_found


class TestInteractiveMode:
    """Test interactive mode features."""
    
    @pytest.mark.skip(reason="Interactive mode testing requires TTY")
    def test_interactive_prompt_handling(self, tmp_path):
        """Test user input prompts."""
        # This would require PTY/TTY simulation
        pass
    
    def test_interactive_progress_display(self, tmp_path):
        """Test real-time progress updates."""
        # Create many files for progress testing
        for i in range(20):
            (tmp_path / f"file{i}.py").write_text(f"def func{i}(): pass")
        
        # Run with progress display (default shows progress)
        process = subprocess.Popen(
            [sys.executable, "-m", "cli.main", "batch", str(tmp_path), "--pattern", "*.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(timeout=10)
        
        # Should complete successfully
        assert process.returncode == 0
        
        # Progress information might be in stderr (rich progress bars)
        # Just verify command completed
        assert stdout or stderr
    
    def test_interactive_error_recovery(self, tmp_path):
        """Test error handling in interactive mode."""
        # Create mix of valid and invalid files
        (tmp_path / "good.py").write_text("def good(): pass")
        (tmp_path / "bad.py").write_text("def bad(: syntax error")
        (tmp_path / "empty.py").write_text("")
        
        runner = CliRunner()
        
        # Run with error handling
        result = runner.invoke(app, [
            "batch", str(tmp_path),
            "--pattern", "*.py",
            "--jsonl",
            "--quiet"
        ])
        
        # Should not fail completely
        assert result.exit_code == 0 or result.exit_code == 1
        
        # Should process good file
        if result.stdout:
            assert "good" in result.stdout
    
    def test_interactive_cancellation(self):
        """Test graceful cancellation."""
        # Create a long-running command
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # Create many files
            for i in range(100):
                (tmp_path / f"file{i}.py").write_text(f"def func{i}(): pass\n" * 100)
            
            # Start process
            process = subprocess.Popen(
                [sys.executable, "-m", "cli.main", "batch", str(tmp_path), "--pattern", "*.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Give it time to start
            time.sleep(0.5)
            
            # Send interrupt signal
            process.send_signal(signal.SIGINT)
            
            # Wait for graceful shutdown
            try:
                stdout, stderr = process.communicate(timeout=5)
                # Should exit with interrupt code
                assert process.returncode in [-2, 130]  # SIGINT codes
            except subprocess.TimeoutExpired:
                process.kill()
                pytest.fail("Process did not handle SIGINT gracefully")


class TestSignalHandling:
    """Test signal handling and cleanup."""
    
    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals only")
    def test_sigint_handling(self, tmp_path):
        """Test Ctrl+C handling."""
        # Create test file
        (tmp_path / "test.py").write_text("def test(): pass")
        
        # Start process
        process = subprocess.Popen(
            [sys.executable, "-m", "cli.main", "chunk", str(tmp_path / "test.py"), "-l", "python"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Send SIGINT immediately
        time.sleep(0.1)
        process.send_signal(signal.SIGINT)
        
        # Should exit cleanly
        try:
            process.wait(timeout=2)
            assert process.returncode in [-2, 130]
        except subprocess.TimeoutExpired:
            process.kill()
            pytest.fail("Process did not handle SIGINT")
    
    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals only")
    def test_sigterm_graceful_shutdown(self, tmp_path):
        """Test graceful termination."""
        # Create files
        for i in range(10):
            (tmp_path / f"file{i}.py").write_text("def test(): pass")
        
        # Start batch process
        process = subprocess.Popen(
            [sys.executable, "-m", "cli.main", "batch", str(tmp_path), "--pattern", "*.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Let it start processing
        time.sleep(0.2)
        
        # Send SIGTERM
        process.terminate()
        
        # Should shutdown gracefully
        try:
            process.wait(timeout=5)
            # SIGTERM usually results in exit code 143 or -15
            assert process.returncode != 0
        except subprocess.TimeoutExpired:
            process.kill()
            pytest.fail("Process did not handle SIGTERM gracefully")
    
    def test_cleanup_on_unexpected_exit(self, tmp_path):
        """Test resource cleanup."""
        # Create output directory
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        # Create temp marker file
        marker = output_dir / ".chunker_lock"
        
        # Run command that might create temporary files
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "chunk", __file__, "-l", "python", "--json"],
            capture_output=True,
            text=True,
            cwd=str(output_dir)
        )
        
        # Check no lock files remain
        assert not marker.exists()
        
        # Check no temp files remain
        temp_files = list(output_dir.glob(".chunker_tmp_*"))
        assert len(temp_files) == 0
    
    def test_partial_results_on_interrupt(self, tmp_path):
        """Test saving partial progress."""
        # Create many files
        for i in range(50):
            (tmp_path / f"file{i}.py").write_text(f"def func{i}(): pass")
        
        output_file = tmp_path / "partial_output.jsonl"
        
        # Start process with output file
        process = subprocess.Popen(
            [
                sys.executable, "-m", "cli.main", "batch",
                str(tmp_path), "--pattern", "*.py",
                "--jsonl"
            ],
            stdout=open(output_file, 'w'),
            stderr=subprocess.PIPE
        )
        
        # Let it process some files
        time.sleep(0.5)
        
        # Interrupt
        process.terminate()
        process.wait(timeout=5)
        
        # Check if partial results were saved
        if output_file.exists():
            lines = output_file.read_text().strip().split('\n')
            # Should have saved some results
            assert len(lines) > 0


class TestOutputFormats:
    """Test various output format options."""
    
    def test_custom_output_templates(self, tmp_path):
        """Test custom output formatting."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def hello():
    return "world"

class Test:
    pass
""")
        
        runner = CliRunner()
        
        # Test different output formats
        # Default format
        result1 = runner.invoke(app, ["chunk", str(test_file), "-l", "python"])
        assert result1.exit_code == 0
        assert "hello" in result1.stdout
        
        # JSON format
        result2 = runner.invoke(app, ["chunk", str(test_file), "-l", "python", "--json"])
        assert result2.exit_code == 0
        data = json.loads(result2.stdout)
        assert isinstance(data, list)
        
        # JSONL format  
        result3 = runner.invoke(app, ["chunk", str(test_file), "-l", "python", "--jsonl"])
        assert result3.exit_code == 0
        lines = result3.stdout.strip().split('\n')
        for line in lines:
            json.loads(line)  # Should be valid JSON
    
    def test_output_redirection(self, tmp_path):
        """Test piping and redirection."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass")
        
        # Test pipe to file
        output_file = tmp_path / "output.json"
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "chunk", str(test_file), "-l", "python", "--json"],
            stdout=open(output_file, 'w'),
            stderr=subprocess.PIPE
        )
        
        assert result.returncode == 0
        assert output_file.exists()
        
        # Verify output
        with open(output_file) as f:
            data = json.load(f)
            assert len(data) >= 1
        
        # Test pipe to another command
        result = subprocess.run(
            f"{sys.executable} -m cli.main chunk {test_file} -l python --json | {sys.executable} -m json.tool",
            shell=True,
            capture_output=True,
            text=True
        )
        
        # json.tool formats JSON nicely
        assert result.returncode == 0
        assert "{\n" in result.stdout  # Formatted JSON
    
    def test_quiet_and_verbose_modes(self, tmp_path):
        """Test output verbosity control."""
        test_file = tmp_path / "test.py" 
        test_file.write_text("def test(): pass")
        
        runner = CliRunner()
        
        # Quiet mode
        result_quiet = runner.invoke(app, [
            "chunk", str(test_file), "-l", "python", "--quiet"
        ])
        # In quiet mode, might only output results
        assert result_quiet.exit_code == 0
        
        # Verbose mode
        result_verbose = runner.invoke(app, [
            "chunk", str(test_file), "-l", "python", "--verbose"
        ])
        assert result_verbose.exit_code == 0
        # Verbose should have more output
        assert len(result_verbose.stdout) >= len(result_quiet.stdout)
    
    def test_json_streaming_output(self, tmp_path):
        """Test streaming JSON output."""
        # Create multiple files
        for i in range(5):
            (tmp_path / f"file{i}.py").write_text(f"def func{i}(): pass")
        
        # Run with streaming output
        process = subprocess.Popen(
            [
                sys.executable, "-m", "cli.main", "batch",
                str(tmp_path), "--pattern", "*.py",
                "--jsonl", "--quiet"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1  # Line buffered
        )
        
        # Read streaming output
        chunks_received = 0
        for line in process.stdout:
            if line.strip():
                try:
                    json.loads(line)
                    chunks_received += 1
                except json.JSONDecodeError:
                    pass
        
        process.wait()
        assert chunks_received >= 5


class TestErrorScenarios:
    """Test error handling scenarios."""
    
    def test_invalid_option_combinations(self):
        """Test conflicting options."""
        runner = CliRunner()
        
        # Conflicting output formats
        result = runner.invoke(app, [
            "chunk", __file__, "-l", "python",
            "--json", "--jsonl"  # Can't use both
        ])
        # Should fail or warn
        assert result.exit_code != 0 or "warning" in result.stdout.lower()
        
        # Invalid language
        result = runner.invoke(app, [
            "chunk", __file__, "-l", "invalid_language"
        ])
        assert result.exit_code != 0
        assert "language" in result.stdout.lower() or "language" in result.stderr
        
        # Missing required options
        result = runner.invoke(app, ["chunk", __file__])  # No language specified
        # Should fail or auto-detect
        assert result.exit_code != 0 or "python" in result.stdout.lower()
    
    def test_missing_dependencies_handling(self, tmp_path):
        """Test missing language support."""
        # Create file with unsupported extension
        unsupported_file = tmp_path / "test.xyz"
        unsupported_file.write_text("content")
        
        runner = CliRunner()
        
        result = runner.invoke(app, [
            "chunk", str(unsupported_file), "-l", "xyz"
        ])
        
        # Should provide helpful error
        assert result.exit_code != 0
        assert "not supported" in result.stdout.lower() or "not found" in result.stdout.lower()
    
    def test_filesystem_permission_errors(self, tmp_path):
        """Test permission denied scenarios."""
        # Skip on Windows where permissions work differently
        if sys.platform == "win32":
            pytest.skip("Unix permissions test")
        
        # Create read-only file
        readonly_file = tmp_path / "readonly.py"
        readonly_file.write_text("def test(): pass")
        readonly_file.chmod(0o444)
        
        # Create directory without write permission
        readonly_dir = tmp_path / "readonly_dir"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o555)
        
        runner = CliRunner()
        
        # Try to write output to readonly directory
        result = runner.invoke(app, [
            "chunk", str(readonly_file), "-l", "python",
            "--output", str(readonly_dir / "output.json")
        ])
        
        # Should handle permission error gracefully
        assert result.exit_code != 0
        assert "permission" in result.stdout.lower() or "permission" in str(result.exception).lower()
        
        # Cleanup
        readonly_dir.chmod(0o755)
        readonly_file.chmod(0o644)
    
    def test_network_timeout_handling(self, tmp_path):
        """Test remote operation timeouts."""
        # This would test features like remote file access or API calls
        # For now, test with a non-existent network path
        
        runner = CliRunner()
        
        # Try to access non-existent network resource
        result = runner.invoke(app, [
            "chunk", "http://non-existent-host-12345.com/file.py",
            "-l", "python",
            "--timeout", "1"  # 1 second timeout
        ])
        
        # Should fail gracefully
        assert result.exit_code != 0
        # Error message should mention network/timeout/connection
        error_keywords = ["timeout", "connection", "network", "failed", "error"]
        assert any(keyword in result.stdout.lower() for keyword in error_keywords)


def test_cli_version():
    """Test version command."""
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.stdout.lower()


def test_cli_help():
    """Test help command."""
    runner = CliRunner()
    
    # Main help
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "chunk" in result.stdout
    assert "batch" in result.stdout
    
    # Command-specific help
    result = runner.invoke(app, ["chunk", "--help"])
    assert result.exit_code == 0
    assert "language" in result.stdout or "-l" in result.stdout


def test_cli_config_file_loading(tmp_path):
    """Test configuration file loading."""
    # Create config file
    config_file = tmp_path / ".chunkerrc.toml"
    config_file.write_text("""
[general]
default_language = "python"
min_chunk_size = 5

[output]
default_format = "json"
""")
    
    test_file = tmp_path / "test.py"
    test_file.write_text("""
def tiny():
    pass

def larger_function():
    # Line 1
    # Line 2
    # Line 3
    # Line 4
    # Line 5
    pass
""")
    
    runner = CliRunner()
    
    # Run with config
    result = runner.invoke(app, [
        "chunk", str(test_file),
        "--config", str(config_file)
    ])
    
    # Config should be applied
    assert result.exit_code == 0
    # With min_chunk_size=5, tiny() should be filtered out
    if "--json" in result.stdout or result.stdout.startswith('['):
        data = json.loads(result.stdout)
        # Should only have larger_function
        assert all("tiny" not in chunk.get("content", "") for chunk in data)
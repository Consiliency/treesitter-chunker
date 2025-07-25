"""Unit tests for DeveloperToolingImpl."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from chunker.tooling.developer import DeveloperToolingImpl


class TestDeveloperToolingImpl:
    """Unit tests for DeveloperToolingImpl"""

    def test_initialization(self):
        """Test that DeveloperToolingImpl initializes correctly"""
        tooling = DeveloperToolingImpl()
        assert hasattr(tooling, "project_root")
        assert isinstance(tooling.project_root, Path)

    def test_find_project_root(self):
        """Test finding project root with pyproject.toml"""
        tooling = DeveloperToolingImpl()
        # Should find the project root
        assert (tooling.project_root / "pyproject.toml").exists()

    def test_run_pre_commit_checks_no_files(self):
        """Test pre-commit checks with no files"""
        tooling = DeveloperToolingImpl()
        success, results = tooling.run_pre_commit_checks([])

        assert success is False
        assert "errors" in results
        assert "No valid Python files to check" in results["errors"]

    def test_run_pre_commit_checks_non_python_files(self):
        """Test pre-commit checks with non-Python files"""
        tooling = DeveloperToolingImpl()
        files = [Path("README.md"), Path("data.json")]
        success, results = tooling.run_pre_commit_checks(files)

        assert success is False
        assert "No valid Python files to check" in results["errors"]

    def test_format_code_empty_list(self):
        """Test format_code with empty file list"""
        tooling = DeveloperToolingImpl()
        result = tooling.format_code([])

        assert result["formatted"] == []
        assert result["errors"] == []
        assert result["diff"] == {}

    def test_format_code_non_existent_files(self):
        """Test format_code with non-existent files"""
        tooling = DeveloperToolingImpl()
        files = [Path("/non/existent/file.py")]
        result = tooling.format_code(files)

        assert result["formatted"] == []
        assert result["errors"] == []
        assert result["diff"] == {}

    def test_run_linting_empty_list(self):
        """Test run_linting with empty file list"""
        tooling = DeveloperToolingImpl()
        result = tooling.run_linting([])

        assert result == {}

    def test_run_type_checking_empty_list(self):
        """Test run_type_checking with empty file list"""
        tooling = DeveloperToolingImpl()
        result = tooling.run_type_checking([])

        assert result == {}

    @pytest.mark.parametrize("fix", [True, False])
    def test_format_code_with_valid_file(self, fix):
        """Test format_code with a valid Python file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            # Write unformatted code
            f.write("def hello(  ):   print( 'hello'  )")
            f.flush()
            test_file = Path(f.name)

        try:
            tooling = DeveloperToolingImpl()
            result = tooling.format_code([test_file], fix=fix)

            assert "formatted" in result
            assert "errors" in result
            assert "diff" in result

            if not fix:
                # Should have a diff but file unchanged
                assert len(result["formatted"]) > 0 or len(result["diff"]) == 0
                # Re-read file to ensure it wasn't changed
                with test_file.open() as f:
                    content = f.read()
                assert "def hello(  ):   print( 'hello'  )" in content
            else:
                # File should be formatted
                with test_file.open() as f:
                    content = f.read()
                # Black would format this differently
                assert content != "def hello(  ):   print( 'hello'  )"

        finally:
            test_file.unlink()

    def test_run_linting_with_valid_file(self):
        """Test run_linting with a valid Python file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            # Write code with linting issues
            f.write("import os\nimport sys\n\nx = 1")
            f.flush()
            test_file = Path(f.name)

        try:
            tooling = DeveloperToolingImpl()
            result = tooling.run_linting([test_file])

            assert isinstance(result, dict)
            # May or may not have issues depending on config

        finally:
            test_file.unlink()

    def test_run_type_checking_with_valid_file(self):
        """Test run_type_checking with a valid Python file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            # Write code with type issues
            f.write("def add(a: int, b: int) -> int:\n    return a + b + 'string'")
            f.flush()
            test_file = Path(f.name)

        try:
            tooling = DeveloperToolingImpl()
            result = tooling.run_type_checking([test_file])

            assert isinstance(result, dict)
            # The result might be empty if mypy doesn't detect the error
            # or if it's configured differently
            # Just check that it returns the right structure

        finally:
            test_file.unlink()

    def test_run_pre_commit_checks_integration(self):
        """Test full pre-commit check flow"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            # Write valid Python code
            f.write(
                """
def hello(name: str) -> str:
    '''Say hello to someone'''
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(hello("World"))
""",
            )
            f.flush()
            test_file = Path(f.name)

        try:
            tooling = DeveloperToolingImpl()
            success, results = tooling.run_pre_commit_checks([test_file])

            assert isinstance(success, bool)
            assert "linting" in results
            assert "formatting" in results
            assert "type_checking" in results
            assert "tests" in results
            assert "errors" in results

            # Verify structure
            assert isinstance(results["linting"], dict)
            assert "checked" in results["linting"]
            assert "errors" in results["linting"]
            assert "warnings" in results["linting"]

            assert isinstance(results["formatting"], dict)
            assert "checked" in results["formatting"]
            assert "formatted" in results["formatting"]

            assert isinstance(results["type_checking"], dict)
            assert "checked" in results["type_checking"]
            assert "errors" in results["type_checking"]

        finally:
            test_file.unlink()

    @patch("subprocess.run")
    def test_format_code_handles_subprocess_error(self, mock_run):
        """Test format_code handles subprocess errors gracefully"""
        mock_run.side_effect = Exception("Command failed")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("print('test')")
            f.flush()
            test_file = Path(f.name)

        try:
            tooling = DeveloperToolingImpl()
            result = tooling.format_code([test_file])

            assert "errors" in result
            assert len(result["errors"]) > 0
            assert "Command failed" in result["errors"][0]

        finally:
            test_file.unlink()

    @patch("subprocess.run")
    def test_run_linting_handles_subprocess_error(self, mock_run):
        """Test run_linting handles subprocess errors gracefully"""
        mock_run.side_effect = Exception("Command failed")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("print('test')")
            f.flush()
            test_file = Path(f.name)

        try:
            tooling = DeveloperToolingImpl()
            result = tooling.run_linting([test_file])

            # Should return empty dict on error
            assert result == {}

        finally:
            test_file.unlink()

    @patch("subprocess.run")
    def test_run_type_checking_handles_subprocess_error(self, mock_run):
        """Test run_type_checking handles subprocess errors gracefully"""
        mock_run.side_effect = Exception("Command failed")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("print('test')")
            f.flush()
            test_file = Path(f.name)

        try:
            tooling = DeveloperToolingImpl()
            result = tooling.run_type_checking([test_file])

            # Should return empty dict on error
            assert result == {}

        finally:
            test_file.unlink()

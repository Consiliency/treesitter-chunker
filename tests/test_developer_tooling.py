"""Unit tests for DeveloperToolingImpl."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from chunker.tooling.developer import DeveloperToolingImpl


class TestDeveloperToolingImpl:
    """Unit tests for DeveloperToolingImpl"""

    @classmethod
    def test_initialization(cls):
        """Test that DeveloperToolingImpl initializes correctly"""
        tooling = DeveloperToolingImpl()
        assert hasattr(tooling, "project_root")
        assert isinstance(tooling.project_root, Path)

    @classmethod
    def test_find_project_root(cls):
        """Test finding project root with pyproject.toml"""
        tooling = DeveloperToolingImpl()
        assert (tooling.project_root / "pyproject.toml").exists()

    @classmethod
    def test_run_pre_commit_checks_no_files(cls):
        """Test pre-commit checks with no files"""
        tooling = DeveloperToolingImpl()
        success, results = tooling.run_pre_commit_checks([])
        assert success is False
        assert "errors" in results
        assert "No valid Python files to check" in results["errors"]

    @classmethod
    def test_run_pre_commit_checks_non_python_files(cls):
        """Test pre-commit checks with non-Python files"""
        tooling = DeveloperToolingImpl()
        files = [Path("README.md"), Path("data.json")]
        success, results = tooling.run_pre_commit_checks(files)
        assert success is False
        assert "No valid Python files to check" in results["errors"]

    @classmethod
    def test_format_code_empty_list(cls):
        """Test format_code with empty file list"""
        tooling = DeveloperToolingImpl()
        result = tooling.format_code([])
        assert result["formatted"] == []
        assert result["errors"] == []
        assert result["diff"] == {}

    @classmethod
    def test_format_code_non_existent_files(cls):
        """Test format_code with non-existent files"""
        tooling = DeveloperToolingImpl()
        files = [Path("/non/existent/file.py")]
        result = tooling.format_code(files)
        assert result["formatted"] == []
        assert result["errors"] == []
        assert result["diff"] == {}

    @classmethod
    def test_run_linting_empty_list(cls):
        """Test run_linting with empty file list"""
        tooling = DeveloperToolingImpl()
        result = tooling.run_linting([])
        assert result == {}

    @classmethod
    def test_run_type_checking_empty_list(cls):
        """Test run_type_checking with empty file list"""
        tooling = DeveloperToolingImpl()
        result = tooling.run_type_checking([])
        assert result == {}

    @classmethod
    @pytest.mark.parametrize("fix", [True, False])
    def test_format_code_with_valid_file(cls, fix):
        """Test format_code with a valid Python file"""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
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
                assert len(result["formatted"]) > 0 or len(result["diff"]) == 0
                with test_file.open(encoding="utf-8") as f:
                    content = f.read()
                assert "def hello(  ):   print( 'hello'  )" in content
            else:
                with test_file.open(encoding="utf-8") as f:
                    content = f.read()
                assert content != "def hello(  ):   print( 'hello'  )"
        finally:
            test_file.unlink()

    @classmethod
    def test_run_linting_with_valid_file(cls):
        """Test run_linting with a valid Python file"""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write("import os\nimport sys\n\nx = 1")
            f.flush()
            test_file = Path(f.name)
        try:
            tooling = DeveloperToolingImpl()
            result = tooling.run_linting([test_file])
            assert isinstance(result, dict)
        finally:
            test_file.unlink()

    @classmethod
    def test_run_type_checking_with_valid_file(cls):
        """Test run_type_checking with a valid Python file"""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write("def add(a: int, b: int) -> int:\n    return a + b + 'string'")
            f.flush()
            test_file = Path(f.name)
        try:
            tooling = DeveloperToolingImpl()
            result = tooling.run_type_checking([test_file])
            assert isinstance(result, dict)
        finally:
            test_file.unlink()

    @classmethod
    def test_run_pre_commit_checks_integration(cls):
        """Test full pre-commit check flow"""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
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

    @classmethod
    @patch("subprocess.run")
    def test_format_code_handles_subprocess_error(cls, mock_run):
        """Test format_code handles subprocess errors gracefully"""
        mock_run.side_effect = Exception("Command failed")
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
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

    @classmethod
    @patch("subprocess.run")
    def test_run_linting_handles_subprocess_error(cls, mock_run):
        """Test run_linting handles subprocess errors gracefully"""
        mock_run.side_effect = Exception("Command failed")
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write("print('test')")
            f.flush()
            test_file = Path(f.name)
        try:
            tooling = DeveloperToolingImpl()
            result = tooling.run_linting([test_file])
            assert result == {}
        finally:
            test_file.unlink()

    @classmethod
    @patch("subprocess.run")
    def test_run_type_checking_handles_subprocess_error(cls, mock_run):
        """Test run_type_checking handles subprocess errors gracefully"""
        mock_run.side_effect = Exception("Command failed")
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write("print('test')")
            f.flush()
            test_file = Path(f.name)
        try:
            tooling = DeveloperToolingImpl()
            result = tooling.run_type_checking([test_file])
            assert result == {}
        finally:
            test_file.unlink()

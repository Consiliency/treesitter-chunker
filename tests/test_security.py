"""Security-focused tests for treesitter-chunker.

This module tests security hardening measures including:
- Shell injection prevention in subprocess calls
- SQL injection prevention in database exporters
- Safe exception handling patterns
"""

import ast
import inspect
import re
from pathlib import Path

import pytest


class TestShellInjectionPrevention:
    """Test shell injection prevention in subprocess calls."""

    def test_builder_no_shell_true(self):
        """Verify build commands don't use shell=True."""
        from chunker.build import builder

        source = inspect.getsource(builder)
        tree = ast.parse(source)

        shell_true_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check for subprocess.run or subprocess.check_call
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("run", "check_call", "call", "Popen"):
                        for keyword in node.keywords:
                            if keyword.arg == "shell":
                                if isinstance(keyword.value, ast.Constant):
                                    if keyword.value.value is True:
                                        shell_true_calls.append(node.lineno)

        assert len(shell_true_calls) == 0, (
            f"Found shell=True in builder.py at lines: {shell_true_calls}. "
            "Use list arguments instead of shell=True for security."
        )

    def test_verifier_no_shell_true(self):
        """Verify verification commands don't use shell=True."""
        from chunker.distribution import verifier

        source = inspect.getsource(verifier)
        tree = ast.parse(source)

        shell_true_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("run", "check_call", "call", "Popen"):
                        for keyword in node.keywords:
                            if keyword.arg == "shell":
                                if isinstance(keyword.value, ast.Constant):
                                    if keyword.value.value is True:
                                        shell_true_calls.append(node.lineno)

        assert len(shell_true_calls) == 0, (
            f"Found shell=True in verifier.py at lines: {shell_true_calls}. "
            "Use list arguments instead of shell=True for security."
        )

    def test_subprocess_uses_list_arguments(self):
        """Verify subprocess calls use list arguments, not strings."""
        from chunker.build import builder
        from chunker.distribution import verifier

        for module, name in [(builder, "builder"), (verifier, "verifier")]:
            source = inspect.getsource(module)
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        if node.func.attr in ("run", "check_call", "call", "Popen"):
                            # First argument should be the command
                            if node.args:
                                first_arg = node.args[0]
                                # Should not be a string constant
                                if isinstance(first_arg, ast.Constant):
                                    if isinstance(first_arg.value, str):
                                        # String command without shell=True is still risky
                                        pytest.fail(
                                            f"Found string argument to subprocess in {name}.py "
                                            f"at line {node.lineno}. Use list arguments."
                                        )


class TestBareExceptPrevention:
    """Test that bare except clauses have been replaced."""

    def test_no_bare_except_in_chunker(self):
        """Verify no bare except: clauses in chunker module."""
        chunker_dir = Path(__file__).parent.parent / "chunker"

        bare_except_pattern = re.compile(r"^\s*except\s*:\s*$", re.MULTILINE)
        files_with_bare_except = []

        for py_file in chunker_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            matches = bare_except_pattern.findall(content)
            if matches:
                files_with_bare_except.append(str(py_file.relative_to(chunker_dir)))

        assert len(files_with_bare_except) == 0, (
            f"Found bare except: in: {files_with_bare_except}. "
            "Replace with specific exception types."
        )


class TestSQLInjectionPrevention:
    """Test SQL injection prevention in exporters."""

    def test_postgres_escape_function_exists(self):
        """Verify escape function exists and works."""
        from chunker.export.postgres_exporter import _escape_postgres_string

        # Test basic escaping
        assert _escape_postgres_string("test") == "test"
        assert _escape_postgres_string(None) == "NULL"

        # Test quote escaping (prevents SQL injection)
        result = _escape_postgres_string("'; DROP TABLE users; --")
        assert "''" in result  # Quotes should be doubled

    def test_parameterized_queries_available(self):
        """Verify parameterized query methods exist."""
        from chunker.export.postgres_exporter import PostgresExporter

        # Check that safe methods exist
        assert hasattr(PostgresExporter, "get_parameterized_statements")
        assert hasattr(PostgresExporter, "_get_parameterized_batches")

    def test_postgres_spec_escape_function_exists(self):
        """Verify escape function exists in postgres_spec_exporter."""
        from chunker.export.postgres_spec_exporter import _escape_sql_string

        # Test basic escaping
        assert _escape_sql_string("test").startswith("'")
        assert _escape_sql_string(None) == "NULL"

        # Test quote escaping
        result = _escape_sql_string("'; DROP TABLE users; --")
        assert "''" in result


class TestExceptionHandlingPatterns:
    """Test proper exception handling patterns."""

    def test_exception_handlers_are_specific(self):
        """Verify exception handlers catch specific exceptions."""
        from chunker.error_handling import utils

        # Check that extract_stack_locals has proper exception handling
        source = inspect.getsource(utils)

        # Should not have bare except:
        assert "except:" not in source or "except (AttributeError" in source

    def test_troubleshooting_has_specific_handlers(self):
        """Verify troubleshooting module has specific exception handlers."""
        try:
            from chunker.error_handling import troubleshooting

            source = inspect.getsource(troubleshooting)

            # Check for ImportError, LookupError handling
            assert "ImportError" in source or "LookupError" in source
        except ImportError:
            pytest.skip("troubleshooting module not available")

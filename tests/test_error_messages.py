"""Tests for improved error messages with actionable guidance."""

from __future__ import annotations

import argparse
import re
import shlex
from importlib.metadata import distribution

from typer.testing import CliRunner

from chunker.cli.grammar_commands import setup_grammar_parser
from chunker.exceptions import LanguageNotFoundError


class TestLanguageNotFoundErrorMessages:
    """Tests for LanguageNotFoundError message improvements."""

    def test_error_includes_language_name(self):
        """Test that error message includes the requested language name."""
        error = LanguageNotFoundError("python", [])
        assert "python" in str(error)

    def test_error_includes_available_languages(self):
        """Test that error message lists available languages."""
        error = LanguageNotFoundError("kotlin", ["python", "javascript"])
        error_str = str(error)
        assert "python" in error_str
        assert "javascript" in error_str

    def test_error_includes_language_pack_guidance(self):
        """Test that error message mentions tree-sitter-language-pack."""
        error = LanguageNotFoundError("unknown_lang", [])
        error_str = str(error)
        # Should suggest installing the language pack
        assert "tree-sitter-language-pack" in error_str or "language-pack" in error_str

    def test_guidance_names_registered_cli_commands(self):
        guidance = str(LanguageNotFoundError("rust", []))
        commands = re.findall(
            r"(?<![\w/-])((?:treesitter-chunker|tsc) [^\n]+)", guidance
        )
        assert commands, "Missing installed grammar build command"
        scripts = distribution("treesitter-chunker").entry_points.select(
            group="console_scripts"
        )
        for command in commands:
            program, *arguments = shlex.split(command)
            result = CliRunner().invoke(scripts[program].load(), [*arguments, "--help"])
            assert result.exit_code == 0, f"{command}\n{result.output}"

    def test_guidance_explains_pin_sources(self):
        guidance = str(LanguageNotFoundError("rust", []))
        assert "SHA-256" in guidance and "trusted-artifacts.json" in guidance
        command = re.search(r"python -m chunker\.cli ([^\n]+)", guidance)
        assert command
        parser = argparse.ArgumentParser()
        setup_grammar_parser(parser.add_subparsers())
        args = parser.parse_args(shlex.split(command[1]))
        assert args.grammar_command == "info"
        assert args.language == "rust"
        assert args.trusted_artifacts is not None

    def test_error_includes_available_count(self):
        """Test that error message includes count of available languages."""
        available = ["python", "javascript", "typescript", "rust", "go"]
        error = LanguageNotFoundError("kotlin", available)
        error_str = str(error)
        # Should indicate how many languages are available
        assert "5" in error_str or "available" in error_str.lower()

    def test_error_includes_documentation_link(self):
        """Test that error message includes documentation link."""
        error = LanguageNotFoundError("unknown_lang", [])
        error_str = str(error)
        # Should include a link to documentation
        assert (
            "github.com" in error_str.lower()
            or "docs" in error_str.lower()
            or "http" in error_str.lower()
        )

    def test_error_message_is_actionable(self):
        """Test that error message provides clear next steps."""
        error = LanguageNotFoundError("rust", [])
        error_str = str(error)
        # Should have actionable guidance (numbered steps or clear instructions)
        has_steps = any(
            indicator in error_str
            for indicator in ["1.", "2.", "To fix", "Try", "Install", "Run"]
        )
        assert has_steps, f"Error message should be actionable: {error_str}"

    def test_error_with_no_languages_available(self):
        """Test error message when no languages are available at all."""
        error = LanguageNotFoundError("python", [])
        error_str = str(error)
        # Should indicate fresh install situation and provide setup guidance
        assert "language-pack" in error_str.lower() or "install" in error_str.lower()

    def test_error_attributes_preserved(self):
        """Test that error object has correct attributes."""
        error = LanguageNotFoundError("python", ["javascript", "rust"])
        assert error.language == "python"
        assert error.available == ["javascript", "rust"]

    def test_error_details_dict(self):
        """Test that error details dictionary is populated correctly."""
        error = LanguageNotFoundError("python", ["javascript"])
        assert error.details["requested"] == "python"
        assert "javascript" in error.details["available"]

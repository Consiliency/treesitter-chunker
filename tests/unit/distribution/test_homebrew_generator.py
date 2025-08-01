"""Unit tests for Homebrew formula generator"""
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from chunker.distribution.homebrew_generator import HomebrewFormulaGenerator


class TestHomebrewFormulaGenerator:
    """Test Homebrew formula generation"""

    @classmethod
    def test_generate_formula_basic(cls):
        """Test basic formula generation"""
        generator = HomebrewFormulaGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "formula.rb"
            success, formula_path = generator.generate_formula("1.0.0",
                output_path)
            assert success
            assert formula_path.exists()
            content = formula_path.read_text()
            assert "class TreesitterChunker" in content
            assert 'version "1.0.0"' in content or "treesitter-chunker-1.0.0" in content
            assert 'depends_on "python@3.9"' in content

    @classmethod
    def test_version_validation(cls):
        """Test semantic version validation"""
        generator = HomebrewFormulaGenerator()
        assert generator._validate_version("1.0.0")
        assert generator._validate_version("0.1.0")
        assert generator._validate_version("2.3.4")
        assert generator._validate_version("1.0")
        assert not generator._validate_version("1")
        assert not generator._validate_version("1.0.0.0")
        assert not generator._validate_version("v1.0.0")
        assert not generator._validate_version("1.0.alpha")

    @classmethod
    def test_formula_directory_creation(cls):
        """Test formula directory is created if needed"""
        generator = HomebrewFormulaGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "homebrew" / "formula.rb"
            success, formula_path = generator.generate_formula("1.0.0",
                output_path)
            assert success
            assert formula_path.exists()
            assert formula_path.parent.exists()

    @classmethod
    def test_formula_in_directory(cls):
        """Test formula generation when output_path is a directory"""
        generator = HomebrewFormulaGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            success, formula_path = generator.generate_formula("1.0.0",
                output_dir)
            assert success
            assert formula_path.name == "treesitter-chunker.rb"
            assert formula_path.parent == output_dir

    @classmethod
    @patch("urllib.request.urlopen")
    def test_update_sha256(cls, mock_urlopen):
        """Test SHA256 hash update in formula"""
        generator = HomebrewFormulaGenerator()
        mock_response = Mock()
        mock_response.read.return_value = b"fake package data"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        with tempfile.TemporaryDirectory() as tmpdir:
            formula_path = Path(tmpdir) / "formula.rb"
            formula_path.write_text('sha256 "PLACEHOLDER_SHA256"')
            success = generator.update_sha256(formula_path,
                "https://example.com/package.tar.gz")
            assert success
            content = formula_path.read_text()
            assert "PLACEHOLDER_SHA256" not in content
            import re
            assert re.search(r'sha256 "[a-f0-9]{64}"', content)

    @classmethod
    def test_validate_formula_missing_file(cls):
        """Test formula validation with missing file"""
        generator = HomebrewFormulaGenerator()
        success, issues = generator.validate_formula(Path(
            "/nonexistent/formula.rb"))
        assert not success
        assert "Formula file does not exist" in issues

    @classmethod
    @patch("subprocess.run")
    def test_validate_formula_with_brew(cls, mock_run):
        """Test formula validation when brew is available"""
        mock_run.side_effect = [Mock(returncode=0), Mock(returncode=1,
            stderr="Error: formula issue")]
        generator = HomebrewFormulaGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            formula_path = Path(tmpdir) / "formula.rb"
            formula_path.write_text("class TreesitterChunker < Formula\nend")
            success, issues = generator.validate_formula(formula_path)
            assert not success
            assert "Error: formula issue" in issues

    @classmethod
    @patch("subprocess.run")
    def test_validate_formula_without_brew(cls, mock_run):
        """Test formula validation when brew is not available"""
        mock_run.return_value = Mock(returncode=1)
        generator = HomebrewFormulaGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            formula_path = Path(tmpdir) / "formula.rb"
            formula_path.write_text("invalid formula")
            success, issues = generator.validate_formula(formula_path)
            assert not success
            assert any("Missing class definition" in issue for issue in issues)
            valid_content = """class TreesitterChunker < Formula
  desc "Language-agnostic code chunking"
  homepage "https://github.com/example/repo"
  url "https://example.com/package.tar.gz"
  sha256 "abc123"
  license "MIT"
end"""
            formula_path.write_text(valid_content)
            success, issues = generator.validate_formula(formula_path)
            assert success
            assert len(issues) == 0

    @classmethod
    def test_get_package_info(cls):
        """Test package info extraction"""
        generator = HomebrewFormulaGenerator()
        info = generator._get_package_info()
        assert info["name"] == "treesitter-chunker"
        assert "description" in info
        assert "homepage" in info
        assert "license" in info
        assert "dependencies" in info

    @classmethod
    @patch("pathlib.Path.exists")
    def test_get_package_info_from_pyproject(cls, mock_exists):
        """Test package info extraction from pyproject.toml"""
        mock_exists.return_value = True
        with patch("builtins.open", create=True) as mock_open:
            (mock_open.return_value.__enter__.return_value.read.return_value
                ) = (
                b'\n[project]\ndescription = "Custom description"\nlicense = {text = "Apache-2.0"}\n'
                )
            with patch("tomllib.load") as mock_load:
                mock_load.return_value = {"project": {"description":
                    "Custom description", "license": {"text": "Apache-2.0"}}}
                generator = HomebrewFormulaGenerator()
                info = generator._get_package_info()
                assert info["description"] == "Custom description"
                assert info["license"] == "Apache-2.0"

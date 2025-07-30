"""
Homebrew Formula Generator

Creates Homebrew formulas for macOS distribution
"""

import hashlib
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

import tomllib


class HomebrewFormulaGenerator:
    """Generates Homebrew formulas for package distribution"""

    def generate_formula(
        self,
        version: str,
        output_path: Path,
        package_info: dict[str, Any] | None = None,
    ) -> tuple[bool, Path]:
        """
        Generate Homebrew formula for macOS distribution

        Args:
            version: Package version
            output_path: Path for formula file
            package_info: Optional package metadata

        Returns:
            Tuple of (success, formula_path)
        """
        # Get package info if not provided
        if package_info is None:
            package_info = self._get_package_info()

        # Validate version format
        if not self._validate_version(version):
            return False, Path()

        # Generate formula content
        formula_content = self._generate_formula_content(version, package_info)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write formula file
        formula_path = output_path
        if output_path.is_dir():
            formula_path = output_path / "treesitter-chunker.rb"

        try:
            with Path(formula_path).open("w") as f:
                f.write(formula_content)
            return True, formula_path
        except (FileNotFoundError, OSError):
            return False, Path()

    def _validate_version(self, version: str) -> bool:
        """Validate version follows semantic versioning"""
        parts = version.split(".")
        if len(parts) < 2 or len(parts) > 3:
            return False

        try:
            for part in parts:
                int(part)
            return True
        except ValueError:
            return False

    def _get_package_info(self) -> dict[str, Any]:
        """Get package metadata from pyproject.toml or setup.py"""
        info = {
            "name": "treesitter-chunker",
            "description": "Language-agnostic code chunking using tree-sitter",
            "homepage": "https://github.com/aorwall/treesitter-chunker",
            "license": "MIT",
            "dependencies": [
                "python@3.9",
                "tree-sitter",
            ],
        }

        # Try to read from pyproject.toml
        pyproject_path = Path("pyproject.toml")
        if pyproject_path.exists():
            try:

                with Path(pyproject_path).open("rb") as f:
                    data = tomllib.load(f)
                    project = data.get("project", {})
                    info["description"] = project.get(
                        "description",
                        info["description"],
                    )
                    info["license"] = project.get("license", {}).get(
                        "text",
                        info["license"],
                    )
            except (AttributeError, IndexError, KeyError):
                pass  # Use defaults

        return info

    def _generate_formula_content(
        self,
        version: str,
        package_info: dict[str, Any],
    ) -> str:
        """Generate the Homebrew formula content"""
        # Formula template - use format() to avoid f-string issues with Ruby interpolation
        formula = """class TreesitterChunker < Formula
  desc "{description}"
  homepage "{homepage}"
  url "https://files.pythonhosted.org/packages/source/t/treesitter-chunker/treesitter-chunker-{version}.tar.gz"
  sha256 "PLACEHOLDER_SHA256"
  license "{license}"

  depends_on "python@3.9"
  depends_on "tree-sitter"

  resource "tree-sitter" do
    url "https://files.pythonhosted.org/packages/source/t/tree-sitter/tree-sitter-0.20.4.tar.gz"
    sha256 "6adb123e2f3e56399bbf2359924633c882cc40ee8344885200bca0922f713be5"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{{bin}}/chunker", "--version"

    # Test basic functionality
    (testpath/"test.py").write <<~EOS
      def hello():
          print("Hello, world!")
    EOS

    output = shell_output("#{{bin}}/chunker chunk #{{testpath}}/test.py -l python")
    assert_match "hello", output
  end
end
""".format(
            description=package_info["description"],
            homepage=package_info["homepage"],
            version=version,
            license=package_info["license"],
        )
        return formula

    def update_sha256(self, formula_path: Path, package_url: str) -> bool:
        """Update the SHA256 hash in the formula"""
        try:
            # Download the package to calculate SHA256
            with urllib.request.urlopen(package_url) as response:
                data = response.read()
                sha256 = hashlib.sha256(data).hexdigest()

            # Read formula
            with Path(formula_path).open("r") as f:
                content = f.read()

            # Replace placeholder
            content = content.replace("PLACEHOLDER_SHA256", sha256)

            # Write back
            with Path(formula_path).open("w") as f:
                f.write(content)

            return True
        except (OSError, FileNotFoundError, IndexError):
            return False

    def validate_formula(self, formula_path: Path) -> tuple[bool, list[str]]:
        """Validate the generated formula"""
        issues = []

        if not formula_path.exists():
            issues.append("Formula file does not exist")
            return False, issues

        # Check formula syntax
        brew_cmd = subprocess.run(
            ["brew", "--version"],
            capture_output=True,
            check=False,
        )

        if brew_cmd.returncode == 0:
            # Brew is available, use it to audit
            audit_result = subprocess.run(
                ["brew", "audit", "--new-formula", str(formula_path)],
                capture_output=True,
                text=True,
                check=False,
            )

            if audit_result.returncode != 0:
                issues.extend(audit_result.stderr.strip().split("\n"))
        else:
            # Basic validation without brew
            with Path(formula_path).open("r") as f:
                content = f.read()

            if "PLACEHOLDER_SHA256" in content:
                issues.append("SHA256 hash not updated")

            if "class TreesitterChunker" not in content:
                issues.append("Missing class definition")

            required_fields = ["desc", "homepage", "url", "license"]
            for field in required_fields:
                if f'{field} "' not in content:
                    issues.append(f"Missing required field: {field}")

        return len(issues) == 0, issues

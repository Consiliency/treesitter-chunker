#!/usr/bin/env python3
"""Comprehensive quality assurance check for the codebase."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class QualityChecker:
    """Performs comprehensive quality checks."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.results = {}

    def check_file_structure(self) -> dict[str, any]:
        """Check project file structure and organization."""
        print("🔍 Checking file structure...")

        structure = {
            "has_readme": (self.project_root / "README.md").exists(),
            "has_docs_dir": (self.project_root / "docs").exists(),
            "has_tests_dir": (self.project_root / "tests").exists(),
            "has_scripts_dir": (self.project_root / "scripts").exists(),
            "has_archive_dir": (self.project_root / "archive").exists(),
            "has_changelog": (self.project_root / "CHANGELOG.md").exists(),
            "has_contributing": (self.project_root / "CONTRIBUTING.md").exists(),
            "has_security": (self.project_root / "SECURITY.md").exists(),
            "has_support": (self.project_root / "SUPPORT.md").exists(),
            "has_deployment": (self.project_root / "DEPLOYMENT.md").exists(),
        }

        return structure

    def check_documentation_coverage(self) -> dict[str, any]:
        """Check documentation coverage and quality."""
        print("🔍 Checking documentation coverage...")

        coverage = {
            "readme_length": 0,
            "docs_count": 0,
            "api_docs_exist": False,
            "examples_exist": False,
            "installation_guide": False,
        }

        # Check README
        readme_path = self.project_root / "README.md"
        if readme_path.exists():
            content = readme_path.read_text(encoding="utf-8")
            coverage["readme_length"] = len(content.split("\n"))
            coverage["installation_guide"] = (
                "install" in content.lower() or "setup" in content.lower()
            )

        # Check docs directory
        docs_dir = self.project_root / "docs"
        if docs_dir.exists():
            coverage["docs_count"] = len(list(docs_dir.glob("*.md")))
            coverage["api_docs_exist"] = (docs_dir / "api-reference.md").exists()
            coverage["examples_exist"] = (docs_dir / "getting-started.md").exists()

        return coverage

    def check_code_quality(self) -> dict[str, any]:
        """Check code quality metrics."""
        print("🔍 Checking code quality...")

        quality = {"flake8_passed": False, "mypy_passed": False, "test_coverage": 0}

        # Check flake8
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "flake8",
                    "chunker/",
                    "--max-line-length=100",
                    "--count",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            quality["flake8_passed"] = result.returncode == 0
        except:
            quality["flake8_passed"] = False

        # Check mypy
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mypy",
                    "chunker/",
                    "--ignore-missing-imports",
                    "--show-error-codes",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            quality["mypy_passed"] = result.returncode == 0
        except:
            quality["mypy_passed"] = False

        return quality

    def check_dependencies(self) -> dict[str, any]:
        """Check dependency management."""
        print("🔍 Checking dependencies...")

        deps = {
            "has_requirements": (self.project_root / "requirements.txt").exists(),
            "has_setup_py": (self.project_root / "setup.py").exists(),
            "has_pyproject": (self.project_root / "pyproject.toml").exists(),
            "has_pipfile": (self.project_root / "Pipfile").exists(),
            "has_poetry": (self.project_root / "pyproject.toml").exists(),
        }

        return deps

    def check_grammar_files(self) -> dict[str, any]:
        """Check Tree-sitter grammar files."""
        print("🔍 Checking grammar files...")

        grammar_dir = self.project_root / "chunker" / "data" / "grammars" / "build"

        grammar_info = {
            "grammar_dir_exists": grammar_dir.exists(),
            "grammar_count": 0,
            "supported_languages": [],
        }

        if grammar_dir.exists():
            grammar_files = list(grammar_dir.glob("*.so"))
            grammar_info["grammar_count"] = len(grammar_files)

            # Extract language names from filenames
            for grammar_file in grammar_files:
                lang_name = grammar_file.stem.replace("libtree-sitter-", "").replace(
                    ".so",
                    "",
                )
                grammar_info["supported_languages"].append(lang_name)

        return grammar_info

    def run_all_checks(self) -> dict[str, any]:
        """Run all quality checks."""
        print("🚀 Running comprehensive quality assurance...")
        print("=" * 50)

        self.results = {
            "file_structure": self.check_file_structure(),
            "documentation": self.check_documentation_coverage(),
            "code_quality": self.check_code_quality(),
            "dependencies": self.check_dependencies(),
            "grammar_files": self.check_grammar_files(),
        }

        return self.results

    def print_report(self) -> None:
        """Print comprehensive quality report."""
        print("\n QUALITY ASSURANCE REPORT")
        print("=" * 40)

        # File Structure
        print("\n📁 FILE STRUCTURE")
        fs = self.results["file_structure"]
        for key, value in fs.items():
            status = "✅" if value else "❌"
            print(f"   {status} {key.replace('_', ' ').title()}: {value}")

        # Documentation
        print("\n📚 DOCUMENTATION")
        doc = self.results["documentation"]
        print(f"   📖 README length: {doc['readme_length']} lines")
        print(f"   �� Docs count: {doc['docs_count']}")
        print(f"   🔧 API docs: {'✅' if doc['api_docs_exist'] else '❌'}")
        print(f"   💡 Examples: {'✅' if doc['examples_exist'] else '❌'}")
        print(
            f"   �� Installation guide: {'✅' if doc['installation_guide'] else '❌'}",
        )

        # Code Quality
        print("\n🔧 CODE QUALITY")
        cq = self.results["code_quality"]
        print(f"   🧹 Flake8: {'✅ PASS' if cq['flake8_passed'] else '❌ FAIL'}")
        print(f"   �� MyPy: {'✅ PASS' if cq['mypy_passed'] else '❌ FAIL'}")

        # Dependencies
        print("\n📦 DEPENDENCIES")
        deps = self.results["dependencies"]
        for key, value in deps.items():
            status = "✅" if value else "❌"
            print(f"   {status} {key.replace('_', ' ').title()}: {value}")

        # Grammar Files
        print("\n🌳 GRAMMAR FILES")
        gf = self.results["grammar_files"]
        print(f"   📁 Directory exists: {'✅' if gf['grammar_dir_exists'] else '❌'}")
        print(f"   �� Grammar count: {gf['grammar_count']}")
        if gf["supported_languages"]:
            print(
                f"   🌍 Supported languages: {', '.join(gf['supported_languages'][:10])}",
            )
            if len(gf["supported_languages"]) > 10:
                print(f"   ... and {len(gf['supported_languages']) - 10} more")

        # Overall Score
        self.calculate_score()

    def calculate_score(self) -> None:
        """Calculate overall quality score."""
        print("\n�� OVERALL QUALITY SCORE")
        print("=" * 30)

        total_checks = 0
        passed_checks = 0

        # Count checks in each category
        for category, checks in self.results.items():
            if isinstance(checks, dict):
                for key, value in checks.items():
                    total_checks += 1
                    if isinstance(value, bool):
                        if value:
                            passed_checks += 1
                    elif isinstance(value, (int, str)) and value:
                        passed_checks += 1

        score = (passed_checks / max(total_checks, 1)) * 100

        print(f"�� Score: {score:.1f}% ({passed_checks}/{total_checks})")

        if score >= 90:
            print("🏆 EXCELLENT - Ready for production!")
        elif score >= 80:
            print("✅ GOOD - Minor improvements needed")
        elif score >= 70:
            print("⚠️  FAIR - Several improvements needed")
        else:
            print("❌ NEEDS WORK - Significant improvements required")

        # Recommendations
        print("\n💡 RECOMMENDATIONS:")
        if score < 90:
            print("   - Review failed checks above")
            print("   - Fix critical issues before deployment")
            print("   - Consider additional testing")
        else:
            print("   - Codebase is production-ready!")
            print("   - Consider adding more comprehensive tests")
            print("   - Monitor performance in production")


def main():
    """Main quality check function."""
    checker = QualityChecker()
    results = checker.run_all_checks()
    checker.print_report()


if __name__ == "__main__":
    main()

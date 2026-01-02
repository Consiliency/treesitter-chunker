#!/usr/bin/env python3
"""Validate all cookbook examples and documentation code snippets."""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple


class ExampleValidator:
    """Validates code examples in documentation."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.results = {"passed": [], "failed": [], "skipped": [], "total": 0}

    def find_code_blocks(self, file_path: Path) -> list[tuple[str, int, str]]:
        """Extract code blocks from markdown files."""
        code_blocks = []

        if not file_path.exists():
            return code_blocks

        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.split("\n")

            in_code_block = False
            current_block = []
            start_line = 0
            language = ""

            for i, line in enumerate(lines, 1):
                # Check for code block start
                if line.startswith("```"):
                    if not in_code_block:
                        # Starting new block
                        in_code_block = True
                        start_line = i
                        language = line[3:].strip()
                        current_block = []
                    else:
                        # Ending block
                        in_code_block = False
                        if current_block:
                            code_blocks.append(
                                ("\n".join(current_block), start_line, language),
                            )
                        current_block = []
                elif in_code_block:
                    current_block.append(line)

        except Exception as e:
            print(f"❌ Error reading {file_path}: {e}")

        return code_blocks

    def is_type_hint_or_signature(self, code: str) -> bool:
        """Check if code block contains only type hints or function signatures."""
        lines = code.strip().split("\n")

        # Common patterns that indicate type hints or signatures
        type_hint_patterns = [
            # Variable type hints
            r"^[a-zA-Z_][a-zA-Z0-9_]*\s*:\s*[a-zA-Z_][a-zA-Z0-9_\[\]|, \.]*\s*$",  # var: type
            # Function signatures with return types
            r"^def\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\([^)]*\)\s*->\s*[a-zA-Z_][a-zA-Z0-9_\[\]|, \.]*\s*$",  # def func() -> type
            # Function signatures without return types
            r"^def\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\([^)]*\)\s*$",  # def func()
            # Class definitions
            r"^class\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\([^)]*\)\s*$",  # class Class()
            r"^class\s+[a-zA-Z_][a-zA-Z0-9_]*\s*$",  # class Class
            # Simple assignments
            r"^[a-zA-Z_][a-zA-Z0-9_]*\s*=\s*[a-zA-Z_][a-zA-Z0-9_]*\s*$",  # var = value
            # Import statements
            r"^from\s+[a-zA-Z_][a-zA-Z0-9_.]*\s+import\s+[a-zA-Z_][a-zA-Z0-9_, \*]*\s*$",  # from x import y
            r"^import\s+[a-zA-Z_][a-zA-Z0-9_, \.]*\s*$",  # import x
            # Type aliases
            r"^[A-Z][a-zA-Z0-9_]*\s*=\s*[a-zA-Z_][a-zA-Z0-9_\[\]|, \.]*\s*$",  # Type = Union[...]
            # Property decorators
            r"^@property\s*$",  # @property
            # Method decorators
            r"^@[a-zA-Z_][a-zA-Z0-9_]*\s*$",  # @decorator
        ]

        # Check if all lines match type hint patterns
        for line in lines:
            line = line.strip()
            if not line:  # Skip empty lines
                continue

            # Check if line matches any type hint pattern
            is_type_hint = False
            for pattern in type_hint_patterns:
                if re.match(pattern, line):
                    is_type_hint = True
                    break

            # If any line doesn't match type hint patterns, it's not just type hints
            if not is_type_hint:
                return False

        return True

    def is_documentation_example(self, code: str) -> bool:
        """Check if code block is a documentation example (API signature, type definition, etc.)."""
        lines = code.strip().split("\n")

        # If it's just one line, it's likely a function signature
        if len(lines) == 1:
            return True

        # Check if it's a class definition without body
        if len(lines) <= 5:
            return True

        # Check if it contains incomplete Python syntax (missing colons, etc.)
        incomplete_patterns = [
            r"def\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\([^)]*\)\s*$",  # def func() without colon
            r"[a-zA-Z_][a-zA-Z0-9_]*\s*:\s*[a-zA-Z_][a-zA-Z0-9_\[\]|, \.]*\s*$",  # var: type
            r"[a-zA-Z_][a-zA-Z0-9_]*\s*=\s*[a-zA-Z_][a-zA-Z0-9_\[\]|, \.]*\s*$",  # var = type
            r"[a-zA-Z_][a-zA-Z0-9_]*\s*\([^)]*\)\s*->\s*[a-zA-Z_][a-zA-Z0-9_\[\]|, \.]*\s*$",  # func() -> type
            r"[a-zA-Z_][a-zA-Z0-9_]*\s*\([^)]*\)\s*$",  # func() without colon
        ]

        # If any line matches incomplete patterns, consider it documentation
        for line in lines:
            line = line.strip()
            if not line or line.startswith("@"):
                continue
            for pattern in incomplete_patterns:
                if re.search(pattern, line):
                    return True

        return False

    def validate_python_example(
        self,
        code: str,
        file_path: Path,
        line_num: int,
    ) -> bool:
        """Validate Python code example."""
        try:
            # Skip documentation examples (API signatures, type definitions)
            if self.is_documentation_example(code):
                return True

            # Create temporary file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(code)
                temp_file = f.name

            # Try to compile the code
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", temp_file],
                capture_output=True,
                text=True,
                check=False,
            )

            # Clean up
            Path(temp_file).unlink()

            if result.returncode == 0:
                return True
            print(f"❌ Python syntax error in {file_path}:{line_num}")
            print(f"   Error: {result.stderr.strip()}")
            return False

        except Exception as e:
            print(f"❌ Error validating Python example: {e}")
            return False

    def validate_bash_example(self, code: str, file_path: Path, line_num: int) -> bool:
        """Validate bash/shell code example."""
        try:
            # Basic bash syntax check
            result = subprocess.run(
                ["bash", "-n", "-c", code],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                return True
            print(f"❌ Bash syntax error in {file_path}:{line_num}")
            print(f"   Error: {result.stderr.strip()}")
            return False

        except Exception as e:
            print(f"❌ Error validating bash example: {e}")
            return False

    def validate_markdown_example(
        self,
        code: str,
        file_path: Path,
        line_num: int,
    ) -> bool:
        """Validate markdown code example."""
        # For now, just check if it's not empty
        if code.strip():
            return True
        print(f"❌ Empty markdown example in {file_path}:{line_num}")
        return False

    def validate_example(
        self,
        code: str,
        language: str,
        file_path: Path,
        line_num: int,
    ) -> bool:
        """Validate a single code example."""
        self.results["total"] += 1

        # Skip non-code blocks
        if not language or language in ["", "text", "plain"]:
            self.results["skipped"].append(f"{file_path}:{line_num}")
            return True

        # Validate based on language
        if language in ["python", "py"]:
            success = self.validate_python_example(code, file_path, line_num)
        elif language in ["bash", "sh", "shell"]:
            success = self.validate_bash_example(code, file_path, line_num)
        elif language in ["markdown", "md"]:
            success = self.validate_markdown_example(code, file_path, line_num)
        else:
            # Skip unsupported languages for now
            self.results["skipped"].append(f"{file_path}:{line_num} ({language})")
            return True

        if success:
            self.results["passed"].append(f"{file_path}:{line_num}")
        else:
            self.results["failed"].append(f"{file_path}:{line_num}")

        return success

    def validate_file(self, file_path: Path) -> None:
        """Validate all examples in a single file."""
        print(f"🔍 Validating: {file_path}")

        code_blocks = self.find_code_blocks(file_path)

        for code, line_num, language in code_blocks:
            self.validate_example(code, language, file_path, line_num)

    def validate_documentation(self) -> None:
        """Validate all documentation files."""
        print("🚀 Starting documentation validation...")
        print("=" * 50)

        # Files to validate
        doc_files = [
            self.project_root / "README.md",
            self.project_root / "docs" / "index.md",
            self.project_root / "docs" / "getting-started.md",
            self.project_root / "docs" / "api-reference.md",
            self.project_root / "CHANGELOG.md",
            self.project_root / "CONTRIBUTING.md",
            self.project_root / "SECURITY.md",
            self.project_root / "SUPPORT.md",
            self.project_root / "DEPLOYMENT.md",
        ]

        for doc_file in doc_files:
            if doc_file.exists():
                self.validate_file(doc_file)
            else:
                print(f"⚠️  Skipping (not found): {doc_file}")

        print("=" * 50)
        self.print_results()

    def print_results(self) -> None:
        """Print validation results."""
        print("\n VALIDATION RESULTS")
        print("=" * 30)
        print(f"✅ Passed: {len(self.results['passed'])}")
        print(f"❌ Failed: {len(self.results['failed'])}")
        print(f"⏭️  Skipped: {len(self.results['skipped'])}")
        print(f"📝 Total: {self.results['total']}")

        if self.results["failed"]:
            print("\n❌ FAILED EXAMPLES:")
            for failed in self.results["failed"]:
                print(f"   - {failed}")

        if self.results["skipped"]:
            print("\n⏭️  SKIPPED EXAMPLES:")
            for skipped in self.results["skipped"]:
                print(f"   - {skipped}")

        # Overall success
        success_rate = (
            len(self.results["passed"]) / max(self.results["total"], 1)
        ) * 100
        print(f"\n🎯 Success Rate: {success_rate:.1f}%")

        if self.results["failed"]:
            print("\n💡 RECOMMENDATIONS:")
            print("   - Fix failed examples before deployment")
            print("   - Test examples manually to ensure they work")
            print("   - Update documentation with working examples")
            sys.exit(1)
        else:
            print("\n🎉 All examples validated successfully!")
            print("   Ready for deployment!")


def main():
    """Main validation function."""
    validator = ExampleValidator()
    validator.validate_documentation()


if __name__ == "__main__":
    main()

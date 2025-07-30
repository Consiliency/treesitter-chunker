#!/usr/bin/env python3
"""
Development Environment Component Demo

This script demonstrates the features of the development environment component,
including pre-commit setup, linting, formatting, and quality checks.
"""

import sys
import tempfile
from pathlib import Path

import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from chunker.devenv import DevelopmentEnvironment, QualityAssurance


def demo_pre_commit_setup():
    """Demonstrate pre-commit hook setup"""
    print("\n=== Pre-commit Hook Setup Demo ===")

    dev_env = DevelopmentEnvironment()

    # For demo, we'll use the current project
    project_root = Path.cwd()

    if (project_root / ".git").exists() and (
        project_root / ".pre-commit-config.yaml"
    ).exists():
        success = dev_env.setup_pre_commit_hooks(project_root)
        if success:
            print("✓ Pre-commit hooks installed successfully!")
        else:
            print("✗ Pre-commit hook installation failed")
            print("  Make sure 'pre-commit' is installed: pip install pre-commit")
    else:
        print("✗ Not in a git repository or missing .pre-commit-config.yaml")


def demo_linting():
    """Demonstrate code linting capabilities"""
    print("\n=== Code Linting Demo ===")

    dev_env = DevelopmentEnvironment()

    # Create a temporary file with linting issues
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
import os  # unused import
import sys

def bad_function( x,y ):  # spacing issues
    z = x+y  # no spaces around operator
    return z

# Missing type annotations
def process_data(data):
    return data.upper()
""",
        )
        bad_file = f.name

    print(f"Created test file: {bad_file}")

    # Run linting
    success, issues = dev_env.run_linting([bad_file])

    print(f"\nLinting {'passed' if success else 'failed'}")
    print(f"Found {len(issues)} issues:")

    for issue in issues[:5]:  # Show first 5 issues
        print(
            f"  - [{issue['tool']}] {issue['file']}:{issue['line']}:{issue['column']} "
            f"{issue['code']}: {issue['message']}",
        )

    if len(issues) > 5:
        print(f"  ... and {len(issues) - 5} more issues")

    # Clean up
    Path(bad_file).unlink()


def demo_formatting():
    """Demonstrate code formatting"""
    print("\n=== Code Formatting Demo ===")

    dev_env = DevelopmentEnvironment()

    # Create a poorly formatted file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """def poorly_formatted(x,y,z):
    result=x+y+z
    if result>10:
        return True
    else:
        return False

class BadlySpaced:
  def __init__(self):
      self.value=42
""",
        )
        format_file = f.name

    print(f"Created test file: {format_file}")

    # Check if formatting is needed
    success, files = dev_env.format_code([format_file], check_only=True)
    print(f"\nFormatting check: {'passed' if success else 'needs formatting'}")

    if not success:
        # Apply formatting
        success, modified = dev_env.format_code([format_file], check_only=False)
        print(f"Formatting applied: {'success' if success else 'failed'}")

        # Show the formatted content
        with Path(format_file).open("r") as f:
            print("\nFormatted code:")
            print(f.read())

    # Clean up
    Path(format_file).unlink()


def demo_ci_config():
    """Demonstrate CI configuration generation"""
    print("\n=== CI Configuration Generation Demo ===")

    dev_env = DevelopmentEnvironment()

    # Generate CI config for multiple platforms
    config = dev_env.generate_ci_config(
        platforms=["ubuntu-latest", "macos-latest", "windows-latest"],
        python_versions=["3.10", "3.11", "3.12"],
    )

    print("Generated GitHub Actions workflow:")
    print(f"- Name: {config['name']}")
    print(f"- Triggers: {list(config['on'].keys())}")
    print(f"- Jobs: {list(config['jobs'].keys())}")

    # Show matrix configuration
    matrix = config["jobs"]["test"]["strategy"]["matrix"]
    print("\nTest Matrix:")
    print(f"- Platforms: {matrix['os']}")
    print(f"- Python versions: {matrix['python-version']}")

    # Save to temporary file for inspection
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(config, f, default_flow_style=False)
        print(f"\nFull config saved to: {f.name}")


def demo_quality_checks():
    """Demonstrate quality assurance checks"""
    print("\n=== Quality Assurance Demo ===")

    qa = QualityAssurance()

    # Check type coverage
    print("\nChecking type coverage...")
    type_coverage, type_report = qa.check_type_coverage(min_coverage=80.0)

    if "error" in type_report:
        print(f"Type coverage check failed: {type_report['error']}")
    else:
        print(f"Type coverage: {type_coverage:.1f}%")
        print(
            f"Meets minimum (80%): {'✓' if type_report.get('meets_minimum') else '✗'}",
        )

        if type_report.get("files"):
            print("\nTop files by coverage:")
            sorted_files = sorted(
                type_report["files"].items(),
                key=lambda x: x[1].get("coverage", 0),
                reverse=True,
            )
            for filename, info in sorted_files[:5]:
                coverage = info.get("coverage", 0)
                print(f"  - {filename}: {coverage:.1f}%")

    # Check test coverage
    print("\n\nChecking test coverage...")
    test_coverage, test_report = qa.check_test_coverage(min_coverage=80.0)

    if "error" in test_report:
        print(f"Test coverage check failed: {test_report['error']}")
    else:
        print(f"Test coverage: {test_coverage:.1f}%")
        print(
            f"Meets minimum (80%): {'✓' if test_report.get('meets_minimum') else '✗'}",
        )

        if "lines_covered" in test_report:
            print(f"Lines covered: {test_report['lines_covered']}")
            print(f"Lines missing: {test_report['lines_missing']}")


def main():
    """Run all demos"""
    print("=== Development Environment Component Demo ===")
    print("This demo showcases the development environment features.")

    # Run demos
    demo_pre_commit_setup()
    demo_linting()
    demo_formatting()
    demo_ci_config()
    demo_quality_checks()

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    main()

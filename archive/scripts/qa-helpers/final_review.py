#!/usr/bin/env python3
"""Final review and deployment readiness check."""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


class FinalReview:
    """Performs final review before deployment."""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.review_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def check_deployment_readiness(self) -> bool:
        """Check if the project is ready for deployment."""
        print("🚀 FINAL DEPLOYMENT READINESS CHECK")
        print("=" * 45)
        print(f"�� Review Date: {self.review_date}")
        print()

        # Run quality checks
        print("🔍 Running quality assurance...")
        try:
            result = subprocess.run(
                [sys.executable, "scripts/quality_check.py"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                print("✅ Quality checks passed")
            else:
                print("❌ Quality checks failed")
                return False
        except Exception as e:
            print(f"❌ Error running quality checks: {e}")
            return False

        # Run example validation
        print("\n🔍 Validating examples...")
        try:
            result = subprocess.run(
                [sys.executable, "scripts/validate_examples.py"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                print("✅ Examples validated")
            else:
                print("❌ Example validation failed")
                return False
        except Exception as e:
            print(f"❌ Error validating examples: {e}")
            return False

        # Check critical files
        print("\n🔍 Checking critical files...")
        critical_files = [
            "README.md",
            "chunker/__init__.py",
            "chunker/grammar/manager.py",
            "tests/",
            "docs/",
        ]

        for file_path in critical_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                print(f"   ✅ {file_path}")
            else:
                print(f"   ❌ {file_path} - MISSING!")
                return False

        # Check documentation servers
        print("\n🔍 Checking documentation servers...")
        server_scripts = [
            "scripts/serve_mkdocs.py",
            "scripts/serve_sphinx.py",
            "scripts/serve_all.py",
        ]

        for script in server_scripts:
            script_path = self.project_root / script
            if script_path.exists():
                print(f"   ✅ {script}")
            else:
                print(f"   ❌ {script} - MISSING!")
                return False

        return True

    def generate_deployment_summary(self) -> None:
        """Generate deployment summary."""
        print("\n�� DEPLOYMENT SUMMARY")
        print("=" * 25)

        # Project info
        print("🏗️  Project: Tree-sitter Chunker")
        print(f"📁 Location: {self.project_root}")
        print(f"�� Review Date: {self.review_date}")

        # File counts
        python_files = len(list(self.project_root.rglob("*.py")))
        markdown_files = len(list(self.project_root.rglob("*.md")))
        test_files = len(list((self.project_root / "tests").rglob("*.py")))

        print(f"🐍 Python files: {python_files}")
        print(f"📝 Markdown files: {markdown_files}")
        print(f"🧪 Test files: {test_files}")

        # Archive info
        archive_dir = self.project_root / "archive"
        if archive_dir.exists():
            archived_files = len(list(archive_dir.rglob("*.md")))
            print(f"📦 Archived files: {archived_files}")

        # Scripts info
        scripts_dir = self.project_root / "scripts"
        if scripts_dir.exists():
            script_count = len(list(scripts_dir.glob("*.py")))
            print(f"🔧 Scripts: {script_count}")

    def print_next_steps(self) -> None:
        """Print next steps for deployment."""
        print("\n🎯 NEXT STEPS")
        print("=" * 15)

        print("1. 🚀 Deploy to production environment")
        print("2. 📊 Monitor performance and usage")
        print("3. 🐛 Address any production issues")
        print("4. 📈 Plan future enhancements")
        print("5. 🎉 Celebrate successful deployment!")

        print("\n💡 DEPLOYMENT COMMANDS:")
        print("   # Install from source")
        print("   pip install -e .")
        print("")
        print("   # Run tests")
        print("   python scripts/run_all_tests.py")
        print("")
        print("   # Start documentation servers")
        print("   python scripts/serve_all.py")
        print("")
        print("   # Quality check")
        print("   python scripts/quality_check.py")


def main():
    """Main final review function."""
    reviewer = FinalReview()

    print("�� FINAL REVIEW & DEPLOYMENT READINESS")
    print("=" * 50)

    if reviewer.check_deployment_readiness():
        print("\n🎉 DEPLOYMENT READY!")
        reviewer.generate_deployment_summary()
        reviewer.print_next_steps()
        sys.exit(0)
    else:
        print("\n❌ NOT READY FOR DEPLOYMENT")
        print("Please fix the issues above before proceeding.")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Quick validation of key examples and functionality."""

import os
import subprocess
import sys
from pathlib import Path


def quick_test():
    """Run quick validation tests."""
    print("⚡ QUICK VALIDATION")
    print("=" * 30)

    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    # Test 1: Basic import
    print("🔍 Testing basic imports...")
    try:
        import chunker

        print("✅ chunker module imports successfully")
    except ImportError as e:
        print(f"❌ chunker import failed: {e}")
        return False

    # Test 2: Grammar manager
    print("🔍 Testing grammar manager...")
    try:
        from chunker.grammar.manager import TreeSitterGrammarManager

        print("✅ TreeSitterGrammarManager imports successfully")
    except ImportError as e:
        print(f"❌ TreeSitterGrammarManager import failed: {e}")
        return False

    # Test 3: Basic chunking
    print("🔍 Testing basic chunking...")
    try:
        from chunker import chunk_text

        result = chunk_text("print('Hello, World!')", "python")
        print("✅ Basic chunking works")
    except Exception as e:
        print(f"❌ Basic chunking failed: {e}")
        return False

    # Test 4: Check grammar files
    print("🔍 Checking grammar files...")
    grammar_dir = project_root / "chunker" / "data" / "grammars" / "build"
    if grammar_dir.exists():
        grammar_count = len(list(grammar_dir.glob("*.so")))
        print(f"✅ Found {grammar_count} grammar files")
    else:
        print("❌ Grammar directory not found")
        return False

    print("\n🎉 Quick validation completed successfully!")
    return True


if __name__ == "__main__":
    main = quick_test
    if main():
        sys.exit(0)
    else:
        sys.exit(1)

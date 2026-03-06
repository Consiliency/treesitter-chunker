#!/usr/bin/env python3
"""Fix and build failed grammars."""

import subprocess
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from chunker.grammar.builder import TreeSitterGrammarBuilder
from chunker.grammar.manager import TreeSitterGrammarManager


def fetch_and_build_grammar(language: str) -> bool:
    """Fetch and build a grammar."""
    try:
        print(f"\nProcessing {language}...")

        # First, try to fetch the grammar
        manager = TreeSitterGrammarManager()

        # Check if it needs fetching
        if not manager.is_fetched(language):
            print(f"  Fetching {language}...")
            if not manager.fetch_grammar(language):
                print(f"  ✗ Failed to fetch {language}")
                return False

        # Now try to build
        print(f"  Building {language}...")
        builder = TreeSitterGrammarBuilder()

        if builder.build_individual(language):
            # Check if output exists
            build_file = Path("build") / f"{language}.so"
            package_file = Path("chunker/data/grammars/build") / f"{language}.so"

            if build_file.exists():
                # Move to package directory
                package_file.parent.mkdir(parents=True, exist_ok=True)
                if package_file.exists():
                    package_file.unlink()
                build_file.rename(package_file)
                print(f"  ✓ {language} built and moved successfully")
                return True
            if package_file.exists():
                print(f"  ✓ {language} already exists")
                return True

        print(f"  ✗ Failed to build {language}")
        return False

    except Exception as e:
        print(f"  ✗ {language}: {e}")
        return False


def main():
    """Main function."""

    # Failed languages from previous run
    failed_languages = [
        "css",
        "toml",
        "php",
        "ocaml",
        "wasm",
        "ruby",
        "json",
        "xml",
        "html",
        "yaml",
    ]

    print("=" * 60)
    print("Fixing Failed Grammars")
    print("=" * 60)
    print(f"Languages to fix: {', '.join(failed_languages)}")

    # Try simpler languages first (without complex dependencies)
    simple_languages = ["json", "toml", "yaml", "html", "css", "xml"]
    complex_languages = ["ruby", "php", "ocaml", "wasm"]

    successful = []
    still_failed = []

    print("\n--- Processing simple languages ---")
    for lang in simple_languages:
        if lang in failed_languages:
            if fetch_and_build_grammar(lang):
                successful.append(lang)
            else:
                still_failed.append(lang)

    print("\n--- Processing complex languages ---")
    for lang in complex_languages:
        if lang in failed_languages:
            if fetch_and_build_grammar(lang):
                successful.append(lang)
            else:
                still_failed.append(lang)

    # Summary
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    print(f"Fixed: {len(successful)}/{len(failed_languages)}")
    if successful:
        print(f"✓ Successfully built: {', '.join(successful)}")
    if still_failed:
        print(f"✗ Still failing: {', '.join(still_failed)}")

    # Check total available
    package_dir = Path("chunker/data/grammars/build")
    if package_dir.exists():
        available_grammars = list(package_dir.glob("*.so"))
        print(f"\nTotal grammars now available: {len(available_grammars)}/35")

        # List what we have
        all_expected = {
            "c",
            "clojure",
            "cpp",
            "csharp",
            "css",
            "dart",
            "dockerfile",
            "elixir",
            "go",
            "haskell",
            "html",
            "java",
            "javascript",
            "json",
            "julia",
            "kotlin",
            "matlab",
            "nasm",
            "ocaml",
            "php",
            "python",
            "r",
            "ruby",
            "rust",
            "scala",
            "sql",
            "svelte",
            "swift",
            "toml",
            "typescript",
            "vue",
            "wasm",
            "xml",
            "yaml",
            "zig",
        }

        available = {g.stem for g in available_grammars}
        missing = all_expected - available

        if missing:
            print(f"Still missing: {', '.join(sorted(missing))}")
        else:
            print("✅ All 35 grammars are now available!")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build all remaining tree-sitter grammars for Phase 1.6a completion."""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from chunker.grammar.builder import TreeSitterGrammarBuilder


def build_grammar(language: str) -> tuple[str, bool, str]:
    """Build a single grammar.

    Args:
        language: Language name to build

    Returns:
        Tuple of (language, success, message)
    """
    try:
        print(f"Building {language}...")
        builder = TreeSitterGrammarBuilder()

        if builder.build_individual(language):
            # Check if output exists
            build_file = Path("build") / f"{language}.so"
            package_file = Path("chunker/data/grammars/build") / f"{language}.so"

            if build_file.exists():
                # Move to package directory
                package_file.parent.mkdir(parents=True, exist_ok=True)
                if package_file.exists():
                    package_file.unlink()  # Remove existing
                build_file.rename(package_file)
                return (
                    language,
                    True,
                    f"Successfully built and moved to {package_file}",
                )
            if package_file.exists():
                return (language, True, f"Already exists at {package_file}")
            return (language, False, "Built but output file not found")
        return (language, False, "Build failed")

    except Exception as e:
        return (language, False, f"Exception: {e!s}")


def main():
    """Main function to build all remaining grammars."""

    # Already compiled languages
    already_compiled = {"python", "rust", "go", "c", "cpp", "javascript"}

    # All languages we need (from grammar_sources.json)
    all_languages = {
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

    # Languages to build
    languages_to_build = all_languages - already_compiled

    print("=" * 60)
    print("Phase 1.6a: Complete Grammar Compilation")
    print("=" * 60)
    print(f"Total languages needed: {len(all_languages)}")
    print(f"Already compiled: {len(already_compiled)}")
    print(f"To compile: {len(languages_to_build)}")
    print()

    if not languages_to_build:
        print("All grammars are already compiled!")
        return

    print(f"Languages to build: {', '.join(sorted(languages_to_build))}")
    print()

    # Group languages by category for better organization
    categories = {
        "Core Enterprise": ["java", "csharp", "typescript", "kotlin", "swift"],
        "Web & Scripting": ["ruby", "php", "dart", "vue", "svelte"],
        "Functional & Academic": [
            "haskell",
            "ocaml",
            "scala",
            "elixir",
            "clojure",
            "julia",
        ],
        "Specialized & Domain": [
            "matlab",
            "r",
            "sql",
            "nasm",
            "css",
            "html",
            "json",
            "toml",
            "yaml",
            "xml",
        ],
        "Systems & Other": ["dockerfile", "wasm", "zig"],
    }

    # Build languages in parallel with limited concurrency
    max_workers = 4  # Limit to avoid overwhelming the system
    results = []

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all build tasks
        futures = {
            executor.submit(build_grammar, lang): lang for lang in languages_to_build
        }

        # Process results as they complete
        for future in as_completed(futures):
            language = futures[future]
            try:
                result = future.result(timeout=60)
                results.append(result)

                # Print result immediately
                lang, success, msg = result
                if success:
                    print(f"✓ {lang}: {msg}")
                else:
                    print(f"✗ {lang}: {msg}")

            except Exception as e:
                results.append((language, False, f"Timeout or error: {e}"))
                print(f"✗ {language}: Timeout or error: {e}")

    elapsed_time = time.time() - start_time

    # Summary by category
    print("\n" + "=" * 60)
    print("Build Summary by Category:")
    print("=" * 60)

    successful = set()
    failed = []

    for lang, success, msg in results:
        if success:
            successful.add(lang)
        else:
            failed.append((lang, msg))

    for category, langs in categories.items():
        category_langs = [l for l in langs if l in languages_to_build]
        if category_langs:
            built = [l for l in category_langs if l in successful]
            print(f"\n{category}:")
            print(f"  Total: {len(category_langs)}")
            print(f"  Built: {len(built)}/{len(category_langs)}")
            if built:
                print(f"  ✓ {', '.join(built)}")
            not_built = [l for l in category_langs if l not in successful]
            if not_built:
                print(f"  ✗ {', '.join(not_built)}")

    # Final summary
    print("\n" + "=" * 60)
    print("Final Summary:")
    print("=" * 60)
    print(f"Build time: {elapsed_time:.2f} seconds")
    print(f"Successful: {len(successful)}/{len(languages_to_build)}")
    print(f"Failed: {len(failed)}")

    # Check total available
    package_dir = Path("chunker/data/grammars/build")
    if package_dir.exists():
        available_grammars = list(package_dir.glob("*.so"))
        print(
            f"\nTotal grammars available: {len(available_grammars)}/{len(all_languages)}",
        )
        print(f"Available: {', '.join(sorted([g.stem for g in available_grammars]))}")

    # Report failures
    if failed:
        print("\n" + "=" * 60)
        print("Failed Languages:")
        print("=" * 60)
        for lang, msg in failed:
            print(f"  {lang}: {msg}")
        sys.exit(1)
    else:
        print("\n✅ Phase 1.6a COMPLETE! All grammars compiled successfully.")
        print(f"📊 {len(all_languages)} languages ready for use.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Enhanced grammar building script using the GrammarBuilder.
Usage: python scripts/build_grammars.py [languages...]
"""
import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from chunker.grammar import TreeSitterGrammarBuilder

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Build Tree-sitter grammars")
    parser.add_argument(
        "languages",
        nargs="*",
        help="Languages to build (default: all available)",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("grammars"),
        help="Directory containing grammar sources",
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=Path("build"),
        help="Directory for build output",
    )
    parser.add_argument(
        "--individual",
        action="store_true",
        help="Build each language as a separate library",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean build artifacts before building",
    )

    args = parser.parse_args()

    # Create builder
    builder = TreeSitterGrammarBuilder()
    builder.set_source_directory(args.source_dir)
    builder.set_build_directory(args.build_dir)

    # Clean if requested
    if args.clean:
        logger.info("Cleaning build artifacts...")
        builder.clean()

    # Get languages to build
    if args.languages:
        languages = args.languages
    else:
        # Find all available languages
        languages = []
        for grammar_dir in args.source_dir.glob("tree-sitter-*"):
            if grammar_dir.is_dir():
                lang = grammar_dir.name.replace("tree-sitter-", "")
                languages.append(lang)

        if not languages:
            logger.error("No grammar sources found. Run fetch_grammars.py first.")
            return 1

    logger.info("Building %s languages: %s", len(languages), ", ".join(languages))

    # Build languages
    if args.individual:
        # Build each language separately
        success_count = 0
        for lang in languages:
            logger.info("\nBuilding %s...", lang)
            if builder.build_individual(lang):
                success_count += 1
                builder.compile_queries(lang)
            else:
                logger.error("Failed to build %s", lang)
                log = builder.get_build_log(lang)
                if log:
                    logger.error("Build log:\n%s", log)

        logger.info(
            "\nSuccessfully built %s/%s languages",
            success_count,
            len(languages),
        )
    else:
        # Build all languages into one library
        results = builder.build(languages)

        # Copy queries for successful builds
        for lang, success in results.items():
            if success:
                builder.compile_queries(lang)

        # Report results
        success_count = sum(1 for success in results.values() if success)
        logger.info(
            "\nSuccessfully built %s/%s languages",
            success_count,
            len(languages),
        )

        # Show errors
        for lang, success in results.items():
            if not success:
                log = builder.get_build_log(lang)
                if log:
                    logger.error("\n%s error:\n%s", lang, log)

    return 0 if success_count == len(languages) else 1


if __name__ == "__main__":
    sys.exit(main())

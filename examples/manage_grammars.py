#!/usr/bin/env python3
"""Example script for managing Tree-sitter grammars."""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from chunker.grammar import (
    TreeSitterGrammarManager,
    TreeSitterGrammarValidator,
    get_grammar_repository,
)
from chunker.interfaces.grammar import GrammarStatus

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def list_available_grammars():
    """List all available grammars from the repository."""
    repo = get_grammar_repository()

    print("\n=== Available Grammars ===")
    all_grammars = repo.list_all_grammars()

    for i, name in enumerate(all_grammars, 1):
        info = repo.get_grammar_info(name)
        if info:
            print(f"{i:2d}. {name:15s} - {info.repository_url}")

    print(f"\nTotal: {len(all_grammars)} grammars available")

    # Show popular grammars
    print("\n=== Popular Grammars ===")
    popular = repo.get_popular_grammars(limit=10)
    for grammar in popular:
        print(f"  - {grammar.name}")


def search_grammars(query: str):
    """Search for grammars matching a query."""
    repo = get_grammar_repository()

    print(f"\n=== Searching for '{query}' ===")
    results = repo.search(query)

    if not results:
        print("No grammars found matching your query.")
        return

    for grammar in results:
        print(f"\n{grammar.name}:")
        print(f"  Repository: {grammar.repository_url}")
        info = repo.get_grammar_info(grammar.name)
        if info:
            extensions = repo._grammars[grammar.name].get("extensions", [])
            if extensions:
                print(f"  Extensions: {', '.join(extensions)}")


def manage_grammars(action: str, languages: list):
    """Manage grammars (add, fetch, build, remove)."""
    manager = TreeSitterGrammarManager()
    repo = get_grammar_repository()

    for lang in languages:
        print(f"\n=== {action.title()} {lang} ===")

        if action == "add":
            # Get info from repository
            info = repo.get_grammar_info(lang)
            if not info:
                logger.error(f"Grammar '{lang}' not found in repository")
                continue

            # Add to manager
            grammar = manager.add_grammar(lang, info.repository_url)
            print(f"Added {lang} (status: {grammar.status.value})")

        elif action == "fetch":
            # Fetch grammar source
            if manager.fetch_grammar(lang):
                print(f"Successfully fetched {lang}")
            else:
                logger.error(f"Failed to fetch {lang}")

        elif action == "build":
            # Build grammar
            if manager.build_grammar(lang):
                print(f"Successfully built {lang}")
            else:
                logger.error(f"Failed to build {lang}")

        elif action == "remove":
            # Remove grammar
            if manager.remove_grammar(lang):
                print(f"Removed {lang}")
            else:
                logger.error(f"Failed to remove {lang}")


def show_status():
    """Show status of all managed grammars."""
    manager = TreeSitterGrammarManager()
    validator = TreeSitterGrammarValidator()

    print("\n=== Grammar Status ===")
    grammars = manager.list_grammars()

    if not grammars:
        print("No grammars are currently managed.")
        return

    # Group by status
    by_status = {}
    for grammar in grammars:
        status = grammar.status.value
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(grammar)

    # Show each status group
    for status, grammars in by_status.items():
        print(f"\n{status.upper()} ({len(grammars)}):")
        for grammar in grammars:
            print(f"  - {grammar.name}")
            if grammar.error:
                print(f"    Error: {grammar.error}")

            # Validate if ready
            if grammar.status == GrammarStatus.READY:
                valid, error = manager.validate_grammar(grammar.name)
                if not valid:
                    print(f"    Validation failed: {error}")


def check_file_support(filepath: str):
    """Check which grammar supports a file."""
    repo = get_grammar_repository()
    path = Path(filepath)

    print(f"\n=== Checking support for {path.name} ===")

    # Check by extension
    grammar = repo.get_grammar_by_extension(path.suffix)
    if grammar:
        print(f"Language: {grammar.name}")
        print(f"Repository: {grammar.repository_url}")

        # Check if we have it
        manager = TreeSitterGrammarManager()
        local_info = manager.get_grammar_info(grammar.name)
        if local_info:
            print(f"Status: {local_info.status.value}")
        else:
            print("Status: Not installed")
    else:
        print(f"No grammar found for extension '{path.suffix}'")


def main():
    parser = argparse.ArgumentParser(
        description="Manage Tree-sitter grammars",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all available grammars
  %(prog)s list
  
  # Search for grammars
  %(prog)s search javascript
  
  # Add and fetch grammars
  %(prog)s add python go ruby
  %(prog)s fetch python go ruby
  
  # Build grammars
  %(prog)s build python go ruby
  
  # Show status
  %(prog)s status
  
  # Check file support
  %(prog)s check example.py
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # List command
    subparsers.add_parser("list", help="List available grammars")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for grammars")
    search_parser.add_argument("query", help="Search query")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add grammars")
    add_parser.add_argument("languages", nargs="+", help="Languages to add")

    # Fetch command
    fetch_parser = subparsers.add_parser("fetch", help="Fetch grammar sources")
    fetch_parser.add_argument("languages", nargs="+", help="Languages to fetch")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build grammars")
    build_parser.add_argument("languages", nargs="+", help="Languages to build")

    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove grammars")
    remove_parser.add_argument("languages", nargs="+", help="Languages to remove")

    # Status command
    subparsers.add_parser("status", help="Show grammar status")

    # Check command
    check_parser = subparsers.add_parser("check", help="Check file support")
    check_parser.add_argument("file", help="File to check")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute command
    if args.command == "list":
        list_available_grammars()
    elif args.command == "search":
        search_grammars(args.query)
    elif args.command in ["add", "fetch", "build", "remove"]:
        manage_grammars(args.command, args.languages)
    elif args.command == "status":
        show_status()
    elif args.command == "check":
        check_file_support(args.file)

    return 0


if __name__ == "__main__":
    sys.exit(main())

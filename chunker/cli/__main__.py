"""Main CLI entry point for treesitter-chunker.

Usage:
    python -m chunker.cli symbols extract /path/to/project --output symbols.json
    python -m chunker.cli grammar list
    python -m chunker.cli cluster infer /path/to/project --output hierarchy.json
"""

import argparse
import sys

from .cluster_commands import setup_cluster_parser
from .grammar_commands import setup_grammar_parser
from .symbol_commands import setup_symbol_parser


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="chunker",
        description="Tree-sitter Chunker - Semantic code analysis tools",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Set up subcommands
    setup_symbol_parser(subparsers)
    setup_grammar_parser(subparsers)
    setup_cluster_parser(subparsers)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Handle symbol commands
    if args.command == "symbols":
        if not args.symbol_command:
            # Print help for symbols command
            parser.parse_args(["symbols", "--help"])
            return 0
        return args.func(args)

    # Handle grammar commands
    if args.command == "grammar":
        if not args.grammar_command:
            parser.parse_args(["grammar", "--help"])
            return 0
        return args.func(args)

    # Handle cluster commands
    if args.command == "cluster":
        if not hasattr(args, "cluster_command") or not args.cluster_command:
            parser.parse_args(["cluster", "--help"])
            return 0
        return args.func(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

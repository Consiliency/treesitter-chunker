"""CLI commands for symbol extraction and dependency analysis."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from chunker.symbol_graph import extract_symbol_graph
from chunker.types import CALL_RESOLUTION_MODES


def setup_symbol_parser(subparsers: argparse._SubParsersAction) -> None:
    """Set up symbol extraction subcommands."""
    symbol_parser = subparsers.add_parser(
        "symbols",
        help="Extract symbols and relationships from source code",
    )

    symbol_subparsers = symbol_parser.add_subparsers(
        dest="symbol_command",
        help="Symbol extraction commands",
    )

    extract_parser = symbol_subparsers.add_parser(
        "extract",
        help="Extract symbols from a file or directory",
    )
    extract_parser.add_argument(
        "path",
        type=str,
        help="Path to file or directory to analyze",
    )
    extract_parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output file path (default: stdout)",
    )
    extract_parser.add_argument(
        "-l",
        "--language",
        type=str,
        default="python",
        help="Language to analyze (default: python)",
    )
    extract_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    extract_parser.add_argument(
        "--resolution-mode",
        choices=["strict", "permissive"],
        default="permissive",
        help="Relationship resolution policy (default: permissive)",
    )
    extract_parser.add_argument(
        "--call-resolution",
        choices=list(CALL_RESOLUTION_MODES),
        default="name",
        help=(
            "Experimental: call-edge resolution (default: name). 'structural' "
            "narrows ambiguous calls to bare names in Python, JavaScript, "
            "TypeScript and TSX files; it currently resolves JS/TS calls whose "
            "target a lexical binding proves (a script top level only when no "
            "other file in the run may declare the name as a global), and "
            "Python calls through the LEGB scope chain (never a redefinition). "
            "'imports' also resolves JS/TS calls through relative import "
            "bindings, and Python calls through import bindings and module "
            "member chains, to the one definition they prove; for Python it "
            "can resolve fewer calls than 'structural' where other files may "
            "write a module's globals"
        ),
    )
    extract_parser.set_defaults(func=cmd_extract_symbols)


def cmd_extract_symbols(args: argparse.Namespace) -> int:
    """Extract symbols from a file or directory."""
    path = Path(args.path)

    if not path.exists():
        print(f"Error: Path does not exist: {path}", file=sys.stderr)
        return 1

    output = extract_symbol_graph(
        path,
        args.language,
        resolution_mode=args.resolution_mode,
        call_resolution=args.call_resolution,
    )
    if output["metadata"]["files_processed"] == 0:
        print(
            f"Error: No {args.language} source files found in {path}",
            file=sys.stderr,
        )
        return 1

    indent = 2 if args.pretty else None
    json_output = json.dumps(output, indent=indent, default=str)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(json_output, encoding="utf-8")
        metadata = output["metadata"]
        print(f"Extracted symbols from {metadata['files_processed']} files")
        print(f"  Classes: {metadata['total_classes']}")
        print(f"  Functions: {metadata['total_functions']}")
        print(f"  Imports: {metadata['total_imports']}")
        print(f"  Relationships: {metadata['total_relationships']}")
        print(f"Output written to: {output_path}")
    else:
        print(json_output)

    return 0 if not output["metadata"]["errors"] else 1


def extract_symbols_cli(path: str, output: str | None = None) -> dict[str, Any]:
    """Programmatic interface to extract symbols."""
    path_obj = Path(path)
    if not path_obj.exists():
        return {"error": f"Path does not exist: {path}"}

    output_data = extract_symbol_graph(path_obj, "python")

    if output:
        output_path = Path(output)
        json_output = json.dumps(output_data, indent=2, default=str)
        output_path.write_text(json_output, encoding="utf-8")

    return output_data

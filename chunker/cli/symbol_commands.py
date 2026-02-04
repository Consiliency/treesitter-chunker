"""CLI commands for symbol extraction and dependency analysis."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from chunker.extractors.python import PythonExtractor


def setup_symbol_parser(subparsers: argparse._SubParsersAction) -> None:
    """Set up symbol extraction subcommands.

    Args:
        subparsers: Subparser action from main argument parser
    """
    symbol_parser = subparsers.add_parser(
        "symbols",
        help="Extract symbols and relationships from source code",
    )

    symbol_subparsers = symbol_parser.add_subparsers(
        dest="symbol_command",
        help="Symbol extraction commands",
    )

    # Extract command
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
    extract_parser.set_defaults(func=cmd_extract_symbols)


def cmd_extract_symbols(args: argparse.Namespace) -> int:
    """Extract symbols from a file or directory.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    path = Path(args.path)

    if not path.exists():
        print(f"Error: Path does not exist: {path}", file=sys.stderr)
        return 1

    # Collect Python files
    if path.is_file():
        files = [path]
    else:
        files = list(path.rglob("*.py"))
        # Exclude common non-source directories
        files = [
            f
            for f in files
            if not any(
                part in f.parts
                for part in [
                    "__pycache__",
                    ".git",
                    ".venv",
                    "venv",
                    "node_modules",
                    ".tox",
                    ".pytest_cache",
                    "build",
                    "dist",
                    ".eggs",
                ]
            )
        ]

    if not files:
        print(f"Error: No Python files found in {path}", file=sys.stderr)
        return 1

    # Extract symbols from each file
    extractor = PythonExtractor()
    all_symbols: dict[str, list] = {"classes": [], "functions": [], "imports": []}
    all_relationships: list[dict[str, Any]] = []
    all_metadata: dict[str, Any] = {
        "files_processed": 0,
        "total_classes": 0,
        "total_functions": 0,
        "total_imports": 0,
        "total_relationships": 0,
        "errors": [],
    }

    for file_path in sorted(files):
        try:
            source_code = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            all_metadata["errors"].append(f"Error reading {file_path}: {e}")
            continue

        # Compute module name from path relative to root
        try:
            rel_path = file_path.relative_to(path if path.is_dir() else path.parent)
            # Convert path to module name (remove .py, replace / with .)
            module_parts = list(rel_path.parts)
            if module_parts[-1].endswith(".py"):
                module_parts[-1] = module_parts[-1][:-3]
            module_name = ".".join(module_parts)
        except ValueError:
            module_name = file_path.stem

        result = extractor.extract_symbols(source_code, file_path, module_name)

        if result["errors"]:
            all_metadata["errors"].extend(result["errors"])
            continue

        # Merge symbols
        for class_def in result["symbols"]["classes"]:
            all_symbols["classes"].append(class_def)
        for func_def in result["symbols"]["functions"]:
            all_symbols["functions"].append(func_def)
        for import_def in result["symbols"]["imports"]:
            all_symbols["imports"].append(import_def)

        # Merge relationships
        all_relationships.extend(result["relationships"])

        all_metadata["files_processed"] += 1

    # Update totals
    all_metadata["total_classes"] = len(all_symbols["classes"])
    all_metadata["total_functions"] = len(all_symbols["functions"])
    all_metadata["total_imports"] = len(all_symbols["imports"])
    all_metadata["total_relationships"] = len(all_relationships)

    # Build output
    output = {
        "symbols": all_symbols,
        "relationships": all_relationships,
        "metadata": all_metadata,
    }

    # Format JSON
    indent = 2 if args.pretty else None
    json_output = json.dumps(output, indent=indent, default=str)

    # Write output
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(json_output, encoding="utf-8")
        print(f"Extracted symbols from {all_metadata['files_processed']} files")
        print(f"  Classes: {all_metadata['total_classes']}")
        print(f"  Functions: {all_metadata['total_functions']}")
        print(f"  Imports: {all_metadata['total_imports']}")
        print(f"  Relationships: {all_metadata['total_relationships']}")
        print(f"Output written to: {output_path}")
    else:
        print(json_output)

    return 0 if not all_metadata["errors"] else 1


def extract_symbols_cli(path: str, output: str | None = None) -> dict[str, Any]:
    """Programmatic interface to extract symbols.

    Args:
        path: Path to file or directory
        output: Optional output file path

    Returns:
        Extraction result dictionary
    """
    # Create namespace object to simulate parsed args
    args = argparse.Namespace(
        path=path,
        output=output,
        language="python",
        pretty=True,
    )

    path_obj = Path(path)
    if not path_obj.exists():
        return {"error": f"Path does not exist: {path}"}

    # Collect Python files
    if path_obj.is_file():
        files = [path_obj]
    else:
        files = list(path_obj.rglob("*.py"))
        files = [
            f
            for f in files
            if not any(
                part in f.parts
                for part in [
                    "__pycache__",
                    ".git",
                    ".venv",
                    "venv",
                    "node_modules",
                ]
            )
        ]

    extractor = PythonExtractor()
    all_symbols: dict[str, list] = {"classes": [], "functions": [], "imports": []}
    all_relationships: list[dict[str, Any]] = []
    errors: list[str] = []

    for file_path in sorted(files):
        try:
            source_code = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            errors.append(f"Error reading {file_path}: {e}")
            continue

        try:
            rel_path = file_path.relative_to(
                path_obj if path_obj.is_dir() else path_obj.parent
            )
            module_parts = list(rel_path.parts)
            if module_parts[-1].endswith(".py"):
                module_parts[-1] = module_parts[-1][:-3]
            module_name = ".".join(module_parts)
        except ValueError:
            module_name = file_path.stem

        result = extractor.extract_symbols(source_code, file_path, module_name)

        if result["errors"]:
            errors.extend(result["errors"])
            continue

        for class_def in result["symbols"]["classes"]:
            all_symbols["classes"].append(class_def)
        for func_def in result["symbols"]["functions"]:
            all_symbols["functions"].append(func_def)
        for import_def in result["symbols"]["imports"]:
            all_symbols["imports"].append(import_def)

        all_relationships.extend(result["relationships"])

    output_data = {
        "symbols": all_symbols,
        "relationships": all_relationships,
        "metadata": {
            "files_processed": len(files) - len(errors),
            "total_classes": len(all_symbols["classes"]),
            "total_functions": len(all_symbols["functions"]),
            "total_imports": len(all_symbols["imports"]),
            "total_relationships": len(all_relationships),
            "errors": errors,
        },
    }

    if output:
        output_path = Path(output)
        json_output = json.dumps(output_data, indent=2, default=str)
        output_path.write_text(json_output, encoding="utf-8")

    return output_data

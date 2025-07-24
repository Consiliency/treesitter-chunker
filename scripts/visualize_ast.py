#!/usr/bin/env python3
"""Simple command-line AST visualizer."""

from __future__ import annotations

import argparse
from pathlib import Path

from chunker.debug import render_ast_graph

EXT_LANG_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".c": "c",
    ".cpp": "cpp",
    ".rs": "rust",
}


def guess_language(path: Path) -> str | None:
    return EXT_LANG_MAP.get(path.suffix.lower())


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Tree-sitter AST to Graphviz")
    parser.add_argument("file", type=Path, help="Source file to visualize")
    parser.add_argument("--lang", "-l", dest="language", help="Programming language")
    parser.add_argument(
        "--out",
        "-o",
        dest="output",
        type=Path,
        help="Output file (SVG)",
    )
    parser.add_argument(
        "--format",
        "-f",
        dest="format",
        choices=["svg", "png"],
        default="svg",
        help="Graphviz output format",
    )
    args = parser.parse_args()

    language = args.language or guess_language(args.file)
    if not language:
        parser.error("Could not detect language, please specify --lang")

    output_path = str(args.output) if args.output else None
    source = render_ast_graph(
        str(args.file),
        language,
        output_path=output_path,
        format=args.format,
    )

    if not args.output:
        print(source)


if __name__ == "__main__":
    main()

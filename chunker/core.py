"""Core chunking functions used by multiple modules."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .languages import language_config_registry
from .metadata import MetadataExtractorFactory
from .parser import get_parser
from .types import CodeChunk

if TYPE_CHECKING:
    from tree_sitter import Node


def _walk(
    node: Node,
    source: bytes,
    language: str,
    parent_ctx: str | None = None,
    parent_chunk: CodeChunk | None = None,
    extractor=None,
    analyzer=None,
) -> list[CodeChunk]:
    """Walk the AST and extract chunks based on language configuration."""
    # Get language configuration
    config = language_config_registry.get(language)
    if not config:
        # Fallback to hardcoded defaults for backward compatibility
        CHUNK_TYPES = {"function_definition", "class_definition", "method_definition"}

        def should_chunk(node_type):
            return node_type in CHUNK_TYPES

        def should_ignore(_node_type):
            return False

    else:
        should_chunk = config.should_chunk_node
        should_ignore = config.should_ignore_node

    chunks: list[CodeChunk] = []
    current_chunk = None

    # Skip ignored nodes
    if should_ignore(node.type):
        return chunks

    # Check if this node should be a chunk
    if should_chunk(node.type):
        text = source[node.start_byte : node.end_byte].decode()
        current_chunk = CodeChunk(
            language=language,
            file_path="",
            node_type=node.type,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            byte_start=node.start_byte,
            byte_end=node.end_byte,
            parent_context=parent_ctx or "",
            content=text,
            parent_chunk_id=parent_chunk.chunk_id if parent_chunk else None,
        )

        # Extract metadata if extractors are available
        if extractor or analyzer:
            metadata = {}

            if extractor:
                # Extract signature
                signature = extractor.extract_signature(node, source)
                if signature:
                    metadata["signature"] = {
                        "name": signature.name,
                        "parameters": signature.parameters,
                        "return_type": signature.return_type,
                        "decorators": signature.decorators,
                        "modifiers": signature.modifiers,
                    }

                # Extract docstring
                docstring = extractor.extract_docstring(node, source)
                if docstring:
                    metadata["docstring"] = docstring

                # Extract dependencies
                dependencies = extractor.extract_dependencies(node, source)
                metadata["dependencies"] = sorted(dependencies) if dependencies else []
                current_chunk.dependencies = (
                    sorted(dependencies) if dependencies else []
                )

                # Extract imports
                imports = extractor.extract_imports(node, source)
                if imports:
                    metadata["imports"] = imports

                # Extract exports
                exports = extractor.extract_exports(node, source)
                if exports:
                    metadata["exports"] = sorted(exports)

            if analyzer:
                # Calculate complexity metrics
                complexity = analyzer.analyze_complexity(node, source)
                metadata["complexity"] = {
                    "cyclomatic": complexity.cyclomatic,
                    "cognitive": complexity.cognitive,
                    "nesting_depth": complexity.nesting_depth,
                    "lines_of_code": complexity.lines_of_code,
                    "logical_lines": complexity.logical_lines,
                }

            current_chunk.metadata = metadata

        chunks.append(current_chunk)
        parent_ctx = node.type  # nested functions, etc.

    # Walk children with current chunk as parent
    for child in node.children:
        chunks.extend(
            _walk(
                child,
                source,
                language,
                parent_ctx,
                current_chunk or parent_chunk,
                extractor,
                analyzer,
            ),
        )

    return chunks


def chunk_text(
    text: str,
    language: str,
    file_path: str = "",
    extract_metadata: bool = True,
) -> list[CodeChunk]:
    """Parse text and return a list of `CodeChunk`.

    Args:
        text: Source code text to chunk
        language: Programming language
        file_path: Path to the file (optional)
        extract_metadata: Whether to extract metadata (default: True)

    Returns:
        List of CodeChunk objects with optional metadata
    """
    parser = get_parser(language)
    src = text.encode()
    tree = parser.parse(src)

    # Create metadata extractors if requested
    extractor = None
    analyzer = None
    if extract_metadata:
        extractor = MetadataExtractorFactory.create_extractor(language)
        analyzer = MetadataExtractorFactory.create_analyzer(language)

    chunks = _walk(
        tree.root_node,
        src,
        language,
        extractor=extractor,
        analyzer=analyzer,
    )
    for c in chunks:
        c.file_path = file_path
    return chunks


def chunk_file(
    path: str | Path,
    language: str,
    extract_metadata: bool = True,
) -> list[CodeChunk]:
    """Parse the file and return a list of `CodeChunk`.

    Args:
        path: Path to the file to chunk
        language: Programming language
        extract_metadata: Whether to extract metadata (default: True)

    Returns:
        List of CodeChunk objects with optional metadata
    """
    src = Path(path).read_text(encoding="utf-8")
    return chunk_text(src, language, str(path), extract_metadata=extract_metadata)

"""Core chunking functions used by multiple modules."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from .languages import language_config_registry

# Imported lazily below to avoid circular import with multi_language
from .metadata import MetadataExtractorFactory
from .parser import get_parser
from .types import CodeChunk, compute_file_id, compute_node_id, compute_symbol_id

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
    parent_route: list[str] | None = None,
) -> list[CodeChunk]:
    """Walk the AST and extract chunks based on language configuration."""
    # Get language configuration
    config = language_config_registry.get(language)
    if not config:
        # Fallback to hardcoded defaults for backward compatibility
        if language in {"csharp", "c_sharp"}:
            # Tree-sitter C# node types
            chunk_types = {
                "class_declaration",
                "struct_declaration",
                "interface_declaration",
                "enum_declaration",
                "method_declaration",
                "constructor_declaration",
                "property_declaration",
                "field_declaration",
                "record_declaration",
            }
        else:
            chunk_types = {
                "function_definition",
                "class_definition",
                "method_definition",
            }

        def should_chunk(node_type):
            return node_type in chunk_types

        def should_ignore(_node_type):
            return False

    else:
        should_chunk = config.should_chunk_node
        should_ignore = config.should_ignore_node
        # Go: ensure common declaration node types are chunked even if rules are minimal
        if language == "go":
            go_decl_like = {
                "function_declaration",
                "method_declaration",
                "type_declaration",
                "type_spec",
                "const_declaration",
                "var_declaration",
            }

            def should_chunk(node_type: str) -> bool:  # type: ignore[no-redef]
                return config.should_chunk_node(node_type) or node_type in go_decl_like

        # For LISPy languages like Clojure, treat top-level list forms as chunks
        if language == "clojure":

            def should_chunk(node_type: str) -> bool:  # type: ignore[no-redef]
                return node_type == "list_lit" or config.should_chunk_node(node_type)

        # For Dart, the grammar exposes separate signature/body nodes. Treat
        # signatures as declarations for chunking.
        elif language == "dart":
            dart_signature_types = {
                "function_signature",
                "method_signature",
                "getter_signature",
                "setter_signature",
                "constructor_signature",
                "factory_constructor_signature",
            }
            dart_extra_decl_like = {"class_definition", "type_alias"}

            def should_chunk(node_type: str) -> bool:  # type: ignore[no-redef]
                return (
                    config.should_chunk_node(node_type)
                    or node_type in dart_signature_types
                    or node_type in dart_extra_decl_like
                )

    chunks: list[CodeChunk] = []
    current_chunk = None

    # Skip ignored nodes
    if should_ignore(node.type):
        return chunks

    # Ensure route list
    parent_route = (parent_route or []).copy()

    # R special-cases: treat setClass/setMethod calls as chunks
    force_chunk = False
    r_call_name: str | None = None
    if language == "r" and node.type == "call":
        try:
            callee = (getattr(node, "children", None) or [None])[0]
            if getattr(callee, "type", None) == "identifier":
                ident = source[callee.start_byte : callee.end_byte].decode(
                    "utf-8",
                    errors="ignore",
                )
                if ident in {"setClass", "setMethod", "setGeneric"}:
                    force_chunk = True
                    r_call_name = ident
        except Exception:
            pass

    # Check if this node should be a chunk
    if should_chunk(node.type) or force_chunk:
        # Default span covers the current node
        span_start = node.start_byte
        span_end = node.end_byte
        adjusted_node_type = node.type
        # Dart: merge signature + body into a single declaration chunk
        if language == "dart":
            dart_sig_to_decl = {
                "function_signature": "function_declaration",
                "method_signature": "method_declaration",
                "getter_signature": "getter_declaration",
                "setter_signature": "setter_declaration",
                "constructor_signature": "constructor_declaration",
                "factory_constructor_signature": "factory_constructor",
            }
            if node.type in dart_sig_to_decl:
                adjusted_node_type = dart_sig_to_decl[node.type]
                # Find following function_body sibling under same parent
                parent = getattr(node, "parent", None)
                if parent is not None:
                    try:
                        children = list(parent.children)
                        idx = children.index(node)
                        for sib in children[idx + 1 :]:
                            if sib.type == "function_body":
                                span_end = sib.end_byte
                                break
                    except Exception:
                        pass
            elif node.type == "class_definition":
                # Normalize to expected name used in tests/config
                adjusted_node_type = "class_declaration"
            elif node.type == "type_alias":
                # Normalize Dart type aliases to typedef_declaration for tests
                adjusted_node_type = "typedef_declaration"
        # Elixir: reinterpret certain call forms as declarations
        elif language == "elixir":
            if node.type == "call":
                try:
                    for child in getattr(node, "children", []) or []:
                        if getattr(child, "type", None) == "identifier":
                            ident = source[child.start_byte : child.end_byte].decode(
                                "utf-8",
                                errors="ignore",
                            )
                            if ident in {"def", "defp", "defmacro", "defmacrop"}:
                                adjusted_node_type = "function_definition"
                                break
                            if ident == "defmodule":
                                adjusted_node_type = "module_definition"
                                break
                            if ident == "defprotocol":
                                adjusted_node_type = "protocol_definition"
                                break
                            if ident == "defimpl":
                                adjusted_node_type = "implementation_definition"
                                break
                            if ident == "defstruct":
                                adjusted_node_type = "struct_definition"
                                break
                except Exception:
                    pass
        elif language == "haskell":
            # Normalize Haskell node variants to canonical names expected by tests
            if node.type == "type_declaration" or node.type == "type_synomym":
                adjusted_node_type = "type_synonym"
            elif node.type == "class":
                adjusted_node_type = "class_declaration"
            elif node.type == "instance":
                adjusted_node_type = "instance_declaration"
            elif node.type == "header":
                adjusted_node_type = "module_declaration"
        elif language == "scala":
            # Scala: detect case classes and adjust node type
            if node.type == "class_definition":
                # Check if this is a case class by examining first child
                if node.children and node.children[0].type == "case":
                    adjusted_node_type = "case_class_definition"
            elif node.type == "function_definition":
                # Check if this function is inside a class/trait/object (making it a method)
                parent = getattr(node, "parent", None)
                while parent:
                    if parent.type in {
                        "class_definition",
                        "trait_definition",
                        "object_definition",
                        "template_body",
                    }:
                        adjusted_node_type = "method_definition"
                        break
                    parent = getattr(parent, "parent", None)
        elif language == "julia":
            # Map Julia assignment nodes that are actually function definitions
            if node.type == "assignment":
                # Check if left side is a call_expression (function signature)
                for child in node.children:
                    if child.type == "call_expression":
                        adjusted_node_type = "short_function_definition"
                        break
            elif node.type == "abstract_definition":
                adjusted_node_type = "abstract_type_definition"
            elif node.type == "primitive_definition":
                adjusted_node_type = "primitive_type_definition"
        elif language == "sql":
            # Map tree-sitter SQL node types to expected test node types
            if node.type in {
                "insert",
                "update",
                "delete",
                "select",
            } or node.type.startswith("create_"):
                adjusted_node_type = f"{node.type}_statement"
            elif node.type == "ERROR":
                # Handle ERROR nodes that might be CREATE PROCEDURE/FUNCTION
                content = (
                    source[node.start_byte : node.end_byte]
                    .decode(
                        "utf-8",
                        errors="replace",
                    )
                    .lower()
                )
                if "create procedure" in content:
                    adjusted_node_type = "create_procedure_statement"
                elif "create function" in content:
                    adjusted_node_type = "create_function_statement"
                # else keep as ERROR (will be filtered out later)
        # Clojure: reinterpret list forms as their defining form (defn, def, etc.)
        if language == "clojure" and node.type == "list_lit":
            # Use named children to skip parentheses and punctuation tokens
            children = list(getattr(node, "named_children", []) or [])
            if len(children) >= 1 and children[0].type == "sym_lit":
                form_name = (
                    source[children[0].start_byte : children[0].end_byte]
                    .decode("utf-8", errors="replace")
                    .strip()
                )
                if form_name in {
                    "defn",
                    "defn-",
                    "def",
                    "defmacro",
                    "defprotocol",
                    "deftype",
                    "defrecord",
                    "defmulti",
                    "defmethod",
                    "defonce",
                    "defstruct",
                }:
                    adjusted_node_type = form_name
        # For R, include the name identifier for assignment-based function defs by
        # expanding the span to include the full assignment expression
        if language == "r" and node.type in {"function_definition"}:
            parent = getattr(node, "parent", None)
            if parent is not None and parent.type in {
                "assignment",
                "left_assignment",
                "right_assignment",
                "binary_operator",
            }:
                # Expand to the parent span so the chunk content includes the name and <-
                span_start = min(span_start, parent.start_byte)
                span_end = max(span_end, parent.end_byte)
        # For R special call chunks, normalize node type to the callee name
        if language == "r" and force_chunk and r_call_name:
            adjusted_node_type = r_call_name
        text = source[span_start:span_end].decode()
        current_route = [*parent_route, adjusted_node_type]
        current_chunk = CodeChunk(
            language=language,
            file_path="",
            node_type=adjusted_node_type,
            start_line=node.start_point[0] + 1,
            end_line=(
                # Estimate end line from span_end by walking to end_point if same node
                node.end_point[0] + 1
                if span_end == node.end_byte
                else None  # type: ignore[truthy-bool]
            )
            or (node.end_point[0] + 1),
            byte_start=span_start,
            byte_end=span_end,
            parent_context=parent_ctx or "",
            content=text,
            parent_chunk_id=(parent_chunk.node_id if parent_chunk else None),
            parent_route=current_route,
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

            # Set metadata type field for all languages when metadata extraction is enabled
            if language in {"typescript", "tsx"}:
                # TypeScript-specific metadata type mapping
                if adjusted_node_type == "interface_declaration":
                    metadata["type"] = "interface_declaration"
                elif adjusted_node_type == "type_alias_declaration":
                    metadata["type"] = "type_alias_declaration"
                elif adjusted_node_type == "enum_declaration":
                    metadata["type"] = "enum_declaration"
                elif adjusted_node_type in {"internal_module", "module"}:
                    metadata["type"] = "namespace_declaration"
                elif adjusted_node_type == "abstract_class_declaration":
                    metadata["type"] = "class_declaration"
                    metadata["abstract"] = True
                else:
                    metadata["type"] = adjusted_node_type
            else:
                # For other languages, set type to node_type by default
                metadata["type"] = adjusted_node_type

            current_chunk.metadata = metadata
        else:
            # For compatibility, even if no extractors create an empty metadata dict
            current_chunk.metadata = {}

        chunks.append(current_chunk)
        # Set better context for select languages
        if language == "go":
            try:
                if adjusted_node_type in {
                    "function_declaration",
                    "method_declaration",
                    "type_spec",
                    "type_declaration",
                }:
                    name_node = getattr(node, "child_by_field_name", lambda _n: None)(
                        "name",
                    )
                    if name_node is not None:
                        item_name = source[
                            name_node.start_byte : name_node.end_byte
                        ].decode(
                            "utf-8",
                            errors="ignore",
                        )
                        # Assign entity name to parent_context for compatibility with tests
                        current_chunk.parent_context = item_name
            except Exception:
                pass
        # Dart: also emit a synthetic 'widget_class' chunk for Flutter widgets
        if (
            language == "dart"
            and adjusted_node_type == "class_declaration"
            and ("extends StatelessWidget" in text or "extends StatefulWidget" in text)
        ):
            widget_chunk = CodeChunk(
                language=language,
                file_path="",
                node_type="widget_class",
                start_line=current_chunk.start_line,
                end_line=current_chunk.end_line,
                byte_start=current_chunk.byte_start,
                byte_end=current_chunk.byte_end,
                parent_context=current_chunk.parent_context,
                content=current_chunk.content,
                parent_chunk_id=current_chunk.parent_chunk_id,
                parent_route=current_route + ["widget_class"],
            )
            chunks.append(widget_chunk)
        # Vue: synthesize a component_definition from script contents
        if language == "vue" and node.type == "script_element":
            try:
                script_text = text
                if ("export default" in script_text) or (
                    "defineComponent" in script_text
                ):
                    comp_chunk = CodeChunk(
                        language=language,
                        file_path="",
                        node_type="component_definition",
                        start_line=current_chunk.start_line,
                        end_line=current_chunk.end_line,
                        byte_start=current_chunk.byte_start,
                        byte_end=current_chunk.byte_end,
                        parent_context="script_element",
                        content=current_chunk.content,
                        parent_chunk_id=current_chunk.parent_chunk_id,
                        parent_route=current_route + ["component_definition"],
                    )
                    chunks.append(comp_chunk)
            except Exception:
                pass
        # Svelte: synthesize reactive_statement chunks from script contents
        if language == "svelte" and node.type == "script_element":
            try:
                # Extract raw script body between tags if present
                script_text = text
                body = script_text
                gt = script_text.find(">")
                end_tag = script_text.rfind("</")
                if gt != -1 and end_tag != -1 and gt + 1 < end_tag:
                    body = script_text[gt + 1 : end_tag]
                lines = body.splitlines()
                for idx, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.startswith("$:"):
                        reactive_chunk = CodeChunk(
                            language=language,
                            file_path="",
                            node_type="reactive_statement",
                            start_line=current_chunk.start_line + idx,
                            end_line=current_chunk.start_line + idx,
                            byte_start=0,
                            byte_end=0,
                            parent_context="script_element",
                            content=line,
                            parent_chunk_id=current_chunk.parent_chunk_id,
                            parent_route=current_route + ["reactive_statement"],
                        )
                        chunks.append(reactive_chunk)
            except Exception:
                pass
        # Svelte: synthesize control-flow chunks by scanning entire file once at top-level
        if language == "svelte" and parent_chunk is None:
            try:
                full_text = source.decode("utf-8", errors="replace")
                lines = full_text.splitlines()
                for idx, line in enumerate(lines, start=1):
                    stripped = line.strip()
                    cf_type = None
                    if stripped.startswith("{#if"):
                        cf_type = "if_block"
                    elif stripped.startswith("{#each"):
                        cf_type = "each_block"
                    elif stripped.startswith("{#await"):
                        cf_type = "await_block"
                    elif stripped.startswith("{#key"):
                        cf_type = "key_block"
                    if cf_type:
                        cf_chunk = CodeChunk(
                            language=language,
                            file_path="",
                            node_type=cf_type,
                            start_line=idx,
                            end_line=idx,
                            byte_start=0,
                            byte_end=0,
                            parent_context="template",
                            content=line,
                            parent_chunk_id=None,
                            parent_route=[cf_type],
                        )
                        chunks.append(cf_chunk)
            except Exception:
                pass
        parent_ctx = node.type  # nested functions, etc.
        parent_route = current_route

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
                parent_route=parent_route,
            ),
        )

    # Julia-specific post-processing: merge preceding comments with definitions
    if language == "julia":
        chunks = _merge_julia_comments_with_definitions(chunks)

    # MATLAB-specific post-processing: detect scripts
    if language == "matlab":
        chunks = _detect_matlab_scripts(chunks, node, source, parent_chunk)

    return chunks


def _merge_julia_comments_with_definitions(chunks: list[CodeChunk]) -> list[CodeChunk]:
    """Merge Julia comment chunks with following definition chunks."""
    if not chunks:
        return chunks

    merged_chunks = []
    i = 0
    while i < len(chunks):
        current_chunk = chunks[i]

        # Check if this is a line comment followed by a definition
        if (
            current_chunk.node_type == "line_comment"
            and i + 1 < len(chunks)
            and chunks[i + 1].node_type
            in {
                "struct_definition",
                "function_definition",
                "module_definition",
                "macro_definition",
                "macrocall_expression",
                "abstract_definition",
                "primitive_definition",
                "abstract_type_definition",
                "primitive_type_definition",
            }
        ):
            next_chunk = chunks[i + 1]

            # Check if they're adjacent (comment right before definition)
            if (
                current_chunk.end_line + 1 == next_chunk.start_line
                or current_chunk.end_line == next_chunk.start_line
            ):

                # Merge the comment content with the definition content
                merged_content = current_chunk.content + "\n" + next_chunk.content

                # Create a new chunk with the merged content
                merged_chunk = CodeChunk(
                    language=next_chunk.language,
                    file_path=next_chunk.file_path,
                    node_type=next_chunk.node_type,
                    start_line=current_chunk.start_line,
                    end_line=next_chunk.end_line,
                    byte_start=current_chunk.byte_start,
                    byte_end=next_chunk.byte_end,
                    parent_context=next_chunk.parent_context,
                    content=merged_content,
                    parent_chunk_id=next_chunk.parent_chunk_id,
                    parent_route=next_chunk.parent_route,
                )

                # Copy metadata from the definition chunk
                if hasattr(next_chunk, "metadata"):
                    merged_chunk.metadata = next_chunk.metadata

                merged_chunks.append(merged_chunk)
                i += 2  # Skip both chunks
                continue

        # If not merging, just add the current chunk
        merged_chunks.append(current_chunk)
        i += 1

    return merged_chunks


def _detect_matlab_scripts(
    chunks: list[CodeChunk],
    node,
    source: bytes,
    parent_chunk,
) -> list[CodeChunk]:
    """Detect MATLAB scripts and add script chunks when appropriate."""
    # Only process at the source_file level (top level) with no parent chunk
    if node.type != "source_file" or parent_chunk is not None:
        return chunks

    # Check if there are top-level statements that make this a script
    has_top_level_code = False
    has_functions_or_classes = any(
        chunk.node_type in {"function_definition", "classdef", "class_definition"}
        for chunk in chunks
    )

    # Look for top-level statements in the node children
    for child in node.children:
        if child.type in {"assignment", "function_call", "command", "comment"}:
            has_top_level_code = True
            break

    # If there's top-level code, create a script chunk for the whole file
    if has_top_level_code:
        content = source.decode("utf-8", errors="replace")
        script_chunk = CodeChunk(
            language="matlab",
            file_path="",
            node_type="script",
            start_line=1,
            end_line=content.count("\n") + 1,
            byte_start=0,
            byte_end=len(source),
            parent_context="",
            content=content,
            parent_chunk_id=None,
            parent_route=["script"],
        )
        # Insert script chunk at the beginning
        chunks.insert(0, script_chunk)

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

    # Build mapping from temporary IDs (no path) to final IDs (with path)
    tmp_to_final: dict[str, str] = {}
    for c in chunks:
        tmp_id = compute_node_id("", c.language, c.parent_route, c.content)
        final_id = compute_node_id(
            file_path,
            c.language,
            c.parent_route,
            c.content,
        )
        tmp_to_final[tmp_id] = final_id

    for c in chunks:
        c.file_path = file_path
        # update file/node ids now that path is known
        c.file_id = compute_file_id(file_path)
        c.node_id = compute_node_id(
            file_path,
            c.language,
            c.parent_route,
            c.content,
        )
        c.chunk_id = c.node_id
        # fix parent id if it was set using temporary id
        if c.parent_chunk_id and c.parent_chunk_id in tmp_to_final:
            c.parent_chunk_id = tmp_to_final[c.parent_chunk_id]
        # recompute symbol id if signature present
        sig = c.metadata.get("signature") if c.metadata else None
        if sig and sig.get("name"):
            c.symbol_id = compute_symbol_id(language, file_path, sig["name"])
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
    # Read file contents with robust decoding
    p = Path(path)
    try:
        src = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Fallback: replace invalid bytes to avoid crashing on bad encodings
        src = p.read_bytes().decode("utf-8", errors="replace")

    # Special handling for R Markdown: extract embedded R code blocks
    if language == "r" and p.suffix.lower() in {".rmd", ".rmarkdown"}:
        from .multi_language import (  # local import to avoid cycle
            MultiLanguageProcessorImpl,
        )

        ml = MultiLanguageProcessorImpl()
        # Prefer robust Rmd extraction that supports ```{r chunk-name}
        pattern = re.compile(r"```\{r[^}]*\}\s*\r?\n([\s\S]*?)\r?\n```", re.DOTALL)
        snippets = [(m.group(1), m.start(1), m.end(1)) for m in pattern.finditer(src)]
        # Fallback to generic markdown extractor if custom pattern finds nothing
        if not snippets:
            snippets = ml.extract_embedded_code(
                src,
                host_language="markdown",
                target_language="r",
            )
        all_chunks: list[CodeChunk] = []
        for code, start, end in snippets:
            # Derive pseudo file name for chunk id stability
            pseudo_path = f"{p}:{start}-{end}"
            all_chunks.extend(
                chunk_text(
                    code,
                    "r",
                    pseudo_path,
                    extract_metadata=extract_metadata,
                ),
            )
        return all_chunks

    return chunk_text(
        src,
        language,
        str(path),
        extract_metadata=extract_metadata,
    )

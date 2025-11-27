"""
Support for SQL language.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.utils.text import safe_decode_bytes

from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin

if TYPE_CHECKING:
    from tree_sitter import Node


class SQLConfig(LanguageConfig):
    """Language configuration for SQL."""

    @property
    def language_id(self) -> str:
        return "sql"

    @property
    def chunk_types(self) -> set[str]:
        """SQL-specific chunk types."""
        return {
            "statement",
            "create_table",
            "create_view",
            "create_index",
            "create_function",
            "create_procedure",
            "create_trigger",
            "alter_table",
            "drop_table",
            "select",
            "insert",
            "update",
            "delete",
            "comment",
            "ERROR",  # Include ERROR nodes for special handling
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".sql", ".psql", ".mysql", ".tsql"}

    def __init__(self):
        super().__init__()
        self.add_chunk_rule(
            ChunkRule(
                node_types={"cte", "with_clause"},
                include_children=True,
                priority=5,
                metadata={"type": "common_table_expression"},
            ),
        )
        self.add_ignore_type("string")
        self.add_ignore_type("identifier")


# Register the SQL configuration


class SQLPlugin(LanguagePlugin, ExtendedLanguagePluginContract):
    """Plugin for SQL language chunking."""

    @property
    def language_name(self) -> str:
        return "sql"

    @property
    def supported_extensions(self) -> set[str]:
        return {".sql", ".psql", ".mysql", ".tsql"}

    @property
    def default_chunk_types(self) -> set[str]:
        return {
            "statement",
            "create_table",
            "create_view",
            "create_index",
            "create_function",
            "create_procedure",
            "create_trigger",
            "alter_table",
            "drop_table",
            "select",
            "insert",
            "update",
            "delete",
            "comment",
            "ERROR",  # Include ERROR nodes for special handling
        }

    @staticmethod
    def get_node_name(node: Node, source: bytes) -> str | None:
        """Extract the object name from a SQL node."""
        if node.type.startswith("create_"):
            for child in node.children:
                if child.type in {"relation", "identifier"}:
                    return safe_decode_bytes(source[child.start_byte : child.end_byte])
                if child.type == "object_reference":
                    for subchild in child.children:
                        if subchild.type == "identifier":
                            return safe_decode_bytes(
                                source[subchild.start_byte : subchild.end_byte]
                            )
        elif node.type in {"function_definition", "procedure_definition"}:
            for child in node.children:
                if child.type == "identifier":
                    return safe_decode_bytes(source[child.start_byte : child.end_byte])
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to SQL."""
        chunks = []

        def extract_chunks(n: Node, _parent_type: str | None = None):
            if n.type in self.default_chunk_types:
                content = safe_decode_bytes(source[n.start_byte : n.end_byte])

                # Map tree-sitter node types to expected test node types
                node_type = n.type

                # Special handling for ERROR nodes that might be CREATE PROCEDURE
                if n.type == "ERROR":
                    content_lower = content.lower()
                    if "create procedure" in content_lower:
                        node_type = "create_procedure_statement"
                    elif "create function" in content_lower:
                        node_type = "create_function_statement"
                    else:
                        # Skip ERROR nodes that aren't recognized patterns
                        return
                elif n.type in {
                    "insert",
                    "update",
                    "delete",
                    "select",
                } or n.type.startswith("create_"):
                    node_type = f"{n.type}_statement"

                chunk = {
                    "type": node_type,
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "object_name": self.get_node_name(n, source),
                }
                # Add statement type metadata for SQL operations
                if n.type in {"insert", "update", "delete", "select"}:
                    chunk["statement_type"] = n.type.upper()
                elif n.type.startswith("create_"):
                    chunk["statement_type"] = n.type.replace(
                        "create_",
                        "CREATE ",
                    ).upper()
                elif node_type == "create_procedure_statement":
                    chunk["statement_type"] = "CREATE PROCEDURE"
                chunks.append(chunk)
            for child in n.children:
                extract_chunks(child, n.type)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get SQL-specific node types that form chunks."""
        # Return the expected node type names for contract compliance
        return {
            "statement",
            "create_table_statement",
            "create_view_statement",
            "create_index_statement",
            "create_function_statement",
            "create_procedure_statement",
            "create_trigger_statement",
            "alter_table_statement",
            "drop_table_statement",
            "select_statement",
            "insert_statement",
            "update_statement",
            "delete_statement",
            "function_definition",
            "comment",
        }

    @staticmethod
    def should_chunk_node(node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        # Handle both actual tree-sitter types and expected test types
        # Actual tree-sitter SQL statement types
        if node.type in {"insert", "update", "delete", "select"}:
            return True
        # Expected test statement types
        if node.type.endswith("_statement"):
            return True
        # CREATE statements (both forms)
        if node.type.startswith("create_"):
            return True
        # Other SQL constructs
        if node.type in {
            "function_definition",
            "procedure_definition",
            "trigger_definition",
            "statement",
        }:
            return True
        # Handle ERROR nodes that might be unrecognized CREATE statements
        if node.type == "ERROR":
            return True
        return node.type == "comment"

    def get_node_context(self, node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node."""
        obj_name = self.get_node_name(node, source)
        if node.type.startswith("create_"):
            stmt_type = node.type.replace("create_", "").replace("_statement", "")
            if obj_name:
                return f"CREATE {stmt_type.upper()} {obj_name}"
            return f"CREATE {stmt_type.upper()}"
        if node.type == "select":
            for child in node.children:
                if child.type == "from":
                    for subchild in child.children:
                        if subchild.type == "relation":
                            table_name = safe_decode_bytes(
                                source[subchild.start_byte : subchild.end_byte]
                            )
                            return f"SELECT FROM {table_name}"
            return "SELECT statement"
        if node.type in {"insert", "update", "delete"}:
            return f"{node.type.upper()} statement"
        if (
            node.type
            in {
                "function_definition",
                "procedure_definition",
            }
            and obj_name
        ):
            return f"{node.type.replace('_definition', '').upper()} {obj_name}"
        return None

    def process_node(
        self,
        node: Node,
        source: bytes,
        file_path: str,
        parent_context: str | None = None,
    ):
        """Process SQL nodes with special handling for complex statements."""
        if node.type in {"create_function_statement", "create_procedure_statement"}:
            for child in node.children:
                if child.type in {
                    "function_definition",
                    "procedure_definition",
                }:
                    chunk = self.create_chunk(node, source, file_path, parent_context)
                    if chunk and self.should_include_chunk(chunk):
                        chunk.node_type = child.type
                        return chunk
        if node.type == "with_clause":
            chunks = []
            for child in node.children:
                if child.type == "cte":
                    chunk = self.create_chunk(child, source, file_path, parent_context)
                    if chunk and self.should_include_chunk(chunk):
                        chunks.append(chunk)
            return chunks if chunks else None
        return super().process_node(node, source, file_path, parent_context)


# Register the SQL configuration
from .base import language_config_registry

language_config_registry.register(SQLConfig())

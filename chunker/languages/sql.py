"""
Support for SQL language.
"""

from __future__ import annotations

from typing import Optional

from tree_sitter import Node

from ..contracts.language_plugin_contract import ExtendedLanguagePluginContract
from .base import ChunkRule, LanguageConfig
from .plugin_base import LanguagePlugin


class SQLConfig(LanguageConfig):
    """Language configuration for SQL."""

    @property
    def language_id(self) -> str:
        return "sql"

    @property
    def chunk_types(self) -> set[str]:
        """SQL-specific chunk types."""
        return {
            # DDL statements
            "create_table_statement",
            "create_view_statement",
            "create_index_statement",
            "create_function_statement",
            "create_procedure_statement",
            "create_trigger_statement",
            "alter_table_statement",
            "drop_statement",
            # DML statements
            "select_statement",
            "insert_statement",
            "update_statement",
            "delete_statement",
            # Other statements
            "function_definition",
            "procedure_definition",
            "trigger_definition",
            "comment",
        }

    @property
    def file_extensions(self) -> set[str]:
        return {".sql", ".psql", ".mysql", ".tsql"}

    def __init__(self):
        super().__init__()

        # Add rules for complex queries
        self.add_chunk_rule(
            ChunkRule(
                node_types={"cte", "with_clause"},
                include_children=True,
                priority=5,
                metadata={"type": "common_table_expression"},
            ),
        )

        # Ignore certain node types
        self.add_ignore_type("string")
        self.add_ignore_type("identifier")


# Register the SQL configuration
from . import language_config_registry

language_config_registry.register(
    SQLConfig(), aliases=["postgresql", "mysql", "sqlite"],
)


# Plugin implementation for backward compatibility
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
            "create_table_statement",
            "create_view_statement",
            "create_index_statement",
            "create_function_statement",
            "create_procedure_statement",
            "create_trigger_statement",
            "alter_table_statement",
            "drop_statement",
            "select_statement",
            "insert_statement",
            "update_statement",
            "delete_statement",
            "function_definition",
            "procedure_definition",
            "trigger_definition",
            "comment",
        }

    def get_node_name(self, node: Node, source: bytes) -> str | None:
        """Extract the object name from a SQL node."""
        if node.type.startswith("create_"):
            # Look for table/view/function name
            for child in node.children:
                if child.type == "relation" or child.type == "identifier":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
                elif child.type == "object_reference":
                    # Handle schema.table notation
                    for subchild in child.children:
                        if subchild.type == "identifier":
                            return source[
                                subchild.start_byte : subchild.end_byte
                            ].decode("utf-8")
        elif node.type in {"function_definition", "procedure_definition"}:
            # Look for function/procedure name
            for child in node.children:
                if child.type == "identifier":
                    return source[child.start_byte : child.end_byte].decode("utf-8")
        return None

    def get_semantic_chunks(self, node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to SQL."""
        chunks = []

        def extract_chunks(n: Node, parent_type: str = None):
            if n.type in self.default_chunk_types:
                content = source[n.start_byte : n.end_byte].decode(
                    "utf-8", errors="replace",
                )
                chunk = {
                    "type": n.type,
                    "start_line": n.start_point[0] + 1,
                    "end_line": n.end_point[0] + 1,
                    "content": content,
                    "object_name": self.get_node_name(n, source),
                }

                # Add statement type metadata
                if n.type.endswith("_statement"):
                    chunk["statement_type"] = n.type.replace("_statement", "").upper()

                chunks.append(chunk)

            for child in n.children:
                extract_chunks(child, n.type)

        extract_chunks(node)
        return chunks

    def get_chunk_node_types(self) -> set[str]:
        """Get SQL-specific node types that form chunks."""
        return self.default_chunk_types

    def should_chunk_node(self, node: Node) -> bool:
        """Determine if a specific node should be chunked."""
        # All statement nodes should be chunked
        if node.type.endswith("_statement"):
            return True
        # Function and procedure definitions
        if node.type in {
            "function_definition",
            "procedure_definition",
            "trigger_definition",
        }:
            return True
        # Comments are also chunks
        if node.type == "comment":
            return True
        return False

    def get_node_context(self, node: Node, source: bytes) -> Optional[str]:
        """Extract meaningful context for a node."""
        obj_name = self.get_node_name(node, source)

        if node.type.startswith("create_"):
            stmt_type = node.type.replace("create_", "").replace("_statement", "")
            if obj_name:
                return f"CREATE {stmt_type.upper()} {obj_name}"
            return f"CREATE {stmt_type.upper()}"
        elif node.type == "select_statement":
            # Try to extract main table reference
            for child in node.children:
                if child.type == "from_clause":
                    for subchild in child.children:
                        if subchild.type == "relation":
                            table_name = source[
                                subchild.start_byte : subchild.end_byte
                            ].decode("utf-8")
                            return f"SELECT FROM {table_name}"
            return "SELECT statement"
        elif node.type in {"function_definition", "procedure_definition"}:
            if obj_name:
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
        # Handle CREATE FUNCTION/PROCEDURE with body
        if node.type in {"create_function_statement", "create_procedure_statement"}:
            # The actual definition might be in a child node
            for child in node.children:
                if child.type in {"function_definition", "procedure_definition"}:
                    # Use the parent create statement range but mark as definition
                    chunk = self.create_chunk(node, source, file_path, parent_context)
                    if chunk and self.should_include_chunk(chunk):
                        chunk.node_type = child.type
                        return chunk

        # Handle CTEs (Common Table Expressions)
        if node.type == "with_clause":
            # Each CTE should be a separate chunk
            chunks = []
            for child in node.children:
                if child.type == "cte":
                    chunk = self.create_chunk(child, source, file_path, parent_context)
                    if chunk and self.should_include_chunk(chunk):
                        chunks.append(chunk)
            return chunks if chunks else None

        # Default processing
        return super().process_node(node, source, file_path, parent_context)

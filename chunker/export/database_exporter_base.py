"""Base class for database export functionality."""

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ..types import CodeChunk


class DatabaseExporterBase(ABC):
    """Base class for exporting code chunks to databases."""

    def __init__(self):
        self.chunks: list[CodeChunk] = []
        self.relationships: list[dict[str, Any]] = []
        self.schema_version = "1.0"

    def add_chunks(self, chunks: list[CodeChunk]) -> None:
        """Add chunks to be exported."""
        self.chunks.extend(chunks)

    def add_relationship(
        self,
        source_chunk: CodeChunk,
        target_chunk: CodeChunk,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Add a relationship between chunks."""
        rel = {
            "source_id": self._get_chunk_id(source_chunk),
            "target_id": self._get_chunk_id(target_chunk),
            "relationship_type": relationship_type,
            "properties": properties or {},
        }
        self.relationships.append(rel)

    def _get_chunk_id(self, chunk: CodeChunk) -> str:
        """Generate a unique ID for a chunk."""
        # Create a stable hash based on file path and position
        id_string = f"{chunk.file_path}:{chunk.start_line}:{chunk.end_line}"
        return hashlib.md5(id_string.encode()).hexdigest()

    def _get_chunk_data(self, chunk: CodeChunk) -> dict[str, Any]:
        """Convert chunk to database-friendly format."""
        # Get chunk_type from metadata or use node_type as fallback
        chunk_type = (
            chunk.metadata.get("chunk_type", chunk.node_type)
            if chunk.metadata
            else chunk.node_type
        )

        return {
            "id": self._get_chunk_id(chunk),
            "file_path": str(chunk.file_path),
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "start_byte": chunk.byte_start,
            "end_byte": chunk.byte_end,
            "content": chunk.content,
            "chunk_type": chunk_type,
            "language": chunk.language,
            "metadata": chunk.metadata or {},
        }

    @abstractmethod
    def get_schema_ddl(self) -> str:
        """Get the DDL statements to create the database schema.

        Returns:
            SQL DDL statements as a string
        """
        raise NotImplementedError("Subclasses must implement get_schema_ddl()")

    @abstractmethod
    def export(self, output_path: Path, **options) -> None:
        """Export chunks to the database format.

        Args:
            output_path: Path for the output file/database
            **options: Export-specific options
        """
        raise NotImplementedError("Subclasses must implement export()")

    @abstractmethod
    def get_insert_statements(self, batch_size: int = 100) -> list[str]:
        """Generate INSERT statements for the chunks.

        Args:
            batch_size: Number of records per INSERT statement

        Returns:
            List of SQL INSERT statements
        """
        raise NotImplementedError("Subclasses must implement get_insert_statements()")

    def get_index_statements(self) -> list[str]:
        """Get index creation statements for common queries.

        Returns:
            List of CREATE INDEX statements
        """
        return [
            # Files table indices
            "CREATE INDEX IF NOT EXISTS idx_file_path ON files(path);",
            "CREATE INDEX IF NOT EXISTS idx_files_language ON files(language);",
            # Chunks table indices
            "CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON chunks(file_id);",
            "CREATE INDEX IF NOT EXISTS idx_chunks_chunk_type ON chunks(chunk_type);",
            "CREATE INDEX IF NOT EXISTS idx_chunks_position ON chunks(file_id, start_line, end_line);",
            # Relationships table indices
            "CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_id);",
            "CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_id);",
            "CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(relationship_type);",
            # Composite indices for common queries
            "CREATE INDEX IF NOT EXISTS idx_chunks_file_type ON chunks(file_id, chunk_type);",
            "CREATE INDEX IF NOT EXISTS idx_relationships_source_type ON relationships(source_id, relationship_type);",
        ]

    def get_analysis_queries(self) -> dict[str, str]:
        """Get useful analysis queries for the exported data.

        Returns:
            Dict mapping query names to SQL queries
        """
        return {
            "chunks_per_file": """
                SELECT file_path, COUNT(*) as chunk_count
                FROM chunks
                GROUP BY file_path
                ORDER BY chunk_count DESC;
            """,
            "chunks_by_type": """
                SELECT chunk_type, COUNT(*) as count
                FROM chunks
                GROUP BY chunk_type
                ORDER BY count DESC;
            """,
            "average_chunk_size": """
                SELECT chunk_type,
                       AVG(end_line - start_line + 1) as avg_lines,
                       MIN(end_line - start_line + 1) as min_lines,
                       MAX(end_line - start_line + 1) as max_lines
                FROM chunks
                GROUP BY chunk_type;
            """,
            "relationship_summary": """
                SELECT relationship_type, COUNT(*) as count
                FROM relationships
                GROUP BY relationship_type
                ORDER BY count DESC;
            """,
            "most_connected_chunks": """
                SELECT c.id, c.file_path, c.chunk_type,
                       COUNT(DISTINCT r1.target_id) as outgoing,
                       COUNT(DISTINCT r2.source_id) as incoming
                FROM chunks c
                LEFT JOIN relationships r1 ON c.id = r1.source_id
                LEFT JOIN relationships r2 ON c.id = r2.target_id
                GROUP BY c.id, c.file_path, c.chunk_type
                ORDER BY (outgoing + incoming) DESC
                LIMIT 20;
            """,
            "find_dependencies": """
                -- Find all chunks that a given chunk depends on
                WITH RECURSIVE deps AS (
                    SELECT target_id as chunk_id, 1 as depth
                    FROM relationships
                    WHERE source_id = ? AND relationship_type IN ('IMPORTS', 'CALLS')
                    
                    UNION
                    
                    SELECT r.target_id, d.depth + 1
                    FROM relationships r
                    JOIN deps d ON r.source_id = d.chunk_id
                    WHERE r.relationship_type IN ('IMPORTS', 'CALLS')
                    AND d.depth < 5  -- Limit depth to prevent infinite recursion
                )
                SELECT DISTINCT c.*, d.depth
                FROM deps d
                JOIN chunks c ON d.chunk_id = c.id
                ORDER BY d.depth, c.file_path, c.start_line;
            """,
        }

"""Export chunks to database formats (SQLite, PostgreSQL)."""

from __future__ import annotations

import io
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from chunker.exceptions import ChunkerError
from chunker.interfaces.export import (
    ChunkRelationship,
    DatabaseExporter,
    ExportFormat,
    ExportMetadata,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from chunker.types import CodeChunk


class SQLiteExporter(DatabaseExporter):
    """Export chunks and relationships to SQLite database."""

    def __init__(self):
        self._chunks_table = "chunks"
        self._relationships_table = "relationships"
        self._metadata_table = "export_metadata"
        self._batch_size = 1000
        self._indexes = ["chunk_id", "file_path", "node_type", "language"]

    def export(
        self,
        chunks: list[CodeChunk],
        relationships: list[ChunkRelationship],
        output: Path | io.IOBase,
        metadata: ExportMetadata | None = None,
    ) -> None:
        """Export chunks with relationships to SQLite.

        Args:
            chunks: List of code chunks
            relationships: List of chunk relationships
            output: Output path or stream
            metadata: Export metadata
        """
        if isinstance(output, io.IOBase):
            raise ChunkerError("SQLite export requires a file path, not a stream")

        db_path = Path(output)

        # Create database connection
        conn = sqlite3.connect(str(db_path))

        try:
            # Create tables
            self._create_tables(conn)

            # Insert metadata
            if metadata:
                self._insert_metadata(conn, metadata)

            # Insert chunks in batches
            self._insert_chunks(conn, chunks)

            # Insert relationships in batches
            self._insert_relationships(conn, relationships)

            # Create indexes
            self._create_indexes(conn)

            # Commit changes
            conn.commit()

        finally:
            conn.close()

    def export_streaming(
        self,
        chunk_iterator: Iterator[CodeChunk],
        relationship_iterator: Iterator[ChunkRelationship],
        output: Path | io.IOBase,
    ) -> None:
        """Export using iterators for large datasets."""
        if isinstance(output, io.IOBase):
            raise ChunkerError("SQLite export requires a file path, not a stream")

        db_path = Path(output)

        # Create database connection
        conn = sqlite3.connect(str(db_path))

        try:
            # Create tables
            self._create_tables(conn)

            # Stream chunks in batches
            chunk_batch = []
            for chunk in chunk_iterator:
                chunk_batch.append(chunk)
                if len(chunk_batch) >= self._batch_size:
                    self._insert_chunks(conn, chunk_batch)
                    chunk_batch = []

            # Insert remaining chunks
            if chunk_batch:
                self._insert_chunks(conn, chunk_batch)

            # Stream relationships in batches
            rel_batch = []
            for rel in relationship_iterator:
                rel_batch.append(rel)
                if len(rel_batch) >= self._batch_size:
                    self._insert_relationships(conn, rel_batch)
                    rel_batch = []

            # Insert remaining relationships
            if rel_batch:
                self._insert_relationships(conn, rel_batch)

            # Create indexes
            self._create_indexes(conn)

            # Commit changes
            conn.commit()

        finally:
            conn.close()

    def set_table_names(self, chunks_table: str, relationships_table: str) -> None:
        """Set custom table names."""
        self._chunks_table = chunks_table
        self._relationships_table = relationships_table

    def create_indexes(self, columns: list[str]) -> None:
        """Create indexes on specified columns."""
        self._indexes = columns

    def set_batch_size(self, size: int) -> None:
        """Set batch size for inserts."""
        self._batch_size = size

    def supports_format(self, format: ExportFormat) -> bool:
        """Check if this exporter supports a format."""
        return format == ExportFormat.SQLITE

    def get_schema(self) -> dict[str, Any]:
        """Get the export schema."""
        return {
            "format": "sqlite",
            "version": "3",
            "tables": {
                "chunks": self._chunks_table,
                "relationships": self._relationships_table,
                "metadata": self._metadata_table,
            },
            "indexes": self._indexes,
            "batch_size": self._batch_size,
        }

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        """Create database tables."""
        cursor = conn.cursor()

        # Create chunks table
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self._chunks_table} (
                chunk_id TEXT PRIMARY KEY,
                language TEXT NOT NULL,
                file_path TEXT NOT NULL,
                node_type TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                byte_start INTEGER NOT NULL,
                byte_end INTEGER NOT NULL,
                parent_context TEXT,
                content TEXT NOT NULL,
                parent_chunk_id TEXT,
                chunk_references TEXT,  -- JSON array
                chunk_dependencies TEXT,  -- JSON array
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
        )

        # Create relationships table
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self._relationships_table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_chunk_id TEXT NOT NULL,
                target_chunk_id TEXT NOT NULL,
                relationship_type TEXT NOT NULL,
                metadata TEXT,  -- JSON object
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_chunk_id) REFERENCES {self._chunks_table}(chunk_id),
                FOREIGN KEY (target_chunk_id) REFERENCES {self._chunks_table}(chunk_id)
            )
        """,
        )

        # Create metadata table
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self._metadata_table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                format TEXT NOT NULL,
                version TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                source_files TEXT NOT NULL,  -- JSON array
                chunk_count INTEGER NOT NULL,
                relationship_count INTEGER NOT NULL,
                options TEXT,  -- JSON object
                export_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
        )

    def _insert_metadata(
        self,
        conn: sqlite3.Connection,
        metadata: ExportMetadata,
    ) -> None:
        """Insert export metadata."""
        cursor = conn.cursor()

        cursor.execute(
            f"""
            INSERT INTO {self._metadata_table}
            (format, version, created_at, source_files, chunk_count, relationship_count, options)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                metadata.format.value,
                metadata.version,
                metadata.created_at,
                json.dumps(metadata.source_files),
                metadata.chunk_count,
                metadata.relationship_count,
                json.dumps(metadata.options),
            ),
        )

    def _insert_chunks(self, conn: sqlite3.Connection, chunks: list[CodeChunk]) -> None:
        """Insert chunks in batch."""
        cursor = conn.cursor()

        chunk_data = [
            (
                chunk.chunk_id,
                chunk.language,
                chunk.file_path,
                chunk.node_type,
                chunk.start_line,
                chunk.end_line,
                chunk.byte_start,
                chunk.byte_end,
                chunk.parent_context,
                chunk.content,
                chunk.parent_chunk_id,
                json.dumps(chunk.references),
                json.dumps(chunk.dependencies),
            )
            for chunk in chunks
        ]

        cursor.executemany(
            f"""
            INSERT OR REPLACE INTO {self._chunks_table}
            (chunk_id, language, file_path, node_type, start_line, end_line,
             byte_start, byte_end, parent_context, content, parent_chunk_id,
             chunk_references, chunk_dependencies)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            chunk_data,
        )

    def _insert_relationships(
        self,
        conn: sqlite3.Connection,
        relationships: list[ChunkRelationship],
    ) -> None:
        """Insert relationships in batch."""
        cursor = conn.cursor()

        rel_data = [
            (
                rel.source_chunk_id,
                rel.target_chunk_id,
                rel.relationship_type.value,
                json.dumps(rel.metadata) if rel.metadata else None,
            )
            for rel in relationships
        ]

        cursor.executemany(
            f"""
            INSERT INTO {self._relationships_table}
            (source_chunk_id, target_chunk_id, relationship_type, metadata)
            VALUES (?, ?, ?, ?)
        """,
            rel_data,
        )

    def _create_indexes(self, conn: sqlite3.Connection) -> None:
        """Create database indexes."""
        cursor = conn.cursor()

        # Create indexes on chunks table
        for column in self._indexes:
            if column in [
                "chunk_id",
                "file_path",
                "node_type",
                "language",
                "parent_chunk_id",
            ]:
                index_name = f"idx_{self._chunks_table}_{column}"
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS {index_name} ON {self._chunks_table}({column})",
                )

        # Create indexes on relationships table
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{self._relationships_table}_source "
            f"ON {self._relationships_table}(source_chunk_id)",
        )
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{self._relationships_table}_target "
            f"ON {self._relationships_table}(target_chunk_id)",
        )
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{self._relationships_table}_type "
            f"ON {self._relationships_table}(relationship_type)",
        )


class PostgreSQLExporter(DatabaseExporter):
    """Export chunks and relationships to PostgreSQL database.

    Note: This exporter generates SQL scripts rather than directly
    connecting to a database, to avoid dependency on psycopg2.
    """

    def __init__(self):
        self._chunks_table = "chunks"
        self._relationships_table = "relationships"
        self._metadata_table = "export_metadata"
        self._batch_size = 1000
        self._indexes = ["chunk_id", "file_path", "node_type", "language"]
        self._schema = "public"

    def export(
        self,
        chunks: list[CodeChunk],
        relationships: list[ChunkRelationship],
        output: Path | io.IOBase,
        metadata: ExportMetadata | None = None,
    ) -> None:
        """Export chunks with relationships as PostgreSQL SQL script.

        Args:
            chunks: List of code chunks
            relationships: List of chunk relationships
            output: Output path or stream
            metadata: Export metadata
        """
        sql_lines = []

        # Add header
        sql_lines.extend(
            [
                "-- TreeSitter Chunker PostgreSQL Export",
                f"-- Generated: {datetime.now(timezone.utc).isoformat()}",
                f"-- Chunks: {len(chunks)}, Relationships: {len(relationships)}",
                "",
                "BEGIN;",
                "",
            ],
        )

        # Create schema if needed
        if self._schema != "public":
            sql_lines.append(f"CREATE SCHEMA IF NOT EXISTS {self._schema};")
            sql_lines.append(f"SET search_path TO {self._schema};")
            sql_lines.append("")

        # Create tables
        sql_lines.extend(self._generate_create_tables())
        sql_lines.append("")

        # Insert metadata
        if metadata:
            sql_lines.extend(self._generate_insert_metadata(metadata))
            sql_lines.append("")

        # Insert chunks
        sql_lines.extend(self._generate_insert_chunks(chunks))
        sql_lines.append("")

        # Insert relationships
        sql_lines.extend(self._generate_insert_relationships(relationships))
        sql_lines.append("")

        # Create indexes
        sql_lines.extend(self._generate_create_indexes())
        sql_lines.append("")

        # Commit
        sql_lines.append("COMMIT;")

        # Write to output
        sql_content = "\n".join(sql_lines)
        if isinstance(output, str | Path):
            Path(output).write_text(sql_content, encoding="utf-8")
        else:
            output.write(sql_content)

    def export_streaming(
        self,
        chunk_iterator: Iterator[CodeChunk],
        relationship_iterator: Iterator[ChunkRelationship],
        output: Path | io.IOBase,
    ) -> None:
        """Export using iterators for large datasets."""
        # Open output for streaming
        if isinstance(output, str | Path):
            with open(output, "w", encoding="utf-8") as f:
                self._stream_sql(chunk_iterator, relationship_iterator, f)
        else:
            self._stream_sql(chunk_iterator, relationship_iterator, output)

    def set_table_names(self, chunks_table: str, relationships_table: str) -> None:
        """Set custom table names."""
        self._chunks_table = chunks_table
        self._relationships_table = relationships_table

    def create_indexes(self, columns: list[str]) -> None:
        """Create indexes on specified columns."""
        self._indexes = columns

    def set_batch_size(self, size: int) -> None:
        """Set batch size for inserts."""
        self._batch_size = size

    def set_schema(self, schema: str) -> None:
        """Set PostgreSQL schema name."""
        self._schema = schema

    def supports_format(self, format: ExportFormat) -> bool:
        """Check if this exporter supports a format."""
        return format == ExportFormat.POSTGRESQL

    def get_schema(self) -> dict[str, Any]:
        """Get the export schema."""
        return {
            "format": "postgresql",
            "version": "13+",
            "schema": self._schema,
            "tables": {
                "chunks": self._chunks_table,
                "relationships": self._relationships_table,
                "metadata": self._metadata_table,
            },
            "indexes": self._indexes,
            "batch_size": self._batch_size,
        }

    def _generate_create_tables(self) -> list[str]:
        """Generate CREATE TABLE statements."""
        return [
            f"CREATE TABLE IF NOT EXISTS {self._chunks_table} (",
            "    chunk_id VARCHAR(64) PRIMARY KEY,",
            "    language VARCHAR(32) NOT NULL,",
            "    file_path TEXT NOT NULL,",
            "    node_type VARCHAR(64) NOT NULL,",
            "    start_line INTEGER NOT NULL,",
            "    end_line INTEGER NOT NULL,",
            "    byte_start INTEGER NOT NULL,",
            "    byte_end INTEGER NOT NULL,",
            "    parent_context TEXT,",
            "    content TEXT NOT NULL,",
            "    parent_chunk_id VARCHAR(64),",
            "    chunk_references JSONB DEFAULT '[]'::jsonb,",
            "    chunk_dependencies JSONB DEFAULT '[]'::jsonb,",
            "    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            ");",
            "",
            f"CREATE TABLE IF NOT EXISTS {self._relationships_table} (",
            "    id SERIAL PRIMARY KEY,",
            "    source_chunk_id VARCHAR(64) NOT NULL,",
            "    target_chunk_id VARCHAR(64) NOT NULL,",
            "    relationship_type VARCHAR(32) NOT NULL,",
            "    metadata JSONB,",
            "    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,",
            f"    FOREIGN KEY (source_chunk_id) REFERENCES {self._chunks_table}(chunk_id),",
            f"    FOREIGN KEY (target_chunk_id) REFERENCES {self._chunks_table}(chunk_id)",
            ");",
            "",
            f"CREATE TABLE IF NOT EXISTS {self._metadata_table} (",
            "    id SERIAL PRIMARY KEY,",
            "    format VARCHAR(32) NOT NULL,",
            "    version VARCHAR(16) NOT NULL,",
            "    created_at TIMESTAMP NOT NULL,",
            "    source_files JSONB NOT NULL,",
            "    chunk_count INTEGER NOT NULL,",
            "    relationship_count INTEGER NOT NULL,",
            "    options JSONB,",
            "    export_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            ");",
        ]

    def _generate_insert_metadata(self, metadata: ExportMetadata) -> list[str]:
        """Generate INSERT statement for metadata."""
        return [
            f"INSERT INTO {self._metadata_table}",
            "(format, version, created_at, source_files, chunk_count, relationship_count, options)",
            "VALUES (",
            f"    '{metadata.format.value}',",
            f"    '{metadata.version}',",
            f"    '{metadata.created_at}',",
            f"    '{json.dumps(metadata.source_files)}'::jsonb,",
            f"    {metadata.chunk_count},",
            f"    {metadata.relationship_count},",
            f"    '{json.dumps(metadata.options)}'::jsonb",
            ");",
        ]

    def _generate_insert_chunks(self, chunks: list[CodeChunk]) -> list[str]:
        """Generate INSERT statements for chunks."""
        lines = []

        for i in range(0, len(chunks), self._batch_size):
            batch = chunks[i : i + self._batch_size]

            lines.append(f"INSERT INTO {self._chunks_table}")
            lines.append(
                "(chunk_id, language, file_path, node_type, start_line, end_line,",
            )
            lines.append(
                " byte_start, byte_end, parent_context, content, parent_chunk_id,",
            )
            lines.append(" chunk_references, chunk_dependencies)")
            lines.append("VALUES")

            values = []
            for chunk in batch:
                # Escape single quotes in content
                content = chunk.content.replace("'", "''")
                parent_context = (
                    chunk.parent_context.replace("'", "''")
                    if chunk.parent_context
                    else "NULL"
                )
                parent_chunk_id = (
                    f"'{chunk.parent_chunk_id}'" if chunk.parent_chunk_id else "NULL"
                )

                value = (
                    f"('{chunk.chunk_id}', '{chunk.language}', '{chunk.file_path}', "
                    f"'{chunk.node_type}', {chunk.start_line}, {chunk.end_line}, "
                    f"{chunk.byte_start}, {chunk.byte_end}, "
                    f"'{parent_context}', '{content}', {parent_chunk_id}, "
                    f"'{json.dumps(chunk.references)}'::jsonb, "
                    f"'{json.dumps(chunk.dependencies)}'::jsonb)"
                )
                values.append(value)

            lines.append(",\n".join(values))
            lines.append("ON CONFLICT (chunk_id) DO UPDATE SET")
            lines.append("    content = EXCLUDED.content,")
            lines.append("    chunk_references = EXCLUDED.chunk_references,")
            lines.append("    chunk_dependencies = EXCLUDED.chunk_dependencies;")
            lines.append("")

        return lines

    def _generate_insert_relationships(
        self,
        relationships: list[ChunkRelationship],
    ) -> list[str]:
        """Generate INSERT statements for relationships."""
        lines = []

        for i in range(0, len(relationships), self._batch_size):
            batch = relationships[i : i + self._batch_size]

            lines.append(f"INSERT INTO {self._relationships_table}")
            lines.append(
                "(source_chunk_id, target_chunk_id, relationship_type, metadata)",
            )
            lines.append("VALUES")

            values = []
            for rel in batch:
                metadata = (
                    f"'{json.dumps(rel.metadata)}'::jsonb" if rel.metadata else "NULL"
                )
                value = (
                    f"('{rel.source_chunk_id}', '{rel.target_chunk_id}', "
                    f"'{rel.relationship_type.value}', {metadata})"
                )
                values.append(value)

            lines.append(",\n".join(values) + ";")
            lines.append("")

        return lines

    def _generate_create_indexes(self) -> list[str]:
        """Generate CREATE INDEX statements."""
        lines = []

        # Create indexes on chunks table
        for column in self._indexes:
            if column in [
                "chunk_id",
                "file_path",
                "node_type",
                "language",
                "parent_chunk_id",
            ]:
                index_name = f"idx_{self._chunks_table}_{column}"
                lines.append(
                    f"CREATE INDEX IF NOT EXISTS {index_name} ON {self._chunks_table}({column});",
                )

        # Create indexes on relationships table
        lines.extend(
            [
                f"CREATE INDEX IF NOT EXISTS idx_{self._relationships_table}_source "
                f"ON {self._relationships_table}(source_chunk_id);",
                f"CREATE INDEX IF NOT EXISTS idx_{self._relationships_table}_target "
                f"ON {self._relationships_table}(target_chunk_id);",
                f"CREATE INDEX IF NOT EXISTS idx_{self._relationships_table}_type "
                f"ON {self._relationships_table}(relationship_type);",
            ],
        )

        # Add GIN indexes for JSONB columns
        lines.extend(
            [
                f"CREATE INDEX IF NOT EXISTS idx_{self._chunks_table}_references_gin "
                f"ON {self._chunks_table} USING GIN (chunk_references);",
                f"CREATE INDEX IF NOT EXISTS idx_{self._chunks_table}_dependencies_gin "
                f"ON {self._chunks_table} USING GIN (chunk_dependencies);",
                f"CREATE INDEX IF NOT EXISTS idx_{self._relationships_table}_metadata_gin "
                f"ON {self._relationships_table} USING GIN (metadata);",
            ],
        )

        return lines

    def _stream_sql(
        self,
        chunk_iterator: Iterator[CodeChunk],
        relationship_iterator: Iterator[ChunkRelationship],
        output: io.IOBase,
    ) -> None:
        """Stream SQL statements to output."""
        # Write header
        output.write("-- TreeSitter Chunker PostgreSQL Export\n")
        output.write(f"-- Generated: {datetime.now(timezone.utc).isoformat()}\n")
        output.write("\nBEGIN;\n\n")

        # Write schema setup
        if self._schema != "public":
            output.write(f"CREATE SCHEMA IF NOT EXISTS {self._schema};\n")
            output.write(f"SET search_path TO {self._schema};\n\n")

        # Write table creation
        for line in self._generate_create_tables():
            output.write(line + "\n")
        output.write("\n")

        # Stream chunks in batches
        output.write("-- Chunks\n")
        chunk_batch = []
        for chunk in chunk_iterator:
            chunk_batch.append(chunk)
            if len(chunk_batch) >= self._batch_size:
                for line in self._generate_insert_chunks(chunk_batch):
                    output.write(line + "\n")
                chunk_batch = []
                output.flush()

        # Write remaining chunks
        if chunk_batch:
            for line in self._generate_insert_chunks(chunk_batch):
                output.write(line + "\n")

        output.write("\n")

        # Stream relationships in batches
        output.write("-- Relationships\n")
        rel_batch = []
        for rel in relationship_iterator:
            rel_batch.append(rel)
            if len(rel_batch) >= self._batch_size:
                for line in self._generate_insert_relationships(rel_batch):
                    output.write(line + "\n")
                rel_batch = []
                output.flush()

        # Write remaining relationships
        if rel_batch:
            for line in self._generate_insert_relationships(rel_batch):
                output.write(line + "\n")

        output.write("\n")

        # Write indexes
        output.write("-- Indexes\n")
        for line in self._generate_create_indexes():
            output.write(line + "\n")

        output.write("\nCOMMIT;\n")

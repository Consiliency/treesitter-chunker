"""PostgreSQL export implementation for code chunks."""

import csv
import json
import re
from pathlib import Path
from typing import Any

from .database_exporter_base import DatabaseExporterBase


def _escape_postgres_string(value: str) -> str:
    """Safely escape a string for PostgreSQL.

    Uses proper escaping to prevent SQL injection by:
    1. Escaping single quotes by doubling them
    2. Escaping backslashes
    3. Handling special characters

    Args:
        value: The string to escape

    Returns:
        Safely escaped string for use in SQL
    """
    if value is None:
        return "NULL"
    # Escape backslashes first, then single quotes
    escaped = value.replace("\\", "\\\\").replace("'", "''")
    # Remove any null bytes which can cause issues
    escaped = escaped.replace("\x00", "")
    return escaped


def _escape_postgres_identifier(identifier: str) -> str:
    """Safely escape a PostgreSQL identifier (table/column name).

    Args:
        identifier: The identifier to escape

    Returns:
        Safely escaped identifier
    """
    # Remove any characters that aren't alphanumeric or underscore
    return re.sub(r"[^\w]", "", identifier)


class PostgresExporter(DatabaseExporterBase):
    """Export code chunks to PostgreSQL fmt."""

    @staticmethod
    def get_schema_ddl() -> str:
        """Get PostgreSQL schema DDL with advanced features."""
        return """
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For similarity search

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_info (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO schema_info (key, value) VALUES ('version', '1.0')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP;

-- Main chunks table with JSONB for metadata
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    start_byte INTEGER,
    end_byte INTEGER,
    content TEXT NOT NULL,
    chunk_type TEXT,
    language TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Add generated columns for common queries
    line_count INTEGER GENERATED ALWAYS AS (end_line - start_line + 1) STORED,
    content_hash TEXT GENERATED ALWAYS AS (md5(content)) STORED
);

-- Relationships with JSONB properties
CREATE TABLE IF NOT EXISTS relationships (
    id SERIAL PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    target_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Prevent duplicate relationships
    CONSTRAINT unique_relationship UNIQUE (source_id, target_id, relationship_type)
);

-- Partitioned table for large codebases (by language)
CREATE TABLE IF NOT EXISTS chunks_partitioned (
    LIKE chunks INCLUDING ALL
) PARTITION BY LIST (language);

-- Create partitions for common languages
CREATE TABLE IF NOT EXISTS chunks_python PARTITION OF chunks_partitioned FOR VALUES IN ('python');
CREATE TABLE IF NOT EXISTS chunks_javascript PARTITION OF chunks_partitioned FOR VALUES IN ('javascript', 'typescript');
CREATE TABLE IF NOT EXISTS chunks_java PARTITION OF chunks_partitioned FOR VALUES IN ('java');
CREATE TABLE IF NOT EXISTS chunks_cpp PARTITION OF chunks_partitioned FOR VALUES IN ('c', 'cpp', 'c++');

-- Full-text search configuration
CREATE TEXT SEARCH CONFIGURATION IF NOT EXISTS code_search (COPY = simple);

-- Add trigram index for similarity search on main table
CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm ON chunks USING GIN (content gin_trgm_ops);

-- Materialized view for fast aggregations
CREATE MATERIALIZED VIEW IF NOT EXISTS file_stats AS
SELECT
    file_path,
    language,
    COUNT(*) as chunk_count,
    SUM(line_count) as total_lines,
    COUNT(DISTINCT chunk_type) as chunk_type_count,
    AVG((metadata->>'cyclomatic_complexity')::NUMERIC) as avg_complexity,
    MAX((metadata->>'token_count')::INTEGER) as max_tokens
FROM chunks
GROUP BY file_path, language
WITH DATA;

CREATE UNIQUE INDEX ON file_stats (file_path);

-- Materialized view for relationship graph
CREATE MATERIALIZED VIEW IF NOT EXISTS chunk_graph AS
SELECT
    c.id,
    c.file_path,
    c.chunk_type,
    c.language,
    c.metadata->>'name' as chunk_name,
    COUNT(DISTINCT r_out.target_id) as outgoing_count,
    COUNT(DISTINCT r_in.source_id) as incoming_count,
    ARRAY_AGG(DISTINCT r_out.relationship_type) FILTER (WHERE r_out.relationship_type IS NOT NULL) as outgoing_types,
    ARRAY_AGG(DISTINCT r_in.relationship_type) FILTER (WHERE r_in.relationship_type IS NOT NULL) as incoming_types
FROM chunks c
LEFT JOIN relationships r_out ON c.id = r_out.source_id
LEFT JOIN relationships r_in ON c.id = r_in.target_id
GROUP BY c.id, c.file_path, c.chunk_type, c.language, c.metadata
WITH DATA;

CREATE UNIQUE INDEX ON chunk_graph (id);

-- Function to find dependencies recursively
CREATE OR REPLACE FUNCTION find_dependencies(chunk_id TEXT, max_depth INTEGER DEFAULT 5)
RETURNS TABLE (
    id TEXT,
    file_path TEXT,
    chunk_type TEXT,
    depth INTEGER,
    path TEXT[]
) AS $$
WITH RECURSIVE deps AS (
    -- Base case
    SELECT
        c.id,
        c.file_path,
        c.chunk_type,
        0 as depth,
        ARRAY[c.id] as path
    FROM chunks c
    WHERE c.id = chunk_id

    UNION

    -- Recursive case
    SELECT
        c.id,
        c.file_path,
        c.chunk_type,
        d.depth + 1,
        d.path || c.id
    FROM relationships r
    JOIN deps d ON r.source_id = d.id
    JOIN chunks c ON r.target_id = c.id
    WHERE d.depth < max_depth
    AND NOT c.id = ANY(d.path)  -- Prevent cycles
    AND r.relationship_type IN ('IMPORTS', 'CALLS', 'EXTENDS')
)
SELECT * FROM deps WHERE depth > 0
ORDER BY depth, file_path;
$$ LANGUAGE SQL;

-- Function to calculate code metrics
CREATE OR REPLACE FUNCTION calculate_file_metrics(target_file_path TEXT)
RETURNS TABLE (
    metric_name TEXT,
    metric_value NUMERIC
) AS $$
SELECT 'total_chunks', COUNT(*)::NUMERIC FROM chunks WHERE file_path = target_file_path
UNION ALL
SELECT 'total_lines', SUM(line_count)::NUMERIC FROM chunks WHERE file_path = target_file_path
UNION ALL
SELECT 'avg_chunk_size', AVG(line_count)::NUMERIC FROM chunks WHERE file_path = target_file_path
UNION ALL
SELECT 'complexity_sum', SUM((metadata->>'cyclomatic_complexity')::NUMERIC) FROM chunks WHERE file_path = target_file_path
UNION ALL
SELECT 'token_count', SUM((metadata->>'token_count')::NUMERIC) FROM chunks WHERE file_path = target_file_path;
$$ LANGUAGE SQL;
"""

    @staticmethod
    def get_index_statements() -> list[str]:
        """Get PostgreSQL-specific index statements."""
        return [
            "CREATE INDEX IF NOT EXISTS idx_chunks_file_path ON chunks(file_path);",
            "CREATE INDEX IF NOT EXISTS idx_chunks_chunk_type ON chunks(chunk_type);",
            "CREATE INDEX IF NOT EXISTS idx_chunks_language ON chunks(language);",
            "CREATE INDEX IF NOT EXISTS idx_chunks_position ON chunks(file_path, start_line, end_line);",
            "CREATE INDEX IF NOT EXISTS idx_chunks_metadata ON chunks USING GIN (metadata);",
            "CREATE INDEX IF NOT EXISTS idx_relationships_properties ON relationships USING GIN (properties);",
            "CREATE INDEX IF NOT EXISTS idx_chunks_content_fts ON chunks USING GIN (to_tsvector('code_search', content));",
            "CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm ON chunks USING GIN (content gin_trgm_ops);",
            "CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_id);",
            "CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_id);",
            "CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(relationship_type);",
            "CREATE INDEX IF NOT EXISTS idx_chunks_type_language ON chunks(chunk_type, language);",
            "CREATE INDEX IF NOT EXISTS idx_chunks_metadata_name ON chunks((metadata->>'name')) WHERE metadata->>'name' IS NOT NULL;",
            "CREATE INDEX IF NOT EXISTS idx_chunks_metadata_complexity ON chunks((metadata->>'cyclomatic_complexity')::INTEGER) WHERE metadata->>'cyclomatic_complexity' IS NOT NULL;",
        ]

    def get_copy_data(self) -> tuple[str, list[list[Any]]]:
        """Generate COPY fmt data for chunks.

        Returns:
            Tuple of (COPY command, data rows)
        """
        copy_cmd = "COPY chunks (id, file_path, start_line, end_line, start_byte, end_byte, content, chunk_type, language, metadata) FROM STDIN WITH (FORMAT csv, HEADER false, NULL '\\N');"
        rows = []
        for chunk in self.chunks:
            chunk_data = self._get_chunk_data(chunk)
            row = [
                chunk_data["id"],
                chunk_data["file_path"],
                chunk_data["start_line"],
                chunk_data["end_line"],
                (
                    chunk_data["start_byte"]
                    if chunk_data["start_byte"] is not None
                    else "\\N"
                ),
                chunk_data["end_byte"] if chunk_data["end_byte"] is not None else "\\N",
                chunk_data["content"],
                chunk_data["chunk_type"] if chunk_data["chunk_type"] else "\\N",
                chunk_data["language"] if chunk_data["language"] else "\\N",
                json.dumps(chunk_data["metadata"]) if chunk_data["metadata"] else "{}",
            ]
            rows.append(row)
        return copy_cmd, rows

    def get_insert_statements(self, batch_size: int = 100) -> list[str]:
        """Generate INSERT statements with ON CONFLICT handling.

        Uses proper string escaping to prevent SQL injection attacks.
        For production use with untrusted data, prefer get_parameterized_statements()
        which returns queries with placeholders for use with database drivers.
        """
        statements = []
        for i in range(0, len(self.chunks), batch_size):
            batch = self.chunks[i : i + batch_size]
            values_parts = []
            for chunk in batch:
                chunk_data = self._get_chunk_data(chunk)
                # Use safe escaping function instead of simple replace
                content_escaped = _escape_postgres_string(chunk_data["content"])
                id_escaped = _escape_postgres_string(chunk_data["id"])
                file_path_escaped = _escape_postgres_string(chunk_data["file_path"])
                metadata_json = (
                    json.dumps(chunk_data["metadata"])
                    if chunk_data["metadata"]
                    else "{}"
                )
                metadata_escaped = _escape_postgres_string(metadata_json)
                chunk_type_escaped = (
                    f"'{_escape_postgres_string(chunk_data['chunk_type'])}'"
                    if chunk_data["chunk_type"]
                    else "NULL"
                )
                language_escaped = (
                    f"'{_escape_postgres_string(chunk_data['language'])}'"
                    if chunk_data["language"]
                    else "NULL"
                )
                values_parts.append(
                    f"""(
                    '{id_escaped}',
                    '{file_path_escaped}',
                    {chunk_data['start_line']},
                    {chunk_data['end_line']},
                    {chunk_data['start_byte'] if chunk_data['start_byte'] is not None else 'NULL'},
                    {chunk_data['end_byte'] if chunk_data['end_byte'] is not None else 'NULL'},
                    '{content_escaped}',
                    {chunk_type_escaped},
                    {language_escaped},
                    '{metadata_escaped}'::jsonb
                )""",
                )
            statement = f"""
INSERT INTO chunks (id, file_path, start_line, end_line, start_byte, end_byte, content, chunk_type, language, metadata)
VALUES {','.join(values_parts)}
ON CONFLICT (id) DO UPDATE SET
    file_path = EXCLUDED.file_path,
    start_line = EXCLUDED.start_line,
    end_line = EXCLUDED.end_line,
    start_byte = EXCLUDED.start_byte,
    end_byte = EXCLUDED.end_byte,
    content = EXCLUDED.content,
    chunk_type = EXCLUDED.chunk_type,
    language = EXCLUDED.language,
    metadata = EXCLUDED.metadata;"""
            statements.append(statement)
        if self.relationships:
            for i in range(0, len(self.relationships), batch_size):
                batch = self.relationships[i : i + batch_size]
                values_parts = []
                for rel in batch:
                    props_json = (
                        json.dumps(rel["properties"]) if rel["properties"] else "{}"
                    )
                    # Use safe escaping for all string values
                    source_escaped = _escape_postgres_string(rel["source_id"])
                    target_escaped = _escape_postgres_string(rel["target_id"])
                    rel_type_escaped = _escape_postgres_string(rel["relationship_type"])
                    props_escaped = _escape_postgres_string(props_json)
                    values_parts.append(
                        f"""(
                        '{source_escaped}',
                        '{target_escaped}',
                        '{rel_type_escaped}',
                        '{props_escaped}'::jsonb
                    )""",
                    )
                statement = f"""
INSERT INTO relationships (source_id, target_id, relationship_type, properties)
VALUES {','.join(values_parts)}
ON CONFLICT (source_id, target_id, relationship_type) DO UPDATE SET
    properties = EXCLUDED.properties;"""
                statements.append(statement)
        statements.append("REFRESH MATERIALIZED VIEW CONCURRENTLY file_stats;")
        statements.append(
            "REFRESH MATERIALIZED VIEW CONCURRENTLY chunk_graph;",
        )
        return statements

    def get_parameterized_statements(
        self,
        batch_size: int = 100,
    ) -> list[tuple[str, list[tuple[Any, ...]]]]:
        """Generate parameterized INSERT statements for safe database operations.

        Returns queries with $1, $2, etc. placeholders and corresponding parameter
        tuples for use with database drivers like psycopg2/asyncpg.

        This is the recommended approach for production use with untrusted data
        as it completely prevents SQL injection attacks.

        Args:
            batch_size: Number of rows per INSERT statement

        Returns:
            List of (query_template, params_list) tuples where params_list
            contains tuples of values for each row.
        """
        results = []

        # Generate chunk inserts
        for i in range(0, len(self.chunks), batch_size):
            batch = self.chunks[i : i + batch_size]
            params_list = []

            for chunk in batch:
                chunk_data = self._get_chunk_data(chunk)
                metadata_json = (
                    json.dumps(chunk_data["metadata"])
                    if chunk_data["metadata"]
                    else "{}"
                )
                params_list.append((
                    chunk_data["id"],
                    chunk_data["file_path"],
                    chunk_data["start_line"],
                    chunk_data["end_line"],
                    chunk_data["start_byte"],
                    chunk_data["end_byte"],
                    chunk_data["content"],
                    chunk_data["chunk_type"],
                    chunk_data["language"],
                    metadata_json,
                ))

            # Build parameterized query with numbered placeholders
            placeholders = []
            for idx in range(len(batch)):
                base = idx * 10
                placeholders.append(
                    f"(${base + 1}, ${base + 2}, ${base + 3}, ${base + 4}, "
                    f"${base + 5}, ${base + 6}, ${base + 7}, ${base + 8}, "
                    f"${base + 9}, ${base + 10}::jsonb)",
                )

            query = f"""
INSERT INTO chunks (id, file_path, start_line, end_line, start_byte, end_byte, content, chunk_type, language, metadata)
VALUES {', '.join(placeholders)}
ON CONFLICT (id) DO UPDATE SET
    file_path = EXCLUDED.file_path,
    start_line = EXCLUDED.start_line,
    end_line = EXCLUDED.end_line,
    start_byte = EXCLUDED.start_byte,
    end_byte = EXCLUDED.end_byte,
    content = EXCLUDED.content,
    chunk_type = EXCLUDED.chunk_type,
    language = EXCLUDED.language,
    metadata = EXCLUDED.metadata;"""

            results.append((query, params_list))

        # Generate relationship inserts
        if self.relationships:
            for i in range(0, len(self.relationships), batch_size):
                batch = self.relationships[i : i + batch_size]
                params_list = []

                for rel in batch:
                    props_json = (
                        json.dumps(rel["properties"]) if rel["properties"] else "{}"
                    )
                    params_list.append((
                        rel["source_id"],
                        rel["target_id"],
                        rel["relationship_type"],
                        props_json,
                    ))

                placeholders = []
                for idx in range(len(batch)):
                    base = idx * 4
                    placeholders.append(
                        f"(${base + 1}, ${base + 2}, ${base + 3}, ${base + 4}::jsonb)",
                    )

                query = f"""
INSERT INTO relationships (source_id, target_id, relationship_type, properties)
VALUES {', '.join(placeholders)}
ON CONFLICT (source_id, target_id, relationship_type) DO UPDATE SET
    properties = EXCLUDED.properties;"""

                results.append((query, params_list))

        return results

    def export(self, output_path: Path, format: str = "sql", **options) -> None:
        """Export to PostgreSQL fmt.

        Args:
            output_path: Base path for output files
            format: Export format - "sql" or "copy"
            **options: Additional options
        """
        fmt = format
        if fmt == "sql":
            statements = []
            statements.append("-- PostgreSQL export for tree-sitter-chunker")
            statements.append("-- Generated code chunk data")
            statements.append("")
            statements.append("-- Create schema")
            statements.append(self.get_schema_ddl())
            statements.append("")
            statements.append("-- Insert data")
            statements.extend(self.get_insert_statements())
            statements.append("")
            statements.append("-- Create indices")
            statements.extend(self.get_index_statements())
            output_path.write_text("\n".join(statements), encoding="utf-8")
        elif fmt == "copy":
            # Tests expect files in the same directory as tmp_path with fixed names
            base = output_path.parent
            schema_path = base / f"{output_path.name}_schema.sql"
            schema_content = [
                "-- PostgreSQL export (COPY format)",
                self.get_schema_ddl(),
            ]
            schema_path.write_text("\n".join(schema_content), encoding="utf-8")
            copy_cmd, rows = self.get_copy_data()
            chunks_path = base / f"{output_path.name}_chunks.csv"
            with chunks_path.open("w", encoding="utf-8", newline="") as f:
                import csv

                writer = csv.writer(f)
                writer.writerows(rows)
            import_sql = base / f"{output_path.name}_import.sql"
            import_sql.write_text(copy_cmd, encoding="utf-8")
        else:
            raise ValueError(f"Unknown format: {fmt}")

    @staticmethod
    def get_advanced_queries() -> dict[str, str]:
        """Get PostgreSQL-specific advanced queries."""
        queries = super().get_analysis_queries()
        queries.update(
            {
                "similarity_search": """
                -- Find chunks similar to a given chunk
                SELECT
                    c2.id,
                    c2.file_path,
                    c2.chunk_type,
                    similarity(c1.content, c2.content) as similarity_score
                FROM chunks c1
                CROSS JOIN chunks c2
                WHERE c1.id = %s
                AND c1.id != c2.id
                AND c1.chunk_type = c2.chunk_type
                AND similarity(c1.content, c2.content) > 0.3
                ORDER BY similarity_score DESC
                LIMIT 10;
            """,
                "full_text_search": """
                -- Full-text search with ranking
                SELECT
                    id,
                    file_path,
                    chunk_type,
                    ts_headline('code_search', content, query) as highlighted,
                    ts_rank(to_tsvector('code_search', content), query) as rank
                FROM chunks,
                     plainto_tsquery('code_search', %s) query
                WHERE to_tsvector('code_search', content) @@ query
                ORDER BY rank DESC
                LIMIT 20;
            """,
                "jsonb_metadata_query": """
                -- Query chunks by metadata fields
                SELECT
                    id,
                    file_path,
                    chunk_type,
                    metadata->>'name' as name,
                    metadata->>'cyclomatic_complexity' as complexity
                FROM chunks
                WHERE metadata @> %s::jsonb  -- e.g., '{"has_docstring": true}'
                AND (metadata->>'cyclomatic_complexity')::INTEGER > 10
                ORDER BY (metadata->>'cyclomatic_complexity')::INTEGER DESC;
            """,
                "dependency_graph": """
                -- Get full dependency graph for visualization
                WITH RECURSIVE dep_tree AS (
                    -- Start nodes (no incoming dependencies)
                    SELECT
                        c.id,
                        c.file_path,
                        c.chunk_type,
                        c.metadata->>'name' as name,
                        0 as level,
                        ARRAY[c.id] as path
                    FROM chunks c
                    WHERE NOT EXISTS (
                        SELECT 1 FROM relationships r
                        WHERE r.target_id = c.id
                        AND r.relationship_type IN ('IMPORTS', 'EXTENDS')
                    )

                    UNION ALL

                    -- Recursive part
                    SELECT
                        c.id,
                        c.file_path,
                        c.chunk_type,
                        c.metadata->>'name' as name,
                        dt.level + 1,
                        dt.path || c.id
                    FROM relationships r
                    JOIN dep_tree dt ON r.source_id = dt.id
                    JOIN chunks c ON r.target_id = c.id
                    WHERE NOT c.id = ANY(dt.path)  -- Prevent cycles
                    AND r.relationship_type IN ('IMPORTS', 'EXTENDS')
                )
                SELECT * FROM dep_tree
                ORDER BY level, file_path;
            """,
                "hot_spots": """
                -- Find code hot spots (high complexity + many dependencies)
                SELECT
                    cg.id,
                    cg.file_path,
                    cg.chunk_type,
                    cg.chunk_name,
                    (c.metadata->>'cyclomatic_complexity')::INTEGER as complexity,
                    (c.metadata->>'token_count')::INTEGER as tokens,
                    cg.incoming_count + cg.outgoing_count as total_connections,
                    (c.metadata->>'cyclomatic_complexity')::INTEGER * (cg.incoming_count + cg.outgoing_count + 1) as hotness_score
                FROM chunk_graph cg
                JOIN chunks c ON cg.id = c.id
                WHERE c.metadata->>'cyclomatic_complexity' IS NOT NULL
                ORDER BY hotness_score DESC
                LIMIT 20;
            """,
            },
        )
        return queries

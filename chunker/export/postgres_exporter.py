"""PostgreSQL export implementation for code chunks."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from .database_exporter_base import DatabaseExporterBase
from ..types import CodeChunk


class PostgresExporter(DatabaseExporterBase):
    """Export code chunks to PostgreSQL format."""
    
    def get_schema_ddl(self) -> str:
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
    
    def get_index_statements(self) -> List[str]:
        """Get PostgreSQL-specific index statements."""
        return [
            # B-tree indices for exact matches
            "CREATE INDEX IF NOT EXISTS idx_chunks_file_path ON chunks(file_path);",
            "CREATE INDEX IF NOT EXISTS idx_chunks_chunk_type ON chunks(chunk_type);",
            "CREATE INDEX IF NOT EXISTS idx_chunks_language ON chunks(language);",
            "CREATE INDEX IF NOT EXISTS idx_chunks_position ON chunks(file_path, start_line, end_line);",
            
            # GIN indices for JSONB
            "CREATE INDEX IF NOT EXISTS idx_chunks_metadata ON chunks USING GIN (metadata);",
            "CREATE INDEX IF NOT EXISTS idx_relationships_properties ON relationships USING GIN (properties);",
            
            # Full-text search index
            "CREATE INDEX IF NOT EXISTS idx_chunks_content_fts ON chunks USING GIN (to_tsvector('code_search', content));",
            
            # Trigram index for similarity search
            "CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm ON chunks USING GIN (content gin_trgm_ops);",
            
            # Relationship indices
            "CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_id);",
            "CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_id);",
            "CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(relationship_type);",
            
            # Composite indices for common queries
            "CREATE INDEX IF NOT EXISTS idx_chunks_type_language ON chunks(chunk_type, language);",
            "CREATE INDEX IF NOT EXISTS idx_chunks_metadata_name ON chunks((metadata->>'name')) WHERE metadata->>'name' IS NOT NULL;",
            "CREATE INDEX IF NOT EXISTS idx_chunks_metadata_complexity ON chunks((metadata->>'cyclomatic_complexity')::INTEGER) WHERE metadata->>'cyclomatic_complexity' IS NOT NULL;"
        ]
    
    def get_copy_data(self) -> Tuple[str, List[List[Any]]]:
        """Generate COPY format data for chunks.
        
        Returns:
            Tuple of (COPY command, data rows)
        """
        copy_cmd = """COPY chunks (id, file_path, start_line, end_line, start_byte, end_byte, content, chunk_type, language, metadata) FROM STDIN WITH (FORMAT csv, HEADER false, NULL '\\N');"""
        
        rows = []
        for chunk in self.chunks:
            chunk_data = self._get_chunk_data(chunk)
            row = [
                chunk_data["id"],
                chunk_data["file_path"],
                chunk_data["start_line"],
                chunk_data["end_line"],
                chunk_data["start_byte"] if chunk_data["start_byte"] is not None else "\\N",
                chunk_data["end_byte"] if chunk_data["end_byte"] is not None else "\\N",
                chunk_data["content"],
                chunk_data["chunk_type"] if chunk_data["chunk_type"] else "\\N",
                chunk_data["language"] if chunk_data["language"] else "\\N",
                json.dumps(chunk_data["metadata"]) if chunk_data["metadata"] else "{}"
            ]
            rows.append(row)
        
        return copy_cmd, rows
    
    def get_insert_statements(self, batch_size: int = 100) -> List[str]:
        """Generate INSERT statements with ON CONFLICT handling."""
        statements = []
        
        # Insert chunks in batches
        for i in range(0, len(self.chunks), batch_size):
            batch = self.chunks[i:i + batch_size]
            
            values_parts = []
            for chunk in batch:
                chunk_data = self._get_chunk_data(chunk)
                
                # Escape single quotes in content
                content_escaped = chunk_data["content"].replace("'", "''")
                metadata_json = json.dumps(chunk_data["metadata"]) if chunk_data["metadata"] else "{}"
                metadata_escaped = metadata_json.replace("'", "''")
                
                values_parts.append(f"""(
                    '{chunk_data["id"]}',
                    '{chunk_data["file_path"]}',
                    {chunk_data["start_line"]},
                    {chunk_data["end_line"]},
                    {chunk_data["start_byte"] if chunk_data["start_byte"] is not None else "NULL"},
                    {chunk_data["end_byte"] if chunk_data["end_byte"] is not None else "NULL"},
                    '{content_escaped}',
                    {f"'{chunk_data['chunk_type']}'" if chunk_data["chunk_type"] else "NULL"},
                    {f"'{chunk_data['language']}'" if chunk_data["language"] else "NULL"},
                    '{metadata_escaped}'::jsonb
                )""")
            
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
        
        # Insert relationships
        if self.relationships:
            for i in range(0, len(self.relationships), batch_size):
                batch = self.relationships[i:i + batch_size]
                
                values_parts = []
                for rel in batch:
                    props_json = json.dumps(rel["properties"]) if rel["properties"] else "{}"
                    props_escaped = props_json.replace("'", "''")
                    
                    values_parts.append(f"""(
                        '{rel["source_id"]}',
                        '{rel["target_id"]}',
                        '{rel["relationship_type"]}',
                        '{props_escaped}'::jsonb
                    )""")
                
                statement = f"""
INSERT INTO relationships (source_id, target_id, relationship_type, properties)
VALUES {','.join(values_parts)}
ON CONFLICT (source_id, target_id, relationship_type) DO UPDATE SET
    properties = EXCLUDED.properties;"""
                
                statements.append(statement)
        
        # Refresh materialized views
        statements.append("REFRESH MATERIALIZED VIEW CONCURRENTLY file_stats;")
        statements.append("REFRESH MATERIALIZED VIEW CONCURRENTLY chunk_graph;")
        
        return statements
    
    def export(self, output_path: Path, format: str = "sql", **options) -> None:
        """Export to PostgreSQL format.
        
        Args:
            output_path: Base path for output files
            format: Export format - "sql" or "copy"
            **options: Additional options
        """
        if format == "sql":
            # Export as SQL file
            statements = []
            
            # Add header
            statements.append("-- PostgreSQL export for tree-sitter-chunker")
            statements.append("-- Generated code chunk data")
            statements.append("")
            
            # Schema
            statements.append("-- Create schema")
            statements.append(self.get_schema_ddl())
            statements.append("")
            
            # Data
            statements.append("-- Insert data")
            statements.extend(self.get_insert_statements(**options))
            statements.append("")
            
            # Indices
            statements.append("-- Create indices")
            statements.extend(self.get_index_statements())
            
            output_path.write_text("\n".join(statements), encoding='utf-8')
            
        elif format == "copy":
            # Export as COPY format files
            # Schema file
            schema_path = output_path.parent / f"{output_path.stem}_schema.sql"
            schema_content = [
                "-- PostgreSQL schema for tree-sitter-chunker",
                self.get_schema_ddl(),
                "",
                "-- Indices",
                *self.get_index_statements()
            ]
            schema_path.write_text("\n".join(schema_content), encoding='utf-8')
            
            # Chunks COPY file
            chunks_path = output_path.parent / f"{output_path.stem}_chunks.csv"
            copy_cmd, rows = self.get_copy_data()
            
            # Write COPY command
            cmd_path = output_path.parent / f"{output_path.stem}_import.sql"
            import_cmds = [
                "-- Import commands for PostgreSQL",
                f"-- Run: psql -d your_database -f {cmd_path.name}",
                "",
                "-- Import chunks",
                copy_cmd,
            ]
            
            # Write CSV data
            import csv
            with open(chunks_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            
            import_cmds.append(f"\\copy chunks FROM '{chunks_path.name}' CSV NULL '\\N';")
            
            # Relationships COPY file
            if self.relationships:
                rels_path = output_path.parent / f"{output_path.stem}_relationships.csv"
                rel_rows = []
                for rel in self.relationships:
                    rel_rows.append([
                        rel["source_id"],
                        rel["target_id"],
                        rel["relationship_type"],
                        json.dumps(rel["properties"]) if rel["properties"] else "{}"
                    ])
                
                with open(rels_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerows(rel_rows)
                
                import_cmds.append("")
                import_cmds.append("-- Import relationships")
                import_cmds.append(f"\\copy relationships (source_id, target_id, relationship_type, properties) FROM '{rels_path.name}' CSV;")
            
            import_cmds.extend([
                "",
                "-- Refresh materialized views",
                "REFRESH MATERIALIZED VIEW file_stats;",
                "REFRESH MATERIALIZED VIEW chunk_graph;"
            ])
            
            cmd_path.write_text("\n".join(import_cmds), encoding='utf-8')
        
        else:
            raise ValueError(f"Unknown format: {format}")
    
    def get_advanced_queries(self) -> Dict[str, str]:
        """Get PostgreSQL-specific advanced queries."""
        queries = super().get_analysis_queries()
        
        # Add PostgreSQL-specific queries
        queries.update({
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
            """
        })
        
        return queries
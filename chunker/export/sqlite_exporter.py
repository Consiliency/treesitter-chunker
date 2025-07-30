"""SQLite export implementation for code chunks."""

import json
import sqlite3
from pathlib import Path

from .database_exporter_base import DatabaseExporterBase


class SQLiteExporter(DatabaseExporterBase):
    """Export code chunks to SQLite database."""

    def get_schema_ddl(self) -> str:
        """Get SQLite schema DDL."""
        return """
-- Enable foreign key support
PRAGMA foreign_keys = ON;

-- Enable WAL mode for better concurrency
PRAGMA journal_mode = WAL;

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_info (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR REPLACE INTO schema_info (key, value) VALUES ('version', '1.0');
INSERT OR REPLACE INTO schema_info (key, value) VALUES ('created_at', datetime('now'));

-- Files table (normalized)
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    language TEXT,
    size INTEGER,
    hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Main chunks table
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    file_id INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    start_byte INTEGER,
    end_byte INTEGER,
    content TEXT NOT NULL,
    chunk_type TEXT,
    parent_context TEXT,
    metadata TEXT,  -- JSON string
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

-- Relationships between chunks
CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    properties TEXT,  -- JSON string
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES chunks(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES chunks(id) ON DELETE CASCADE,
    UNIQUE(source_id, target_id, relationship_type)
);

-- Metadata normalized tables (optional, for specific metadata fields)
CREATE TABLE IF NOT EXISTS chunk_complexity (
    chunk_id TEXT PRIMARY KEY,
    cyclomatic_complexity INTEGER,
    cognitive_complexity INTEGER,
    lines_of_code INTEGER,
    token_count INTEGER,
    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chunk_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id TEXT NOT NULL,
    import_name TEXT NOT NULL,
    import_type TEXT,  -- 'module', 'function', 'class', etc.
    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE,
    UNIQUE(chunk_id, import_name)
);

-- Full-text search support
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    id UNINDEXED,
    content,
    chunk_type,
    file_path,
    tokenize='porter unicode61'
);

-- Trigger to keep FTS index updated
CREATE TRIGGER IF NOT EXISTS chunks_fts_insert AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts (id, content, chunk_type, file_path)
  SELECT NEW.id, NEW.content, NEW.chunk_type, f.path
  FROM files f WHERE f.id = NEW.file_id;
END;

CREATE TRIGGER IF NOT EXISTS chunks_fts_delete AFTER DELETE ON chunks BEGIN
  DELETE FROM chunks_fts WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS chunks_fts_update AFTER UPDATE ON chunks BEGIN
  DELETE FROM chunks_fts WHERE id = OLD.id;
  INSERT INTO chunks_fts (id, content, chunk_type, file_path)
  SELECT NEW.id, NEW.content, NEW.chunk_type, f.path
  FROM files f WHERE f.id = NEW.file_id;
END;

-- Views for common queries
CREATE VIEW IF NOT EXISTS chunk_summary AS
SELECT
    c.id,
    f.path as file_path,
    c.chunk_type,
    f.language,
    c.start_line,
    c.end_line,
    (c.end_line - c.start_line + 1) as lines,
    cc.token_count,
    cc.cyclomatic_complexity,
    (SELECT COUNT(*) FROM relationships WHERE source_id = c.id) as outgoing_relationships,
    (SELECT COUNT(*) FROM relationships WHERE target_id = c.id) as incoming_relationships
FROM chunks c
JOIN files f ON c.file_id = f.id
LEFT JOIN chunk_complexity cc ON c.id = cc.chunk_id;

CREATE VIEW IF NOT EXISTS file_summary AS
SELECT
    f.path as file_path,
    f.language,
    COUNT(c.id) as chunk_count,
    COALESCE(SUM(c.end_line - c.start_line + 1), 0) as total_lines,
    COUNT(DISTINCT c.chunk_type) as chunk_types,
    f.size,
    f.hash
FROM files f
LEFT JOIN chunks c ON f.id = c.file_id
GROUP BY f.id, f.path, f.language, f.size, f.hash;

-- View for chunk hierarchy
CREATE VIEW IF NOT EXISTS chunk_hierarchy AS
WITH RECURSIVE hierarchy AS (
    -- Base case: chunks without parent
    SELECT c.id, c.chunk_type, f.path as file_path, c.start_line, c.end_line,
           0 as depth, c.id as root_id
    FROM chunks c
    JOIN files f ON c.file_id = f.id
    WHERE NOT EXISTS (
        SELECT 1 FROM relationships r
        WHERE r.target_id = c.id AND r.relationship_type = 'CONTAINS'
    )

    UNION ALL

    -- Recursive case: children chunks
    SELECT c.id, c.chunk_type, f.path as file_path, c.start_line, c.end_line,
           h.depth + 1, h.root_id
    FROM chunks c
    JOIN files f ON c.file_id = f.id
    JOIN relationships r ON r.target_id = c.id
    JOIN hierarchy h ON r.source_id = h.id
    WHERE r.relationship_type = 'CONTAINS'
)
SELECT * FROM hierarchy ORDER BY root_id, depth, start_line;
"""

    def get_insert_statements(self, _batch_size: int = 100) -> list[str]:
        """Generate INSERT statements for SQLite.

        Note: For SQLite export, we'll use the connection directly instead of
        generating SQL strings.
        """
        # This method is not used for SQLite - we insert directly
        return []

    def export(
        self,
        output_path: Path,
        create_indices: bool = True,
        _enable_fts: bool = True,
        **options,
    ) -> None:
        """Export chunks to SQLite database.

        Args:
            output_path: Path for the SQLite database file
            create_indices: Whether to create indices
            enable_fts: Whether to populate full-text search
            **options: Additional options
        """
        # Remove existing database if it exists
        if output_path.exists():
            output_path.unlink()

        # Create connection
        conn = sqlite3.connect(str(output_path))
        conn.row_factory = sqlite3.Row

        try:
            # Create schema
            conn.executescript(self.get_schema_ddl())

            # First, collect unique files and insert them
            files_data = {}
            file_id_map = {}

            for chunk in self.chunks:
                file_path = str(chunk.file_path)
                if file_path not in files_data:
                    files_data[file_path] = {
                        "path": file_path,
                        "language": chunk.language,
                        "size": None,  # Could be calculated if needed
                        "hash": None,  # Could be calculated if needed
                    }

            # Insert files and get their IDs
            for file_path, file_info in files_data.items():
                cursor = conn.execute(
                    "INSERT INTO files (path, language, size, hash) VALUES (?, ?, ?, ?)",
                    (
                        file_info["path"],
                        file_info["language"],
                        file_info["size"],
                        file_info["hash"],
                    ),
                )
                file_id_map[file_path] = cursor.lastrowid

            # Prepare chunk data
            chunks_data = []
            complexity_data = []
            imports_data = []

            for chunk in self.chunks:
                chunk_data = self._get_chunk_data(chunk)
                chunk_id = chunk_data["id"]
                file_id = file_id_map[chunk_data["file_path"]]

                # Main chunk data
                chunks_data.append(
                    (
                        chunk_id,
                        file_id,
                        chunk_data["start_line"],
                        chunk_data["end_line"],
                        chunk_data["start_byte"],
                        chunk_data["end_byte"],
                        chunk_data["content"],
                        chunk_data["chunk_type"],
                        chunk.parent_context,  # Use the actual parent_context from chunk
                        (
                            json.dumps(chunk_data["metadata"])
                            if chunk_data["metadata"]
                            else None
                        ),
                    ),
                )

                # Extract complexity metrics if available
                metadata = chunk_data["metadata"]
                if metadata:
                    if any(
                        key in metadata
                        for key in [
                            "cyclomatic_complexity",
                            "cognitive_complexity",
                            "lines_of_code",
                            "token_count",
                        ]
                    ):
                        complexity_data.append(
                            (
                                chunk_id,
                                metadata.get("cyclomatic_complexity"),
                                metadata.get("cognitive_complexity"),
                                metadata.get("lines_of_code"),
                                metadata.get("token_count"),
                            ),
                        )

                    # Extract imports
                    if "imports" in metadata:
                        for import_name in metadata["imports"]:
                            imports_data.append((chunk_id, import_name, None))

            # Bulk insert chunks
            conn.executemany(
                "INSERT INTO chunks (id, file_id, start_line, end_line, start_byte, end_byte, content, chunk_type, parent_context, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                chunks_data,
            )

            # Insert complexity data
            if complexity_data:
                conn.executemany(
                    "INSERT INTO chunk_complexity (chunk_id, cyclomatic_complexity, cognitive_complexity, lines_of_code, token_count) "
                    "VALUES (?, ?, ?, ?, ?)",
                    complexity_data,
                )

            # Insert imports
            if imports_data:
                conn.executemany(
                    "INSERT OR IGNORE INTO chunk_imports (chunk_id, import_name, import_type) VALUES (?, ?, ?)",
                    imports_data,
                )

            # Insert relationships
            if self.relationships:
                rel_data = [
                    (
                        rel["source_id"],
                        rel["target_id"],
                        rel["relationship_type"],
                        (json.dumps(rel["properties"]) if rel["properties"] else None),
                    )
                    for rel in self.relationships
                ]

                conn.executemany(
                    "INSERT OR IGNORE INTO relationships (source_id, target_id, relationship_type, properties) "
                    "VALUES (?, ?, ?, ?)",
                    rel_data,
                )

            # Note: FTS is populated automatically via triggers

            # Create indices
            if create_indices:
                for index_stmt in self.get_index_statements():
                    try:
                        conn.execute(index_stmt)
                    except sqlite3.OperationalError:
                        # Index might already exist
                        pass

            # Add statistics
            conn.execute(
                """
                INSERT INTO schema_info (key, value)
                SELECT 'total_chunks', COUNT(*) FROM chunks
            """,
            )

            conn.execute(
                """
                INSERT INTO schema_info (key, value)
                SELECT 'total_relationships', COUNT(*) FROM relationships
            """,
            )

            conn.execute(
                """
                INSERT INTO schema_info (key, value)
                SELECT 'total_files', COUNT(*) FROM files
            """,
            )

            conn.commit()

        finally:
            conn.close()

    def get_example_queries(self) -> dict[str, str]:
        """Get example queries for SQLite."""
        queries = super().get_analysis_queries()

        # Add SQLite-specific queries
        queries.update(
            {
                "search_content": """
                -- Full-text search for content
                SELECT c.id, c.file_path, c.chunk_type, c.start_line, c.end_line,
                       snippet(chunks_fts, 1, '<b>', '</b>', '...', 32) as match_snippet
                FROM chunks_fts fts
                JOIN chunks c ON fts.id = c.id
                WHERE chunks_fts MATCH ?
                ORDER BY rank;
            """,
                "complex_functions": """
                -- Find the most complex functions
                SELECT c.file_path, c.chunk_type, c.start_line, c.end_line,
                       cc.cyclomatic_complexity, cc.cognitive_complexity, cc.token_count
                FROM chunks c
                JOIN chunk_complexity cc ON c.id = cc.chunk_id
                WHERE c.chunk_type IN ('function', 'method')
                ORDER BY cc.cyclomatic_complexity DESC
                LIMIT 20;
            """,
                "file_dependencies": """
                -- Find all files that a given file depends on
                SELECT DISTINCT target_file.file_path as dependency
                FROM chunks source
                JOIN relationships r ON source.id = r.source_id
                JOIN chunks target ON r.target_id = target.id
                JOIN (SELECT DISTINCT file_path FROM chunks) target_file ON target.file_path = target_file.file_path
                WHERE source.file_path = ?
                AND r.relationship_type IN ('IMPORTS', 'INCLUDES')
                ORDER BY dependency;
            """,
                "duplicate_detection": """
                -- Find potentially duplicate chunks (same content)
                SELECT c1.file_path as file1, c1.start_line as line1,
                       c2.file_path as file2, c2.start_line as line2,
                       c1.chunk_type, LENGTH(c1.content) as size
                FROM chunks c1
                JOIN chunks c2 ON c1.content = c2.content AND c1.id < c2.id
                WHERE c1.chunk_type = c2.chunk_type
                ORDER BY size DESC;
            """,
            },
        )

        return queries

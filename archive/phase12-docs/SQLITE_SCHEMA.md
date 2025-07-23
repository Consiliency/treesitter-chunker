# SQLite Export Schema Documentation

## Overview

The SQLite exporter creates a normalized relational database for storing code chunks with full-text search capabilities, metadata storage, and analytical views.

## Database Configuration

- **Foreign Keys**: Enabled for referential integrity
- **WAL Mode**: Enabled for better concurrency
- **FTS5**: Used for full-text search with Porter stemming

## Tables

### `schema_info`
Tracks database schema version and metadata.
- `key` (TEXT PRIMARY KEY): Metadata key
- `value` (TEXT NOT NULL): Metadata value

### `files`
Normalized file information.
- `id` (INTEGER PRIMARY KEY): Auto-incrementing file ID
- `path` (TEXT UNIQUE NOT NULL): File path
- `language` (TEXT): Programming language
- `size` (INTEGER): File size in bytes
- `hash` (TEXT): File content hash
- `created_at` (TIMESTAMP): Record creation time
- `updated_at` (TIMESTAMP): Record update time

### `chunks`
Main table storing code chunks.
- `id` (TEXT PRIMARY KEY): Unique chunk identifier (MD5 hash)
- `file_id` (INTEGER NOT NULL): Foreign key to files table
- `start_line` (INTEGER NOT NULL): Starting line number
- `end_line` (INTEGER NOT NULL): Ending line number
- `start_byte` (INTEGER): Starting byte offset
- `end_byte` (INTEGER): Ending byte offset
- `content` (TEXT NOT NULL): Chunk source code
- `chunk_type` (TEXT): Type (function, class, method, etc.)
- `parent_context` (TEXT): Parent context (module, class, etc.)
- `metadata` (TEXT): JSON metadata
- `created_at` (TIMESTAMP): Record creation time

### `relationships`
Stores relationships between chunks.
- `id` (INTEGER PRIMARY KEY): Auto-incrementing ID
- `source_id` (TEXT NOT NULL): Source chunk ID
- `target_id` (TEXT NOT NULL): Target chunk ID
- `relationship_type` (TEXT NOT NULL): Type (CALLS, IMPORTS, CONTAINS, etc.)
- `properties` (TEXT): JSON properties
- `created_at` (TIMESTAMP): Record creation time
- **Constraint**: Unique on (source_id, target_id, relationship_type)

### `chunk_complexity`
Normalized complexity metrics.
- `chunk_id` (TEXT PRIMARY KEY): Foreign key to chunks
- `cyclomatic_complexity` (INTEGER): Cyclomatic complexity
- `cognitive_complexity` (INTEGER): Cognitive complexity
- `lines_of_code` (INTEGER): Lines of code
- `token_count` (INTEGER): Token count

### `chunk_imports`
Normalized import information.
- `id` (INTEGER PRIMARY KEY): Auto-incrementing ID
- `chunk_id` (TEXT NOT NULL): Foreign key to chunks
- `import_name` (TEXT NOT NULL): Import name
- `import_type` (TEXT): Import type (module, function, class)
- **Constraint**: Unique on (chunk_id, import_name)

### `chunks_fts`
Virtual FTS5 table for full-text search.
- `id` (UNINDEXED): Chunk ID
- `content`: Searchable content
- `chunk_type`: Searchable chunk type
- `file_path`: Searchable file path

## Views

### `chunk_summary`
Denormalized view for chunk analysis.
```sql
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
LEFT JOIN chunk_complexity cc ON c.id = cc.chunk_id
```

### `file_summary`
Aggregated file statistics.
```sql
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
GROUP BY f.id, f.path, f.language, f.size, f.hash
```

### `chunk_hierarchy`
Recursive view showing chunk containment hierarchy.
```sql
WITH RECURSIVE hierarchy AS (
    -- Base case: top-level chunks
    SELECT c.id, c.chunk_type, f.path as file_path, c.start_line, c.end_line,
           0 as depth, c.id as root_id
    FROM chunks c
    JOIN files f ON c.file_id = f.id
    WHERE NOT EXISTS (
        SELECT 1 FROM relationships r 
        WHERE r.target_id = c.id AND r.relationship_type = 'CONTAINS'
    )
    
    UNION ALL
    
    -- Recursive case: contained chunks
    SELECT c.id, c.chunk_type, f.path as file_path, c.start_line, c.end_line,
           h.depth + 1, h.root_id
    FROM chunks c
    JOIN files f ON c.file_id = f.id
    JOIN relationships r ON r.target_id = c.id
    JOIN hierarchy h ON r.source_id = h.id
    WHERE r.relationship_type = 'CONTAINS'
)
SELECT * FROM hierarchy ORDER BY root_id, depth, start_line
```

## Indices

- `idx_file_path`: On files(path)
- `idx_files_language`: On files(language)
- `idx_chunks_file_id`: On chunks(file_id)
- `idx_chunks_chunk_type`: On chunks(chunk_type)
- `idx_chunks_position`: On chunks(file_id, start_line, end_line)
- `idx_relationships_source`: On relationships(source_id)
- `idx_relationships_target`: On relationships(target_id)
- `idx_relationships_type`: On relationships(relationship_type)
- `idx_chunks_file_type`: On chunks(file_id, chunk_type)
- `idx_relationships_source_type`: On relationships(source_id, relationship_type)

## Triggers

### `chunks_fts_insert`
Automatically populates FTS table on chunk insertion.

### `chunks_fts_delete`
Removes from FTS table on chunk deletion.

### `chunks_fts_update`
Updates FTS table on chunk modification.

## Example Queries

### Full-Text Search
```sql
SELECT c.*, snippet(chunks_fts, 1, '<b>', '</b>', '...', 32) as match_snippet
FROM chunks_fts fts
JOIN chunks c ON fts.id = c.id
WHERE chunks_fts MATCH 'search term'
ORDER BY rank;
```

### Find Complex Functions
```sql
SELECT c.*, cc.cyclomatic_complexity
FROM chunks c
JOIN chunk_complexity cc ON c.id = cc.chunk_id
WHERE c.chunk_type IN ('function', 'method')
ORDER BY cc.cyclomatic_complexity DESC
LIMIT 20;
```

### File Dependencies
```sql
SELECT DISTINCT f2.path as dependency
FROM chunks c1
JOIN files f1 ON c1.file_id = f1.id
JOIN relationships r ON c1.id = r.source_id
JOIN chunks c2 ON r.target_id = c2.id
JOIN files f2 ON c2.file_id = f2.id
WHERE f1.path = ? AND r.relationship_type IN ('IMPORTS', 'CALLS')
ORDER BY f2.path;
```

### Duplicate Detection
```sql
SELECT f1.path as file1, c1.start_line as line1,
       f2.path as file2, c2.start_line as line2,
       c1.chunk_type, LENGTH(c1.content) as size
FROM chunks c1
JOIN files f1 ON c1.file_id = f1.id
JOIN chunks c2 ON c1.content = c2.content AND c1.id < c2.id
JOIN files f2 ON c2.file_id = f2.id
WHERE c1.chunk_type = c2.chunk_type
ORDER BY size DESC;
```

## JSON Metadata Queries

Using SQLite's JSON1 extension:
```sql
-- Find chunks with specific metadata
SELECT * FROM chunks 
WHERE json_extract(metadata, '$.cyclomatic_complexity') > 10;

-- Extract all imports
SELECT c.id, json_each.value as import
FROM chunks c, json_each(json_extract(c.metadata, '$.imports'))
WHERE json_extract(c.metadata, '$.imports') IS NOT NULL;
```
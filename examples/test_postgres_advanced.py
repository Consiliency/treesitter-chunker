#!/usr/bin/env python3
"""Advanced integration test for PostgreSQL exporter features."""

import csv
import json
import tempfile
from pathlib import Path

from chunker.export.postgres_exporter import PostgresExporter
from chunker.types import CodeChunk


def test_postgres_advanced_features():
    """Test all advanced PostgreSQL features."""

    # Create test chunks with rich metadata
    chunks = [
        CodeChunk(
            file_path="src/main.py",
            start_line=1,
            end_line=100,
            byte_start=0,
            byte_end=3000,
            content="class ComplexClass:\n    def method(self):\n        pass",
            node_type="class",
            language="python",
            parent_context="module",
            metadata={
                "name": "ComplexClass",
                "chunk_type": "class",
                "cyclomatic_complexity": 15,
                "token_count": 250,
                "has_docstring": True,
                "methods": ["method1", "method2", "method3"],
                "imports": ["os", "sys", "json"],
                "security_issues": ["SQL_INJECTION_RISK"],
                "nested_data": {
                    "depth": 3,
                    "patterns": ["singleton", "factory"],
                },
            },
        ),
        CodeChunk(
            file_path="lib/utils.js",
            start_line=50,
            end_line=75,
            byte_start=1000,
            byte_end=1800,
            content="function process() { return data.map(x => x * 2); }",
            node_type="function",
            language="javascript",
            parent_context="module",
            metadata={
                "name": "process",
                "chunk_type": "function",
                "cyclomatic_complexity": 3,
                "token_count": 45,
                "async": True,
                "parameters": ["data"],
                "returns": "Array<number>",
            },
        ),
    ]

    # Create exporter
    exporter = PostgresExporter()
    exporter.add_chunks(chunks)

    # Add complex relationships
    exporter.add_relationship(
        chunks[0],
        chunks[1],
        "CALLS",
        {
            "context": "data_processing",
            "frequency": 10,
            "async": True,
            "metadata": {"critical": True},
        },
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # Test 1: Schema DDL includes all advanced features
        schema = exporter.get_schema_ddl()

        # JSONB support
        assert "JSONB" in schema
        assert "metadata JSONB" in schema
        assert "properties JSONB" in schema

        # Partitioning
        assert "PARTITION BY LIST (language)" in schema
        assert "chunks_python PARTITION OF chunks_partitioned" in schema
        assert "chunks_javascript PARTITION OF chunks_partitioned" in schema

        # Materialized views
        assert "CREATE MATERIALIZED VIEW" in schema
        assert "file_stats" in schema
        assert "chunk_graph" in schema

        # Functions
        assert "CREATE OR REPLACE FUNCTION find_dependencies" in schema
        assert "CREATE OR REPLACE FUNCTION calculate_file_metrics" in schema
        assert "WITH RECURSIVE" in schema

        # Generated columns
        assert "GENERATED ALWAYS AS" in schema
        assert (
            "line_count INTEGER GENERATED ALWAYS AS (end_line - start_line + 1)"
            in schema
        )
        assert "content_hash TEXT GENERATED ALWAYS AS (md5(content))" in schema

        # Full-text search
        assert "CREATE TEXT SEARCH CONFIGURATION" in schema
        assert "code_search" in schema

        # Trigram support
        assert "pg_trgm" in schema
        assert "gin_trgm_ops" in schema

        # Test 2: Index statements include advanced indexes
        indexes = exporter.get_index_statements()

        # GIN indexes for JSONB
        assert any("GIN (metadata)" in idx for idx in indexes)
        assert any("GIN (properties)" in idx for idx in indexes)

        # Full-text search index
        assert any("to_tsvector" in idx for idx in indexes)

        # Trigram index
        assert any("gin_trgm_ops" in idx for idx in indexes)

        # Functional indexes
        assert any("metadata->>'name'" in idx for idx in indexes)
        assert any("metadata->>'cyclomatic_complexity'" in idx for idx in indexes)

        # Test 3: SQL export with proper escaping and JSONB
        sql_file = output_dir / "test.sql"
        exporter.export(sql_file, format="sql")

        content = sql_file.read_text()

        # Check JSONB casting
        assert "::jsonb" in content

        # Check ON CONFLICT handling
        assert "ON CONFLICT (id) DO UPDATE" in content

        # Check materialized view refresh
        assert "REFRESH MATERIALIZED VIEW CONCURRENTLY" in content

        # Test 4: COPY format export
        copy_base = output_dir / "test"
        exporter.export(copy_base, format="copy")

        # Verify all files created
        assert (output_dir / "test_schema.sql").exists()
        assert (output_dir / "test_chunks.csv").exists()
        assert (output_dir / "test_relationships.csv").exists()
        assert (output_dir / "test_import.sql").exists()

        # Verify CSV content
        with Path(output_dir / "test_chunks.csv").open(
            "r",
            encoding="utf-8",
        ) as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 2  # Two chunks

            # Check JSONB metadata is properly formatted
            for row in rows:
                metadata_col = row[-1]  # Last column is metadata
                metadata = json.loads(metadata_col)
                assert isinstance(metadata, dict)
                assert "chunk_type" in metadata

        # Test 5: Advanced queries
        queries = exporter.get_advanced_queries()

        required_queries = [
            "similarity_search",
            "full_text_search",
            "jsonb_metadata_query",
            "dependency_graph",
            "hot_spots",
        ]

        for query_name in required_queries:
            assert query_name in queries
            query = queries[query_name]

            if query_name == "similarity_search":
                assert "similarity(" in query
                # Check that trigram index exists somewhere in the index statements
                assert any(
                    "gin_trgm_ops" in idx for idx in exporter.get_index_statements()
                )

            elif query_name == "full_text_search":
                assert "to_tsvector" in query
                assert "ts_rank" in query
                assert "ts_headline" in query

            elif query_name == "jsonb_metadata_query":
                assert "@>" in query  # JSONB containment operator
                assert "->>" in query  # JSONB field extraction

            elif query_name == "dependency_graph":
                assert "WITH RECURSIVE" in query
                assert "ARRAY[" in query  # Path tracking

            elif query_name == "hot_spots":
                assert "chunk_graph" in query  # Uses materialized view
                assert "hotness_score" in query

    print("✓ All PostgreSQL advanced features verified!")


if __name__ == "__main__":
    test_postgres_advanced_features()

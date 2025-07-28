"""Integration tests for Phase 12: Graph & Database Export."""

import csv
import sqlite3
import xml.etree.ElementTree as ET

import pytest

from chunker.export.dot_exporter import DotExporter
from chunker.export.graphml_exporter import GraphMLExporter
from chunker.export.neo4j_exporter import Neo4jExporter
from chunker.export.postgres_exporter import PostgresExporter
from chunker.export.sqlite_exporter import SQLiteExporter
from chunker.types import CodeChunk


@pytest.fixture()
def sample_chunks():
    """Create sample code chunks for testing."""
    return [
        CodeChunk(
            language="python",
            file_path="src/main.py",
            node_type="function",
            start_line=1,
            end_line=10,
            byte_start=0,
            byte_end=200,
            parent_context="module",
            content="def main():\n    pass",
            metadata={
                "name": "main",
                "cyclomatic_complexity": 1,
                "token_count": 15,
                "imports": ["sys", "os"],
                "chunk_type": "function",  # Add chunk_type to metadata for GraphML export
            },
        ),
        CodeChunk(
            language="python",
            file_path="src/utils.py",
            node_type="function",
            start_line=5,
            end_line=15,
            byte_start=100,
            byte_end=300,
            parent_context="module",
            content="def helper():\n    return 42",
            metadata={
                "name": "helper",
                "cyclomatic_complexity": 2,
                "token_count": 20,
                "chunk_type": "function",
            },
        ),
        CodeChunk(
            language="python",
            file_path="src/main.py",
            node_type="class",
            start_line=15,
            end_line=30,
            byte_start=250,
            byte_end=500,
            parent_context="module",
            content="class App:\n    def __init__(self):\n        pass",
            metadata={
                "name": "App",
                "parent_id": "src/main.py:1:10",  # References main function
                "chunk_type": "class",
            },
        ),
    ]


class TestGraphMLExporter:
    """Test GraphML export functionality."""

    def test_basic_export(self, sample_chunks, tmp_path):
        """Test basic GraphML export."""
        exporter = GraphMLExporter()
        exporter.add_chunks(sample_chunks)

        # Add a relationship
        exporter.add_relationship(
            sample_chunks[0],
            sample_chunks[1],
            "CALLS",
            {"line": 5},
        )

        # Export to file
        output_file = tmp_path / "test.graphml"
        exporter.export(output_file)

        # Verify file exists and is valid XML
        assert output_file.exists()
        tree = ET.parse(output_file)
        root = tree.getroot()

        # Check GraphML namespace
        assert "graphml.graphdrawing.org" in root.tag

        # Check nodes exist
        graph = root.find(".//{http://graphml.graphdrawing.org/xmlns}graph")
        nodes = graph.findall(".//{http://graphml.graphdrawing.org/xmlns}node")
        assert len(nodes) == 3

        # Check edges exist
        edges = graph.findall(".//{http://graphml.graphdrawing.org/xmlns}edge")
        assert len(edges) == 1

    def test_visualization_hints(self, sample_chunks):
        """Test adding visualization hints."""
        exporter = GraphMLExporter()
        exporter.add_chunks(sample_chunks)

        # Add visualization hints
        exporter.add_visualization_hints(
            node_colors={"function": "#FF0000", "class": "#00FF00"},
            edge_colors={"CALLS": "#0000FF"},
            node_shapes={"function": "ellipse", "class": "rectangle"},
        )

        # Export as string
        graphml_str = exporter.export_string()

        # Check that color attributes are present
        assert "color" in graphml_str
        assert "#FF0000" in graphml_str  # Function color
        assert "#00FF00" in graphml_str  # Class color

    def test_relationship_extraction(self, sample_chunks):
        """Test automatic relationship extraction."""
        exporter = GraphMLExporter()
        exporter.add_chunks(sample_chunks)
        exporter.extract_relationships(sample_chunks)

        # Should find parent-child relationship
        assert len(exporter.edges) >= 1
        parent_child_found = any(
            edge.relationship_type == "CONTAINS" for edge in exporter.edges
        )
        assert parent_child_found


class TestNeo4jExporter:
    """Test Neo4j export functionality."""

    def test_csv_export(self, sample_chunks, tmp_path):
        """Test CSV export for Neo4j."""
        exporter = Neo4jExporter()
        exporter.add_chunks(sample_chunks)
        exporter.add_relationship(
            sample_chunks[0],
            sample_chunks[1],
            "CALLS",
            {"frequency": 10},
        )

        # Export to CSV
        output_base = tmp_path / "neo4j_export"
        exporter.export(output_base, format="csv")

        # Check files exist
        nodes_file = tmp_path / "neo4j_export_nodes.csv"
        rels_file = tmp_path / "neo4j_export_relationships.csv"
        import_file = tmp_path / "neo4j_export_import.sh"

        assert nodes_file.exists()
        assert rels_file.exists()
        assert import_file.exists()

        # Verify CSV content
        with open(nodes_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 3
            assert "nodeId:ID" in rows[0]
            assert ":LABEL" in rows[0]

    def test_cypher_generation(self, sample_chunks):
        """Test Cypher statement generation."""
        exporter = Neo4jExporter()
        exporter.add_chunks(sample_chunks)

        statements = exporter.generate_cypher_statements()

        # Check for constraints and indices
        constraint_found = any("CONSTRAINT" in stmt for stmt in statements)
        index_found = any("INDEX" in stmt for stmt in statements)

        assert constraint_found
        assert index_found

        # Check for node creation
        create_found = any(
            "CREATE" in stmt and "CodeChunk" in stmt for stmt in statements
        )
        assert create_found

    def test_label_assignment(self, sample_chunks):
        """Test that chunks get appropriate labels."""
        exporter = Neo4jExporter()
        exporter.add_chunks(sample_chunks)

        # Check labels
        for node_id in exporter.node_labels:
            labels = exporter.node_labels[node_id]
            assert "CodeChunk" in labels  # Base label
            assert "Python" in labels  # Language label


class TestDotExporter:
    """Test DOT (Graphviz) export functionality."""

    def test_basic_dot_export(self, sample_chunks, tmp_path):
        """Test basic DOT export."""
        exporter = DotExporter()
        exporter.add_chunks(sample_chunks)
        exporter.add_relationship(
            sample_chunks[0],
            sample_chunks[1],
            "CALLS",
        )

        # Export to file
        output_file = tmp_path / "test.dot"
        exporter.export(output_file)

        # Verify file content
        content = output_file.read_text()
        assert "digraph CodeGraph" in content
        assert "->" in content  # Has edges
        assert "ellipse" in content  # Has function shape (ellipse)

    def test_clustering(self, sample_chunks):
        """Test clustering by file."""
        exporter = DotExporter()
        exporter.add_chunks(sample_chunks)

        # Export with clustering
        dot_str = exporter.export_string(use_clusters=True)

        # Check for subgraphs
        assert "subgraph cluster_" in dot_str
        assert "src/main.py" in dot_str
        assert "src/utils.py" in dot_str

    def test_custom_styles(self, sample_chunks):
        """Test custom styling."""
        exporter = DotExporter()
        exporter.add_chunks(sample_chunks)

        # Set custom styles
        exporter.set_node_style("function", shape="diamond", fillcolor="yellow")
        exporter.set_edge_style("CALLS", style="bold", color="red")

        dot_str = exporter.export_string()

        # Verify styles are applied
        assert "diamond" in dot_str
        assert "yellow" in dot_str


class TestSQLiteExporter:
    """Test SQLite export functionality."""

    def test_database_creation(self, sample_chunks, tmp_path):
        """Test SQLite database creation."""
        exporter = SQLiteExporter()
        exporter.add_chunks(sample_chunks)
        exporter.add_relationship(
            sample_chunks[0],
            sample_chunks[1],
            "CALLS",
        )

        # Export to database
        db_path = tmp_path / "chunks.db"
        exporter.export(db_path)

        # Verify database exists
        assert db_path.exists()

        # Connect and verify schema
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        assert "chunks" in tables
        assert "relationships" in tables
        assert "schema_info" in tables

        # Check data
        cursor.execute("SELECT COUNT(*) FROM chunks")
        assert cursor.fetchone()[0] == 3

        cursor.execute("SELECT COUNT(*) FROM relationships")
        assert cursor.fetchone()[0] == 1

        conn.close()

    def test_full_text_search(self, sample_chunks, tmp_path):
        """Test full-text search capability."""
        exporter = SQLiteExporter()
        exporter.add_chunks(sample_chunks)

        db_path = tmp_path / "chunks_fts.db"
        exporter.export(db_path, enable_fts=True)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Test FTS
        cursor.execute(
            "SELECT * FROM chunks_fts WHERE chunks_fts MATCH ?",
            ("main",),
        )
        results = cursor.fetchall()
        assert len(results) > 0

        conn.close()

    def test_views_and_indices(self, sample_chunks, tmp_path):
        """Test that views and indices are created."""
        exporter = SQLiteExporter()
        exporter.add_chunks(sample_chunks)

        db_path = tmp_path / "chunks_indexed.db"
        exporter.export(db_path, create_indices=True)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Check views
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
        views = {row[0] for row in cursor.fetchall()}
        assert "chunk_summary" in views
        assert "file_summary" in views

        # Check indices
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indices = {row[0] for row in cursor.fetchall()}
        assert any("file_path" in idx for idx in indices)

        conn.close()


class TestPostgresExporter:
    """Test PostgreSQL export functionality."""

    def test_sql_export(self, sample_chunks, tmp_path):
        """Test SQL export for PostgreSQL."""
        exporter = PostgresExporter()
        exporter.add_chunks(sample_chunks)
        exporter.add_relationship(
            sample_chunks[0],
            sample_chunks[1],
            "IMPORTS",
        )

        # Export as SQL
        sql_file = tmp_path / "postgres_export.sql"
        exporter.export(sql_file, format="sql")

        # Verify content
        content = sql_file.read_text()

        # Check for PostgreSQL-specific features
        assert "JSONB" in content
        assert "CREATE EXTENSION" in content
        assert "GENERATED ALWAYS AS" in content
        assert "ON CONFLICT" in content

        # Check for data
        assert "INSERT INTO chunks" in content
        assert "INSERT INTO relationships" in content

    def test_copy_format_export(self, sample_chunks, tmp_path):
        """Test COPY format export."""
        exporter = PostgresExporter()
        exporter.add_chunks(sample_chunks)

        # Export as COPY format
        output_base = tmp_path / "pg_export"
        exporter.export(output_base, format="copy")

        # Check files
        schema_file = tmp_path / "pg_export_schema.sql"
        chunks_file = tmp_path / "pg_export_chunks.csv"
        import_file = tmp_path / "pg_export_import.sql"

        assert schema_file.exists()
        assert chunks_file.exists()
        assert import_file.exists()

        # Verify CSV content
        with open(chunks_file) as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 3  # 3 chunks

    def test_advanced_features(self, sample_chunks):
        """Test advanced PostgreSQL features."""
        exporter = PostgresExporter()
        exporter.add_chunks(sample_chunks)

        # Get schema
        schema = exporter.get_schema_ddl()

        # Check for advanced features
        assert "PARTITION BY" in schema  # Partitioning
        assert "MATERIALIZED VIEW" in schema  # Mat views
        assert "CREATE OR REPLACE FUNCTION" in schema  # Functions
        assert "gin_trgm_ops" in schema  # Trigram search

        # Check for recursive CTE function
        assert "WITH RECURSIVE" in schema


class TestCrossExporterIntegration:
    """Test integration between different exporters."""

    def test_consistent_ids(self, sample_chunks):
        """Test that all exporters generate consistent IDs."""
        chunk = sample_chunks[0]

        # Create all exporters
        graphml = GraphMLExporter()
        neo4j = Neo4jExporter()
        sqlite = SQLiteExporter()
        postgres = PostgresExporter()

        # Add same chunk to all
        for exporter in [graphml, neo4j, sqlite, postgres]:
            exporter.add_chunks([chunk])

        # Get IDs
        graphml_id = next(iter(graphml.nodes.keys()))
        neo4j_id = next(iter(neo4j.nodes.keys()))
        sqlite_id = sqlite._get_chunk_id(chunk)
        postgres_id = postgres._get_chunk_id(chunk)

        # For graph exporters, IDs should be consistent
        assert graphml_id == neo4j_id

        # For database exporters, IDs should be consistent
        assert sqlite_id == postgres_id

    def test_relationship_consistency(self, sample_chunks):
        """Test that relationships are handled consistently."""
        exporters = [
            GraphMLExporter(),
            Neo4jExporter(),
            DotExporter(),
            SQLiteExporter(),
            PostgresExporter(),
        ]

        # Add same data to all exporters
        for exporter in exporters:
            exporter.add_chunks(sample_chunks)
            exporter.add_relationship(
                sample_chunks[0],
                sample_chunks[1],
                "DEPENDS_ON",
                {"weight": 1},
            )

        # All should have the relationship
        for exporter in exporters[:3]:  # Graph exporters
            assert len(exporter.edges) == 1
            assert exporter.edges[0].relationship_type == "DEPENDS_ON"

        for exporter in exporters[3:]:  # Database exporters
            assert len(exporter.relationships) == 1
            assert exporter.relationships[0]["relationship_type"] == "DEPENDS_ON"

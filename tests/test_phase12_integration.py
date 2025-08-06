"""Integration tests for Phase 12: Graph & Database Export."""

import csv
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

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
            content="""def main():
    pass""",
            metadata={
                "name": "main",
                "cyclomatic_complexity": 1,
                "token_count": 15,
                "imports": ["sys", "os"],
                "chunk_type": "function",
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
            content="""def helper():
    return 42""",
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
            content="""class App:
    def __init__(self):
        pass""",
            metadata={
                "name": "App",
                "parent_id": "src/main.py:1:10",
                "chunk_type": "class",
            },
        ),
    ]


class TestGraphMLExporter:
    """Test GraphML export functionality."""

    @classmethod
    def test_basic_export(cls, sample_chunks, tmp_path):
        """Test basic GraphML export."""
        exporter = GraphMLExporter()
        exporter.add_chunks(sample_chunks)
        exporter.add_relationship(
            sample_chunks[0],
            sample_chunks[1],
            "CALLS",
            {"line": 5},
        )
        output_file = tmp_path / "test.graphml"
        exporter.export(output_file)
        assert output_file.exists()
        tree = ET.parse(output_file)  # noqa: S314 - Parsing test-generated XML
        root = tree.getroot()
        assert "graphml.graphdrawing.org" in root.tag
        graph = root.find(".//{http://graphml.graphdrawing.org/xmlns}graph")
        nodes = graph.findall(".//{http://graphml.graphdrawing.org/xmlns}node")
        assert len(nodes) == 3
        edges = graph.findall(".//{http://graphml.graphdrawing.org/xmlns}edge")
        assert len(edges) == 1

    @classmethod
    def test_visualization_hints(cls, sample_chunks):
        """Test adding visualization hints."""
        exporter = GraphMLExporter()
        exporter.add_chunks(sample_chunks)
        exporter.add_visualization_hints(
            node_colors={"function": "#FF0000", "class": "#00FF00"},
            edge_colors={"CALLS": "#0000FF"},
            node_shapes={"function": "ellipse", "class": "rectangle"},
        )
        graphml_str = exporter.export_string()
        assert "color" in graphml_str
        assert "#FF0000" in graphml_str
        assert "#00FF00" in graphml_str

    @classmethod
    def test_relationship_extraction(cls, sample_chunks):
        """Test automatic relationship extraction."""
        exporter = GraphMLExporter()
        exporter.add_chunks(sample_chunks)
        exporter.extract_relationships(sample_chunks)
        assert len(exporter.edges) >= 1
        parent_child_found = any(
            edge.relationship_type == "CONTAINS" for edge in exporter.edges
        )
        assert parent_child_found


class TestNeo4jExporter:
    """Test Neo4j export functionality."""

    @classmethod
    def test_csv_export(cls, sample_chunks, tmp_path):
        """Test CSV export for Neo4j."""
        exporter = Neo4jExporter()
        exporter.add_chunks(sample_chunks)
        exporter.add_relationship(
            sample_chunks[0],
            sample_chunks[1],
            "CALLS",
            {"frequency": 10},
        )
        output_base = tmp_path / "neo4j_export"
        exporter.export(output_base, format="csv")
        nodes_file = tmp_path / "neo4j_export_nodes.csv"
        rels_file = tmp_path / "neo4j_export_relationships.csv"
        import_file = tmp_path / "neo4j_export_import.sh"
        assert nodes_file.exists()
        assert rels_file.exists()
        assert import_file.exists()
        with Path(nodes_file).open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 3
            assert "nodeId:ID" in rows[0]
            assert ":LABEL" in rows[0]

    @classmethod
    def test_cypher_generation(cls, sample_chunks):
        """Test Cypher statement generation."""
        exporter = Neo4jExporter()
        exporter.add_chunks(sample_chunks)
        statements = exporter.generate_cypher_statements()
        constraint_found = any("CONSTRAINT" in stmt for stmt in statements)
        index_found = any("INDEX" in stmt for stmt in statements)
        assert constraint_found
        assert index_found
        create_found = any(
            "CREATE" in stmt and "CodeChunk" in stmt for stmt in statements
        )
        assert create_found

    @classmethod
    def test_label_assignment(cls, sample_chunks):
        """Test that chunks get appropriate labels."""
        exporter = Neo4jExporter()
        exporter.add_chunks(sample_chunks)
        for node_id in exporter.node_labels:
            labels = exporter.node_labels[node_id]
            assert "CodeChunk" in labels
            assert "Python" in labels


class TestDotExporter:
    """Test DOT (Graphviz) export functionality."""

    @classmethod
    def test_basic_dot_export(cls, sample_chunks, tmp_path):
        """Test basic DOT export."""
        exporter = DotExporter()
        exporter.add_chunks(sample_chunks)
        exporter.add_relationship(sample_chunks[0], sample_chunks[1], "CALLS")
        output_file = tmp_path / "test.dot"
        exporter.export(output_file)
        content = output_file.read_text()
        assert "digraph CodeGraph" in content
        assert "->" in content
        assert "ellipse" in content

    @classmethod
    def test_clustering(cls, sample_chunks):
        """Test clustering by file."""
        exporter = DotExporter()
        exporter.add_chunks(sample_chunks)
        dot_str = exporter.export_string(use_clusters=True)
        assert "subgraph cluster_" in dot_str
        assert "src/main.py" in dot_str
        assert "src/utils.py" in dot_str

    @classmethod
    def test_custom_styles(cls, sample_chunks):
        """Test custom styling."""
        exporter = DotExporter()
        exporter.add_chunks(sample_chunks)
        exporter.set_node_style(
            "function",
            shape="diamond",
            fillcolor="yellow",
        )
        exporter.set_edge_style("CALLS", style="bold", color="red")
        dot_str = exporter.export_string()
        assert "diamond" in dot_str
        assert "yellow" in dot_str


class TestSQLiteExporter:
    """Test SQLite export functionality."""

    @classmethod
    def test_database_creation(cls, sample_chunks, tmp_path):
        """Test SQLite database creation."""
        exporter = SQLiteExporter()
        exporter.add_chunks(sample_chunks)
        exporter.add_relationship(sample_chunks[0], sample_chunks[1], "CALLS")
        db_path = tmp_path / "chunks.db"
        exporter.export(db_path)
        assert db_path.exists()
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        assert "chunks" in tables
        assert "relationships" in tables
        assert "schema_info" in tables
        cursor.execute("SELECT COUNT(*) FROM chunks")
        assert cursor.fetchone()[0] == 3
        cursor.execute("SELECT COUNT(*) FROM relationships")
        assert cursor.fetchone()[0] == 1
        conn.close()

    @classmethod
    def test_full_text_search(cls, sample_chunks, tmp_path):
        """Test full-text search capability."""
        exporter = SQLiteExporter()
        exporter.add_chunks(sample_chunks)
        db_path = tmp_path / "chunks_fts.db"
        exporter.export(db_path, enable_fts=True)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chunks_fts WHERE chunks_fts MATCH ?", ("main",))
        results = cursor.fetchall()
        assert len(results) > 0
        conn.close()

    @classmethod
    def test_views_and_indices(cls, sample_chunks, tmp_path):
        """Test that views and indices are created."""
        exporter = SQLiteExporter()
        exporter.add_chunks(sample_chunks)
        db_path = tmp_path / "chunks_indexed.db"
        exporter.export(db_path, create_indices=True)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
        views = {row[0] for row in cursor.fetchall()}
        assert "chunk_summary" in views
        assert "file_summary" in views
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indices = {row[0] for row in cursor.fetchall()}
        assert any("file_path" in idx for idx in indices)
        conn.close()


class TestPostgresExporter:
    """Test PostgreSQL export functionality."""

    @classmethod
    def test_sql_export(cls, sample_chunks, tmp_path):
        """Test SQL export for PostgreSQL."""
        exporter = PostgresExporter()
        exporter.add_chunks(sample_chunks)
        exporter.add_relationship(
            sample_chunks[0],
            sample_chunks[1],
            "IMPORTS",
        )
        sql_file = tmp_path / "postgres_export.sql"
        exporter.export(sql_file, format="sql")
        content = sql_file.read_text()
        assert "JSONB" in content
        assert "CREATE EXTENSION" in content
        assert "GENERATED ALWAYS AS" in content
        assert "ON CONFLICT" in content
        assert "INSERT INTO chunks" in content
        assert "INSERT INTO relationships" in content

    @classmethod
    def test_copy_format_export(cls, sample_chunks, tmp_path):
        """Test COPY format export."""
        exporter = PostgresExporter()
        exporter.add_chunks(sample_chunks)
        output_base = tmp_path / "pg_export"
        exporter.export(output_base, format="copy")
        schema_file = tmp_path / "pg_export_schema.sql"
        chunks_file = tmp_path / "pg_export_chunks.csv"
        import_file = tmp_path / "pg_export_import.sql"
        assert schema_file.exists()
        assert chunks_file.exists()
        assert import_file.exists()
        with Path(chunks_file).open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 3

    @classmethod
    def test_advanced_features(cls, sample_chunks):
        """Test advanced PostgreSQL features."""
        exporter = PostgresExporter()
        exporter.add_chunks(sample_chunks)
        schema = exporter.get_schema_ddl()
        assert "PARTITION BY" in schema
        assert "MATERIALIZED VIEW" in schema
        assert "CREATE OR REPLACE FUNCTION" in schema
        assert "gin_trgm_ops" in schema
        assert "WITH RECURSIVE" in schema


class TestCrossExporterIntegration:
    """Test integration between different exporters."""

    @classmethod
    def test_consistent_ids(cls, sample_chunks):
        """Test that all exporters generate consistent IDs."""
        chunk = sample_chunks[0]
        graphml = GraphMLExporter()
        neo4j = Neo4jExporter()
        sqlite = SQLiteExporter()
        postgres = PostgresExporter()
        for exporter in [graphml, neo4j, sqlite, postgres]:
            exporter.add_chunks([chunk])
        graphml_id = next(iter(graphml.nodes.keys()))
        neo4j_id = next(iter(neo4j.nodes.keys()))
        sqlite_id = sqlite._get_chunk_id(chunk)
        postgres_id = postgres._get_chunk_id(chunk)
        assert graphml_id == neo4j_id
        assert sqlite_id == postgres_id

    @classmethod
    def test_relationship_consistency(cls, sample_chunks):
        """Test that relationships are handled consistently."""
        exporters = [
            GraphMLExporter(),
            Neo4jExporter(),
            DotExporter(),
            SQLiteExporter(),
            PostgresExporter(),
        ]
        for exporter in exporters:
            exporter.add_chunks(sample_chunks)
            exporter.add_relationship(
                sample_chunks[0],
                sample_chunks[1],
                "DEPENDS_ON",
                {"weight": 1},
            )
        for exporter in exporters[:3]:
            assert len(exporter.edges) == 1
            assert exporter.edges[0].relationship_type == "DEPENDS_ON"
        for exporter in exporters[3:]:
            assert len(exporter.relationships) == 1
            assert exporter.relationships[0]["relationship_type"] == "DEPENDS_ON"

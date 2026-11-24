"""Integration tests for Phase 12: Graph & Database Export."""

import csv
import os
import sqlite3
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest

from chunker.export.dot_exporter import DotExporter
from chunker.export.graphml_exporter import GraphMLExporter
from chunker.export.neo4j_exporter import Neo4jExporter
from chunker.export.postgres_exporter import PostgresExporter
from chunker.export.sqlite_exporter import SQLiteExporter
from chunker.types import CodeChunk


@pytest.fixture
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
        tree = ET.parse(output_file)
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


COMMON_QUERIES = {
    "chunks_per_file",
    "chunks_by_type",
    "average_chunk_size",
    "relationship_summary",
    "most_connected_chunks",
    "find_dependencies",
}
SQLITE_QUERIES = {
    "search_content",
    "complex_functions",
    "file_dependencies",
    "duplicate_detection",
}
POSTGRES_QUERIES = {
    "similarity_search",
    "full_text_search",
    "jsonb_metadata_query",
    "dependency_graph",
    "hot_spots",
}
SOURCE_PATH = "src/a'b.py"


@pytest.fixture
def query_data(sample_chunks):
    # IDs and edges are explicit so the oracle can be checked independently.
    chunks = [
        replace(
            sample_chunks[0],
            chunk_id=key,
            file_path=path,
            node_type=kind,
            start_line=start,
            end_line=end,
            content=content,
            metadata={
                "name": key,
                "cyclomatic_complexity": complexity,
                "has_docstring": doc,
                "token_count": 10,
            },
        )
        for key, path, kind, start, end, content, complexity, doc in [
            ("a", SOURCE_PATH, "function", 1, 3, "twin café\r\n", 15, True),
            ("b", "b.py", "function", 5, 9, "twin café\r\n", 2, True),
            ("c", SOURCE_PATH, "class", 7, 7, "twin café\r\n", 20, False),
            ("d", "d.py", "class", 1, 2, "needlexyz", 1, True),
            ("e", "e.py", "class", 2, 3, "different", 1, True),
            ("f", "f.py", "class", 4, 6, "isolated", 1, True),
        ]
    ]
    edges = [
        ("a", "b", "IMPORTS"),
        ("a", "b", "CALLS"),
        ("b", "c", "IMPORTS"),
        ("c", "b", "IMPORTS"),
        ("a", "d", "INCLUDES"),
        ("b", "d", "EXTENDS"),
        ("a", "e", "CALLS"),
    ]
    return chunks, edges


def _mapping(exporter, name, keys):
    accessor = getattr(exporter, name)
    instance_mapping = getattr(exporter(), name)()
    mapping = accessor()
    assert set(mapping) == keys and instance_mapping == mapping
    instance_mapping.clear()
    assert set(mapping) == set(accessor()) == keys
    return mapping


def _check_common_queries(execute, queries, chunk_columns):
    def read(key, labels, *args):
        cur = execute(queries[key], args)
        assert [d[0] for d in cur.description] == labels.split()
        return cur.fetchall()

    per_file = read("chunks_per_file", "file_path chunk_count")
    assert per_file[0] == (SOURCE_PATH, 2)
    assert sorted(per_file[1:]) == [
        (name, 1) for name in ["b.py", "d.py", "e.py", "f.py"]
    ]
    assert read("chunks_by_type", "chunk_type count") == [("class", 4), ("function", 2)]
    sizes = sorted(
        read("average_chunk_size", "chunk_type avg_lines min_lines max_lines")
    )
    assert sizes == [("class", 2, 1, 3), ("function", 4, 3, 5)]
    summaries = read("relationship_summary", "relationship_type count")
    assert summaries[:2] == [("IMPORTS", 3), ("CALLS", 2)]
    assert sorted(summaries[2:]) == [("EXTENDS", 1), ("INCLUDES", 1)]
    degrees = read("most_connected_chunks", "id file_path chunk_type outgoing incoming")
    assert [r[3] + r[4] for r in degrees] == [4, 3, 2, 2, 1, 0]
    assert sorted(degrees) == [
        ("a", SOURCE_PATH, "function", 3, 0),
        ("b", "b.py", "function", 2, 2),
        ("c", SOURCE_PATH, "class", 1, 1),
        ("d", "d.py", "class", 0, 2),
        ("e", "e.py", "class", 0, 1),
        ("f", "f.py", "class", 0, 0),
    ]

    def deps(anchor):
        return [
            (r[0], r[-1])
            for r in read("find_dependencies", chunk_columns + " depth", anchor)
        ]

    assert deps("a") == [("b", 1), ("e", 1), ("c", 2), ("b", 3), ("c", 4), ("b", 5)]
    assert deps("b") == [("c", 1), ("b", 2), ("c", 3), ("b", 4), ("c", 5)]
    assert deps("missing") == []


def _snapshot(sample_chunks, marker):
    exporter = SQLiteExporter()
    exporter.add_chunks(
        [
            replace(
                sample_chunks[0],
                chunk_id="shared",
                file_path=f"{marker}.py",
                content=f"{marker} café\r\n",
            ),
            replace(
                sample_chunks[1], chunk_id=marker, file_path="util.py", content="end"
            ),
        ]
    )
    exporter.add_relationship(*exporter.chunks, "CALLS")
    return exporter


def _assert_snapshot(path, marker, indexed=True):
    with closing(sqlite3.connect(path)) as db:

        def rows(sql):
            return db.execute(sql).fetchall()

        assert rows("PRAGMA integrity_check") == [("ok",)]
        assert rows("PRAGMA foreign_key_check") == []
        assert rows(
            "SELECT chunks.id, path, content FROM chunks JOIN files ON file_id=files.id ORDER BY chunks.id"
        ) == sorted(
            [
                ("shared", f"{marker}.py", f"{marker} café\r\n"),
                (marker, "util.py", "end"),
            ]
            if marker
            else []
        )
        assert rows(
            "SELECT source_id,target_id,relationship_type FROM relationships"
        ) == ([("shared", marker, "CALLS")] if marker else [])
        assert rows("SELECT id, content FROM chunks_fts ORDER BY id") == sorted(
            [("shared", f"{marker} café\r\n"), (marker, "end")] if marker else []
        )
        assert rows("SELECT id FROM chunks_fts WHERE chunks_fts MATCH 'café'") == (
            [("shared",)] if marker else []
        )
        assert rows(
            "SELECT file_path,chunk_count FROM file_summary ORDER BY file_path"
        ) == sorted([(f"{marker}.py", 1), ("util.py", 1)] if marker else [])
        assert dict(
            rows("SELECT key,value FROM schema_info WHERE key LIKE 'total_%'")
        ) == {
            "total_files": "2" if marker else "0",
            "total_chunks": "2" if marker else "0",
            "total_relationships": "1" if marker else "0",
        }
        assert (
            bool(
                rows("SELECT name FROM sqlite_schema WHERE name='idx_chunks_position'")
            )
            == indexed
        )


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

    @pytest.mark.parametrize("existing", [True, False])
    @pytest.mark.parametrize("error", ["duplicate", "foreign key"])
    def test_failed_build(self, tmp_path, sample_chunks, existing, error):
        path = tmp_path / "snapshot.db"
        if existing:
            _snapshot(sample_chunks, "before").export(path)
        exporter = _snapshot(sample_chunks, "after")
        if error == "duplicate":
            exporter.add_chunks(exporter.chunks[:1])
        else:
            exporter.relationships[0]["target_id"] = "missing"
        with pytest.raises(sqlite3.IntegrityError):
            exporter.export(path)
        if existing:
            _assert_snapshot(path, "before")
        assert list(tmp_path.iterdir()) == ([path] if existing else [])

    @pytest.mark.parametrize("indexed", [True, False])
    def test_replacement(self, tmp_path, sample_chunks, indexed):
        path = tmp_path / "snapshot.db"
        for marker in ["before", "after", None]:
            exporter = _snapshot(sample_chunks, marker) if marker else SQLiteExporter()
            exporter.export(path, create_indices=indexed)
            _assert_snapshot(path, marker, indexed)
            assert list(tmp_path.iterdir()) == [path]

    def test_live_publication(self, tmp_path, sample_chunks):
        path = tmp_path / "café #?.db" if os.name != "nt" else tmp_path / "café #.db"
        _snapshot(sample_chunks, "before").export(path)
        with closing(sqlite3.connect(path)) as reader:
            reader.execute("UPDATE files SET size=123")
            reader.commit()
            reader.execute("BEGIN")

            def paths():
                return reader.execute("SELECT path FROM files ORDER BY path").fetchall()

            assert paths() == [("before.py",), ("util.py",)]
            _snapshot(sample_chunks, "after").export(path)
            assert paths() == [("before.py",), ("util.py",)]
            _assert_snapshot(path, "after")
            reader.rollback()
            assert paths() == [("after.py",), ("util.py",)]
            reader.execute("BEGIN IMMEDIATE")
            script = """
import sqlite3, sys
from pathlib import Path
from chunker.export.sqlite_exporter import SQLiteExporter
try:
    SQLiteExporter().export(Path(sys.argv[1]))
except sqlite3.OperationalError as exc:
    assert 'locked' in str(exc), exc
else:
    raise AssertionError('locked export succeeded')
"""
            subprocess.run(
                [sys.executable, "-c", script, str(path)], timeout=30, check=True
            )
            reader.rollback()
        _assert_snapshot(path, "after")
        SQLiteExporter().export(path)
        moved = path.rename(tmp_path / "closed.db")
        _assert_snapshot(moved, None)

    def test_interrupted_backup(self, tmp_path, sample_chunks, monkeypatch):
        path = tmp_path / "snapshot.db"
        _snapshot(sample_chunks, "before").export(path)
        exporter = _snapshot(sample_chunks, "after")
        exporter.chunks[0].content = "large " * 300000

        def interrupt(status, remaining, total):
            assert status == sqlite3.SQLITE_OK and 0 < remaining < total
            raise RuntimeError("interrupted")

        monkeypatch.setattr(
            "chunker.export.sqlite_exporter._backup_progress", interrupt
        )
        with pytest.raises(RuntimeError, match="interrupted"):
            exporter.export(path)
        _assert_snapshot(path, "before")

    @pytest.mark.parametrize("contents", [b"x", b"unrelated " * 100])
    def test_existing_non_database(self, tmp_path, contents):
        path = tmp_path / "snapshot.db"
        path.write_bytes(contents)
        with pytest.raises(sqlite3.DatabaseError):
            SQLiteExporter().export(path)
        assert path.read_bytes() == contents

    @pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
    def test_orphan_sidecar(self, tmp_path, suffix):
        path = tmp_path / "snapshot.db"
        orphan = path.with_name(path.name + suffix)
        orphan.write_bytes(b"orphan")
        with pytest.raises(sqlite3.OperationalError, match="orphan"):
            SQLiteExporter().export(path)
        assert list(tmp_path.iterdir()) == [orphan]
        assert orphan.read_bytes() == b"orphan"

    def test_unsupported_paths(self, tmp_path, sample_chunks):
        path = tmp_path / "snapshot.db"
        _snapshot(sample_chunks, "before").export(path)
        with pytest.raises(ValueError):
            SQLiteExporter().export(tmp_path)
        hard = tmp_path / "hard.db"
        hard.hardlink_to(path)
        with pytest.raises(ValueError):
            SQLiteExporter().export(hard)
        _assert_snapshot(path, "before")
        hard.unlink()
        try:
            (tmp_path / "link.db").symlink_to(path)
        except OSError:
            pytest.skip("symlink creation unavailable")
        with pytest.raises(ValueError):
            SQLiteExporter().export(tmp_path / "link.db")
        _assert_snapshot(path, "before")

    @pytest.mark.skipif(os.name == "nt", reason="POSIX write permissions")
    def test_read_only_destination(self, tmp_path, sample_chunks):
        path = tmp_path / "snapshot.db"
        _snapshot(sample_chunks, "before").export(path)
        path.chmod(0o444)
        try:
            if os.access(path, os.W_OK):
                pytest.skip("process can write read-only files")
            with pytest.raises(sqlite3.OperationalError):
                SQLiteExporter().export(path)
            _assert_snapshot(path, "before")
        finally:
            path.chmod(0o644)

    @pytest.mark.skipif(os.name == "nt", reason="POSIX link publication")
    def test_first_publish_race(self, tmp_path, sample_chunks, monkeypatch):
        path = tmp_path / "snapshot.db"
        winner = tmp_path / "winner.db"
        _snapshot(sample_chunks, "before").export(winner)
        winner_identity = winner.stat()
        link = os.link

        def race(stage, final):
            link(winner, final)
            link(stage, final)

        def release(_delay):
            _assert_snapshot(path, "before")
            winner.unlink()

        monkeypatch.setattr(os, "link", race)
        monkeypatch.setattr("chunker.export.sqlite_exporter.time.sleep", release)
        _snapshot(sample_chunks, "after").export(path)
        assert not winner.exists()  # The competing link was installed and released.
        assert os.path.samestat(winner_identity, path.stat())
        _assert_snapshot(path, "after")

    def test_queries(self, tmp_path, query_data):
        chunks, edges = query_data
        by_id = {c.chunk_id: c for c in chunks}
        exporter = SQLiteExporter()
        exporter.add_chunks(chunks)
        for source, target, relation in edges:
            exporter.add_relationship(by_id[source], by_id[target], relation)
        path = tmp_path / "snapshot.db"
        exporter.export(path)
        analysis = _mapping(SQLiteExporter, "get_analysis_queries", COMMON_QUERIES)
        examples = _mapping(
            SQLiteExporter, "get_example_queries", COMMON_QUERIES | SQLITE_QUERIES
        )
        assert analysis.items() <= examples.items()
        with closing(sqlite3.connect(path)) as db:
            _check_common_queries(
                db.execute,
                examples,
                "id file_id start_line end_line start_byte end_byte content chunk_type parent_context metadata created_at",
            )

            def read(key, labels, *args):
                cur = db.execute(examples[key], args)
                assert [d[0] for d in cur.description] == labels.split()
                return cur.fetchall()

            search = "id file_path chunk_type start_line end_line match_snippet"
            assert read("search_content", search, "needlexyz") == [
                ("d", "d.py", "class", 1, 2, "<b>needlexyz</b>")
            ]
            assert read("search_content", search, "absent") == []
            assert read(
                "complex_functions",
                "file_path chunk_type start_line end_line cyclomatic_complexity cognitive_complexity token_count",
            ) == [
                (SOURCE_PATH, "function", 1, 3, 15, None, 10),
                ("b.py", "function", 5, 9, 2, None, 10),
            ]
            assert read("file_dependencies", "dependency", SOURCE_PATH) == [
                ("b.py",),
                ("d.py",),
            ]
            assert read("file_dependencies", "dependency", "unknown") == []
            assert read(
                "duplicate_detection", "file1 line1 file2 line2 chunk_type size"
            ) == [(SOURCE_PATH, 1, "b.py", 5, "function", 11)]


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

    def test_query_mapping(self):
        analysis = _mapping(PostgresExporter, "get_analysis_queries", COMMON_QUERIES)
        examples = _mapping(
            PostgresExporter, "get_advanced_queries", COMMON_QUERIES | POSTGRES_QUERIES
        )
        assert analysis.items() <= examples.items()
        assert "%s" in analysis["find_dependencies"]

    def test_query_execution(self, query_data):
        dsn = os.environ.get("CHUNKER_TEST_POSTGRES_DSN")
        if not dsn:
            pytest.skip(
                "set CHUNKER_TEST_POSTGRES_DSN to a disposable PostgreSQL database"
            )
        import psycopg
        from psycopg import sql
        from psycopg.types.json import Jsonb

        chunks, edges = query_data
        queries = PostgresExporter.get_advanced_queries()
        with closing(psycopg.connect(dsn)) as conn:
            # The uncommitted schema, extensions and data roll back on close.
            schema = sql.Identifier("Test chunks " + uuid.uuid4().hex)
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(schema))
            conn.execute(sql.SQL("SET LOCAL search_path TO {}, public").format(schema))
            conn.execute("SET LOCAL statement_timeout = '15s'")
            ddl = PostgresExporter.get_schema_ddl()
            conn.execute(ddl)
            conn.execute(ddl)  # Re-exporting reuses the schema's search configuration.
            for c in chunks:
                conn.execute(
                    "INSERT INTO chunks(id, file_path, chunk_type, start_line, end_line, content, language, metadata) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        c.chunk_id,
                        str(c.file_path),
                        c.node_type,
                        c.start_line,
                        c.end_line,
                        c.content,
                        c.language,
                        Jsonb(c.metadata),
                    ),
                )
            for edge in edges:
                conn.execute(
                    "INSERT INTO relationships(source_id,target_id,relationship_type) VALUES (%s,%s,%s)",
                    edge,
                )
            conn.execute("REFRESH MATERIALIZED VIEW chunk_graph")
            _check_common_queries(
                conn.execute,
                queries,
                "id file_path start_line end_line start_byte end_byte content chunk_type language metadata created_at line_count content_hash",
            )

            def read(key, labels, *args):
                cur = conn.execute(queries[key], args)
                assert [d[0] for d in cur.description] == labels.split()
                return cur.fetchall()

            similarity = "id file_path chunk_type similarity_score"
            assert read("similarity_search", similarity, "a") == [
                ("b", "b.py", "function", 1)
            ]
            assert read("similarity_search", similarity, "missing") == []
            search = "id file_path chunk_type highlighted rank"
            hits = read("full_text_search", search, "needlexyz")
            assert len(hits) == 1 and hits[0][:4] == (
                "d",
                "d.py",
                "class",
                "<b>needlexyz</b>",
            )
            assert hits[0][-1] > 0
            assert read("full_text_search", search, "absent") == []
            fields = "id file_path chunk_type name complexity"
            assert read("jsonb_metadata_query", fields, '{"has_docstring":true}') == [
                ("a", SOURCE_PATH, "function", "a", "15")
            ]
            assert read("jsonb_metadata_query", fields, '{"absent":true}') == []
            graph = read("dependency_graph", "id file_path chunk_type name level path")
            assert sorted(
                (key, level, path) for key, _, _, _, level, path in graph
            ) == [
                ("a", 0, ["a"]),
                ("b", 1, ["a", "b"]),
                ("c", 2, ["a", "b", "c"]),
                ("d", 2, ["a", "b", "d"]),
                ("e", 0, ["e"]),
                ("f", 0, ["f"]),
            ]
            hot = read(
                "hot_spots",
                "id file_path chunk_type chunk_name complexity tokens total_connections hotness_score",
            )
            assert [r[-1] for r in hot] == [60, 60, 10, 3, 2, 1]
            assert sorted((r[0], *r[4:]) for r in hot) == [
                ("a", 15, 10, 3, 60),
                ("b", 2, 10, 4, 10),
                ("c", 20, 10, 2, 60),
                ("d", 1, 10, 2, 3),
                ("e", 1, 10, 1, 2),
                ("f", 1, 10, 0, 1),
            ]


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

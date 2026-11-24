"""Integration tests for structured export functionality."""

import json
import sqlite3

import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import pytest

from chunker.core import chunk_file
from chunker.exceptions import ChunkerError
from chunker.export import (
    ASTRelationshipTracker,
    DOTExporter,
    GraphMLExporter,
    Neo4jExporter,
    SQLiteExporter,
    StructuredExportOrchestrator,
    StructuredJSONExporter,
    StructuredJSONLExporter,
    StructuredParquetExporter,
)
from chunker.interfaces.export import ChunkRelationship, ExportFormat, RelationshipType
from chunker.types import CodeChunk


def read_parquet_table(path):
    """Read parquet table with compatibility for older pyarrow versions."""
    # For pyarrow < 16, use OSFile to avoid path conversion issues
    if int(pa.__version__.split(".")[0]) < 16:
        with pa.OSFile(str(path), "rb") as source:
            return pq.read_table(source)
    else:
        return pq.read_table(str(path))


@pytest.fixture
def sample_python_file(tmp_path):
    """Create a sample Python file with relationships."""
    file_path = tmp_path / "sample.py"
    file_path.write_text(
        """
class Animal:
    ""\"Base animal class.""\"
    def __init__(self, name):
        self.name = name

    def speak(self):
        pass

class Dog(Animal):
    ""\"Dog class inheriting from Animal.""\"
    def __init__(self, name, breed):
        super().__init__(name)
        self.breed = breed

    def speak(self):
        return f"{self.name} barks!"

    def play_fetch(self):
        return "Fetching the ball!"

class Cat(Animal):
    ""\"Cat class inheriting from Animal.""\"
    def speak(self):
        return f"{self.name} meows!"

def create_pet(pet_type, name):
    ""\"Factory function to create pets.""\"
    if pet_type == "dog":
        return Dog(name, "mixed")
    elif pet_type == "cat":
        return Cat(name)
    else:
        return Animal(name)

# Test the classes
if __name__ == "__main__":
    dog = create_pet("dog", "Buddy")
    print(dog.speak())
""",
    )
    return file_path


@pytest.fixture
def sample_javascript_file(tmp_path):
    """Create a sample JavaScript file with relationships."""
    file_path = tmp_path / "sample.js"
    file_path.write_text(
        """
// Base Shape class
class Shape {
    constructor(color) {
        this.color = color;
    }

    getArea() {
        throw new Error("getArea must be implemented");
    }
}

// Circle extends Shape
class Circle extends Shape {
    constructor(color, radius) {
        super(color);
        this.radius = radius;
    }

    getArea() {
        return Math.PI * this.radius ** 2;
    }
}

// Rectangle extends Shape
class Rectangle extends Shape {
    constructor(color, width, height) {
        super(color);
        this.width = width;
        this.height = height;
    }

    getArea() {
        return this.width * this.height;
    }
}

// Factory function
function createShape(type, color, ...dimensions) {
    switch(type) {
        case 'circle':
            return new Circle(color, dimensions[0]);
        case 'rectangle':
            return new Rectangle(color, dimensions[0], dimensions[1]);
        default:
            throw new Error(`Unknown shape type: ${type}`);
    }
}

// Usage
const circle = createShape('circle', 'red', 5);
console.log(circle.getArea());
""",
    )
    return file_path


class TestStructuredExportIntegration:
    """Test structured export with relationship tracking."""

    @classmethod
    def test_end_to_end_json_export(cls, sample_python_file, tmp_path):
        """Test complete JSON export with relationships."""
        chunks = chunk_file(sample_python_file, "python")
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)
        orchestrator = StructuredExportOrchestrator()
        json_exporter = StructuredJSONExporter(indent=2)
        orchestrator.register_exporter(ExportFormat.JSON, json_exporter)
        output_path = tmp_path / "export.json"
        orchestrator.export(chunks, relationships, output_path)
        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert "metadata" in data
        assert "chunks" in data
        assert "relationships" in data
        assert len(data["chunks"]) > 0
        class_chunks = [c for c in data["chunks"] if "class" in c["node_type"]]
        assert len(class_chunks) >= 3
        class_names = []
        for chunk in class_chunks:
            content = chunk["content"]
            for line in content.split("\n"):
                if line.strip().startswith("class "):
                    name = line.split("class ")[1].split("(")[0].split(":")[0].strip()
                    class_names.append(name)
                    break
        assert "Animal" in class_names
        assert "Dog" in class_names
        assert "Cat" in class_names
        assert len(data["relationships"]) > 0
        inheritance_rels = [
            r for r in data["relationships"] if r["relationship_type"] == "inherits"
        ]
        assert len(inheritance_rels) >= 2

    @classmethod
    def test_end_to_end_jsonl_export(cls, sample_javascript_file, tmp_path):
        """Test complete JSONL export with streaming."""
        chunks = chunk_file(sample_javascript_file, "javascript")
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)
        orchestrator = StructuredExportOrchestrator()
        jsonl_exporter = StructuredJSONLExporter()
        orchestrator.register_exporter(ExportFormat.JSONL, jsonl_exporter)
        output_path = tmp_path / "export.jsonl"
        orchestrator.export(chunks, relationships, output_path)
        assert output_path.exists()
        lines = output_path.read_text().strip().split("\n")
        assert len(lines) > 0
        metadata_found = False
        chunk_count = 0
        relationship_count = 0
        for line in lines:
            record = json.loads(line)
            assert "type" in record
            assert "data" in record
            if record["type"] == "metadata":
                metadata_found = True
            elif record["type"] == "chunk":
                chunk_count += 1
            elif record["type"] == "relationship":
                relationship_count += 1
        assert metadata_found
        assert chunk_count > 0
        assert relationship_count > 0

    @classmethod
    def test_end_to_end_parquet_export(cls, sample_python_file, tmp_path):
        """Test complete Parquet export."""
        chunks = chunk_file(sample_python_file, "python")
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)
        orchestrator = StructuredExportOrchestrator()
        parquet_exporter = StructuredParquetExporter()
        orchestrator.register_exporter(ExportFormat.PARQUET, parquet_exporter)
        output_path = tmp_path / "export.parquet"
        orchestrator.export(chunks, relationships, output_path)
        chunks_file = tmp_path / "export_chunks.parquet"
        relationships_file = tmp_path / "export_relationships.parquet"
        assert chunks_file.exists()
        assert relationships_file.exists()
        chunks_table = read_parquet_table(chunks_file)
        assert len(chunks_table) > 0
        assert "chunk_id" in chunks_table.column_names
        assert "content" in chunks_table.column_names
        rel_table = read_parquet_table(relationships_file)
        assert len(rel_table) > 0
        assert "source_chunk_id" in rel_table.column_names
        assert "relationship_type" in rel_table.column_names

    @classmethod
    def test_end_to_end_graphml_export(cls, sample_python_file, tmp_path):
        """Test complete GraphML export."""
        chunks = chunk_file(sample_python_file, "python")
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)
        orchestrator = StructuredExportOrchestrator()
        graphml_exporter = GraphMLExporter()
        orchestrator.register_exporter(ExportFormat.GRAPHML, graphml_exporter)
        output_path = tmp_path / "export.graphml"
        orchestrator.export(chunks, relationships, output_path)
        assert output_path.exists()
        content = output_path.read_text()
        assert "<?xml" in content
        assert "<graphml" in content
        assert "<graph" in content
        assert "<node" in content
        assert "<edge" in content

    @classmethod
    def test_end_to_end_dot_export(cls, sample_javascript_file, tmp_path):
        """Test complete DOT export."""
        chunks = chunk_file(sample_javascript_file, "javascript")
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)
        orchestrator = StructuredExportOrchestrator()
        dot_exporter = DOTExporter()
        orchestrator.register_exporter(ExportFormat.DOT, dot_exporter)
        output_path = tmp_path / "export.dot"
        orchestrator.export(chunks, relationships, output_path)
        assert output_path.exists()
        content = output_path.read_text()
        assert "digraph CodeStructure" in content
        assert "->" in content
        assert "[label=" in content

    @classmethod
    def test_end_to_end_sqlite_export(cls, sample_python_file, tmp_path):
        """Test complete SQLite export."""
        chunks = chunk_file(sample_python_file, "python")
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)
        orchestrator = StructuredExportOrchestrator()
        sqlite_exporter = SQLiteExporter()
        orchestrator.register_exporter(ExportFormat.SQLITE, sqlite_exporter)
        output_path = tmp_path / "export.db"
        orchestrator.export(chunks, relationships, output_path)
        assert output_path.exists()
        conn = sqlite3.connect(str(output_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert "chunks" in tables
        assert "relationships" in tables
        cursor.execute("SELECT COUNT(*) FROM chunks")
        chunk_count = cursor.fetchone()[0]
        assert chunk_count > 0
        cursor.execute("SELECT COUNT(*) FROM relationships")
        rel_count = cursor.fetchone()[0]
        assert rel_count > 0
        conn.close()

    @classmethod
    def test_end_to_end_neo4j_export(cls, sample_python_file, tmp_path):
        """Test complete Neo4j Cypher export."""
        chunks = chunk_file(sample_python_file, "python")
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)
        orchestrator = StructuredExportOrchestrator()
        neo4j_exporter = Neo4jExporter()
        orchestrator.register_exporter(ExportFormat.NEO4J, neo4j_exporter)
        output_path = tmp_path / "export.cypher"
        orchestrator.export(chunks, relationships, output_path)
        assert output_path.exists()
        content = output_path.read_text()
        assert "CREATE CONSTRAINT" in content
        assert "CREATE INDEX" in content
        assert "MERGE (c:CodeChunk" in content
        assert "MERGE (source)-[r:" in content

    @classmethod
    def test_relationship_tracking_python(cls, sample_python_file):
        """Test relationship tracking for Python code."""
        chunks = chunk_file(sample_python_file, "python")
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)
        inheritance_rels = [
            r for r in relationships if r.relationship_type.value == "inherits"
        ]
        assert len(inheritance_rels) >= 2
        call_rels = [r for r in relationships if r.relationship_type.value == "calls"]
        assert len(call_rels) > 0

    @classmethod
    def test_relationship_tracking_javascript(cls, sample_javascript_file):
        """Test relationship tracking for JavaScript code."""
        chunks = chunk_file(sample_javascript_file, "javascript")
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)
        inheritance_rels = [
            r for r in relationships if r.relationship_type.value == "inherits"
        ]
        assert len(inheritance_rels) >= 2
        call_rels = [r for r in relationships if r.relationship_type.value == "calls"]
        assert len(call_rels) > 0

    @classmethod
    def test_streaming_export(cls, sample_python_file, tmp_path):
        """Test streaming export functionality."""
        chunks = chunk_file(sample_python_file, "python")
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)

        def chunk_iterator():
            yield from chunks

        def rel_iterator():
            yield from relationships

        orchestrator = StructuredExportOrchestrator()
        jsonl_exporter = StructuredJSONLExporter()
        orchestrator.register_exporter(ExportFormat.JSONL, jsonl_exporter)
        output_path = tmp_path / "streaming.jsonl"
        orchestrator.export_streaming(chunk_iterator(), rel_iterator(), output_path)
        assert output_path.exists()
        lines = output_path.read_text().strip().split("\n")
        assert len(lines) > 0
        first_record = json.loads(lines[0])
        assert first_record["type"] == "metadata"
        assert first_record["data"]["streaming"] is True


def parquet_chunk(chunk_id, language="python", file_path="sample.py"):
    return CodeChunk(
        chunk_id=chunk_id,
        language=language,
        file_path=file_path,
        node_type="function",
        start_line=1,
        end_line=1,
        byte_start=0,
        byte_end=4,
        parent_context="",
        content="π\r\n",
    )


def parquet_edge(source, target):
    return ChunkRelationship(source, target, RelationshipType.CALLS)


def partition_rows(root):
    rows = ds.dataset(root, format="parquet").to_table().to_pylist()
    return sorted((r["chunk_id"], r["file_path"], r["language"]) for r in rows)


def test_parquet_named_partition_roots_and_sidecars(tmp_path):
    orch = StructuredExportOrchestrator()
    orch.register_exporter(
        ExportFormat.PARQUET, StructuredParquetExporter(partition_by=["language"])
    )
    first = [
        parquet_chunk("first-py", file_path="first.py"),
        parquet_chunk("first-js", "javascript", "first.js"),
    ]
    second = [parquet_chunk("second", file_path="second.py")]
    orch.export(
        first, [parquet_edge("first-py", "first-js")], tmp_path / "first.parquet"
    )
    orch.export(second, [parquet_edge("second", "second")], tmp_path / "second.parquet")

    assert partition_rows(tmp_path / "first_chunks") == [
        ("first-js", "first.js", "javascript"),
        ("first-py", "first.py", "python"),
    ]
    assert partition_rows(tmp_path / "second_chunks") == [
        ("second", "second.py", "python")
    ]
    assert not (tmp_path / "language=python/data.parquet").exists()
    for name, source, target, files in [
        ("first", "first-py", "first-js", ["first.js", "first.py"]),
        ("second", "second", "second", ["second.py"]),
    ]:
        assert pq.read_table(
            tmp_path / f"{name}_relationships.parquet"
        ).to_pylist() == [
            {
                "source_chunk_id": source,
                "target_chunk_id": target,
                "relationship_type": "calls",
                "metadata": "",
            }
        ]
        (metadata,) = pq.read_table(tmp_path / f"{name}_metadata.parquet").to_pylist()
        assert sorted(metadata["source_files"]) == files
        assert metadata["chunk_count"] == len(files)

    orch.export(second, [], tmp_path / "first.parquet")
    assert partition_rows(tmp_path / "first_chunks") == [
        ("first-js", "first.js", "javascript"),
        ("second", "second.py", "python"),
    ]


def test_parquet_encoded_ordered_partition_values(tmp_path):
    exporter = StructuredParquetExporter(partition_by=["language", "file_path"])
    reports = tmp_path / "reports"
    sentinel = tmp_path / "data.parquet"
    sentinel.write_bytes(b"outside")
    exporter.export([parquet_chunk("other")], [], reports / "other.parquet")
    path = "src/../../c:\\π%/pkg.py."
    exporter.export(
        [parquet_chunk("encoded", file_path=path)], [], reports / "run.v1.parquet"
    )
    leaf = (
        reports
        / "run.v1_chunks/language=python/file_path=src%2F..%2F..%2Fc%3A%5C%CF%80%25%2Fpkg.py%2E/data.parquet"
    )
    with pq.ParquetFile(leaf) as reader:
        (row,) = reader.read().to_pylist()
        assert (row["chunk_id"], row["file_path"], row["content"]) == (
            "encoded",
            path,
            "π\r\n",
        )
    assert sentinel.read_bytes() == b"outside"
    assert partition_rows(reports / "other_chunks") == [
        ("other", "sample.py", "python")
    ]


def test_parquet_partition_collision_precedes_writes(tmp_path):
    exporter = StructuredParquetExporter(partition_by=["language", "file_path"])
    output = tmp_path / "collision.parquet"
    exporter.export([parquet_chunk("seed")], [], output)
    root = tmp_path / "collision_chunks"
    seeded = root / "language=python/file_path=sample.py/data.parquet"
    original = seeded.read_bytes()

    with pytest.raises(ChunkerError, match="collision"):
        exporter.export(
            [
                parquet_chunk("new", "ruby"),
                parquet_chunk("one"),
                parquet_chunk("two", "Python", "two.py"),
            ],
            [],
            output,
        )
    assert seeded.read_bytes() == original
    assert not (root / "language=ruby").exists()


@pytest.mark.parametrize(
    ("partition_by", "partitioned"),
    [(None, False), ([], False), (["unknown"], False), (["unknown", "language"], True)],
)
def test_parquet_batch_partition_selection(tmp_path, partition_by, partitioned):
    StructuredParquetExporter(partition_by=partition_by).export(
        [parquet_chunk("control")], [], tmp_path / "selection.parquet"
    )
    root = tmp_path / "selection_chunks"
    flat = tmp_path / "selection_chunks.parquet"
    assert root.is_dir() == partitioned
    assert flat.is_file() != partitioned
    with pq.ParquetFile(
        root / "language=python/data.parquet" if partitioned else flat
    ) as reader:
        (row,) = reader.read().to_pylist()
    assert (row["chunk_id"], row["content"]) == ("control", "π\r\n")


@pytest.mark.parametrize(
    ("seed", "chunk_ids", "edges"),
    [(False, [], []), (True, [], []), (True, ["new"], []), (True, [], [("x", "y")])],
)
def test_parquet_empty_stream_artifacts(tmp_path, seed, chunk_ids, edges):
    exporter = StructuredParquetExporter(partition_by=["language"])
    output = tmp_path / "stream.parquet"
    if seed:
        exporter.export_streaming(
            iter([parquet_chunk("old")]), iter([parquet_edge("old", "old")]), output
        )
    exporter.export_streaming(
        (parquet_chunk(i) for i in chunk_ids),
        (parquet_edge(a, b) for a, b in edges),
        output,
    )
    string, integer, strings = pa.string(), pa.int64(), pa.list_(pa.string())
    chunks_schema = pa.schema(
        [
            ("chunk_id", string, False),
            ("language", string, False),
            ("file_path", string, False),
            ("node_type", string, False),
            ("start_line", integer, False),
            ("end_line", integer, False),
            ("byte_start", integer, False),
            ("byte_end", integer, False),
            ("parent_context", string),
            ("content", string, False),
            ("parent_chunk_id", string),
            ("references", strings),
            ("dependencies", strings),
            ("lines_of_code", integer),
            ("byte_size", integer),
        ]
    )
    edges_schema = pa.schema(
        [
            ("source_chunk_id", string, False),
            ("target_chunk_id", string, False),
            ("relationship_type", string, False),
            ("metadata", string),
        ]
    )
    with pq.ParquetFile(tmp_path / "stream_chunks.parquet") as reader:
        assert reader.schema_arrow == chunks_schema
        assert reader.metadata.num_rows == len(chunk_ids)
        assert reader.read()["chunk_id"].to_pylist() == chunk_ids
    with pq.ParquetFile(tmp_path / "stream_relationships.parquet") as reader:
        assert reader.schema_arrow == edges_schema
        assert reader.metadata.num_rows == len(edges)
        assert [
            (r["source_chunk_id"], r["target_chunk_id"], r["relationship_type"])
            for r in reader.read().to_pylist()
        ] == [(a, b, "calls") for a, b in edges]
    assert not (tmp_path / "stream_chunks").exists()


def test_parquet_stream_batches_and_compression(tmp_path):
    class OneShot:
        def __init__(self, rows, file):
            self.rows = rows
            self.file = file
            self.used = False

        def __iter__(self):
            assert not self.used
            self.used = True
            for i, row in enumerate(self.rows):
                if i == 2:
                    assert self.file.exists()
                yield row

    chunks = tmp_path / "stream_chunks.parquet"
    edges = tmp_path / "stream_relationships.parquet"
    ids = ["one", "two", "three"]
    exporter = StructuredParquetExporter(compression="gzip", partition_by=["language"])
    exporter.set_batch_size(2)
    exporter.export_streaming(
        OneShot([parquet_chunk(i) for i in ids], chunks),
        OneShot([parquet_edge(i, i) for i in ids], edges),
        tmp_path / "stream.parquet",
    )
    for path, column in [(chunks, "chunk_id"), (edges, "source_chunk_id")]:
        with pq.ParquetFile(path) as reader:
            assert reader.read()[column].to_pylist() == ids
            groups = [
                reader.metadata.row_group(i) for i in range(reader.num_row_groups)
            ]
            assert [g.num_rows for g in groups] == [2, 1]
            assert all(g.column(0).compression == "GZIP" for g in groups)
        path.rename(path.with_suffix(".moved"))


@pytest.mark.parametrize(
    ("fail_kind", "count"),
    [("chunks", 0), ("chunks", 1), ("relationships", 1), ("relationships", 2)],
)
def test_parquet_stream_failure_preserves_completed_batches(tmp_path, fail_kind, count):
    path = tmp_path / "stream.parquet"
    chunks, edges = (
        tmp_path / "stream_chunks.parquet",
        tmp_path / "stream_relationships.parquet",
    )
    exporter = StructuredParquetExporter()
    exporter.set_batch_size(2)
    exporter.export_streaming(
        iter([parquet_chunk("old")]), iter([parquet_edge("old", "old")]), path
    )
    original_chunks, original_edges = chunks.read_bytes(), edges.read_bytes()

    def failing(row):
        for _ in range(count):
            yield row
        raise RuntimeError("broken source")

    with pytest.raises(RuntimeError, match="broken source") as caught:
        exporter.export_streaming(
            (
                failing(parquet_chunk("new"))
                if fail_kind == "chunks"
                else iter([parquet_chunk("new")])
            ),
            failing(parquet_edge("new", "target")),
            path,
        )
    assert caught.value.__traceback__ is not None
    if fail_kind == "chunks":
        assert chunks.read_bytes() == original_chunks
    else:
        assert pq.read_table(chunks)["chunk_id"].to_pylist() == ["new"]
    if count < 2:
        assert edges.read_bytes() == original_edges
    else:
        assert pq.read_table(edges)["source_chunk_id"].to_pylist() == ["new", "new"]
    edges.rename(tmp_path / "renamed.parquet")

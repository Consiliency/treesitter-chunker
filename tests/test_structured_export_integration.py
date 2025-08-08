"""Integration tests for structured export functionality."""

import json
import sqlite3

import pyarrow.parquet as pq
import pytest

from chunker.core import chunk_file
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
from chunker.interfaces.export import ExportFormat


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
        chunks_table = pq.read_table(chunks_file)
        assert len(chunks_table) > 0
        assert "chunk_id" in chunks_table.column_names
        assert "content" in chunks_table.column_names
        rel_table = pq.read_table(relationships_file)
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

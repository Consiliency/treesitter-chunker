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
        '''
class Animal:
    """Base animal class."""
    def __init__(self, name):
        self.name = name

    def speak(self):
        pass

class Dog(Animal):
    """Dog class inheriting from Animal."""
    def __init__(self, name, breed):
        super().__init__(name)
        self.breed = breed

    def speak(self):
        return f"{self.name} barks!"

    def play_fetch(self):
        return "Fetching the ball!"

class Cat(Animal):
    """Cat class inheriting from Animal."""
    def speak(self):
        return f"{self.name} meows!"

def create_pet(pet_type, name):
    """Factory function to create pets."""
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
''',
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

    def test_end_to_end_json_export(self, sample_python_file, tmp_path):
        """Test complete JSON export with relationships."""
        # Chunk the file
        chunks = chunk_file(sample_python_file, "python")

        # Track relationships
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)

        # Create orchestrator
        orchestrator = StructuredExportOrchestrator()
        json_exporter = StructuredJSONExporter(indent=2)
        orchestrator.register_exporter(ExportFormat.JSON, json_exporter)

        # Export
        output_path = tmp_path / "export.json"
        orchestrator.export(chunks, relationships, output_path)

        # Verify output
        assert output_path.exists()

        # Load and verify content
        data = json.loads(output_path.read_text())
        assert "metadata" in data
        assert "chunks" in data
        assert "relationships" in data

        # Verify chunks
        assert len(data["chunks"]) > 0

        # Extract class names from chunks
        class_chunks = [c for c in data["chunks"] if "class" in c["node_type"]]
        assert len(class_chunks) >= 3  # Should have Animal, Dog, Cat

        # Extract class names more carefully
        class_names = []
        for chunk in class_chunks:
            content = chunk["content"]
            # Find class definition line
            for line in content.split("\n"):
                if line.strip().startswith("class "):
                    name = line.split("class ")[1].split("(")[0].split(":")[0].strip()
                    class_names.append(name)
                    break

        assert "Animal" in class_names
        assert "Dog" in class_names
        assert "Cat" in class_names

        # Verify relationships
        assert len(data["relationships"]) > 0
        inheritance_rels = [
            r for r in data["relationships"] if r["relationship_type"] == "inherits"
        ]
        assert len(inheritance_rels) >= 2  # Dog and Cat inherit from Animal

    def test_end_to_end_jsonl_export(self, sample_javascript_file, tmp_path):
        """Test complete JSONL export with streaming."""
        # Chunk the file
        chunks = chunk_file(sample_javascript_file, "javascript")

        # Track relationships
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)

        # Create orchestrator
        orchestrator = StructuredExportOrchestrator()
        jsonl_exporter = StructuredJSONLExporter()
        orchestrator.register_exporter(ExportFormat.JSONL, jsonl_exporter)

        # Export
        output_path = tmp_path / "export.jsonl"
        orchestrator.export(chunks, relationships, output_path)

        # Verify output
        assert output_path.exists()

        # Read and verify JSONL
        lines = output_path.read_text().strip().split("\n")
        assert len(lines) > 0

        # Parse records
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

    def test_end_to_end_parquet_export(self, sample_python_file, tmp_path):
        """Test complete Parquet export."""
        # Chunk the file
        chunks = chunk_file(sample_python_file, "python")

        # Track relationships
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)

        # Create orchestrator
        orchestrator = StructuredExportOrchestrator()
        parquet_exporter = StructuredParquetExporter()
        orchestrator.register_exporter(ExportFormat.PARQUET, parquet_exporter)

        # Export
        output_path = tmp_path / "export.parquet"
        orchestrator.export(chunks, relationships, output_path)

        # Verify output files
        chunks_file = tmp_path / "export_chunks.parquet"
        relationships_file = tmp_path / "export_relationships.parquet"

        assert chunks_file.exists()
        assert relationships_file.exists()

        # Read and verify chunks
        chunks_table = pq.read_table(chunks_file)
        assert len(chunks_table) > 0
        assert "chunk_id" in chunks_table.column_names
        assert "content" in chunks_table.column_names

        # Read and verify relationships
        rel_table = pq.read_table(relationships_file)
        assert len(rel_table) > 0
        assert "source_chunk_id" in rel_table.column_names
        assert "relationship_type" in rel_table.column_names

    def test_end_to_end_graphml_export(self, sample_python_file, tmp_path):
        """Test complete GraphML export."""
        # Chunk the file
        chunks = chunk_file(sample_python_file, "python")

        # Track relationships
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)

        # Create orchestrator
        orchestrator = StructuredExportOrchestrator()
        graphml_exporter = GraphMLExporter()
        orchestrator.register_exporter(ExportFormat.GRAPHML, graphml_exporter)

        # Export
        output_path = tmp_path / "export.graphml"
        orchestrator.export(chunks, relationships, output_path)

        # Verify output
        assert output_path.exists()

        # Basic XML validation
        content = output_path.read_text()
        assert "<?xml" in content
        assert "<graphml" in content
        assert "<graph" in content
        assert "<node" in content
        assert "<edge" in content

    def test_end_to_end_dot_export(self, sample_javascript_file, tmp_path):
        """Test complete DOT export."""
        # Chunk the file
        chunks = chunk_file(sample_javascript_file, "javascript")

        # Track relationships
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)

        # Create orchestrator
        orchestrator = StructuredExportOrchestrator()
        dot_exporter = DOTExporter()
        orchestrator.register_exporter(ExportFormat.DOT, dot_exporter)

        # Export
        output_path = tmp_path / "export.dot"
        orchestrator.export(chunks, relationships, output_path)

        # Verify output
        assert output_path.exists()

        # Basic DOT validation
        content = output_path.read_text()
        assert "digraph CodeStructure" in content
        assert "->" in content  # Has edges
        assert "[label=" in content  # Has labels

    def test_end_to_end_sqlite_export(self, sample_python_file, tmp_path):
        """Test complete SQLite export."""
        # Chunk the file
        chunks = chunk_file(sample_python_file, "python")

        # Track relationships
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)

        # Create orchestrator
        orchestrator = StructuredExportOrchestrator()
        sqlite_exporter = SQLiteExporter()
        orchestrator.register_exporter(ExportFormat.SQLITE, sqlite_exporter)

        # Export
        output_path = tmp_path / "export.db"
        orchestrator.export(chunks, relationships, output_path)

        # Verify output
        assert output_path.exists()

        # Connect and verify database
        conn = sqlite3.connect(str(output_path))
        cursor = conn.cursor()

        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert "chunks" in tables
        assert "relationships" in tables

        # Check data
        cursor.execute("SELECT COUNT(*) FROM chunks")
        chunk_count = cursor.fetchone()[0]
        assert chunk_count > 0

        cursor.execute("SELECT COUNT(*) FROM relationships")
        rel_count = cursor.fetchone()[0]
        assert rel_count > 0

        conn.close()

    def test_end_to_end_neo4j_export(self, sample_python_file, tmp_path):
        """Test complete Neo4j Cypher export."""
        # Chunk the file
        chunks = chunk_file(sample_python_file, "python")

        # Track relationships
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)

        # Create orchestrator
        orchestrator = StructuredExportOrchestrator()
        neo4j_exporter = Neo4jExporter()
        orchestrator.register_exporter(ExportFormat.NEO4J, neo4j_exporter)

        # Export
        output_path = tmp_path / "export.cypher"
        orchestrator.export(chunks, relationships, output_path)

        # Verify output
        assert output_path.exists()

        # Basic Cypher validation
        content = output_path.read_text()
        assert "CREATE CONSTRAINT" in content
        assert "CREATE INDEX" in content
        assert "MERGE (c:CodeChunk" in content
        assert "MERGE (source)-[r:" in content

    def test_relationship_tracking_python(self, sample_python_file):
        """Test relationship tracking for Python code."""
        # Chunk the file
        chunks = chunk_file(sample_python_file, "python")

        # Track relationships
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)

        # Verify inheritance relationships
        inheritance_rels = [
            r for r in relationships if r.relationship_type.value == "inherits"
        ]
        assert len(inheritance_rels) >= 2

        # Verify call relationships
        call_rels = [r for r in relationships if r.relationship_type.value == "calls"]
        assert len(call_rels) > 0  # create_pet calls Dog/Cat constructors

    def test_relationship_tracking_javascript(self, sample_javascript_file):
        """Test relationship tracking for JavaScript code."""
        # Chunk the file
        chunks = chunk_file(sample_javascript_file, "javascript")

        # Track relationships
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)

        # Verify inheritance relationships
        inheritance_rels = [
            r for r in relationships if r.relationship_type.value == "inherits"
        ]
        assert len(inheritance_rels) >= 2  # Circle and Rectangle extend Shape

        # Verify call relationships
        call_rels = [r for r in relationships if r.relationship_type.value == "calls"]
        assert len(call_rels) > 0  # createShape calls constructors

    def test_streaming_export(self, sample_python_file, tmp_path):
        """Test streaming export functionality."""
        # Chunk the file
        chunks = chunk_file(sample_python_file, "python")

        # Track relationships
        tracker = ASTRelationshipTracker()
        relationships = tracker.infer_relationships(chunks)

        # Create iterators
        def chunk_iterator():
            yield from chunks

        def rel_iterator():
            yield from relationships

        # Test JSONL streaming
        orchestrator = StructuredExportOrchestrator()
        jsonl_exporter = StructuredJSONLExporter()
        orchestrator.register_exporter(ExportFormat.JSONL, jsonl_exporter)

        output_path = tmp_path / "streaming.jsonl"
        orchestrator.export_streaming(chunk_iterator(), rel_iterator(), output_path)

        assert output_path.exists()

        # Verify content
        lines = output_path.read_text().strip().split("\n")
        assert len(lines) > 0

        # First line should be metadata
        first_record = json.loads(lines[0])
        assert first_record["type"] == "metadata"
        assert first_record["data"]["streaming"] is True

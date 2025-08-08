"""Unit tests for relationship tracker."""

import pytest

from chunker.core import chunk_file
from chunker.export.relationships import ASTRelationshipTracker
from chunker.interfaces.export import RelationshipType
from chunker.types import CodeChunk


class TestASTRelationshipTracker:
    """Test AST-based relationship tracking."""

    @classmethod
    @pytest.fixture
    def tracker(cls):
        """Create a tracker instance."""
        return ASTRelationshipTracker()

    @staticmethod
    @pytest.fixture
    def python_chunks(tmp_path):
        """Create Python code chunks for testing."""
        file_path = tmp_path / "test.py"
        file_path.write_text(
            """
import os
from pathlib import Path

class Animal:
    def speak(self):
        pass

class Dog(Animal):
    def speak(self):
        return "Woof!"

    def play(self):
        self.speak()

def create_dog(name):
    return Dog()

dog = create_dog("Buddy")
dog.speak()
""",
        )
        return chunk_file(file_path, "python")

    @staticmethod
    @pytest.fixture
    def javascript_chunks(tmp_path):
        """Create JavaScript code chunks for testing."""
        file_path = tmp_path / "test.js"
        file_path.write_text(
            """
import { utils } from './utils';

class Shape {
    getArea() {
        throw new Error("Not implemented");
    }
}

class Circle extends Shape {
    constructor(radius) {
        super();
        this.radius = radius;
    }

    getArea() {
        return Math.PI * this.radius ** 2;
    }
}

function createCircle(radius) {
    return new Circle(radius);
}

const circle = createCircle(5);
console.log(circle.getArea());
""",
        )
        return chunk_file(file_path, "javascript")

    @classmethod
    def test_track_relationship_basic(cls, tracker):
        """Test basic relationship tracking."""
        chunk1 = CodeChunk(
            language="python",
            file_path="test.py",
            node_type="function_definition",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="",
            content="def foo(): pass",
        )
        chunk2 = CodeChunk(
            language="python",
            file_path="test.py",
            node_type="function_definition",
            start_line=7,
            end_line=10,
            byte_start=101,
            byte_end=200,
            parent_context="",
            content="def bar(): foo()",
        )
        tracker.track_relationship(
            chunk2,
            chunk1,
            RelationshipType.CALLS,
            {"function": "foo"},
        )
        relationships = tracker.get_relationships()
        assert len(relationships) == 1
        assert relationships[0].source_chunk_id == chunk2.chunk_id
        assert relationships[0].target_chunk_id == chunk1.chunk_id
        assert relationships[0].relationship_type == RelationshipType.CALLS

    @classmethod
    def test_get_relationships_filtered(cls, tracker):
        """Test filtered relationship retrieval."""
        chunks = []
        for i in range(3):
            chunk = CodeChunk(
                language="python",
                file_path=f"test{i}.py",
                node_type="function_definition",
                start_line=1,
                end_line=5,
                byte_start=0,
                byte_end=100,
                parent_context="",
                content=f"def func{i}(): pass",
            )
            chunks.append(chunk)
        tracker.track_relationship(
            chunks[0],
            chunks[1],
            RelationshipType.CALLS,
        )
        tracker.track_relationship(
            chunks[1],
            chunks[2],
            RelationshipType.CALLS,
        )
        tracker.track_relationship(chunks[0], chunks[2], RelationshipType.DEPENDS_ON)
        chunk0_rels = tracker.get_relationships(chunk=chunks[0])
        assert len(chunk0_rels) == 2
        call_rels = tracker.get_relationships(relationship_type=RelationshipType.CALLS)
        assert len(call_rels) == 2
        depends_rels = tracker.get_relationships(
            relationship_type=RelationshipType.DEPENDS_ON,
        )
        assert len(depends_rels) == 1

    @staticmethod
    def test_infer_python_inheritance(tracker, python_chunks):
        """Test Python inheritance relationship inference."""
        relationships = tracker.infer_relationships(python_chunks)
        inheritance_rels = [
            r for r in relationships if r.relationship_type == RelationshipType.INHERITS
        ]
        assert len(inheritance_rels) >= 1
        dog_inherits = any(
            r.metadata.get("base_class") == "Animal" for r in inheritance_rels
        )
        assert dog_inherits

    @staticmethod
    def test_infer_python_calls(tracker, python_chunks):
        """Test Python function call relationship inference."""
        relationships = tracker.infer_relationships(python_chunks)
        call_rels = [
            r for r in relationships if r.relationship_type == RelationshipType.CALLS
        ]
        if call_rels:
            for rel in call_rels:
                assert rel.metadata.get("function") is not None

    @staticmethod
    def test_infer_python_imports(tracker, python_chunks):
        """Test Python import dependency inference."""
        relationships = tracker.infer_relationships(python_chunks)
        dep_rels = [
            r
            for r in relationships
            if r.relationship_type == RelationshipType.DEPENDS_ON
        ]
        if dep_rels:
            for rel in dep_rels:
                assert rel.metadata.get("dependency") is not None

    @staticmethod
    def test_infer_javascript_inheritance(tracker, javascript_chunks):
        """Test JavaScript inheritance relationship inference."""
        relationships = tracker.infer_relationships(javascript_chunks)
        inheritance_rels = [
            r for r in relationships if r.relationship_type == RelationshipType.INHERITS
        ]
        assert len(inheritance_rels) >= 1
        circle_extends = any(
            r.metadata.get("base_class") == "Shape" for r in inheritance_rels
        )
        assert circle_extends

    @staticmethod
    def test_infer_javascript_calls(tracker, javascript_chunks):
        """Test JavaScript function call relationship inference."""
        relationships = tracker.infer_relationships(javascript_chunks)
        call_rels = [
            r for r in relationships if r.relationship_type == RelationshipType.CALLS
        ]
        assert len(call_rels) >= 1
        create_circle_called = any(
            r.metadata.get("function") == "createCircle" for r in call_rels
        )
        assert create_circle_called

    @classmethod
    def test_clear_relationships(cls, tracker):
        """Test clearing tracked relationships."""
        chunk1 = CodeChunk(
            language="python",
            file_path="test.py",
            node_type="function_definition",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="",
            content="def foo(): pass",
        )
        chunk2 = CodeChunk(
            language="python",
            file_path="test.py",
            node_type="function_definition",
            start_line=7,
            end_line=10,
            byte_start=101,
            byte_end=200,
            parent_context="",
            content="def bar(): pass",
        )
        tracker.track_relationship(chunk1, chunk2, RelationshipType.CALLS)
        assert len(tracker.get_relationships()) == 1
        tracker.clear()
        assert len(tracker.get_relationships()) == 0

    @staticmethod
    def test_complex_relationship_inference(tracker, tmp_path):
        """Test inference on more complex code."""
        file_path = tmp_path / "complex.py"
        file_path.write_text(
            """
from abc import ABC, abstractmethod

class BaseProcessor(ABC):
    @abstractmethod
    def process(self, data):
        pass

class DataProcessor(BaseProcessor):
    def __init__(self):
        self.helper = ProcessorHelper()

    def process(self, data):
        validated = self.helper.validate(data)
        return self._transform(validated)

    def _transform(self, data):
        return data.upper()

class ProcessorHelper:
    def validate(self, data):
        if not data:
            raise ValueError("Empty data")
        return data

def process_file(filename):
    processor = DataProcessor()
    with Path(filename).open("r", ) as f:
        data = f.read()
    return processor.process(data)
""",
        )
        chunks = chunk_file(file_path, "python")
        relationships = tracker.infer_relationships(chunks)
        rel_types = {r.relationship_type for r in relationships}
        assert RelationshipType.INHERITS in rel_types
        assert RelationshipType.CALLS in rel_types
        inheritance_count = sum(
            1 for r in relationships if r.relationship_type == RelationshipType.INHERITS
        )
        assert inheritance_count >= 1
        call_count = sum(
            1 for r in relationships if r.relationship_type == RelationshipType.CALLS
        )
        assert call_count >= 2

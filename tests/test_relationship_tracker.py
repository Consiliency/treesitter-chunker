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

    @staticmethod
    def test_cross_file_python_calls(tracker, tmp_path):
        """Test that function calls across files are detected."""
        # File 1: utility functions
        utils_file = tmp_path / "utils.py"
        utils_file.write_text(
            """
def helper_func(x):
    '''Helper function.'''
    return x * 2

def another_helper():
    '''Another helper.'''
    return 42
""",
            encoding="utf-8",
        )

        # File 2: main code that calls utilities
        main_file = tmp_path / "main.py"
        main_file.write_text(
            """
from utils import helper_func, another_helper

def main():
    '''Main function.'''
    result = helper_func(10)
    value = another_helper()
    return result + value

def process():
    '''Process function.'''
    return helper_func(5)
""",
            encoding="utf-8",
        )

        # Create chunks from both files
        utils_chunks = chunk_file(utils_file, "python")
        main_chunks = chunk_file(main_file, "python")
        all_chunks = utils_chunks + main_chunks

        # Infer relationships
        relationships = tracker.infer_relationships(all_chunks)

        # Verify cross-file calls are detected
        call_rels = [
            r for r in relationships if r.relationship_type == RelationshipType.CALLS
        ]

        # Should detect at least 3 cross-file calls:
        # main() -> helper_func(), main() -> another_helper(), process() -> helper_func()
        assert len(call_rels) >= 3, (
            f"Expected at least 3 cross-file calls, got {len(call_rels)}"
        )

        # Verify relationships span across files
        source_files = {
            tracker._chunk_index[r.source_chunk_id].file_path for r in call_rels
        }
        target_files = {
            tracker._chunk_index[r.target_chunk_id].file_path for r in call_rels
        }

        # Should have calls from main.py to utils.py
        assert str(main_file) in source_files
        assert str(utils_file) in target_files

    @staticmethod
    def test_cross_file_python_inheritance(tracker, tmp_path):
        """Test that class inheritance across files is detected."""
        # File 1: base classes
        base_file = tmp_path / "base.py"
        base_file.write_text(
            """
class Animal:
    '''Base animal class.'''
    def speak(self):
        pass

class Mammal(Animal):
    '''Mammal class.'''
    def breathe(self):
        pass
""",
            encoding="utf-8",
        )

        # File 2: derived classes
        derived_file = tmp_path / "derived.py"
        derived_file.write_text(
            """
from base import Animal, Mammal

class Dog(Mammal):
    '''Dog class inherits from Mammal.'''
    def speak(self):
        return 'Woof!'

class Cat(Animal):
    '''Cat class inherits from Animal.'''
    def speak(self):
        return 'Meow!'
""",
            encoding="utf-8",
        )

        # Create chunks from both files
        base_chunks = chunk_file(base_file, "python")
        derived_chunks = chunk_file(derived_file, "python")
        all_chunks = base_chunks + derived_chunks

        # Infer relationships
        relationships = tracker.infer_relationships(all_chunks)

        # Verify cross-file inheritance is detected
        inherit_rels = [
            r
            for r in relationships
            if r.relationship_type == RelationshipType.INHERITS
        ]

        # Should detect at least 3 inheritance relationships:
        # Mammal -> Animal (same file), Dog -> Mammal (cross-file), Cat -> Animal (cross-file)
        assert len(inherit_rels) >= 3, (
            f"Expected at least 3 inheritance relationships, got {len(inherit_rels)}"
        )

        # Verify at least one cross-file inheritance
        cross_file_inherit = [
            r
            for r in inherit_rels
            if tracker._chunk_index[r.source_chunk_id].file_path
            != tracker._chunk_index[r.target_chunk_id].file_path
        ]
        assert len(cross_file_inherit) >= 2, (
            f"Expected at least 2 cross-file inheritance relationships, "
            f"got {len(cross_file_inherit)}"
        )

    @staticmethod
    def test_cross_file_javascript_calls(tracker, tmp_path):
        """Test that JavaScript function calls across files are detected."""
        # File 1: utility functions
        utils_file = tmp_path / "utils.js"
        utils_file.write_text(
            """
function calculateSum(numbers) {
    return numbers.reduce((a, b) => a + b, 0);
}

function formatResult(value) {
    return `Result: ${value}`;
}
""",
            encoding="utf-8",
        )

        # File 2: main code
        main_file = tmp_path / "main.js"
        main_file.write_text(
            """
import { calculateSum, formatResult } from './utils.js';

function processData(data) {
    const sum = calculateSum(data);
    return formatResult(sum);
}

function analyze(values) {
    return calculateSum(values);
}
""",
            encoding="utf-8",
        )

        # Create chunks from both files
        utils_chunks = chunk_file(utils_file, "javascript")
        main_chunks = chunk_file(main_file, "javascript")
        all_chunks = utils_chunks + main_chunks

        # Infer relationships
        relationships = tracker.infer_relationships(all_chunks)

        # Verify cross-file calls are detected
        call_rels = [
            r for r in relationships if r.relationship_type == RelationshipType.CALLS
        ]

        # Should detect at least 3 cross-file calls:
        # processData() -> calculateSum(), processData() -> formatResult(),
        # analyze() -> calculateSum()
        assert len(call_rels) >= 3, (
            f"Expected at least 3 cross-file calls, got {len(call_rels)}"
        )

        # Verify relationships span across files
        cross_file_calls = [
            r
            for r in call_rels
            if tracker._chunk_index[r.source_chunk_id].file_path
            != tracker._chunk_index[r.target_chunk_id].file_path
        ]
        assert len(cross_file_calls) >= 2, (
            f"Expected at least 2 cross-file calls, got {len(cross_file_calls)}"
        )

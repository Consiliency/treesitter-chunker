"""Tests for SemanticLensExporter."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from chunker.export.formats.semantic_lens import (
    EDGE_KIND_MAP,
    NODE_KIND_MAP,
    SemanticLensExporter,
)
from chunker.interfaces.export import (
    ChunkRelationship,
    ExportFormat,
    RelationshipType,
)
from chunker.types import CodeChunk


@pytest.fixture
def sample_chunks() -> list[CodeChunk]:
    """Create sample chunks for testing."""
    return [
        CodeChunk(
            language="typescript",
            file_path="src/user.ts",
            node_type="class_definition",
            start_line=1,
            end_line=50,
            byte_start=0,
            byte_end=1000,
            parent_context="UserService",
            content="class UserService { ... }",
            qualified_route=["module:user", "class_definition:UserService"],
            metadata={"visibility": "public"},
        ),
        CodeChunk(
            language="typescript",
            file_path="src/user.ts",
            node_type="method_definition",
            start_line=10,
            end_line=20,
            byte_start=100,
            byte_end=300,
            parent_context="UserService.getUser",
            content="async getUser(id: string) { ... }",
            qualified_route=[
                "module:user",
                "class_definition:UserService",
                "method_definition:getUser",
            ],
            metadata={"visibility": "public", "signature": "(id: string) => Promise<User>"},
        ),
    ]


@pytest.fixture
def sample_relationships(sample_chunks: list[CodeChunk]) -> list[ChunkRelationship]:
    """Create sample relationships for testing."""
    return [
        ChunkRelationship(
            source_chunk_id=sample_chunks[0].chunk_id,
            target_chunk_id=sample_chunks[1].chunk_id,
            relationship_type=RelationshipType.DEFINES,
            metadata={"confidence": 1.0},
        ),
        ChunkRelationship(
            source_chunk_id=sample_chunks[1].chunk_id,
            target_chunk_id=sample_chunks[0].chunk_id,
            relationship_type=RelationshipType.CALLS,
            metadata=None,
        ),
    ]


class TestSemanticLensExporter:
    """Tests for SemanticLensExporter class."""

    def test_supports_format(self):
        """Test format support check."""
        assert SemanticLensExporter.supports_format(ExportFormat.SEMANTIC_LENS)
        assert not SemanticLensExporter.supports_format(ExportFormat.JSON)
        assert not SemanticLensExporter.supports_format(ExportFormat.GRAPHML)

    def test_get_schema(self):
        """Test schema retrieval."""
        exporter = SemanticLensExporter()
        schema = exporter.get_schema()

        assert schema["format"] == "semantic_lens"
        assert schema["version"] == "v1.0"
        assert "structure" in schema
        assert "nodes" in schema["structure"]
        assert "edges" in schema["structure"]

    def test_export_basic(self, sample_chunks, sample_relationships):
        """Test basic export to stream."""
        exporter = SemanticLensExporter()
        output = io.StringIO()

        exporter.export(sample_chunks, sample_relationships, output)

        output.seek(0)
        bundle = json.load(output)

        assert bundle["version"] == "v1.0"
        assert "generated_at" in bundle
        assert bundle["generated_at"].endswith("Z")
        assert len(bundle["nodes"]) == 2
        assert len(bundle["edges"]) >= 1
        assert "annotations" in bundle
        assert "patterns" in bundle
        assert bundle["patterns"] == []

    def test_export_to_file(self, sample_chunks, sample_relationships, tmp_path):
        """Test export to file path."""
        exporter = SemanticLensExporter()
        output_file = tmp_path / "output.slb"

        exporter.export(sample_chunks, sample_relationships, output_file)

        assert output_file.exists()
        bundle = json.loads(output_file.read_text())
        assert bundle["version"] == "v1.0"

    def test_node_mapping(self, sample_chunks):
        """Test chunk to node conversion."""
        exporter = SemanticLensExporter()
        output = io.StringIO()

        exporter.export(sample_chunks, [], output)

        output.seek(0)
        bundle = json.load(output)

        # Check class node
        class_node = next(n for n in bundle["nodes"] if n["kind"] == "class")
        assert class_node["name"] == "UserService"
        assert class_node["language"] == "typescript"
        assert class_node["file"] == "src/user.ts"
        assert class_node["visibility"] == "public"
        assert len(class_node["node_id"]) >= 8

        # Check method node
        method_node = next(n for n in bundle["nodes"] if n["kind"] == "method")
        assert method_node["name"] == "getUser"
        assert method_node["signature"] == "(id: string) => Promise<User>"

    def test_edge_mapping(self, sample_chunks, sample_relationships):
        """Test relationship to edge conversion."""
        exporter = SemanticLensExporter()
        output = io.StringIO()

        exporter.export(sample_chunks, sample_relationships, output)

        output.seek(0)
        bundle = json.load(output)

        edges = bundle["edges"]
        edge_kinds = {e["kind"] for e in edges}

        assert "defines" in edge_kinds or "calls" in edge_kinds
        for edge in edges:
            assert len(edge["edge_id"]) >= 8
            assert 0.0 <= edge["confidence"] <= 1.0
            assert "chunker" in edge["evidence"]

    def test_all_node_kinds_mapped(self):
        """Verify all mapped node types produce valid kinds."""
        for node_type, kind in NODE_KIND_MAP.items():
            assert kind in (
                "module", "class", "interface", "trait",
                "function", "method", "field", "property",
            ), f"Invalid kind '{kind}' for node_type '{node_type}'"

    def test_all_edge_kinds_mapped(self):
        """Verify all mapped relationship types produce valid kinds."""
        for rel_type, kind in EDGE_KIND_MAP.items():
            assert kind in (
                "defines", "imports", "calls", "inherits",
                "implements", "uses", "reads", "writes", "throws",
            ), f"Invalid kind '{kind}' for relationship '{rel_type}'"

    def test_repo_metadata(self, sample_chunks):
        """Test repository metadata inclusion."""
        exporter = SemanticLensExporter(
            repo_url="https://github.com/example/project",
            repo_commit="abc1234",
            repo_branch="main",
        )
        output = io.StringIO()

        exporter.export(sample_chunks, [], output)

        output.seek(0)
        bundle = json.load(output)

        assert bundle["repo"]["url"] == "https://github.com/example/project"
        assert bundle["repo"]["commit"] == "abc1234"
        assert bundle["repo"]["branch"] == "main"

    def test_export_streaming(self, sample_chunks, sample_relationships):
        """Test streaming export (collects all due to JSON structure)."""
        exporter = SemanticLensExporter()
        output = io.StringIO()

        exporter.export_streaming(
            iter(sample_chunks),
            iter(sample_relationships),
            output,
        )

        output.seek(0)
        bundle = json.load(output)
        assert len(bundle["nodes"]) == 2

    def test_compact_output(self, sample_chunks):
        """Test compact (no indent) output."""
        exporter = SemanticLensExporter(indent=None)
        output = io.StringIO()

        exporter.export(sample_chunks, [], output)

        output.seek(0)
        content = output.read()
        assert "\n" not in content.strip()

    def test_empty_export(self):
        """Test export with no chunks or relationships."""
        exporter = SemanticLensExporter()
        output = io.StringIO()

        exporter.export([], [], output)

        output.seek(0)
        bundle = json.load(output)

        assert bundle["nodes"] == []
        assert bundle["edges"] == []
        assert bundle["patterns"] == []

    def test_unknown_node_type_skipped(self):
        """Test that unknown node types are skipped."""
        chunk = CodeChunk(
            language="typescript",
            file_path="src/test.ts",
            node_type="comment",  # Not in NODE_KIND_MAP
            start_line=1,
            end_line=1,
            byte_start=0,
            byte_end=50,
            parent_context="",
            content="// comment",
        )
        exporter = SemanticLensExporter()
        output = io.StringIO()

        exporter.export([chunk], [], output)

        output.seek(0)
        bundle = json.load(output)
        assert bundle["nodes"] == []

    def test_annotations_created(self, sample_chunks):
        """Test that annotations are created from metadata."""
        exporter = SemanticLensExporter()
        output = io.StringIO()

        exporter.export(sample_chunks, [], output)

        output.seek(0)
        bundle = json.load(output)

        assert len(bundle["annotations"]) > 0
        for annotation in bundle["annotations"]:
            assert "target_id" in annotation
            assert "tags" in annotation

    def test_unicode_handling(self):
        """Test handling of Unicode in content and names."""
        chunk = CodeChunk(
            language="typescript",
            file_path="src/emoji.ts",
            node_type="function_definition",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="getUserName",
            content='function getUserName() { return "名前"; }',
            qualified_route=["function_definition:getUserName"],
        )
        exporter = SemanticLensExporter()
        output = io.StringIO()

        exporter.export([chunk], [], output)

        output.seek(0)
        bundle = json.load(output)

        assert len(bundle["nodes"]) == 1
        assert bundle["nodes"][0]["name"] == "getUserName"

    def test_span_format(self, sample_chunks):
        """Test that span is exported as [byte_start, byte_end] array."""
        exporter = SemanticLensExporter()
        output = io.StringIO()

        exporter.export(sample_chunks, [], output)

        output.seek(0)
        bundle = json.load(output)

        for node in bundle["nodes"]:
            assert isinstance(node["span"], list)
            assert len(node["span"]) == 2
            assert isinstance(node["span"][0], int)
            assert isinstance(node["span"][1], int)

    def test_route_format(self, sample_chunks):
        """Test that route is joined with :: separator."""
        exporter = SemanticLensExporter()
        output = io.StringIO()

        exporter.export(sample_chunks, [], output)

        output.seek(0)
        bundle = json.load(output)

        class_node = next(n for n in bundle["nodes"] if n["kind"] == "class")
        assert "::" in class_node["route"]
        assert class_node["route"] == "module:user::class_definition:UserService"

    def test_name_extraction_from_qualified_route(self):
        """Test name extraction when qualified_route has type:name format."""
        chunk = CodeChunk(
            language="typescript",
            file_path="src/test.ts",
            node_type="function_definition",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="",
            content="function myFunc() {}",
            qualified_route=["function_definition:myFunc"],
        )
        exporter = SemanticLensExporter()
        output = io.StringIO()

        exporter.export([chunk], [], output)

        output.seek(0)
        bundle = json.load(output)

        assert bundle["nodes"][0]["name"] == "myFunc"

    def test_name_extraction_fallback_to_parent_context(self):
        """Test name extraction fallback to parent_context."""
        chunk = CodeChunk(
            language="typescript",
            file_path="src/test.ts",
            node_type="function_definition",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="module.myFunction",
            content="function myFunction() {}",
            qualified_route=[],
        )
        exporter = SemanticLensExporter()
        output = io.StringIO()

        exporter.export([chunk], [], output)

        output.seek(0)
        bundle = json.load(output)

        assert bundle["nodes"][0]["name"] == "myFunction"

    def test_visibility_unknown_default(self):
        """Test that missing visibility defaults to unknown."""
        chunk = CodeChunk(
            language="typescript",
            file_path="src/test.ts",
            node_type="function_definition",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="myFunc",
            content="function myFunc() {}",
            metadata={},  # No visibility
        )
        exporter = SemanticLensExporter()
        output = io.StringIO()

        exporter.export([chunk], [], output)

        output.seek(0)
        bundle = json.load(output)

        assert bundle["nodes"][0]["visibility"] == "unknown"

    def test_edge_confidence_from_metadata(self):
        """Test that edge confidence is extracted from relationship metadata."""
        chunk1 = CodeChunk(
            language="typescript",
            file_path="src/a.ts",
            node_type="function_definition",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="funcA",
            content="function funcA() {}",
        )
        chunk2 = CodeChunk(
            language="typescript",
            file_path="src/b.ts",
            node_type="function_definition",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="funcB",
            content="function funcB() {}",
        )
        rel = ChunkRelationship(
            source_chunk_id=chunk1.chunk_id,
            target_chunk_id=chunk2.chunk_id,
            relationship_type=RelationshipType.CALLS,
            metadata={"confidence": 0.85},
        )

        exporter = SemanticLensExporter()
        output = io.StringIO()

        exporter.export([chunk1, chunk2], [rel], output)

        output.seek(0)
        bundle = json.load(output)

        assert len(bundle["edges"]) == 1
        assert bundle["edges"][0]["confidence"] == 0.85

    def test_include_content_annotation(self):
        """Test that content_lines is added when include_content=True."""
        chunk = CodeChunk(
            language="typescript",
            file_path="src/test.ts",
            node_type="function_definition",
            start_line=1,
            end_line=10,
            byte_start=0,
            byte_end=200,
            parent_context="myFunc",
            content="function myFunc() {\n  // many lines\n}",
        )
        exporter = SemanticLensExporter(include_content=True)
        output = io.StringIO()

        exporter.export([chunk], [], output)

        output.seek(0)
        bundle = json.load(output)

        annotation = bundle["annotations"][0]
        assert "kv" in annotation
        assert annotation["kv"]["content_lines"] == 10  # end_line - start_line + 1

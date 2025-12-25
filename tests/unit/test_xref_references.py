"""Tests for REQ-TSC-008: Reconcile dependencies vs references for REFERENCES edges."""

import pytest
from chunker.types import CodeChunk
from chunker.graph.xref import build_xref


def make_chunk(
    node_id: str,
    name: str,
    references: list[str] | None = None,
    dependencies: list[str] | None = None,
    metadata: dict | None = None,
) -> CodeChunk:
    """Create a minimal CodeChunk for testing."""
    return CodeChunk(
        language="python",
        file_path="test.py",
        node_type="function_definition",
        start_line=1,
        end_line=10,
        byte_start=0,
        byte_end=100,
        parent_context="",
        content=f"def {name}(): pass",
        node_id=node_id,
        chunk_id=node_id,
        references=references or [],
        dependencies=dependencies or [],
        metadata=metadata or {"signature": {"name": name}},
    )


class TestXrefReferences:
    """Test REFERENCES edge creation from various sources."""

    def test_references_from_direct_attribute(self):
        """REFERENCES edges should be created from chunk.references attribute."""
        source = make_chunk("src", "caller", references=["target_func"])
        target = make_chunk("tgt", "target_func")

        nodes, edges = build_xref([source, target])

        refs = [e for e in edges if e["type"] == "REFERENCES"]
        assert len(refs) == 1
        assert refs[0]["src"] == "src"
        assert refs[0]["dst"] == "tgt"

    def test_references_from_dependencies_attribute(self):
        """REFERENCES edges should be created from chunk.dependencies attribute (REQ-TSC-008)."""
        source = make_chunk("src", "caller", dependencies=["target_func"])
        target = make_chunk("tgt", "target_func")

        nodes, edges = build_xref([source, target])

        refs = [e for e in edges if e["type"] == "REFERENCES"]
        assert len(refs) == 1, "dependencies should produce REFERENCES edges"
        assert refs[0]["src"] == "src"
        assert refs[0]["dst"] == "tgt"

    def test_references_from_metadata_references(self):
        """REFERENCES edges should work with legacy metadata['references']."""
        source = make_chunk(
            "src",
            "caller",
            metadata={"signature": {"name": "caller"}, "references": ["target_func"]},
        )
        target = make_chunk("tgt", "target_func")

        nodes, edges = build_xref([source, target])

        refs = [e for e in edges if e["type"] == "REFERENCES"]
        assert len(refs) == 1
        assert refs[0]["src"] == "src"
        assert refs[0]["dst"] == "tgt"

    def test_references_from_metadata_dependencies(self):
        """REFERENCES edges should work with legacy metadata['dependencies']."""
        source = make_chunk(
            "src",
            "caller",
            metadata={
                "signature": {"name": "caller"},
                "dependencies": ["target_func"],
            },
        )
        target = make_chunk("tgt", "target_func")

        nodes, edges = build_xref([source, target])

        refs = [e for e in edges if e["type"] == "REFERENCES"]
        assert len(refs) == 1
        assert refs[0]["src"] == "src"
        assert refs[0]["dst"] == "tgt"

    def test_references_deduplicated(self):
        """Same reference from multiple sources should not create duplicate edges."""
        source = make_chunk(
            "src",
            "caller",
            references=["target_func"],
            dependencies=["target_func"],
            metadata={
                "signature": {"name": "caller"},
                "references": ["target_func"],
                "dependencies": ["target_func"],
            },
        )
        target = make_chunk("tgt", "target_func")

        nodes, edges = build_xref([source, target])

        refs = [e for e in edges if e["type"] == "REFERENCES"]
        # Should still create edge (dedup happens at identifier collection, not edge creation)
        # But since it's the same target, we expect one edge
        assert len(refs) == 1

    def test_combined_sources(self):
        """REFERENCES from multiple sources should all create edges."""
        source = make_chunk(
            "src",
            "caller",
            references=["func_a"],
            dependencies=["func_b"],
        )
        target_a = make_chunk("tgt_a", "func_a")
        target_b = make_chunk("tgt_b", "func_b")

        nodes, edges = build_xref([source, target_a, target_b])

        refs = [e for e in edges if e["type"] == "REFERENCES"]
        assert len(refs) == 2
        targets = {e["dst"] for e in refs}
        assert targets == {"tgt_a", "tgt_b"}

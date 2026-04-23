from pathlib import Path

from chunker.boundary import SemanticEdge, dumps_boundary_ir, extract_boundary_ir


class _DuplicateResolver:
    supported_languages = ("python",)

    def __init__(self, resolver_id: str, confidence: float):
        self.resolver_id = resolver_id
        self.resolver_version = "0.1.0"
        self.confidence = confidence

    def enrich(self, context):
        source = context.nodes[0]["id"]
        target = context.nodes[-1]["id"]
        return (
            SemanticEdge(
                source_node_id=source,
                target_node_id=target,
                relationship_type="calls",
                resolution="resolved",
                reference="semantic_call",
                confidence=self.confidence,
                resolver_id=self.resolver_id,
                resolver_version=self.resolver_version,
            ),
        )


def test_semantic_output_is_byte_identical_across_double_run(tmp_path: Path):
    (tmp_path / "app.py").write_text(
        "def a():\n    return 1\n\ndef b():\n    return a()\n",
        encoding="utf-8",
    )
    resolvers = (
        _DuplicateResolver("tests.z", 0.4),
        _DuplicateResolver("tests.a", 0.8),
    )

    first = dumps_boundary_ir(
        extract_boundary_ir(tmp_path, "python", semantic_resolvers=resolvers)
    )
    second = dumps_boundary_ir(
        extract_boundary_ir(
            tmp_path, "python", semantic_resolvers=tuple(reversed(resolvers))
        )
    )

    assert first == second


def test_semantic_dedup_keeps_highest_confidence(tmp_path: Path):
    (tmp_path / "app.py").write_text(
        "def a():\n    return 1\n\ndef b():\n    return a()\n",
        encoding="utf-8",
    )

    ir = extract_boundary_ir(
        tmp_path,
        "python",
        semantic_resolvers=(
            _DuplicateResolver("tests.same", 0.4),
            _DuplicateResolver("tests.same", 0.9),
        ),
    )
    semantic_edges = [
        edge for edge in ir["edges"] if edge["provenance"]["source"] == "semantic"
    ]

    assert len(semantic_edges) == 1
    assert semantic_edges[0]["provenance"]["confidence"] == 0.9

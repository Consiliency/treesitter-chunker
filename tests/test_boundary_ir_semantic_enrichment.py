import json
from pathlib import Path

import pytest

from chunker.boundary import (
    BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION,
    SEMANTIC_RESOLVER_API_VERSION,
    SemanticEdge,
    dumps_boundary_ir,
    extract_boundary_ir,
)


class _FakeResolver:
    resolver_id = "tests.fake"
    resolver_version = "0.1.0"
    supported_languages = ("python",)

    def __init__(self, confidence: float = 0.9):
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
                candidates=(target,),
                confidence=self.confidence,
                resolver_id=self.resolver_id,
                resolver_version=self.resolver_version,
                metadata={"reason": "test"},
            ),
        )


class _FailingResolver:
    resolver_id = "tests.fail"
    resolver_version = "0.1.0"
    supported_languages = ("python",)

    def enrich(self, context):
        raise RuntimeError("semantic boom")


def _write_repo(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        """def helper():
    return 1

def service():
    return helper()
""",
        encoding="utf-8",
    )


def test_syntax_only_output_is_byte_identical_with_default_semantics(tmp_path: Path):
    _write_repo(tmp_path)

    default = dumps_boundary_ir(extract_boundary_ir(tmp_path, "python"))
    explicit = dumps_boundary_ir(
        extract_boundary_ir(tmp_path, "python", semantic_resolvers=None)
    )

    assert default == explicit


def test_semantic_resolver_adds_supplemental_edge(tmp_path: Path):
    _write_repo(tmp_path)

    ir = extract_boundary_ir(
        tmp_path,
        "python",
        semantic_resolvers=(_FakeResolver(),),
    )
    semantic_edges = [
        edge for edge in ir["edges"] if edge["provenance"]["source"] == "semantic"
    ]

    assert ir["schema_version"] == BOUNDARY_IR_SEMANTIC_SCHEMA_VERSION
    assert len(semantic_edges) == 1
    assert semantic_edges[0]["provenance"] == {
        "confidence": 0.9,
        "resolver": "tests.fake",
        "resolver_api_version": SEMANTIC_RESOLVER_API_VERSION,
        "resolver_version": "0.1.0",
        "source": "semantic",
    }
    assert "enforcement_grade" not in semantic_edges[0]["provenance"]


def test_syntax_edges_remain_unchanged_when_semantic_edges_are_added(tmp_path: Path):
    _write_repo(tmp_path)

    baseline = extract_boundary_ir(tmp_path, "python")
    enriched = extract_boundary_ir(
        tmp_path,
        "python",
        semantic_resolvers=(_FakeResolver(),),
    )

    enriched_syntax_edges = [
        edge for edge in enriched["edges"] if edge["provenance"]["source"] == "syntax"
    ]
    assert enriched_syntax_edges == baseline["edges"]


def test_semantic_min_confidence_filters_without_mutating_syntax(tmp_path: Path):
    _write_repo(tmp_path)

    baseline = extract_boundary_ir(tmp_path, "python")
    enriched = extract_boundary_ir(
        tmp_path,
        "python",
        semantic_resolvers=(_FakeResolver(confidence=0.2),),
        semantic_min_confidence=0.5,
    )

    assert [
        edge for edge in enriched["edges"] if edge["provenance"]["source"] == "semantic"
    ] == []
    assert [
        edge for edge in enriched["edges"] if edge["provenance"]["source"] == "syntax"
    ] == baseline["edges"]


def test_semantic_resolver_errors_are_diagnostics_without_fail_fast(tmp_path: Path):
    _write_repo(tmp_path)

    ir = extract_boundary_ir(
        tmp_path,
        "python",
        semantic_resolvers=(_FailingResolver(),),
    )

    diagnostics = [
        diagnostic
        for diagnostic in ir["diagnostics"]
        if diagnostic["code"] == "boundary.semantic_resolver_error"
    ]
    assert len(diagnostics) == 1
    assert diagnostics[0]["stage"] == "semantic"
    assert diagnostics[0]["details"]["resolver"] == "tests.fail"


def test_semantic_resolver_errors_raise_with_fail_fast(tmp_path: Path):
    _write_repo(tmp_path)

    with pytest.raises(RuntimeError, match="semantic boom"):
        extract_boundary_ir(
            tmp_path,
            "python",
            fail_fast=True,
            semantic_resolvers=(_FailingResolver(),),
        )


def test_incremental_semantic_cache_key_payload_includes_resolver_fingerprint(
    tmp_path: Path,
):
    cache_dir = tmp_path / ".boundary-cache"
    _write_repo(tmp_path)

    syntax_ir = extract_boundary_ir(
        tmp_path, "python", incremental=True, cache_dir=cache_dir
    )
    semantic_ir = extract_boundary_ir(
        tmp_path,
        "python",
        incremental=True,
        cache_dir=cache_dir,
        semantic_resolvers=(_FakeResolver(),),
    )
    records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in cache_dir.glob("boundary_v1_*.json")
    ]
    semantic_payloads = [
        record["key_payload"]
        for record in records
        if record["key_payload"].get("semantic_schema_version")
    ]

    assert dumps_boundary_ir(syntax_ir) != dumps_boundary_ir(semantic_ir)
    assert semantic_payloads
    assert semantic_payloads[0]["semantic_resolvers"][0]["resolver_id"] == "tests.fake"

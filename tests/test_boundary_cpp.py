"""Boundary IR extraction tests for the C++ object-oriented surface.

These tests pin the fix for a C++ extraction defect surfaced by the parity
engine: C++ had no ``CppConfig`` registered, so the chunker fell back to the
generic default chunk types and emitted only ``function_definition`` chunks --
classes, structs, namespaces, and in-class members were silently dropped.

Assertions cover emitted *kinds*, *symbols*, and *qualified names* -- not just
chunk counts -- because the kind/symbol mapping is the thing that regressed.
"""

from __future__ import annotations

import collections

from chunker.boundary import (
    canonicalize_for_parity,
    extract_boundary_ir,
    parity_digest,
)


def _nodes_by_kind(nodes: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = collections.defaultdict(list)
    for node in nodes:
        grouped[node["kind"]].append(node)
    return grouped


def _symbols(nodes: list[dict], kind: str) -> set[str | None]:
    return {node.get("symbol") for node in nodes if node["kind"] == kind}


def _qualified_names(nodes: list[dict], kind: str) -> set[str | None]:
    return {node.get("qualified_name") for node in nodes if node["kind"] == kind}


class TestCppBoundary:
    """C++ now emits class/struct/namespace/method/field boundaries."""

    @staticmethod
    def test_class_with_inline_and_out_of_line_methods(tmp_path):
        src = tmp_path / "gateway.cpp"
        src.write_text(
            "class Gateway { public: void send(); int count(); };\n"
            "void Gateway::send(){}\n",
        )
        nodes = extract_boundary_ir(str(src), "cpp")["nodes"]
        kinds = collections.Counter(node["kind"] for node in nodes)
        # The class_specifier is emitted (previously dropped) ...
        assert kinds["class"] == 1
        assert _symbols(nodes, "class") == {"Gateway"}
        # ... and the in-class member declarations resolve to `method`, not the
        # bare `function` the generic fallback produced.
        assert kinds["method"] >= 2
        assert {"send", "count"} <= _symbols(nodes, "method")
        # In-class methods carry the class-qualified name.
        assert {"Gateway.send", "Gateway.count"} <= _qualified_names(nodes, "method")
        # The out-of-line definition resolves to `method` (not `function`).
        assert kinds.get("function", 0) == 0

    @staticmethod
    def test_namespace_struct_and_fields(tmp_path):
        src = tmp_path / "net.cpp"
        src.write_text(
            "namespace net {\n"
            "class Gateway {\n"
            "public:\n"
            "    void send();\n"
            "    int total;\n"
            "    int* buffer;\n"
            "};\n"
            "struct Packet { int len; };\n"
            "}\n",
        )
        nodes = extract_boundary_ir(str(src), "cpp")["nodes"]
        by_kind = _nodes_by_kind(nodes)
        # namespace -> module (the repo's module-equivalent kind).
        assert _symbols(nodes, "module") == {"net"}
        # struct_specifier -> struct.
        assert _symbols(nodes, "struct") == {"Packet"}
        assert _qualified_names(nodes, "struct") == {"net.Packet"}
        # class nested in the namespace carries the namespace-qualified name.
        assert _qualified_names(nodes, "class") == {"net.Gateway"}
        # Data members (incl. pointer members) keep their own names and stay
        # `field_declaration` (matching how Java emits fields), not `method`.
        field_symbols = _symbols(nodes, "field_declaration")
        assert {"total", "buffer", "len"} <= field_symbols
        # The method keeps `method` kind and is namespace+class qualified.
        assert "net.Gateway.send" in _qualified_names(nodes, "method")
        assert by_kind  # sanity: something was emitted

    @staticmethod
    def test_cpp_extraction_is_deterministic_and_path_independent(tmp_path):
        body = "namespace a { class B { public: void f(); int g; }; }\n"
        first = tmp_path / "one" / "x.cpp"
        first.parent.mkdir()
        first.write_text(body)
        second = tmp_path / "two" / "x.cpp"
        second.parent.mkdir()
        second.write_text(body)

        def digest(path) -> str:
            doc = extract_boundary_ir(str(path), "cpp")
            return parity_digest(canonicalize_for_parity(doc))

        assert digest(first) == digest(first)  # byte-reproducible
        assert digest(first) == digest(second)  # absolute-path independent

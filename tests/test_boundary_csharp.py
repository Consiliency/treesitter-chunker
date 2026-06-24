"""Boundary IR extraction tests for the C# surface.

These tests pin the fix for a C# extraction defect surfaced by the parity
engine: ``CSharpConfig`` was complete, but C# emitted *nothing*. The C# grammar
that tree-sitter-language-pack 0.9.0 pulls transitively is
``tree-sitter-c-sharp==0.23.1``, built against tree-sitter ABI 15; the pinned
``tree_sitter==0.24`` core caps at ABI 14, so the grammar failed to load
("Incompatible Language version 15. Must be between 13 and 14"), the error was
swallowed, and the chunker produced ``{}``. The fix pins the ABI-14
``tree-sitter-c-sharp==0.23.0`` via a ``[tool.uv] override-dependencies`` entry
(additive: only C# changes).

A second defect is also pinned here: ``EXTENSION_MAP`` maps ``.cs`` -> ``csharp``
while the registry's ``language_id`` is ``c_sharp``, so passing the ``c_sharp``
alias collected zero files. Language aliases are now canonicalized so both
``csharp`` and ``c_sharp`` resolve to the same files and hash identically.

Assertions cover emitted *kinds*, *symbols*, and *qualified names* -- not just
chunk counts -- because the kind/symbol mapping is the thing that regressed.
"""

from __future__ import annotations

import collections

from chunker.boundary import (
    canonicalize_for_parity,
    dumps_boundary_ir,
    extract_boundary_ir,
    parity_digest,
)

# A namespace + class (with field, method, property) + enum -- the full surface
# named in the exit criteria.
SAMPLE = (
    "namespace MyApp.Core\n"
    "{\n"
    "    public enum Status { Active, Inactive }\n"
    "\n"
    "    public class Widget\n"
    "    {\n"
    "        private int _count;\n"
    "\n"
    "        public int Increment(int by)\n"
    "        {\n"
    "            _count += by;\n"
    "            return _count;\n"
    "        }\n"
    "\n"
    "        public string Name { get; set; }\n"
    "    }\n"
    "}\n"
)


def _symbols(nodes: list[dict], kind: str) -> set[str | None]:
    return {node.get("symbol") for node in nodes if node["kind"] == kind}


def _qualified_names(nodes: list[dict], kind: str) -> set[str | None]:
    return {node.get("qualified_name") for node in nodes if node["kind"] == kind}


class TestCSharpBoundary:
    """C# now emits namespace/class/method/field/enum/property boundaries."""

    @staticmethod
    def test_namespace_class_enum_method_field_property(tmp_path):
        src = tmp_path / "Sample.cs"
        src.write_text(SAMPLE)
        nodes = extract_boundary_ir(str(src), "csharp")["nodes"]
        kinds = collections.Counter(node["kind"] for node in nodes)

        # The namespace surfaces as `module` (the repo's namespace-equivalent
        # kind), matching how C++ emits namespace_definition.
        assert kinds["module"] == 1
        assert _symbols(nodes, "module") == {"MyApp.Core"}

        # The class is emitted and namespace-qualified.
        assert kinds["class"] == 1
        assert _symbols(nodes, "class") == {"Widget"}
        assert _qualified_names(nodes, "class") == {"MyApp.Core.Widget"}

        # The enum is emitted and namespace-qualified.
        assert kinds["enum"] == 1
        assert _symbols(nodes, "enum") == {"Status"}
        assert _qualified_names(nodes, "enum") == {"MyApp.Core.Status"}

        # The method resolves to `method` and carries the class-qualified name.
        assert kinds["method"] == 1
        assert _symbols(nodes, "method") == {"Increment"}
        assert "MyApp.Core.Widget.Increment" in _qualified_names(nodes, "method")

        # Fields stay `field_declaration` (matching how Java/C++ emit fields).
        assert kinds["field_declaration"] == 1

        # Properties stay `property_declaration` and carry the class-qualified name.
        assert kinds["property_declaration"] == 1
        assert "MyApp.Core.Widget.Name" in _qualified_names(
            nodes, "property_declaration"
        )

    @staticmethod
    def test_file_scoped_namespace(tmp_path):
        src = tmp_path / "FileScoped.cs"
        src.write_text(
            "namespace MyApp.Tools;\n"
            "public class Helper {\n"
            "    public void Run() {}\n"
            "}\n"
        )
        nodes = extract_boundary_ir(str(src), "csharp")["nodes"]
        # The C# 10 file-scoped namespace form also surfaces as `module`.
        assert _symbols(nodes, "module") == {"MyApp.Tools"}
        assert _symbols(nodes, "class") == {"Helper"}

    @staticmethod
    def test_csharp_and_c_sharp_aliases_hash_identically(tmp_path):
        src = tmp_path / "Sample.cs"
        src.write_text(SAMPLE)

        def canonical_bytes(language: str) -> str:
            doc = extract_boundary_ir(str(src), language)
            return dumps_boundary_ir(canonicalize_for_parity(doc))

        # The `c_sharp` alias (registry language_id) and `csharp` (EXTENSION_MAP
        # value + display name) must collect the same files and produce a
        # byte-identical canonical IR.
        assert canonical_bytes("csharp") == canonical_bytes("c_sharp")
        # And both emit the full boundary set (not the previous empty result).
        assert len(extract_boundary_ir(str(src), "c_sharp")["nodes"]) == 6

    @staticmethod
    def test_csharp_extraction_is_deterministic_and_path_independent(tmp_path):
        first = tmp_path / "one" / "x.cs"
        first.parent.mkdir()
        first.write_text(SAMPLE)
        second = tmp_path / "two" / "x.cs"
        second.parent.mkdir()
        second.write_text(SAMPLE)

        def digest(path) -> str:
            doc = extract_boundary_ir(str(path), "csharp")
            return parity_digest(canonicalize_for_parity(doc))

        assert digest(first) == digest(first)  # byte-reproducible
        assert digest(first) == digest(second)  # absolute-path independent

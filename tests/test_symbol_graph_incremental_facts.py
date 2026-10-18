import unicodedata
from pathlib import Path

from chunker.types import CodeChunk
from chunker.symbol_graph import (
    assemble_symbol_graph,
    collect_source_files,
    extract_symbol_facts_for_file,
    extract_symbol_graph,
)


def _assert_496_sources_match_files(graph: dict, symbol_name: str) -> None:
    symbols = {
        symbol_id: symbol
        for symbol_id, symbol in graph["symbol_lookup"].items()
        if symbol["name"] == symbol_name
    }
    assert len(symbols) == 2
    assert len(set(symbols)) == 2
    assert all(
        symbol["definition_id"] in symbol_id for symbol_id, symbol in symbols.items()
    )
    assert graph["relationships"]
    for relationship in graph["relationships"]:
        assert relationship["from"] in graph["symbol_lookup"]
        source = graph["symbol_lookup"][relationship["from"]]
        assert source["file"] == relationship["file"]


def test_symbol_facts_include_reusable_file_fields(tmp_path: Path):
    source = tmp_path / "service.py"
    source.write_text(
        """def run():
    import os
    return os.getcwd()
""",
        encoding="utf-8",
    )

    facts = extract_symbol_facts_for_file(source, tmp_path, "python")

    assert facts["display_file"] == "service.py"
    assert facts["path"] == "service.py"
    assert facts["module"] == "service"
    assert facts["language"] == "python"
    assert facts["symbol_lookup"]
    assert facts["import_strings"]
    assert facts["chunk_records"]
    assert facts["errors"] == []


def test_assemble_symbol_facts_matches_extract_symbol_graph(tmp_path: Path):
    (tmp_path / "helper.py").write_text(
        "class Helper:\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "service.py").write_text(
        """from helper import Helper

def build():
    return Helper()
""",
        encoding="utf-8",
    )

    facts = [
        extract_symbol_facts_for_file(path, tmp_path, "python")
        for path in collect_source_files(tmp_path, "python")
    ]

    assembled = assemble_symbol_graph(
        facts,
        total_files=2,
        resolution_mode="permissive",
    )
    direct = extract_symbol_graph(tmp_path, "python", resolution_mode="permissive")

    assert assembled == direct


def test_assemble_symbol_graph_preserves_sorted_resolution_candidates(tmp_path: Path):
    (tmp_path / "a.py").write_text("def target():\n    return 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def target():\n    return 2\n", encoding="utf-8")
    (tmp_path / "use.py").write_text(
        "def caller():\n    return target()\n",
        encoding="utf-8",
    )

    graph = extract_symbol_graph(tmp_path, "python", resolution_mode="strict")
    ambiguous = [
        rel for rel in graph["relationships"] if rel["resolution"] == "ambiguous"
    ]

    assert ambiguous
    assert all(rel["candidates"] == sorted(rel["candidates"]) for rel in ambiguous)


def test_496_anchor_module_and_package_definitions_survive(tmp_path: Path):
    package = tmp_path / "pkg"
    package.mkdir()
    (tmp_path / "pkg.py").write_text(
        "def run():\n    return sorted([])\n", encoding="utf-8"
    )
    (package / "__init__.py").write_text(
        "import time\ndef run():\n    return time.time()\n", encoding="utf-8"
    )

    graph = extract_symbol_graph(tmp_path, "python")

    _assert_496_sources_match_files(graph, "run")
    call_files = {
        (relationship["reference"], relationship["file"])
        for relationship in graph["relationships"]
        if relationship["type"] == "calls"
    }
    assert call_files == {("sorted", "pkg.py"), ("time", "pkg/__init__.py")}


def test_496_anchor_typescript_and_tsx_definitions_survive(tmp_path: Path):
    (tmp_path / "x.ts").write_text(
        "export function f() { return g(); }\n", encoding="utf-8"
    )
    (tmp_path / "x.tsx").write_text(
        "export function f() { return k(); }\n", encoding="utf-8"
    )

    graph = extract_symbol_graph(tmp_path)

    _assert_496_sources_match_files(graph, "f")
    assert {
        (relationship["reference"], relationship["file"])
        for relationship in graph["relationships"]
        if relationship["type"] == "calls"
    } == {("g", "x.ts"), ("k", "x.tsx")}


def test_496_anchor_identical_python_calls_survive_reversed_fact_order(
    tmp_path: Path,
):
    package = tmp_path / "pkg"
    package.mkdir()
    source = "def run():\n    return sorted([])\n"
    (tmp_path / "pkg.py").write_text(source, encoding="utf-8")
    (package / "__init__.py").write_text(source, encoding="utf-8")
    paths = [tmp_path / "pkg.py", package / "__init__.py"]
    facts = [extract_symbol_facts_for_file(path, tmp_path, "python") for path in paths]

    graphs = (
        assemble_symbol_graph(facts, total_files=2),
        assemble_symbol_graph(list(reversed(facts)), total_files=2),
    )

    for graph in graphs:
        _assert_496_sources_match_files(graph, "run")
        calls = {
            (relationship["from"], relationship["reference"], relationship["file"])
            for relationship in graph["relationships"]
            if relationship["type"] == "calls"
        }
        assert len(calls) == 2
        assert {(reference, file) for _, reference, file in calls} == {
            ("sorted", "pkg.py"),
            ("sorted", "pkg/__init__.py"),
        }
    assert graphs[0]["symbol_lookup"] == graphs[1]["symbol_lookup"]
    assert {
        (item["from"], item["to"], item["type"], item["reference"], item["file"])
        for item in graphs[0]["relationships"]
    } == {
        (item["from"], item["to"], item["type"], item["reference"], item["file"])
        for item in graphs[1]["relationships"]
    }


def test_496_anchor_identical_typescript_and_tsx_calls_survive(tmp_path: Path):
    source = "export function f() { return shared(); }\n"
    (tmp_path / "x.ts").write_text(source, encoding="utf-8")
    (tmp_path / "x.tsx").write_text(source, encoding="utf-8")

    graph = extract_symbol_graph(tmp_path)

    _assert_496_sources_match_files(graph, "f")
    calls = [
        relationship
        for relationship in graph["relationships"]
        if relationship["type"] == "calls" and relationship["reference"] == "shared"
    ]
    assert len(calls) == 2
    assert {relationship["file"] for relationship in calls} == {"x.ts", "x.tsx"}


def test_496_anchor_dotted_directory_and_file_definitions_survive(tmp_path: Path):
    nested = tmp_path / "src" / "api"
    nested.mkdir(parents=True)
    (nested / "client.ts").write_text(
        "export function send() { return nestedCall(); }\n", encoding="utf-8"
    )
    (tmp_path / "src" / "api.client.ts").write_text(
        "export function send() { return dottedCall(); }\n", encoding="utf-8"
    )

    graph = extract_symbol_graph(tmp_path, "typescript")

    _assert_496_sources_match_files(graph, "send")
    assert {
        (relationship["reference"], relationship["file"])
        for relationship in graph["relationships"]
        if relationship["type"] == "calls"
    } == {
        ("nestedCall", "src/api/client.ts"),
        ("dottedCall", "src/api.client.ts"),
    }


def test_496_anchor_nfd_module_and_package_paths_are_preserved(tmp_path: Path):
    module = unicodedata.normalize("NFD", "café")
    package = tmp_path / module
    package.mkdir()
    source = "def serve():\n    return sorted([])\n"
    (tmp_path / f"{module}.py").write_text(source, encoding="utf-8")
    (package / "__init__.py").write_text(source, encoding="utf-8")

    graph = extract_symbol_graph(tmp_path, "python")

    _assert_496_sources_match_files(graph, "serve")
    expected_paths = {f"{module}.py", f"{module}/__init__.py"}
    assert {
        relationship["file"]
        for relationship in graph["relationships"]
        if relationship["type"] == "calls"
    } == expected_paths
    assert all(unicodedata.is_normalized("NFD", path) for path in expected_paths)


def test_496_anchor_occurrence_counts_chunks_before_graph_filter(
    tmp_path: Path, monkeypatch
):
    source = tmp_path / "sample.py"
    source.write_text("def keep():\n    pass\n", encoding="utf-8")

    def chunk(metadata: dict, node_id: str) -> CodeChunk:
        value = CodeChunk(
            language="python",
            file_path="sample.py",
            node_type="function_definition",
            start_line=1,
            end_line=2,
            byte_start=0,
            byte_end=20,
            parent_context="",
            content="def keep():\n    pass\n",
            node_id=node_id,
            metadata=metadata,
        )
        value.definition_id = "shared-definition"
        return value

    chunks = [
        chunk(
            {"symbol": "filtered", "kind": "variable", "qualified_name": "filtered"},
            "node-filtered",
        ),
        chunk(
            {"symbol": "keep", "kind": "function", "qualified_name": "keep"},
            "node-keep",
        ),
    ]
    monkeypatch.setattr(
        "chunker.symbol_graph.chunk_file", lambda *args, **kwargs: chunks
    )

    facts = extract_symbol_facts_for_file(source, tmp_path, "python")

    assert list(facts["symbol_lookup"]) == ["shared-definition#1"]


def test_496_anchor_unrelated_callee_does_not_change_caller_source(tmp_path: Path):
    caller_path = tmp_path / "caller.py"
    caller_path.write_text(
        "def caller():\n    return target()\n",
        encoding="utf-8",
    )
    first = extract_symbol_graph(tmp_path, "python")
    first_source = next(
        relationship["from"]
        for relationship in first["relationships"]
        if relationship["reference"] == "target"
    )

    (tmp_path / "unrelated.py").write_text(
        "def target():\n    return 1\n",
        encoding="utf-8",
    )
    second = extract_symbol_graph(tmp_path, "python")
    second_edge = next(
        relationship
        for relationship in second["relationships"]
        if relationship["file"] == "caller.py" and relationship["reference"] == "target"
    )

    assert second_edge["from"] == first_source
    assert second["symbol_lookup"][first_source]["file"] == "caller.py"


def test_496_anchor_nfd_path_uses_canonical_definition_identity(tmp_path: Path):
    source = tmp_path / "cafe\u0301.py"
    source.write_text(
        "def serve():\n    return missing()\n",
        encoding="utf-8",
    )

    graph = extract_symbol_graph(source, "python")
    symbol_id, symbol = next(iter(graph["symbol_lookup"].items()))
    relationship = next(
        item for item in graph["relationships"] if item["reference"] == "missing"
    )

    assert symbol["file"] == source.name
    assert symbol_id == symbol["definition_id"]
    assert relationship["from"] == symbol_id
    assert relationship["file"] == source.name

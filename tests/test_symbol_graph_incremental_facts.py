from pathlib import Path

from chunker.symbol_graph import (
    assemble_symbol_graph,
    collect_source_files,
    extract_symbol_facts_for_file,
    extract_symbol_graph,
)


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

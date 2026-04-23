from pathlib import Path
from textwrap import dedent

from chunker.symbol_graph import extract_symbol_graph


def _calls_to(result: dict, reference: str) -> list[dict]:
    return [
        rel
        for rel in result["relationships"]
        if rel["type"] == "calls" and rel["reference"] == reference
    ]


def test_unqualified_duplicate_call_is_ambiguous_with_sorted_candidates(
    tmp_path: Path,
):
    (tmp_path / "alpha.py").write_text(
        "def helper():\n    return 'alpha'\n",
        encoding="utf-8",
    )
    (tmp_path / "beta.py").write_text(
        "def helper():\n    return 'beta'\n",
        encoding="utf-8",
    )
    (tmp_path / "service.py").write_text(
        "def use_helper():\n    return helper()\n",
        encoding="utf-8",
    )

    result = extract_symbol_graph(tmp_path, "python")
    relationships = _calls_to(result, "helper")

    assert len(relationships) == 1
    relationship = relationships[0]
    assert relationship["resolution"] == "ambiguous"
    assert relationship["to"] == "helper"
    assert relationship["is_internal"] is False
    assert relationship["candidates"] == sorted(relationship["candidates"])
    assert len(relationship["candidates"]) == 2
    assert relationship["resolution_mode"] == "permissive"
    assert relationship["provenance"]["source"] == "syntax"


def test_missing_call_is_unresolved_and_preserves_reference(tmp_path: Path):
    (tmp_path / "service.py").write_text(
        "def use_missing():\n    return missing_call()\n",
        encoding="utf-8",
    )

    result = extract_symbol_graph(tmp_path, "python", resolution_mode="strict")
    relationships = _calls_to(result, "missing_call")

    assert len(relationships) == 1
    relationship = relationships[0]
    assert relationship["resolution"] == "unresolved"
    assert relationship["to"] == "missing_call"
    assert relationship["is_internal"] is False
    assert relationship["candidates"] == []
    assert relationship["resolution_mode"] == "strict"


def test_unique_call_remains_resolved_and_legacy_internal(tmp_path: Path):
    source = dedent(
        """\
        def helper():
            return 'ok'

        def use_helper():
            return helper()
        """
    )
    (tmp_path / "service.py").write_text(source, encoding="utf-8")

    result = extract_symbol_graph(tmp_path, "python")
    relationships = _calls_to(result, "helper")

    assert len(relationships) == 1
    relationship = relationships[0]
    assert relationship["resolution"] == "resolved"
    assert relationship["to"] != "helper"
    assert relationship["is_internal"] is True
    assert relationship["candidates"] == [relationship["to"]]

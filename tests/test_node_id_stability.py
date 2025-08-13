from pathlib import Path

from chunker.core import chunk_file


def _first_chunk_id(path: Path, language: str) -> str:
    chunks = chunk_file(str(path), language)
    assert chunks, "expected at least one chunk"
    return chunks[0].node_id


def test_node_id_stable_across_runs_same_content(tmp_path):
    code = """
def foo(x):
    return x + 1
""".lstrip()
    p = tmp_path / "a.py"
    p.write_text(code, encoding="utf-8")
    id1 = _first_chunk_id(p, "python")
    id2 = _first_chunk_id(p, "python")
    assert id1 == id2


def test_node_id_changes_on_path_change(tmp_path):
    code = """
def bar():
    return 42
""".lstrip()
    p1 = tmp_path / "m1.py"
    p2 = tmp_path / "nested" / "m1.py"
    p1.write_text(code, encoding="utf-8")
    p2.parent.mkdir(parents=True, exist_ok=True)
    p2.write_text(code, encoding="utf-8")
    id1 = _first_chunk_id(p1, "python")
    id2 = _first_chunk_id(p2, "python")
    assert id1 != id2

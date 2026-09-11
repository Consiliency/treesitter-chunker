from chunker.incremental import DefaultIncrementalProcessor
from chunker.interfaces.incremental import ChangeType
from chunker.types import CodeChunk


def _chunk(
    content: str, *, definition_id: str, file_path: str = "src/example.py"
) -> CodeChunk:
    return CodeChunk(
        language="python",
        file_path=file_path,
        node_type="function_definition",
        start_line=1,
        end_line=2,
        byte_start=0,
        byte_end=len(content.encode("utf-8")),
        parent_context="",
        content=content,
        qualified_route=["function_definition:example"],
        definition_id=definition_id,
    )


def test_content_diff_reparses_with_path_and_definition_identity(monkeypatch):
    old = _chunk("def example():\n    return 1\n", definition_id="definition")
    seen = {}

    def reparse(content, language, file_path):
        seen.update(content=content, language=language, file_path=file_path)
        return [_chunk(content, definition_id="definition", file_path=file_path)]

    monkeypatch.setattr("chunker.incremental.chunk_text", reparse)
    diff = DefaultIncrementalProcessor().compute_diff(
        [old],
        "def example():\n    return 2\n",
        "python",
    )

    assert seen["file_path"] == "src/example.py"
    assert diff.summary["modified"] == 1
    assert diff.summary["added"] == diff.summary["deleted"] == 0
    assert diff.changes[0].change_type is ChangeType.MODIFIED


def test_overload_diff_preserves_every_definition():
    from chunker import chunk_text

    source = "class A { int foo(int a) { return 1; } int foo(String a) { return 2; } int foo(int a, int b) { return 3; } }"
    old = chunk_text(source, "java", file_path="A.java")
    new = chunk_text(source.replace("return 2", "return 4"), "java", file_path="A.java")
    processor = DefaultIncrementalProcessor()
    processor.store_chunks("A.java", old)
    diff = processor.compute_diff("A.java", new)
    assert len(old) == len(new) == 4
    assert sum(diff.summary[k] for k in ("added", "modified", "unchanged")) == len(new)
    assert {c.chunk_id for c in processor.update_chunks(old, diff)} == {
        c.chunk_id for c in new
    }
    content_diff = processor.compute_diff(
        old, source.replace("return 2", "return 4"), "java"
    )
    assert {c.chunk_id for c in processor.update_chunks(old, content_diff)} == {
        c.chunk_id for c in new
    }


def test_update_body_edit_removes_previous_occurrence():
    from chunker import chunk_text

    old = chunk_text("def f():\n    return 1\n", "python", file_path="a.py")
    new = chunk_text("def f():\n    return 2\n", "python", file_path="a.py")
    processor = DefaultIncrementalProcessor()
    processor.store_chunks("a.py", old)
    updated = processor.update_chunks(old, processor.compute_diff("a.py", new))
    assert [c.chunk_id for c in updated] == [c.chunk_id for c in new]


def test_update_refreshes_unchanged_chunk_positions():
    from chunker import chunk_text

    source = "def f():\n    return 1\n\ndef g():\n    return 2\n"
    old = chunk_text(source, "python", file_path="a.py")
    new = chunk_text(
        source.replace("return 1", "return 10000"), "python", file_path="a.py"
    )
    processor = DefaultIncrementalProcessor()
    processor.store_chunks("a.py", old)
    diff = processor.compute_diff("a.py", new)
    assert diff.summary["unchanged"] == 1
    updated = processor.update_chunks(old, diff)
    assert [c.chunk_id for c in updated] == [c.chunk_id for c in new]
    assert [c.byte_start for c in updated] == [c.byte_start for c in new]


def test_multiline_overload_deletion_and_relocation_reconstructs_new_file():
    from chunker import chunk_text

    old_source = (
        "class A {\n"
        "  int foo(int a) { return 1; }\n"
        "  int foo(long a) { return 1; }\n"
        "}\n"
    )
    new_source = "class A {\n\n\n  int foo(int a) { return 1; }\n}\n"
    old = chunk_text(old_source, "java", file_path="A.java")
    new = chunk_text(new_source, "java", file_path="A.java")
    processor = DefaultIncrementalProcessor()
    for previous in (old, list(reversed(old))):
        diff = processor.compute_diff(previous, new_source, "java")
        updated = processor.update_chunks(previous, diff)
        assert len(updated) == len(new) == 2
        assert updated == new
        assert diff.summary["moved"] == 0
        assert sum(
            diff.summary[k] for k in ("added", "modified", "moved", "unchanged")
        ) == len(new)
        assert sum(
            diff.summary[k] for k in ("deleted", "modified", "moved", "unchanged")
        ) == len(old)


def test_move_detection_never_reuses_a_target():
    from chunker import chunk_text

    old = chunk_text(
        "def foo():\n    return 1\n\ndef bar():\n    return 1\n",
        "python",
        file_path="a.py",
    )
    new = chunk_text("\n\n\n\n\ndef baz():\n    return 1\n", "python", file_path="a.py")
    matches = DefaultIncrementalProcessor.detect_moved_chunks(old, new)
    assert len(matches) == 1
    assert len({after.chunk_id for _, after in matches}) == len(matches)


def test_duplicate_python_definition_reduction_and_relocation():
    from chunker import chunk_text

    body = "def f():\n    return 1\n"
    old = chunk_text(body + "\n" + body, "python", file_path="a.py")
    new_source = "\n" + body
    expected = chunk_text(new_source, "python", file_path="a.py")
    processor = DefaultIncrementalProcessor()
    diff = processor.compute_diff(old, new_source, "python")
    assert processor.update_chunks(old, diff) == expected
    assert diff.summary["moved"] == 0
    assert diff.summary["deleted"] == 2
    assert diff.summary["added"] == 1

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

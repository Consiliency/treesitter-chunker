"""Physical UTF-8 span and identity contracts for file-backed chunkers."""

import pytest
import tiktoken

from chunker.chunker import chunk_file_with_token_limit
from chunker.core import chunk_file
from chunker.repo.processor import GitAwareRepoProcessor
from chunker.vfs import InMemoryFileSystem, LocalFileSystem
from chunker.vfs_chunker import VFSChunker


def assert_definitions(chunks, core, source, expected):
    for chunk, reference, literal in zip(chunks, core, expected, strict=True):
        start = source.index(literal)
        assert (chunk.byte_start, chunk.byte_end) == (start, start + len(literal))
        assert (
            source[chunk.byte_start : chunk.byte_end]
            == chunk.content.encode()
            == literal
        )
        assert chunk.node_id == reference.node_id
        assert chunk.parent_chunk_id == reference.parent_chunk_id


@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
def test_token_file_offsets(tmp_path, newline):
    path = tmp_path / "a.py"
    body = b"def f():" + newline + b"    return 1"
    path.write_bytes(b"# comment" + newline + body + newline)
    assert_definitions(
        chunk_file_with_token_limit(path, "python", 100),
        chunk_file(path, "python"),
        path.read_bytes(),
        [body],
    )


@pytest.mark.parametrize(
    "reader", ["token", "vfs", "stream", "memory", "batch", "iterator"]
)
def test_nested_reader_offsets(tmp_path, reader):
    path = tmp_path / "pkg" / "a.py"
    path.parent.mkdir()
    method = "def f(self):\r\n        return 'é'".encode()
    outer = b"class A:\n    " + method
    path.write_bytes("# préface\r\n".encode() + outer)
    source = path.read_bytes()
    identity = "pkg/a.py"
    if reader == "token":
        identity = str(path)
        chunks = chunk_file_with_token_limit(path, "python", 100)
    elif reader in {"vfs", "stream", "memory"}:
        if reader == "memory":
            vfs = InMemoryFileSystem()
            identity = "virtual/member.py"
            vfs.add_file(identity, source, is_text=False)
        else:
            vfs = LocalFileSystem(tmp_path)
        chunks = list(
            VFSChunker(vfs).chunk_file(identity, "python", streaming=reader == "stream")
        )
    else:
        proc = GitAwareRepoProcessor(show_progress=False, max_workers=1)
        if reader == "batch":
            (result,) = proc.process_repository(
                str(tmp_path), incremental=False
            ).file_results
        else:
            (result,) = proc.process_files_iterator(str(tmp_path))
        assert result.file_path == identity
        chunks = result.chunks
        assert all(c.metadata["file_path"] == identity for c in chunks)
    core = chunk_file(path, "python", identity_path=identity)
    assert_definitions(chunks, core, source, [outer, method])
    assert chunks[1].parent_chunk_id == chunks[0].chunk_id


def test_token_file_split_offsets(tmp_path):
    path = tmp_path / "split.py"
    lines = [
        b"def f():",
        "    # café".encode(),
        b"    apple = 1",
        b"    berry = 2",
        b"    return apple + berry",
    ]
    path.write_bytes(b"# head\r\n" + b"\r\n".join(lines) + b"\r\n")
    source = path.read_bytes()
    (parent,) = chunk_file(path, "python")
    parts = chunk_file_with_token_limit(path, "python", 10)
    assert len(parts) > 1
    previous_end = parent.byte_start
    encoding = tiktoken.get_encoding("cl100k_base")
    for part in parts:
        content = part.content.encode()
        start = source.index(content)
        assert previous_end <= start < part.byte_end <= parent.byte_end
        assert (part.byte_start, part.byte_end) == (start, start + len(content))
        assert source[part.byte_start : part.byte_end] == content
        assert part.parent_chunk_id == parent.chunk_id
        assert part.metadata["token_count"] == len(encoding.encode(part.content)) <= 10
        previous_end = part.byte_end
    for line in lines:
        assert sum(part.content.count(line.decode()) for part in parts) == 1


@pytest.mark.parametrize("streaming", [False, True])
def test_vfs_span_ends_inside_crlf(tmp_path, streaming):
    path = tmp_path / "a.py"
    body = b"def f():\r\n    return 1 # tail\r"
    path.write_bytes(b"# head\r\n" + body + b"\n")
    chunks = VFSChunker(LocalFileSystem(tmp_path)).chunk_file(
        path.name, "python", streaming=streaming
    )
    assert_definitions(
        chunks,
        chunk_file(path, "python", identity_path=path.name),
        path.read_bytes(),
        [body],
    )


@pytest.mark.parametrize("reader", ["token", "batch", "iterator", "memory", "vfs"])
def test_invalid_utf8_reader_policy(tmp_path, reader):
    path = tmp_path / "a.py"
    prefix = b"# \xff\r\n"
    function = b"def f():\r\n    return '\xff'"
    path.write_bytes(prefix + function + b"\r\n")
    if reader in {"vfs", "memory"}:
        if reader == "memory":
            vfs = InMemoryFileSystem()
            vfs.add_file(path.name, path.read_bytes(), is_text=False)
        else:
            vfs = LocalFileSystem(tmp_path)
        with pytest.raises(UnicodeDecodeError):
            VFSChunker(vfs).chunk_file(path.name, "python")
        return
    if reader == "token":
        (chunk,) = chunk_file_with_token_limit(path, "python", 100)
        codec, errors = "utf-8", "replace"
    else:
        proc = GitAwareRepoProcessor(show_progress=False, max_workers=1)
        if reader == "batch":
            (result,) = proc.process_repository(
                str(tmp_path), incremental=False
            ).file_results
        else:
            (result,) = proc.process_files_iterator(str(tmp_path))
        (chunk,) = result.chunks
        codec, errors = "latin-1", "strict"
    expected = function.decode(codec, errors)
    start = len(prefix.decode(codec, errors).encode())
    assert chunk.content == expected
    assert (chunk.byte_start, chunk.byte_end) == (start, start + len(expected.encode()))


def test_watch_physical_offsets_and_decode_error(tmp_path):
    path = tmp_path / "good.py"
    body = b"def f():\r\n    return 1"
    path.write_bytes(b"# comment\r\n" + body + b"\r\n")
    (tmp_path / "bad.py").write_bytes(b"def bad():\r\n    return '\xff'\r\n")
    updates = []
    GitAwareRepoProcessor(max_workers=1, show_progress=False).watch_repository(
        str(tmp_path), updates.append, max_iterations=1
    )
    (delta,) = updates
    (error,) = delta["errors"]
    assert (error["file"], error["type"]) == ("bad.py", "UnicodeDecodeError")
    (node,) = delta["nodes_added"]
    (core,) = chunk_file(path.resolve(), "python")
    assert node["id"] == core.node_id
    (span,) = delta["spans"]
    source = path.read_bytes()
    start = source.index(body)
    assert (span["start_byte"], span["end_byte"]) == (start, start + len(body))
    assert source[span["start_byte"] : span["end_byte"]] == body

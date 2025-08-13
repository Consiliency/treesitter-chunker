from pathlib import Path

from chunker.core import chunk_file
from chunker.streaming import chunk_file_streaming


def test_spans_roundtrip_and_streaming_ids_match(tmp_path):
    # Create a simple Python file
    code = """
def alpha():
    return 1

class Beta:
    def method(self):
        return 2
""".lstrip()
    fpath = tmp_path / "sample.py"
    fpath.write_text(code, encoding="utf-8")

    # Non-streaming
    chunks = chunk_file(str(fpath), "python")
    file_bytes = fpath.read_bytes()
    for c in chunks:
        assert file_bytes[c.byte_start : c.byte_end] == c.content.encode("utf-8")

    # Streaming
    stream_chunks = list(chunk_file_streaming(str(fpath), "python"))

    # Compare IDs and spans between streaming and non-streaming
    # Sort by (start, end) to get deterministic order
    a = sorted([(c.byte_start, c.byte_end, c.node_id) for c in chunks])
    b = sorted([(c.byte_start, c.byte_end, c.node_id) for c in stream_chunks])
    assert a == b

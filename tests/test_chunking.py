from chunker import chunk_file

def test_python_chunks(tmp_path):
    src = tmp_path / "tmp.py"
    src.write_text("def foo():\n    pass\n")
    chunks = chunk_file(src, "python")
    assert chunks, "Should find at least one chunk"
    assert chunks[0].node_type == "function_definition"

from chunker.types import CodeChunk


def test_chunk_id_aliases_node_id():
    c = CodeChunk(
        language="python",
        file_path="/tmp/x.py",
        node_type="function_definition",
        start_line=1,
        end_line=3,
        byte_start=0,
        byte_end=10,
        parent_context="module",
        content="def f():\n  pass\n",
    )

    # Back-compat: chunk_id equals node_id
    assert c.chunk_id == c.node_id
    assert len(c.node_id) == 40


import importlib


def test_chunk_id_aliases_node_id_and_exporter_prefers_node_id():
    # Import DatabaseExporterBase directly from file to avoid package __init__
    import importlib.util
    import pathlib

    mod_path = (
        pathlib.Path(__file__).parents[1] / "chunker/export/database_exporter_base.py"
    )
    spec = importlib.util.spec_from_file_location("db_exp_base_local", mod_path)
    assert spec
    assert spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    DatabaseExporterBase = mod.DatabaseExporterBase
    c = CodeChunk(
        language="python",
        file_path="/tmp/x.py",
        node_type="function_definition",
        start_line=1,
        end_line=3,
        byte_start=0,
        byte_end=10,
        parent_context="module",
        content="def f():\n  pass\n",
    )

    # Back-compat: chunk_id equals node_id
    assert c.chunk_id == c.node_id
    assert len(c.node_id) == 40

    # Exporter should use node_id when present
    assert DatabaseExporterBase._get_chunk_id(c) == c.node_id

# Import DatabaseExporterBase without triggering package-level heavy imports
import importlib

from chunker.types import CodeChunk

DatabaseExporterBase = importlib.import_module(
    "chunker.export.database_exporter_base",
).DatabaseExporterBase


def test_chunk_id_aliases_node_id_and_exporter_prefers_node_id():
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

    # Standard behavior: both chunk_id and node_id are 40-char SHA-1
    assert len(c.chunk_id) == 40
    assert len(c.node_id) == 40
    assert c.chunk_id == c.node_id

    # Exporter should use chunk_id (40-char)
    assert DatabaseExporterBase._get_chunk_id(c) == c.chunk_id

from chunker.boundary import BOUNDARY_IR_SCHEMA_VERSION, select_node_identity
from chunker.types import CodeChunk


def _chunk(**overrides):
    values = {
        "language": "python",
        "file_path": "pkg/example.py",
        "node_type": "function_definition",
        "start_line": 1,
        "end_line": 2,
        "byte_start": 0,
        "byte_end": 20,
        "parent_context": "",
        "content": "def example():\n    pass\n",
        "node_id": "node-1",
        "definition_id": "",
        "metadata": {},
    }
    values.update(overrides)
    return CodeChunk(**values)


def test_schema_version_is_frozen():
    assert BOUNDARY_IR_SCHEMA_VERSION == "1.0"


def test_select_node_identity_prefers_definition_id():
    chunk = _chunk(definition_id="def-1", node_id="node-1")

    identity = select_node_identity(chunk, module_name="pkg.example")

    assert identity == {"source": "definition_id", "value": "def-1"}


def test_select_node_identity_uses_module_and_qualified_name():
    chunk = _chunk(
        node_id="node-1",
        metadata={"qualified_name": "Example.method"},
    )

    identity = select_node_identity(chunk, module_name="pkg.example")

    assert identity == {
        "source": "module + qualified_name",
        "value": "pkg.example:Example.method",
    }


def test_select_node_identity_falls_back_to_node_id():
    chunk = _chunk(node_id="node-1")

    identity = select_node_identity(chunk, module_name="pkg.example")

    assert identity == {"source": "node_id", "value": "node-1"}

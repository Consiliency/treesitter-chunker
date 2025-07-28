"""Tests for WebAssembly (WASM) language plugin."""

import pytest

from chunker.contracts.language_plugin_contract import ExtendedLanguagePluginContract
from chunker.languages.plugin_base import LanguagePlugin
from chunker.languages.wasm import WASMPlugin
from chunker.parser import get_parser


class TestWASMPlugin:
    """Test suite for WebAssembly language plugin."""

    @pytest.fixture
    def plugin(self):
        """Create a WASM plugin instance."""
        return WASMPlugin()

    @pytest.fixture
    def parser(self):
        """Get a WASM parser."""
        return get_parser("wat")

    def test_plugin_properties(self, plugin):
        """Test basic plugin properties."""
        assert plugin.language_name == "wat"
        assert ".wat" in plugin.supported_extensions
        assert ".wast" in plugin.supported_extensions
        assert "module" in plugin.default_chunk_types
        assert "function" in plugin.default_chunk_types
        assert "memory" in plugin.default_chunk_types
        assert "table" in plugin.default_chunk_types
        assert "global" in plugin.default_chunk_types
        assert "export" in plugin.default_chunk_types
        assert "import" in plugin.default_chunk_types

    def test_implements_contracts(self, plugin):
        """Test that plugin implements required contracts."""
        assert isinstance(plugin, LanguagePlugin)
        assert isinstance(plugin, ExtendedLanguagePluginContract)

    def test_module_chunking(self, plugin, parser):
        """Test chunking of WASM modules."""
        code = """
(module
  (func $add (param $a i32) (param $b i32) (result i32)
    local.get $a
    local.get $b
    i32.add)

  (export "add" (func $add))
)
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        module_chunks = [c for c in chunks if c["type"] == "module"]
        assert len(module_chunks) == 1

        func_chunks = [c for c in chunks if c["type"] == "function"]
        assert len(func_chunks) >= 1
        assert any(c["name"] == "add" for c in func_chunks)

        export_chunks = [c for c in chunks if c["type"] == "export"]
        assert len(export_chunks) >= 1
        assert any(c["name"] == "add" for c in export_chunks)

    def test_function_chunking(self, plugin, parser):
        """Test chunking of WASM functions."""
        code = """
(module
  (func $fibonacci (param $n i32) (result i32)
    (if (result i32)
      (i32.lt_s (local.get $n) (i32.const 2))
      (then (local.get $n))
      (else
        (i32.add
          (call $fibonacci (i32.sub (local.get $n) (i32.const 1)))
          (call $fibonacci (i32.sub (local.get $n) (i32.const 2)))))))

  (func $main (result i32)
    (call $fibonacci (i32.const 10)))
)
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        func_chunks = [c for c in chunks if c["type"] == "function"]
        assert len(func_chunks) >= 2

        func_names = [c["name"] for c in func_chunks if c.get("name")]
        assert "fibonacci" in func_names
        assert "main" in func_names

        # Check function signatures
        fib_func = next((c for c in func_chunks if c["name"] == "fibonacci"), None)
        if fib_func:
            assert fib_func.get("param_count", 0) == 1
            assert fib_func.get("result_count", 0) == 1

    def test_memory_chunking(self, plugin, parser):
        """Test chunking of WASM memory declarations."""
        code = """
(module
  (memory $mem1 1)
  (memory $mem2 1 10)
  (memory (export "memory") 2)
)
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        memory_chunks = [c for c in chunks if c["type"] == "memory"]
        assert len(memory_chunks) >= 2

        # Check for named memories
        named_memories = [c for c in memory_chunks if c.get("name")]
        assert any(c["name"] == "mem1" for c in named_memories)
        assert any(c["name"] == "mem2" for c in named_memories)

    def test_table_chunking(self, plugin, parser):
        """Test chunking of WASM table declarations."""
        code = """
(module
  (table $t1 10 funcref)
  (table $t2 0 20 funcref)
  (elem (i32.const 0) $func1 $func2)
)
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        table_chunks = [c for c in chunks if c["type"] == "table"]
        assert len(table_chunks) >= 2

        table_names = [c["name"] for c in table_chunks if c.get("name")]
        assert "t1" in table_names
        assert "t2" in table_names

    def test_global_chunking(self, plugin, parser):
        """Test chunking of WASM global declarations."""
        code = """
(module
  (global $g1 i32 (i32.const 42))
  (global $g2 (mut i32) (i32.const 0))
  (global $pi f32 (f32.const 3.14159))
)
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        global_chunks = [c for c in chunks if c["type"] == "global"]
        assert len(global_chunks) >= 3

        global_names = [c["name"] for c in global_chunks if c.get("name")]
        assert "g1" in global_names
        assert "g2" in global_names
        assert "pi" in global_names

        # Check for mutable global
        mutable_globals = [c for c in global_chunks if c.get("mutable", False)]
        assert len(mutable_globals) >= 1

    def test_import_export_chunking(self, plugin, parser):
        """Test chunking of imports and exports."""
        code = """
(module
  (import "env" "print" (func $print (param i32)))
  (import "env" "memory" (memory 1))
  (import "js" "table" (table 1 funcref))

  (func $add (param i32 i32) (result i32)
    local.get 0
    local.get 1
    i32.add)

  (export "add" (func $add))
  (export "memory" (memory 0))
)
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        import_chunks = [c for c in chunks if c["type"] == "import"]
        export_chunks = [c for c in chunks if c["type"] == "export"]

        assert len(import_chunks) >= 3
        assert len(export_chunks) >= 2

        # Check import names
        import_names = [c["name"] for c in import_chunks if c.get("name")]
        assert any("env.print" in name for name in import_names)
        assert any("env.memory" in name for name in import_names)

        # Check export names
        export_names = [c["name"] for c in export_chunks if c.get("name")]
        assert "add" in export_names
        assert "memory" in export_names

    def test_type_definitions(self, plugin, parser):
        """Test chunking of type definitions."""
        code = """
(module
  (type $sig1 (func (param i32 i32) (result i32)))
  (type $sig2 (func (param f32) (result f32)))

  (func (type $sig1)
    local.get 0
    local.get 1
    i32.add)
)
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        type_chunks = [c for c in chunks if c["type"] == "type_definition"]
        assert len(type_chunks) >= 2

        type_names = [c["name"] for c in type_chunks if c.get("name")]
        assert "sig1" in type_names
        assert "sig2" in type_names

    def test_should_chunk_node(self, plugin, parser):
        """Test should_chunk_node method."""
        code = """
(module
  (func $test)
  (memory 1)
  (global $g i32 (i32.const 0))
)
"""
        tree = parser.parse(code.encode())

        def find_nodes_by_type(node, node_type):
            """Helper to find nodes by type."""
            results = []
            if node.type == node_type:
                results.append(node)
            for child in node.children:
                results.extend(find_nodes_by_type(child, node_type))
            return results

        # Find different node types
        root = tree.root_node
        module_nodes = find_nodes_by_type(root, "module")
        func_nodes = find_nodes_by_type(root, "func") + find_nodes_by_type(
            root,
            "function",
        )
        memory_nodes = find_nodes_by_type(root, "memory")
        global_nodes = find_nodes_by_type(root, "global")

        # All should be chunkable
        assert all(plugin.should_chunk_node(n) for n in module_nodes)
        assert all(plugin.should_chunk_node(n) for n in func_nodes)
        assert all(plugin.should_chunk_node(n) for n in memory_nodes)
        assert all(plugin.should_chunk_node(n) for n in global_nodes)

    def test_get_node_context(self, plugin, parser):
        """Test context extraction for nodes."""
        code = """
(module $mymodule
  (func $add (param i32 i32) (result i32)
    local.get 0
    local.get 1
    i32.add)
  (memory $mem 1)
  (export "add" (func $add))
)
"""
        tree = parser.parse(code.encode())
        source = code.encode()

        def find_first_node_by_type(node, node_type):
            """Helper to find first node by type."""
            if node.type == node_type:
                return node
            for child in node.children:
                result = find_first_node_by_type(child, node_type)
                if result:
                    return result
            return None

        # Test module context
        module_node = find_first_node_by_type(tree.root_node, "module")
        if module_node:
            context = plugin.get_node_context(module_node, source)
            assert context is not None
            assert "module" in context

        # Test function context
        func_node = find_first_node_by_type(
            tree.root_node,
            "func",
        ) or find_first_node_by_type(tree.root_node, "function")
        if func_node:
            context = plugin.get_node_context(func_node, source)
            assert context is not None
            assert "func" in context

    def test_complex_wasm_module(self, plugin, parser):
        """Test with a more complex WASM module."""
        code = """
(module
  ;; Type definitions
  (type $binary_op (func (param i32 i32) (result i32)))
  (type $unary_op (func (param i32) (result i32)))

  ;; Imports
  (import "console" "log" (func $log (param i32)))

  ;; Memory
  (memory (export "memory") 1)

  ;; Globals
  (global $counter (mut i32) (i32.const 0))

  ;; Data section
  (data (i32.const 0) "Hello, WebAssembly!")

  ;; Functions
  (func $increment (type $unary_op)
    (global.set $counter
      (i32.add (global.get $counter) (local.get 0))))

  (func $add (type $binary_op)
    local.get 0
    local.get 1
    i32.add)

  (func $multiply (type $binary_op)
    local.get 0
    local.get 1
    i32.mul)

  ;; Table and elements
  (table funcref (elem $add $multiply))

  ;; Start function
  (func $start
    (call $log (i32.const 0)))
  (start $start)

  ;; Exports
  (export "increment" (func $increment))
  (export "add" (func $add))
  (export "multiply" (func $multiply))
)
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        chunks = plugin.get_semantic_chunks(tree.root_node, code.encode())

        # Should find multiple chunk types
        module_chunks = [c for c in chunks if c["type"] == "module"]
        func_chunks = [c for c in chunks if c["type"] == "function"]
        type_chunks = [c for c in chunks if c["type"] == "type_definition"]
        import_chunks = [c for c in chunks if c["type"] == "import"]
        export_chunks = [c for c in chunks if c["type"] == "export"]
        memory_chunks = [c for c in chunks if c["type"] == "memory"]
        global_chunks = [c for c in chunks if c["type"] == "global"]
        data_chunks = [c for c in chunks if c["type"] == "data_segment"]

        assert len(module_chunks) >= 1
        assert len(func_chunks) >= 4  # increment, add, multiply, start
        assert len(type_chunks) >= 2  # binary_op, unary_op
        assert len(import_chunks) >= 1  # console.log
        assert len(export_chunks) >= 4  # memory, increment, add, multiply
        assert len(memory_chunks) >= 1
        assert len(global_chunks) >= 1  # counter
        assert len(data_chunks) >= 1

        # Verify specific chunks
        assert any(c["name"] == "increment" for c in func_chunks)
        assert any(c["name"] == "add" for c in func_chunks)
        assert any(c["name"] == "multiply" for c in func_chunks)
        assert any(c["name"] == "counter" for c in global_chunks)

    def test_function_metadata(self, plugin, parser):
        """Test function metadata extraction."""
        code = """
(module
  (func $no_params_no_result)

  (func $one_param (param i32))

  (func $two_params_one_result (param i32 i32) (result i32)
    local.get 0
    local.get 1
    i32.add)

  (func $many_params (param i32 f32 i64) (result i32 i32)
    i32.const 0
    i32.const 0)
)
"""
        plugin.set_parser(parser)
        tree = parser.parse(code.encode())
        source = code.encode()

        # Process nodes to check function metadata
        chunks = []

        def process_tree(node):
            chunk = plugin.process_node(node, source, "test.wat")
            if chunk:
                chunks.append(chunk)
            for child in node.children:
                process_tree(child)

        process_tree(tree.root_node)

        # Check function metadata
        func_chunks = [c for c in chunks if "func" in c.node_type]

        # Verify parameter and result counts
        for chunk in func_chunks:
            if chunk.metadata:
                assert "param_count" in chunk.metadata
                assert "result_count" in chunk.metadata
                assert isinstance(chunk.metadata["param_count"], int)
                assert isinstance(chunk.metadata["result_count"], int)
